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

API_URL = "http://127.0.0.1:8000/api/v1/runtime/command"  # 127.0.0.1 not localhost (avoids IPv6 ::1 ambiguity)
SESSION_ID = "windows-voice-conv"

# ============================================================================
# TUNABLES  (all overridable via environment variables)
# ============================================================================
import os

def _env_f(name, default):  # float env helper
    try: return float(os.getenv(name, str(default)))
    except (TypeError, ValueError): return default

def _env_b(name, default):  # bool env helper
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")

# Print per-chunk energy/peak only when DEBUG_VOICE=true (quiet by default).
DEBUG_VOICE = _env_b("DEBUG_VOICE", False)

# --- Microphone ---
# Device is resolved at RUNTIME by name + host API (see resolve_device). We do NOT
# hardcode an index - indices drift and cause PaErrorCode -9996 Invalid device.
MIC_NAME_HINT = "HyperX QuadCast"   # primary mic, matched by name
PREFERRED_HOSTAPI = "WDM-KS"        # the only HyperX endpoint that captures on this box
MIC_DEVICE = None                   # optional manual override (index); None = resolve by name
CAPTURE_RATE = 44100                # HyperX native rate
STT_RATE = 16000                    # Whisper wants 16k
USABLE_PEAK = _env_f("USABLE_PEAK", 0.015)   # device must beat this while speaking
AUTO_DETECT_IF_SILENT = True
# Software gain applied to EVERY captured chunk (helps quiet 20-30 cm speech reach
# STT and the peak gate). Signal is clipped to [-1, 1]. 1.0 = no gain.
MIC_GAIN = _env_f("MIC_GAIN", 2.0)

# --- VAD (over rec chunks) ---
# Hysteresis: a HIGH threshold to START an utterance (avoids false triggers), and a
# LOWER threshold to KEEP accumulating (so normal speech after a loud onset is not
# misread as silence). Acceptance is by VOICED time, not (total - silence).
# Tuned looser for 20-30 cm desk distance (catch quieter onsets and word tails).
CHUNK_MS = 100                              # blocking record granularity (finer)
SILENCE_TIMEOUT_S = _env_f("SILENCE_TIMEOUT_S", 1.0)   # end of turn after trailing silence
MIN_SPEECH_S = _env_f("MIN_SPEECH_S", 0.3)             # accept short commands ("stop"/"כן")
MAX_LISTEN_S = 30.0                         # max wait for speech to start
MAX_UTTERANCE_S = 30.0
START_ENERGY_MULT = _env_f("START_ENERGY_MULT", 2.5)      # start threshold = floor * this
CONTINUE_ENERGY_MULT = _env_f("CONTINUE_ENERGY_MULT", 1.2)  # continue threshold = floor * this
MIN_ABS_FLOOR = _env_f("MIN_ABS_FLOOR", 0.008)           # absolute speech threshold floor
MAX_NOISE_FLOOR = 0.05          # cap floor so an inflated calibration can't gate out speech
COOLDOWN_S = 0.4

# --- STT (faster-whisper) ---
# Default to the KNOWN-GOOD config (base/cpu/int8) - this is the exact config the
# standalone test loads in seconds. "small" caused a startup hang on this machine
# (heavier load + faster-whisper HF revision check on the named model), so it is NOT
# the default. You may still opt into it with GARVIS_WHISPER_MODEL=small once verified.
WHISPER_MODEL = os.getenv("GARVIS_WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("GARVIS_WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.getenv("GARVIS_WHISPER_COMPUTE", "int8")
# Language: empty => auto-detect per utterance (handles he/en switching). Force with
# GARVIS_WHISPER_LANG=he or =en if auto-detect is unreliable for short commands.
WHISPER_LANGUAGE = os.getenv("GARVIS_WHISPER_LANG", "").strip() or None
WHISPER_BEAM = int(os.getenv("GARVIS_WHISPER_BEAM", "5"))

# Timeouts: (connect, read). Fast-fail the connect (5s) so an unreachable backend
# surfaces immediately; allow 90s read for LLM generation.
CONNECT_TIMEOUT_S = 5
HTTP_TIMEOUT_S = 90
RUNTIME_RETRY = True            # retry once on ConnectionError / HTTP 5xx (not 4xx)
RETRY_BACKOFF_S = 0.5

STOP_WORDS = {"goodbye", "exit", "stop", "quit", "stop listening", "shut down",
              "ביי", "להתראות", "תפסיק", "עצור"}

# --- TTS ---
# Engine: "piper" (calmer, natural, local) or "pyttsx3" (SAPI5, robotic, always-on).
# Piper has NO Hebrew voice, so Hebrew replies are always spoken via pyttsx3.
TTS_ENGINE = os.getenv("TTS_ENGINE", "piper").strip().lower()

import shutil
_VOICE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "piper_voices")

