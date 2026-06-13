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
def calibrate_noise_floor(stream, frames: int = 20) -> float:
    """Sample ambient noise for ~0.6s to set an adaptive speech threshold."""
    energies = []
    for _ in range(frames):
        block, _ = stream.read(FRAME_LEN)
        energies.append(float(np.sqrt(np.mean(block.astype(np.float32) ** 2))))
    floor = float(np.median(energies)) if energies else 1e-4
    return max(floor, 1e-4)


def listen_utterance(stream, noise_floor: float) -> np.ndarray | None:
    """
    Record one utterance using VAD:
      - wait for speech (energy > floor * START_ENERGY_MULT)
      - keep recording while speech continues
      - stop after SILENCE_TIMEOUT_S of trailing silence
      - return None if utterance shorter than MIN_SPEECH_S
    """
    speech_thresh = noise_floor * START_ENERGY_MULT
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


def make_tts():
    import pyttsx3
    engine = pyttsx3.init()
    engine.setProperty("rate", 170)
    engine.setProperty("volume", 1.0)
    return engine


def speak(engine, text: str) -> None:
    engine.say(text)
    engine.runAndWait()


# ----------------------------------------------------------------------------
# Main continuous loop (Phase 3) with error recovery (Phase 6) + latency (Phase 5)
# ----------------------------------------------------------------------------
def main() -> None:
    print("=" * 64)
    print("  GARVIS — Continuous Conversation Mode")
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
                speak(tts, "Goodbye.")
                break

            # ---- RUNTIME + OLLAMA ----
            show_state(State.THINKING, "GARVIS is thinking…")
            try:
                reply, rt_dt = ask_garvis(conv, user_text)
            except requests.Timeout:                # Phase 6
                show_state(State.IDLE, "runtime timeout, listening…")
                speak(tts, "That took too long. Let's try again.")
                continue
            except Exception as exc:                # Phase 6
                show_state(State.IDLE, f"runtime error: {exc}")
                speak(tts, "I could not reach my runtime.")
                continue

            # ---- SPEAK ----
            print(f"  🤖 GARVIS: {reply}")
            show_state(State.SPEAKING, "speaking…")
            t0 = time.perf_counter()
            try:
                speak(tts, reply)
            except Exception as exc:                # Phase 6
                show_state(State.IDLE, f"TTS error: {exc}")
            tts_dt = time.perf_counter() - t0

            conv.add(user_text, reply)              # Phase 4
            turn += 1
            print(f"     ⏱  stt {stt_dt:.1f}s · runtime {rt_dt:.1f}s · tts {tts_dt:.1f}s · turn #{turn}\n")
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
