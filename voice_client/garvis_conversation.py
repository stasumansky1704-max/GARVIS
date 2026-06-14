"""
GARVIS Voice — Continuous Conversation Mode (Sprint 1.0)

Reuses the existing, verified stack — nothing rebuilt:
  - faster-whisper (STT)            : already installed & working
  - sounddevice (mic I/O)           : already installed & working
  - pyttsx3 (TTS)                   : already installed & working
  - POST /api/v1/runtime/command    : verified working (Ollama-backed)

Adds ONLY conversation quality:
  Phase 2  energy-based Voice Activity Detection (no fixed 5s window, no new deps)
  Phase 3  continuous loop — listening resumes automatically after each answer
  Phase 4  persistent runtime session_id + last-turn context (model loaded once)
  Phase 5  per-stage latency timing
  Phase 6  graceful error recovery (no crashes, no manual restart)
  Phase 7  voice-state indicators: IDLE / LISTENING / THINKING / SPEAKING

Run on the Windows host (where the mic + deps live):
    python voice_client/garvis_conversation.py
Quit any time with Ctrl+C, or say "goodbye" / "exit".
"""
from __future__ import annotations

import sys
import time
import queue
import signal
from dataclasses import dataclass, field

import numpy as np
import requests

# Hardware/heavy deps are imported lazily inside the functions that use them.
# This lets the module load for headless logic tests and makes each component
# fail gracefully (Phase 6) instead of crashing the whole program at import.

# ----------------------------------------------------------------------------
# Config (all tunable; sensible defaults)
# ----------------------------------------------------------------------------
API_URL = "http://localhost:8000/api/v1/runtime/command"
SESSION_ID = "windows-voice-conv"          # Phase 4: stable session across turns
SAMPLE_RATE = 16000
FRAME_MS = 30                              # VAD analysis frame
FRAME_LEN = SAMPLE_RATE * FRAME_MS // 1000

# Phase 2 — VAD tuning
SILENCE_TIMEOUT_S = 1.0                    # stop after this much trailing silence
MIN_SPEECH_S = 0.4                         # ignore blips shorter than this
MAX_UTTERANCE_S = 30.0                     # hard safety cap
START_ENERGY_MULT = 3.0                    # speech must exceed noise floor * this
PREROLL_FRAMES = 8                         # keep audio just before speech onset

WHISPER_MODEL = "base"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE = "int8"

HTTP_TIMEOUT_S = 90
STOP_WORDS = {"goodbye", "exit", "quit", "stop listening", "shut down"}


# ----------------------------------------------------------------------------
# Phase 7 — voice-state indicator (terminal; mirrors dashboard LISTENING/THINKING/SPEAKING/IDLE)
# ----------------------------------------------------------------------------
class State:
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"


_GLYPH = {
    State.IDLE: "·",
    State.LISTENING: "🎤",
    State.THINKING: "🧠",
    State.SPEAKING: "🔊",
}


def show_state(state: str, detail: str = "") -> None:
    print(f"\r[{_GLYPH.get(state,'')} {state:<9}] {detail:<60}", end="", flush=True)


# ----------------------------------------------------------------------------
# Phase 4 — conversation/session state
# ----------------------------------------------------------------------------
@dataclass
class Conversation:
    session_id: str = SESSION_ID
    turns: list[tuple[str, str]] = field(default_factory=list)  # (user, garvis)

    def add(self, user: str, garvis: str) -> None:
        self.turns.append((user, garvis))

    @property
    def last(self) -> tuple[str, str] | None:
        return self.turns[-1] if self.turns else None


# ----------------------------------------------------------------------------
# Phase 2 — VAD capture (energy-based, pure numpy; replaces the fixed 5s window)
# ----------------------------------------------------------------------------
MIN_ABS_FLOOR = 0.005   # absolute floor so a silent room can't make the threshold ~0
                        # and so TTS tail / fan noise can't false-trigger.


def calibrate_noise_floor(stream, frames: int = 15) -> float:
    """Sample ambient noise to set an adaptive speech threshold (with abs floor)."""
    energies = []
    for _ in range(frames):
        block, _ = stream.read(FRAME_LEN)
        energies.append(float(np.sqrt(np.mean(block.astype(np.float32) ** 2))))
    floor = float(np.median(energies)) if energies else MIN_ABS_FLOOR
    return max(floor, MIN_ABS_FLOOR)