def _find_piper():
    cand = (os.getenv("PIPER_EXE") or shutil.which("piper") or shutil.which("piper.exe")
            or r"C:\Users\staso\AppData\Roaming\Python\Python314\Scripts\piper.exe")
    return cand if cand and os.path.exists(cand) else None

PIPER_EXE = _find_piper()
# English Piper voice model (calm). Override with TTS_VOICE=<path to .onnx>.
TTS_VOICE = os.getenv("TTS_VOICE", os.path.join(_VOICE_DIR, "en_US-lessac-medium.onnx"))
# Russian Piper voice. NOTE: on Python 3.14 the bundled espeak phonemizer currently
# fails for Russian (no piper-phonemize wheel) - the routing is wired and will work
# on an env where Russian phonemization is available; otherwise it falls back.
TTS_VOICE_RU = os.getenv("TTS_VOICE_RU", os.path.join(_VOICE_DIR, "ru_RU-dmitri-medium.onnx"))
PIPER_LENGTH_SCALE = _env_f("PIPER_LENGTH_SCALE", 1.15)  # >1.0 = slower / calmer
PIPER_SENTENCE_SILENCE = _env_f("PIPER_SENTENCE_SILENCE", 0.35)  # pause between sentences
PIPER_RETRY = True              # retry Piper once on transient empty-output failures

# pyttsx3 (fallback + Hebrew): slow it slightly for a calmer cadence.
TTS_RATE = int(os.getenv("TTS_RATE", "165"))
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
    audio = rec.reshape(-1)
    if MIC_GAIN != 1.0 and audio.size:
        audio = np.clip(audio * MIC_GAIN, -1.0, 1.0)  # software gain for quiet/far speech
    return audio


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
        if DEBUG_VOICE:
            log("VAD_DBG", f"energy={e:.4f} peak={peak_of(c):.4f} "
                           f"start_thr={start_thresh:.4f} cont_thr={cont_thresh:.4f} "
                           f"{'SPEAK' if (e > (cont_thresh if started else start_thresh)) else 'sil'}")

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
    # Print the EXACT config before loading so a hang/mismatch is obvious.
    log("STATE", f"loading Whisper model={WHISPER_MODEL!r} device={WHISPER_DEVICE!r} "
                 f"compute_type={WHISPER_COMPUTE!r} ...")
    model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)
    log("STATE", "Whisper loaded")
    return model


