"""
JARVIS Voice - Continuous Conversation Mode (Windows voice client)

Capture architecture: sd.rec() BLOCKING CHUNKS (not InputStream).
Reason: on this machine the only HyperX endpoint that actually captures audio is
the WDM-KS one (device 21, peak ~0.07); the MME/DirectSound/WASAPI duplicates read
near-silence. WDM-KS does NOT support the streaming InputStream API
("Blocking API not supported"), so we record short blocking chunks with sd.rec().

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
MIC_DEVICE = 21                 # WDM-KS HyperX (the only endpoint that captures). None = auto
MIC_NAME_HINT = "HyperX QuadCast"
CAPTURE_RATE = 44100            # device 21 native rate
STT_RATE = 16000                # Whisper wants 16k
USABLE_PEAK = 0.02              # device must beat this while speaking
AUTO_DETECT_IF_SILENT = True

# --- VAD (over rec chunks) ---
CHUNK_MS = 120                  # blocking record granularity
SILENCE_TIMEOUT_S = 1.2         # end of turn after this trailing silence
MIN_SPEECH_S = 0.4              # reject blips shorter than this
MAX_LISTEN_S = 20.0            # max wait for speech to start
MAX_UTTERANCE_S = 30.0
START_ENERGY_MULT = 3.0
MIN_ABS_FLOOR = 0.01           # absolute speech threshold floor
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


def _is_output(name: str) -> bool:
    low = name.lower()
    return any(t in low for t in _OUTPUT_TOKENS)


def list_input_devices():
    """[(index, name, default_rate)] for real input devices (no outputs/loopback)."""
    import sounddevice as sd
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) > 0 and not _is_output(d["name"]):
            out.append((i, d["name"], int(d.get("default_samplerate", 44100))))
    return out


def rec_chunk(seconds: float, device, rate: int) -> np.ndarray:
    """Blocking record of `seconds` from `device` at `rate`. Mono float32. WDM-KS-safe."""
    import sounddevice as sd
    rec = sd.rec(int(seconds * rate), samplerate=rate, channels=1,
                 dtype="float32", device=device)
    sd.wait()
    return rec.reshape(-1)


def peak_of(a: np.ndarray) -> float:
    return float(np.max(np.abs(a))) if a.size else 0.0


def measure_peak(device, rate: int, seconds: float = 0.6) -> float:
    try:
        return peak_of(rec_chunk(seconds, device, rate))
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
    """Return (index, rate, name). Prefer MIC_DEVICE (21), else name hint, else default."""
    import sounddevice as sd
    devices = list_input_devices()
    by_idx = {i: (i, n, sr) for i, n, sr in devices}

    if MIC_DEVICE is not None and MIC_DEVICE in by_idx:
        i, n, _ = by_idx[MIC_DEVICE]
        return i, CAPTURE_RATE, n
    if MIC_NAME_HINT:
        for i, n, sr in devices:
            if MIC_NAME_HINT.lower() in n.lower():
                return i, CAPTURE_RATE, n
    try:
        di = sd.default.device[0]
        if di in by_idx:
            i, n, sr = by_idx[di]
            return i, sr, n
    except Exception:
        pass
    if devices:
        i, n, sr = devices[0]
        return i, sr, n
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
def listen_utterance(device, rate: int, noise_floor: float):
    """
    Record blocking chunks until speech starts, then until trailing silence.
    Logs VAD_START / VAD_STOP. Returns audio (at `rate`) or None.
    """
    thresh = max(noise_floor, MIN_ABS_FLOOR) * START_ENERGY_MULT
    chunk_s = CHUNK_MS / 1000.0
    collected = []
    started = False
    silence = 0.0
    waited = 0.0
    total = 0.0
    prev = None  # one chunk of preroll

    while True:
        c = rec_chunk(chunk_s, device, rate)
        e = float(np.sqrt(np.mean(c ** 2))) if c.size else 0.0
        speaking = e > thresh

        if not started:
            if speaking:
                started = True
                log("VAD_START", f"energy={e:.4f}")
                if prev is not None:
                    collected.append(prev)
                collected.append(c)
            else:
                prev = c
                waited += chunk_s
                if waited >= MAX_LISTEN_S:
                    log("VAD_STOP", "timeout (no speech)")
                    return None
            continue

        collected.append(c)
        total += chunk_s
        if speaking:
            silence = 0.0
        else:
            silence += chunk_s
            if silence >= SILENCE_TIMEOUT_S:
                log("VAD_STOP", "silence")
                break
        if total >= MAX_UTTERANCE_S:
            log("VAD_STOP", "max utterance")
            break

    audio = np.concatenate(collected) if collected else np.zeros(0, dtype=np.float32)
    speech_dur = max(0.0, total - silence)
    if speech_dur < MIN_SPEECH_S:
        log("VAD_STOP", f"too short ({speech_dur:.2f}s) - rejected")
        return None
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
        print("[ERROR] no input device found"); sys.exit(1)

    device, rate, name, peak = guided_calibration(device, rate, name)
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
            audio = listen_utterance(device, rate, noise_floor)
            if audio is None:
                time.sleep(COOLDOWN_S)
                continue

            log("TRANSCRIBING")
            t0 = time.perf_counter()
            try:
                user_text = transcribe(model, resample_to_stt(audio, rate))
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