def listen_utterance(stream, noise_floor: float) -> np.ndarray | None:
    """
    Record one utterance using VAD:
      - wait for speech (energy > floor * START_ENERGY_MULT)
      - keep recording while speech continues
      - stop after SILENCE_TIMEOUT_S of trailing silence
      - return None if utterance shorter than MIN_SPEECH_S
    """
    # adaptive threshold, but never below a usable absolute minimum
    speech_thresh = max(noise_floor, MIN_ABS_FLOOR) * START_ENERGY_MULT
    preroll: list[np.ndarray] = []
    collected: list[np.ndarray] = []
    started = False
    silence_run = 0.0
    total = 0.0

    show_state(State.LISTENING, "waiting for speech…")
    while True:
        block, _ = stream.read(FRAME_LEN)
        mono = block.reshape(-1).astype(np.float32)
        energy = float(np.sqrt(np.mean(mono ** 2)))
        is_speech = energy > speech_thresh

        if not started:
            preroll.append(mono)
            if len(preroll) > PREROLL_FRAMES:
                preroll.pop(0)
            if is_speech:
                started = True
                collected.extend(preroll)   # keep the lead-in so first word isn't clipped
                collected.append(mono)
                show_state(State.LISTENING, "speech detected…")
            continue

        collected.append(mono)
        total += FRAME_MS / 1000.0
        if is_speech:
            silence_run = 0.0
        else:
            silence_run += FRAME_MS / 1000.0
            if silence_run >= SILENCE_TIMEOUT_S:
                break
        if total >= MAX_UTTERANCE_S:
            break

    audio = np.concatenate(collected) if collected else np.zeros(0, dtype=np.float32)
    speech_dur = max(0.0, total - silence_run)
    if speech_dur < MIN_SPEECH_S:
        return None
    return audio


# ----------------------------------------------------------------------------
# STT / Runtime / TTS — reuse existing working components
# ----------------------------------------------------------------------------
def load_stt():
    from faster_whisper import WhisperModel
    return WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)


def transcribe(model, audio: np.ndarray) -> str:
    segments, _ = model.transcribe(audio, vad_filter=True, condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segments).strip()


def ask_garvis(conv: Conversation, text: str) -> tuple[str, float]:
    """POST to the existing runtime command endpoint. Returns (reply, latency_s)."""
    t0 = time.perf_counter()
    r = requests.post(
        API_URL,
        json={"text": text, "source": "voice", "session_id": conv.session_id, "metadata": {}},
        timeout=HTTP_TIMEOUT_S,
    )
    dt = time.perf_counter() - t0
    r.raise_for_status()
    data = r.json()
    return (data.get("response_text") or "I did not get a response."), dt


TTS_RATE = 170
TTS_VOLUME = 1.0


def make_tts():
    """Kept for call-site compatibility; engine is created per-utterance now."""
    return None


def tts_reset() -> None:
    """
    Reset the TTS subsystem. With a fresh-engine-per-call design there is no
    persistent engine to drop, but Windows SAPI can leave a wedged COM apartment
    after a failed runAndWait(); this re-initialises COM so the next engine is clean.
    """
    print("   [TTS_ENGINE_RESET]", flush=True)
    try:
        import pythoncom  # provided by pywin32, pulled in by pyttsx3 on Windows
        pythoncom.CoUninitialize()
        pythoncom.CoInitialize()
    except Exception:
        # pythoncom not present / not on Windows — fresh pyttsx3.init() is enough
        pass


def _speak_once(text: str) -> None:
    """
    Speak ONE utterance with a FRESH pyttsx3 engine, then fully dispose it.

    Why fresh each call: reusing one engine across repeated runAndWait() calls in
    a loop reliably wedges SAPI5/pyttsx3 on Windows — the first utterance plays,
    then every later runAndWait() silently no-ops (the exact reported symptom).
    A new init()/say()/runAndWait()/stop() per reply avoids the shared run loop.
    """
    import pyttsx3
    print("   [TTS_INIT]", flush=True)
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
    """
    Speak `text` reliably. Logs TTS_INIT / TTS_START / TTS_DONE / TTS_ERROR /
    TTS_ENGINE_RESET. On failure: prints the exact exception, resets the engine,
    retries ONCE, and never raises — the conversation always continues.
    Returns True if spoken, False if both attempts failed.
    """
    if not text or not text.strip():
        return True
    preview = text[:60].replace("\n", " ")

    for attempt in (1, 2):
        print(f"   [TTS_START] (attempt {attempt}) {preview!r}", flush=True)
        try:
            _speak_once(text)
            print("   [TTS_DONE]", flush=True)
            return True
        except Exception as exc:
            print(f"   [TTS_ERROR] {type(exc).__name__}: {exc}", flush=True)
            if attempt == 1:
                tts_reset()          # recover, then one retry
            # else: fall through, give up after 2nd failure
    return False


