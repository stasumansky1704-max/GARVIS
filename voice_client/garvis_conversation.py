"""
JARVIS Voice - Continuous Conversation Mode (Windows voice client)

Capture architecture: sd.rec() BLOCKING CHUNKS.
Note: sd.rec() opens a PortAudio InputStream internally - that is the ONLY way
sounddevice captures audio; there is no InputStream-free path. The previous crash
("Error opening InputStream / PaErrorCode -9996 Invalid device") was NOT a leftover
streaming path - it was sd.rec() failing because the device INDEX was invalid.

PortAudio indices are not stable (they shift on USB re-enumeration / reboot), so we
NEVER hardcode an index for capture. We resolve the HyperX at runtime by NAME +
WDM-KS host API (the only HyperX endpoint that actually captures on this machine,
peak ~0.07; the MME/DirectSound/WASAPI duplicates read near-silence), validate it is
openable with check_input_settings, and auto re-resolve if an index goes stale.

Reuses the verified stack: faster-whisper (STT), pyttsx3 (TTS),
POST /api/v1/runtime/command (Ollama-backed). Audio resampled to 16k for Whisper.

Logs: MIC_DEVICE / MIC_PEAK / VAD_START / VAD_STOP / TRANSCRIBING / TTS_START / TTS_DONE.

Run on Windows:  python voice_client/garvis_conversation.py
Say "goodbye" / "exit" / "stop" / "quit" (or Ctrl+C) to end.
"""
from __future__ import annotations

import sys
import time
import signal
from dataclasses import dataclass, field

import numpy as np
import requests

API_URL = "http://localhost:8000/api/v1/runtime/command"
SESSION_ID = "windows-voice-conv"

# --- Microphone ---
# Device is resolved at RUNTIME by name + host API (see resolve_device). We do NOT
# hardcode an index - indices drift and cause PaErrorCode -9996 Invalid device.
MIC_NAME_HINT = "HyperX QuadCast"   # primary mic, matched by name
PREFERRED_HOSTAPI = "WDM-KS"        # the only HyperX endpoint that captures on this box
MIC_DEVICE = None                   # optional manual override (index); None = resolve by name
CAPTURE_RATE = 44100                # HyperX native rate
STT_RATE = 16000                    # Whisper wants 16k
USABLE_PEAK = 0.02                  # device must beat this while speaking
AUTO_DETECT_IF_SILENT = True

# --- VAD (over rec chunks) ---
# Hysteresis: a HIGH threshold to START an utterance (avoids false triggers), and a
# LOWER threshold to KEEP accumulating (so normal speech after a loud onset is not
# misread as silence). Acceptance is by VOICED time, not (total - silence).
CHUNK_MS = 120                  # blocking record granularity
SILENCE_TIMEOUT_S = 1.2         # end of turn after this trailing silence
MIN_SPEECH_S = 0.4              # reject blips with less than this voiced time
MAX_LISTEN_S = 20.0             # max wait for speech to start
MAX_UTTERANCE_S = 30.0
START_ENERGY_MULT = 3.0         # start threshold = floor * this
CONTINUE_ENERGY_MULT = 1.4      # continue threshold = floor * this (lower than start)
MIN_ABS_FLOOR = 0.01            # absolute speech threshold floor
MAX_NOISE_FLOOR = 0.05          # cap floor so an inflated calibration can't gate out speech
COOLDOWN_S = 0.4

WHISPER_MODEL = "base"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE = "int8"
HTTP_TIMEOUT_S = 90
STOP_WORDS = {"goodbye", "exit", "stop", "quit", "stop listening", "shut down"}

TTS_RATE = 170
TTS_VOLUME = 1.0


def log(tag: str, msg: str = "") -> None:
    print(f"[{tag}] {msg}", flush=True)


# ----------------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------------
@dataclass
class Conversation:
    session_id: str = SESSION_ID
    turns: list = field(default_factory=list)

    def add(self, user: str, jarvis: str) -> None:
        self.turns.append((user, jarvis))

    @property
    def last(self):
        return self.turns[-1] if self.turns else None


# ----------------------------------------------------------------------------
# Audio helpers (sd.rec blocking)
# ----------------------------------------------------------------------------
_OUTPUT_TOKENS = ("speaker", "output", "playback", "render", "loopback",
                  "stereo mix", "what u hear", "wave out", "spdif", "hdmi",
                  "display audio", "headphones")

# Live capture target, resolved by name + host API (never a hardcoded index).
# rec_chunk re-resolves into this if an index goes stale (PaErrorCode -9996).
_ACTIVE = {"device": None, "rate": CAPTURE_RATE, "name": ""}


def _is_output(name: str) -> bool:
    low = name.lower()
    return any(t in low for t in _OUTPUT_TOKENS)