def transcribe(model, audio16: np.ndarray) -> str:
    # vad_filter=False on purpose: our own VAD already segmented the utterance, and
    # Whisper's internal VAD tends to trim leading/trailing words (the missed-words
    # problem). language=None auto-detects per utterance so he/en both work.
    segments, info = model.transcribe(
        audio16,
        language=WHISPER_LANGUAGE,
        beam_size=WHISPER_BEAM,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    if DEBUG_VOICE:
        log("STT_LANG", f"{getattr(info, 'language', '?')} "
                        f"p={getattr(info, 'language_probability', 0.0):.2f}")
    return text


def _runtime_post_once(conv: Conversation, text: str):
    """Single POST to the runtime. Logs URL + status/body. Raises HTTPError on non-2xx."""
    log("RUNTIME_REQUEST", f"POST {API_URL}")
    t0 = time.perf_counter()
    r = requests.post(API_URL, json={"text": text, "source": "voice",
                                     "session_id": conv.session_id, "metadata": {}},
                      timeout=(CONNECT_TIMEOUT_S, HTTP_TIMEOUT_S))
    dt = time.perf_counter() - t0
    body_preview = (r.text or "")[:200].replace("\n", " ")
    log("RUNTIME_RESPONSE", f"status={r.status_code} dt={dt:.1f}s body={body_preview!r}")
    r.raise_for_status()
    return (r.json().get("response_text") or "I did not get a response."), dt


def ask_jarvis(conv: Conversation, text: str):
    """
    POST to the runtime with ONE retry on transient failures (ConnectionError or
    HTTP 5xx) - covers the brief Ollama model-reload window. Never retries 4xx.
    Read timeouts (slow generation) are NOT retried; they propagate as Timeout.
    """
    attempts = 2 if RUNTIME_RETRY else 1
    for attempt in range(1, attempts + 1):
        try:
            return _runtime_post_once(conv, text)
        except requests.ConnectionError as exc:
            if attempt < attempts:
                log("RUNTIME_RETRY", f"ConnectionError ({type(exc).__name__}) - retry {attempt+1}/{attempts}")
                time.sleep(RETRY_BACKOFF_S)
                continue
            raise
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else 0
            if 500 <= code < 600 and attempt < attempts:
                log("RUNTIME_RETRY", f"HTTP {code} - retry {attempt+1}/{attempts}")
                time.sleep(RETRY_BACKOFF_S)
                continue
            raise  # 4xx, or 5xx after final attempt -> propagate, do not retry


def is_stop_word(text: str) -> bool:
    return text.lower().strip(" .!?,") in STOP_WORDS


# ----------------------------------------------------------------------------
# TTS
#   Dispatcher speak() routes by engine + language:
#     - Hebrew text          -> pyttsx3 (Piper has no Hebrew voice)
#     - TTS_ENGINE == piper   -> Piper (calm), falling back to pyttsx3 on any failure
#     - TTS_ENGINE == pyttsx3 -> pyttsx3 directly
#   pyttsx3 path keeps the fresh-engine-per-utterance + reset/retry behaviour.
# ----------------------------------------------------------------------------
import re as _re
_HEBREW = _re.compile(r"[֐-׿]")
_CYRILLIC = _re.compile(r"[Ѐ-ӿ]")


def _is_hebrew(text: str) -> bool:
    return bool(_HEBREW.search(text or ""))


def _is_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC.search(text or ""))


def _voice_for(text: str) -> str:
    """Pick the Piper voice model for the text's script (Russian -> RU, else EN)."""
    return TTS_VOICE_RU if _is_cyrillic(text) else TTS_VOICE


def piper_available() -> bool:
    return bool(PIPER_EXE) and os.path.exists(TTS_VOICE)


def _piper_synth_play(text: str, voice: str) -> bool:
    import subprocess, tempfile, winsound
    wav = None
    try:
        fd, wav = tempfile.mkstemp(suffix=".wav", prefix="jarvis_tts_")
        os.close(fd)
        proc = subprocess.run(
            [PIPER_EXE, "-m", voice, "-f", wav,
             "--length-scale", str(PIPER_LENGTH_SCALE),
             "--sentence-silence", str(PIPER_SENTENCE_SILENCE)],
            input=text.encode("utf-8"), capture_output=True, timeout=60,
        )
        if proc.returncode != 0 or not os.path.exists(wav) or os.path.getsize(wav) < 1024:
            err = proc.stderr.decode("utf-8", "replace")
            log("TTS_ERROR", f"piper rc={proc.returncode} {err[-160:]!r}")
            return False
        winsound.PlaySound(wav, winsound.SND_FILENAME)   # blocking playback
        return True
    except Exception as exc:
        log("TTS_ERROR", f"piper {type(exc).__name__}: {exc}")
        return False
    finally:
        if wav and os.path.exists(wav):
            try:
                os.remove(wav)
            except Exception:
                pass