# ----------------------------------------------------------------------------
# Main continuous loop (Phase 3) with error recovery (Phase 6) + latency (Phase 5)
# ----------------------------------------------------------------------------
def main() -> None:
    print("=" * 64)
    print("  JARVIS — Continuous Conversation Mode")
    print("=" * 64)

    # one-time inits (Phase 4: model loaded ONCE, reused every turn)
    show_state(State.IDLE, "loading Whisper…")
    try:
        model = load_stt()
    except Exception as exc:  # Phase 6
        print(f"\n❌ Could not load STT model: {exc}")
        sys.exit(1)

    try:
        tts = make_tts()
    except Exception as exc:  # Phase 6
        print(f"\n❌ Could not init TTS: {exc}")
        sys.exit(1)

    conv = Conversation()

    # graceful Ctrl+C
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))

    try:
        import sounddevice as sd
        stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=FRAME_LEN)
        stream.start()
    except Exception as exc:  # Phase 6: mic unavailable
        print(f"\n❌ Microphone unavailable: {exc}")
        sys.exit(1)

    show_state(State.IDLE, "calibrating mic…")
    try:
        noise_floor = calibrate_noise_floor(stream)
    except Exception:
        noise_floor = 1e-3
    print(f"\n  Noise floor ~{noise_floor:.4f} · say 'goodbye' to exit.\n")

    turn = 0
    while not stop["flag"]:
        try:
            # ---- LISTEN (Phase 2 VAD) ----
            audio = listen_utterance(stream, noise_floor)
            if audio is None:                       # Phase 6: no speech
                show_state(State.IDLE, "no speech, still listening…")
                continue

            # ---- STT ----
            show_state(State.THINKING, "transcribing…")
            t0 = time.perf_counter()
            try:
                user_text = transcribe(model, audio)
            except Exception as exc:                # Phase 6
                show_state(State.IDLE, f"STT error: {exc}")
                continue
            stt_dt = time.perf_counter() - t0
            if not user_text:
                show_state(State.IDLE, "empty transcript, listening…")
                continue

            print(f"\n  🗣️  You: {user_text}")
            if user_text.lower().strip(" .!?") in STOP_WORDS:
                speak("Goodbye.")
                break

            # ---- RUNTIME + OLLAMA ----
            show_state(State.THINKING, "JARVIS is thinking…")
            try:
                reply, rt_dt = ask_garvis(conv, user_text)
            except requests.Timeout:                # Phase 6
                show_state(State.IDLE, "runtime timeout, listening…")
                speak("That took too long. Let us try again.")
                continue
            except Exception as exc:                # Phase 6
                show_state(State.IDLE, f"runtime error: {exc}")
                speak("I could not reach my runtime.")
                continue

            # ---- SPEAK ----
            print(f"  🤖 JARVIS: {reply}")
            show_state(State.SPEAKING, "speaking…")
            t0 = time.perf_counter()
            try:
                speak(reply)
            except Exception as exc:                # Phase 6
                show_state(State.IDLE, f"TTS error: {exc}")
            tts_dt = time.perf_counter() - t0

            conv.add(user_text, reply)              # Phase 4
            turn += 1
            print(f"     ⏱  stt {stt_dt:.1f}s · runtime {rt_dt:.1f}s · tts {tts_dt:.1f}s · turn #{turn}\n")

            # ---- settle + re-calibrate so the loop reliably hears the NEXT turn ----
            # (fixes "spoke once then stopped": TTS tail can bleed into the mic and
            #  the room level can drift; re-adapt the noise floor each turn.)
            time.sleep(0.4)
            try:
                # drain any buffered audio from the speaker bleed
                for _ in range(int(0.3 / (FRAME_MS / 1000))):
                    stream.read(FRAME_LEN)
                noise_floor = calibrate_noise_floor(stream, frames=10)
            except Exception:
                pass
            show_state(State.IDLE, "listening resumes…")  # Phase 3: auto back to listen

        except Exception as exc:                    # Phase 6: never crash the loop
            show_state(State.IDLE, f"recovered from: {exc}")
            time.sleep(0.5)

    try:
        stream.stop(); stream.close()
    except Exception:
        pass
    print(f"\n\n  Conversation ended — {turn} turn(s).")


if __name__ == "__main__":
    main()