def _hostapi_name(hostapi_idx: int) -> str:
    import sounddevice as sd
    try:
        return sd.query_hostapis()[hostapi_idx]["name"]
    except Exception:
        return ""


def list_input_devices():
    """[(index, name, default_rate)] for real input devices (no outputs/loopback)."""
    import sounddevice as sd
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) > 0 and not _is_output(d["name"]):
            out.append((i, d["name"], int(d.get("default_samplerate", 44100))))
    return out


def _openable(device, rate: int) -> bool:
    """True if PortAudio can actually open this device at this rate (no -9996)."""
    import sounddevice as sd
    try:
        sd.check_input_settings(device=device, samplerate=rate,
                                channels=1, dtype="float32")
        return True
    except Exception:
        return False


def _do_rec(seconds: float, device, rate: int) -> np.ndarray:
    import sounddevice as sd
    rec = sd.rec(int(seconds * rate), samplerate=rate, channels=1,
                 dtype="float32", device=device)
    sd.wait()
    return rec.reshape(-1)


def rec_chunk(seconds: float, device, rate: int) -> np.ndarray:
    """
    Blocking record of `seconds` from `device` at `rate` (mono float32).
    sd.rec opens an InputStream internally; if the index has gone stale PortAudio
    raises -9996 Invalid device. We catch that, re-resolve the mic by name/host API
    into _ACTIVE, and retry once so the session self-heals instead of crashing.
    """
    import sounddevice as sd
    try:
        return _do_rec(seconds, device, rate)
    except sd.PortAudioError as exc:
        log("MIC_RERESOLVE", f"{exc} - re-resolving mic by name/host API")
        i, r, n = select_device()
        if i is None:
            raise
        _ACTIVE.update(device=i, rate=r, name=n)
        return _do_rec(seconds, _ACTIVE["device"], _ACTIVE["rate"])


def peak_of(a: np.ndarray) -> float:
    return float(np.max(np.abs(a))) if a.size else 0.0


def measure_peak(device, rate: int, seconds: float = 0.6) -> float:
    # Raw record (no self-heal) so per-device scan peaks are not redirected to
    # the HyperX when a scanned index fails to open.
    if not _openable(device, rate):
        return 0.0
    try:
        return peak_of(_do_rec(seconds, device, rate))
    except Exception:
        return 0.0


def resample_to_stt(audio: np.ndarray, src_rate: int) -> np.ndarray:
    if src_rate == STT_RATE or audio.size == 0:
        return audio
    n = int(round(len(audio) * STT_RATE / src_rate))
    if n <= 0:
        return audio
    xo = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    xn = np.linspace(0.0, 1.0, num=n, endpoint=False)
    return np.interp(xn, xo, audio).astype(np.float32)


# ----------------------------------------------------------------------------
# Device selection + guided calibration
# ----------------------------------------------------------------------------
def select_device():
    """
    Resolve the capture device at RUNTIME and return (index, rate, name).
    Indices are NOT stable, so we rank candidates by name + host API and return the
    first one PortAudio can actually open (check_input_settings) - never a raw index.

    Priority:
      1. MIC_DEVICE override (only if set AND openable)
      2. HyperX (MIC_NAME_HINT) on the PREFERRED_HOSTAPI (WDM-KS) - openable
      3. HyperX on any host API - openable
      4. default input device - openable
      5. first openable real input device
    Populates _ACTIVE as a side effect.
    """
    import sounddevice as sd
    devices = list_input_devices()

    def hostapi_of(idx: int) -> str:
        try:
            return _hostapi_name(sd.query_devices()[idx]["hostapi"])
        except Exception:
            return ""

    def finish(i, rate, n):
        _ACTIVE.update(device=i, rate=rate, name=n)
        return i, rate, n

    hint = (MIC_NAME_HINT or "").lower()
    pref = (PREFERRED_HOSTAPI or "").lower()

    # 1. explicit manual override
    if MIC_DEVICE is not None:
        for i, n, sr in devices:
            if i == MIC_DEVICE and _openable(i, CAPTURE_RATE):
                return finish(i, CAPTURE_RATE, n)

    # 2. HyperX on preferred host API (WDM-KS) - the verified-good endpoint
    if hint:
        for i, n, sr in devices:
            if hint in n.lower() and pref in hostapi_of(i).lower() \
                    and _openable(i, CAPTURE_RATE):
                return finish(i, CAPTURE_RATE, n)
        # 3. HyperX on any host API
        for i, n, sr in devices:
            if hint in n.lower():
                rate = CAPTURE_RATE if _openable(i, CAPTURE_RATE) else sr
                if _openable(i, rate):
                    return finish(i, rate, n)

    # 4. system default input
    try:
        di = sd.default.device[0]
        for i, n, sr in devices:
            if i == di and _openable(i, sr):
                return finish(i, sr, n)
    except Exception:
        pass

    # 5. first openable input
    for i, n, sr in devices:
        if _openable(i, sr):
            return finish(i, sr, n)

    return None, CAPTURE_RATE, "system default"