def speak_piper(text: str, voice: str | None = None) -> bool:
    """Synthesize with Piper and play (blocking). Retries once. Never raises."""
    voice = voice or _voice_for(text)
    if not PIPER_EXE or not os.path.exists(voice):
        return False
    log("TTS_START", f"(piper {os.path.basename(voice)}) {text[:60].replace(chr(10), ' ')!r}")
    attempts = 2 if PIPER_RETRY else 1
    for attempt in range(1, attempts + 1):
        if _piper_synth_play(text, voice):
            log("TTS_DONE", "(piper)")
            return True
        if attempt < attempts:
            log("TTS_RETRY", f"piper attempt {attempt+1}/{attempts}")
    return False


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


def speak_pyttsx3(text: str) -> bool:
    preview = text[:60].replace("\n", " ")
    for attempt in (1, 2):
        log("TTS_START", f"(pyttsx3 attempt {attempt}) {preview!r}")
        try:
            _speak_once(text)
            log("TTS_DONE", "(pyttsx3)")
            return True
        except Exception as exc:
            log("TTS_ERROR", f"pyttsx3 {type(exc).__name__}: {exc}")
            if attempt == 1:
                tts_reset()
    return False


def speak(text: str) -> bool:
    """
    Language- and engine-aware TTS dispatcher. Never raises.
      - Hebrew  -> pyttsx3 (Piper has no Hebrew voice)
      - Russian -> Piper ru_RU voice (speak_piper auto-selects by Cyrillic script)
      - English -> Piper en_US voice
      - any Piper failure -> pyttsx3 fallback
    """
    if not text or not text.strip():
        return True
    # Piper has no Hebrew voice -> Hebrew always via pyttsx3.
    if TTS_ENGINE == "piper" and not _is_hebrew(text):
        if speak_piper(text):       # picks RU voice for Cyrillic, EN otherwise
            return True
        log("TTS_FALLBACK", "piper failed -> pyttsx3")
    return speak_pyttsx3(text)


# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------
def main() -> None:
    # Make stdout/stderr UTF-8 so Hebrew transcriptions/replies print without
    # crashing on a cp1252 Windows console.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 64)
    print("  JARVIS - Continuous Conversation (rec-based capture)")
    print("=" * 64)

    # 1) Load Whisper FIRST and confirm it before any Piper or microphone init.
    try:
        model = load_stt()
    except Exception as exc:
        import traceback
        log("STATE", f"Whisper load FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        sys.exit(1)

    # 2) Only after Whisper is confirmed loaded: log runtime/TTS and init the mic.
    log("RUNTIME_URL", API_URL)   # audit: which runtime URL this client calls
    if TTS_ENGINE == "piper" and piper_available():
        ru = "yes" if os.path.exists(TTS_VOICE_RU) else "no"
        log("TTS_ENGINE", f"piper EN={os.path.basename(TTS_VOICE)} RU={os.path.basename(TTS_VOICE_RU)}"
                          f"(present={ru}) len-scale={PIPER_LENGTH_SCALE}; Hebrew -> pyttsx3")
    else:
        reason = "" if TTS_ENGINE != "piper" else " (piper.exe or voice model missing)"
        log("TTS_ENGINE", f"pyttsx3{reason}")

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
            except requests.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else "?"
                body = (exc.response.text[:200].replace("\n", " ") if exc.response is not None else "")
                log("RUNTIME_HTTP_ERROR", f"status={code} body={body!r}")
                speak("My runtime returned an error."); continue
            except requests.ConnectionError as exc:
                log("RUNTIME_CONN_ERROR", f"{type(exc).__name__}: {exc}")
                speak("I could not reach my runtime."); continue
            except requests.Timeout as exc:
                log("RUNTIME_TIMEOUT", f"{type(exc).__name__}: {exc}")
                speak("That took too long. Let us try again."); continue
            except Exception as exc:
                log("RUNTIME_ERROR", f"{type(exc).__name__}: {exc}")
                speak("Something went wrong talking to my runtime."); continue

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