def guided_calibration(device, rate: int, name: str) -> tuple[int, int, str, float]:
    """
    Ask the user to speak, measure peak. If the chosen device is silent and
    AUTO_DETECT_IF_SILENT, scan all input devices WHILE the user speaks and pick
    the loudest usable one. Returns (device, rate, name, peak).
    """
    log("MIC_DEVICE", f"[{device}] {name} @ {rate} Hz")
    print("\n  Calibration: please SPEAK normally for 3 seconds...", flush=True)
    time.sleep(0.3)
    peak = measure_peak(device, rate, seconds=3.0)
    log("MIC_PEAK", f"{peak:.5f} (need > {USABLE_PEAK})")
    if peak >= USABLE_PEAK or not AUTO_DETECT_IF_SILENT:
        return device, rate, name, peak

    print(f"\n  '{name}' too quiet. Scanning input devices - keep SPEAKING...", flush=True)
    best = (device, rate, name, peak)
    for i, n, sr in list_input_devices():
        for try_rate in {sr, CAPTURE_RATE, 48000}:
            p = measure_peak(i, try_rate, seconds=1.0)
            log("  scan", f"[{i}] {n[:30]:<30} @{try_rate} peak={p:.5f}")
            if p > best[3]:
                best = (i, try_rate, n, p)
    log("MIC_DEVICE", f"auto-selected [{best[0]}] {best[2]} @ {best[1]} Hz peak={best[3]:.5f}")
    return best


# ----------------------------------------------------------------------------
# VAD over rec chunks
# ----------------------------------------------------------------------------
def listen_utterance(noise_floor: float):
    """
    Record blocking chunks (from the live _ACTIVE device) until speech starts, then
    until trailing silence. Reading _ACTIVE each chunk means a mid-utterance mic
    re-resolve (index drift) propagates automatically. Logs VAD_START / VAD_STOP.
    Returns audio (at the active capture rate) or None.
    """
    floor = min(max(noise_floor, MIN_ABS_FLOOR), MAX_NOISE_FLOOR)
    start_thresh = floor * START_ENERGY_MULT
    cont_thresh = max(floor * CONTINUE_ENERGY_MULT, MIN_ABS_FLOOR)
    chunk_s = CHUNK_MS / 1000.0

    collected = []
    started = False
    silence = 0.0     # trailing silence since last voiced chunk
    waited = 0.0      # time waited for speech to begin
    voiced_s = 0.0    # accumulated VOICED time (what acceptance is based on)
    total_s = 0.0     # all captured time once started
    prev = None       # one chunk of preroll before the onset

    while True:
        c = rec_chunk(chunk_s, _ACTIVE["device"], _ACTIVE["rate"])
        e = float(np.sqrt(np.mean(c ** 2))) if c.size else 0.0

        if not started:
            if e > start_thresh:
                started = True
                log("VAD_START", f"energy={e:.4f} start_thr={start_thresh:.4f} "
                                 f"cont_thr={cont_thresh:.4f}")
                if prev is not None:           # keep one preroll chunk of context
                    collected.append(prev)
                    total_s += chunk_s
                collected.append(c)            # the onset chunk IS voiced
                total_s += chunk_s
                voiced_s += chunk_s
            else:
                prev = c
                waited += chunk_s
                if waited >= MAX_LISTEN_S:
                    log("VAD_STOP", "timeout (no speech)")
                    return None
            continue

        # accumulating: always append, classify with the LOWER continue threshold
        collected.append(c)
        total_s += chunk_s
        if e > cont_thresh:
            voiced_s += chunk_s
            silence = 0.0
        else:
            silence += chunk_s
            if silence >= SILENCE_TIMEOUT_S:
                log("VAD_STOP", f"silence (voiced={voiced_s:.2f}s total={total_s:.2f}s)")
                break
        if total_s >= MAX_UTTERANCE_S:
            log("VAD_STOP", f"max utterance (voiced={voiced_s:.2f}s)")
            break

    audio = np.concatenate(collected) if collected else np.zeros(0, dtype=np.float32)
    if voiced_s < MIN_SPEECH_S:
        log("VAD_STOP", f"too short (voiced {voiced_s:.2f}s < {MIN_SPEECH_S}s) - rejected")
        return None
    log("VAD_OK", f"{audio.size} samples voiced={voiced_s:.2f}s total={total_s:.2f}s")
    return audio


def calibrate_noise_floor(device, rate: int) -> float:
    a = rec_chunk(0.5, device, rate)
    return max(float(np.sqrt(np.mean(a ** 2))) if a.size else 0.0, MIN_ABS_FLOOR)


# ----------------------------------------------------------------------------
# STT / Runtime
# ----------------------------------------------------------------------------
def load_stt():
    from faster_whisper import WhisperModel
    return WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)


def transcribe(model, audio16: np.ndarray) -> str:
    segments, _ = model.transcribe(audio16, vad_filter=True, condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segments).strip()


def ask_jarvis(conv: Conversation, text: str):
    t0 = time.perf_counter()
    r = requests.post(API_URL, json={"text": text, "source": "voice",
                                     "session_id": conv.session_id, "metadata": {}},
                      timeout=HTTP_TIMEOUT_S)
    dt = time.perf_counter() - t0
    r.raise_for_status()
    return (r.json().get("response_text") or "I did not get a response."), dt


def is_stop_word(text: str) -> bool:
    return text.lower().strip(" .!?,") in STOP_WORDS


# ----------------------------------------------------------------------------
# TTS (fresh engine per utterance; reset + retry; never raises)
# ----------------------------------------------------------------------------
def tts_reset() -> None:
    log("TTS_RESET")
    try:
        import pythoncom
        pythoncom.CoUninitialize(); pythoncom.CoInitialize()
    except Exception:
        pass


def _speak_once(text: str) -> None:
    import pyttsx3
    engine = pyttsx3.init()
    try:
        engine.setProperty("rate", TTS_RATE)
        engine.setProperty("volume", TTS_VOLUME)
        engine.say(text)
        engine.runAndWait()
    finally:
        try:
            engine.stop()
        except Exception:
            pass
        del engine


def speak(text: str) -> bool:
    if not text or not text.strip():
        return True
    preview = text[:60].replace("\n", " ")
    for attempt in (1, 2):
        log("TTS_START", f"(attempt {attempt}) {preview!r}")
        try:
            _speak_once(text)
            log("TTS_DONE")
            return True
        except Exception as exc:
            log("TTS_ERROR", f"{type(exc).__name__}: {exc}")
            if attempt == 1:
                tts_reset()
    return False


# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------
def main() -> None:
    print("=" * 64)
    print("  JARVIS - Continuous Conversation (rec-based capture)")
    print("=" * 64)

    log("STATE", "loading Whisper...")
    try:
        model = load_stt()
    except Exception as exc:
        print(f"[ERROR] STT load failed: {exc}"); sys.exit(1)

    device, rate, name = select_device()
    if device is None:
        print("[ERROR] no openable input device found"); sys.exit(1)

    device, rate, name, peak = guided_calibration(device, rate, name)
    _ACTIVE.update(device=device, rate=rate, name=name)  # sync after any auto-detect
    if peak < USABLE_PEAK:
        print(f"\n[WARN] selected mic peak {peak:.5f} < {USABLE_PEAK}. "
              f"Check the HyperX mute button / Windows input level, then rerun.")
        # continue anyway - user may speak louder

    try:
        noise_floor = calibrate_noise_floor(device, rate)
    except Exception:
        noise_floor = MIN_ABS_FLOOR
    log("STATE", f"ready - noise floor {noise_floor:.4f} - say 'goodbye' to exit")

    conv = Conversation()
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))

    turn = 0
    while not stop["flag"]:
        try:
            log("LISTENING", "waiting for speech...")
            audio = listen_utterance(noise_floor)
            if audio is None:
                time.sleep(COOLDOWN_S)
                continue

            log("TRANSCRIBING")
            t0 = time.perf_counter()
            try:
                user_text = transcribe(model, resample_to_stt(audio, _ACTIVE["rate"]))
            except Exception as exc:
                log("STT_ERROR", str(exc)); continue
            stt_dt = time.perf_counter() - t0
            if not user_text:
                log("TRANSCRIBING", "empty"); time.sleep(COOLDOWN_S); continue

            print(f"  You: {user_text}")
            if is_stop_word(user_text):
                speak("Goodbye.")
                break

            log("THINKING", "JARVIS is thinking...")
            try:
                reply, rt_dt = ask_jarvis(conv, user_text)
            except requests.Timeout:
                log("RUNTIME_TIMEOUT"); speak("That took too long. Let us try again."); continue
            except Exception as exc:
                log("RUNTIME_ERROR", str(exc)); speak("I could not reach my runtime."); continue

            print(f"  JARVIS: {reply}")
            t0 = time.perf_counter()
            speak(reply)
            tts_dt = time.perf_counter() - t0

            conv.add(user_text, reply)
            turn += 1
            print(f"     [timing] stt {stt_dt:.1f}s | runtime {rt_dt:.1f}s | tts {tts_dt:.1f}s | turn #{turn}")
            time.sleep(COOLDOWN_S)

        except Exception as exc:
            log("ERROR_RECOVERY", f"{type(exc).__name__}: {exc}")
            time.sleep(0.5)

    print(f"\n  Conversation ended - {turn} turn(s).")


if __name__ == "__main__":
    main()
