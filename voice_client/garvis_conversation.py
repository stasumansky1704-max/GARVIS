"""
GARVIS Voice — Continuous Conversation Mode (Windows voice client)

Explicit state machine with TTS fully isolated from listening:

    IDLE -> LISTENING -> TRANSCRIBING -> THINKING -> SPEAKING -> COOLDOWN -> LISTENING
                                          (any failure) -> ERROR_RECOVERY -> COOLDOWN

Reuses the existing verified stack (nothing rebuilt):
    faster-whisper (STT), sounddevice (mic), pyttsx3 (TTS), POST /api/v1/runtime/command

Key reliability rules:
  - NEVER listen while speaking: the mic InputStream is STOPPED before TTS and
    restarted after a cooldown, so TTS output cannot bleed into the mic and the
    loop cannot half-listen during speech.
  - Fresh pyttsx3 engine per utterance (a shared engine + repeated runAndWait()
    wedges Windows SAPI5 -> silent after the first reply). On failure: reset + retry.
  - Re-calibrate the noise floor before every listening turn (adaptive + abs floor).

Run on the Windows host (mic + deps live there):
    python voice_client/garvis_conversation.py
Say "goodbye" / "exit" / "stop" / "quit" (or Ctrl+C) to end.
"""
from __future__ import annotations

import sys
import time
import signal
from dataclasses import dataclass, field

import numpy as np
import requests

# Heavy/hardware deps imported lazily so the module loads headless for tests.

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
API_URL = "http://localhost:8000/api/v1/runtime/command"
SESSION_ID = "windows-voice-conv"
SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_LEN = SAMPLE_RATE * FRAME_MS // 1000

# VAD tuning
SILENCE_TIMEOUT_S = 1.0          # end of turn after this trailing silence
MIN_SPEECH_S = 0.4               # reject blips shorter than this
MAX_LISTEN_S = 20.0              # max time waiting for speech to START
MAX_UTTERANCE_S = 30.0           # max length of a single utterance
START_ENERGY_MULT = 3.0          # speech must exceed noise floor * this
MIN_ABS_FLOOR = 0.005            # absolute threshold floor (silent room / TTS tail safety)
PREROLL_FRAMES = 8               # audio kept just before speech onset

COOLDOWN_S = 0.5                 # 300–700ms cooldown after speaking

WHISPER_MODEL = "base"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE = "int8"
HTTP_TIMEOUT_S = 90
STOP_WORDS = {"goodbye", "exit", "stop", "quit", "stop listening", "shut down"}

TTS_RATE = 170
TTS_VOLUME = 1.0


# ----------------------------------------------------------------------------
# States
# ----------------------------------------------------------------------------
class State:
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    COOLDOWN = "COOLDOWN"
    ERROR_RECOVERY = "ERROR_RECOVERY"


def log_state(state: str, detail: str = "") -> None:
    print(f"[{state:<15}] {detail}", flush=True)


# ----------------------------------------------------------------------------
# Conversation/session state
# ----------------------------------------------------------------------------
@dataclass
class Conversation:
    session_id: str = SESSION_ID
    turns: list[tuple[str, str]] = field(default_factory=list)

    def add(self, user: str, garvis: str) -> None:
        self.turns.append((user, garvis))

    @property
    def last(self) -> tuple[str, str] | None:
        return self.turns[-1] if self.turns else None


# ----------------------------------------------------------------------------
# TTS — isolated, fresh engine per utterance, full logs, reset + retry
# ----------------------------------------------------------------------------
def tts_reset() -> None:
    print("   [TTS_RESET]", flush=True)
    try:
        import pythoncom  # pywin32 (pulled in by pyttsx3 on Windows)
        pythoncom.CoUninitialize()
        pythoncom.CoInitialize()
    except Exception:
        pass  # not on Windows / not present — fresh init() suffices


def _speak_once(text: str) -> None:
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
    """Speak text reliably. Logs TTS_START/TTS_DONE/TTS_ERROR(+TTS_RESET). Never raises."""
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
                tts_reset()
    return False


# ----------------------------------------------------------------------------
# Mic stream lifecycle (stop fully while speaking)
# ----------------------------------------------------------------------------
def open_stream():
    import sounddevice as sd
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=FRAME_LEN)
    stream.start()
    return stream


def close_stream(stream) -> None:
    try:
        stream.stop()
        stream.close()
    except Exception:
        pass


def speak_isolated(stream, text: str) -> bool:
    """Stop the mic, speak fully, restart the mic. Never listen while speaking."""
    try:
        stream.stop()           # pause capture so TTS can't bleed into the mic
    except Exception:
        pass
    ok = speak(text)
    try:
        stream.start()          # resume capture for the next turn
    except Exception:
        pass
    return ok


def recover_stream(stream):
    log_state(State.ERROR_RECOVERY, "resetting mic stream")
    close_stream(stream)
    try:
        return open_stream()
    except Exception as exc:
        print(f"❌ mic reopen failed: {exc}; retrying in 1s")
        time.sleep(1.0)
        return open_stream()


# ----------------------------------------------------------------------------
# VAD
# ----------------------------------------------------------------------------
def calibrate_noise_floor(stream, frames: int = 12) -> float:
    energies = []
    for _ in range(frames):
        block, _ = stream.read(FRAME_LEN)
        energies.append(float(np.sqrt(np.mean(block.astype(np.float32) ** 2))))
    floor = float(np.median(energies)) if energies else MIN_ABS_FLOOR
    return max(floor, MIN_ABS_FLOOR)


def listen_utterance(stream, noise_floor: float) -> np.ndarray | None:
    """Capture one utterance. Logs VAD_START / VAD_STOP / VAD_TIMEOUT. None on timeout/too-short."""
    speech_thresh = max(noise_floor, MIN_ABS_FLOOR) * START_ENERGY_MULT
    preroll: list[np.ndarray] = []
    collected: list[np.ndarray] = []
    started = False
    silence_run = 0.0
    wait = 0.0
    total = 0.0

    while True:
        block, _ = stream.read(FRAME_LEN)
        mono = block.reshape(-1).astype(np.float32)
        energy = float(np.sqrt(np.mean(mono ** 2)))
        is_speech = energy > speech_thresh

        if not started:
            wait += FRAME_MS / 1000.0
            preroll.append(mono)
            if len(preroll) > PREROLL_FRAMES:
                preroll.pop(0)
            if is_speech:
                started = True
                print("   [VAD_START]", flush=True)
                collected.extend(preroll)
                collected.append(mono)
            elif wait >= MAX_LISTEN_S:
                print("   [VAD_TIMEOUT] no speech", flush=True)
                return None
            continue

        collected.append(mono)
        total += FRAME_MS / 1000.0
        if is_speech:
            silence_run = 0.0
        else:
            silence_run += FRAME_MS / 1000.0
            if silence_run >= SILENCE_TIMEOUT_S:
                print("   [VAD_STOP] silence", flush=True)
                break
        if total >= MAX_UTTERANCE_S:
            print("   [VAD_STOP] max utterance", flush=True)
            break

    speech_dur = max(0.0, total - silence_run)
    if speech_dur < MIN_SPEECH_S:
        print(f"   [VAD_STOP] too short ({speech_dur:.2f}s) — rejected", flush=True)
        return None
    return np.concatenate(collected) if collected else None


# ----------------------------------------------------------------------------
# STT / Runtime
# ----------------------------------------------------------------------------
def load_stt():
    from faster_whisper import WhisperModel
    return WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)


def transcribe(model, audio: np.ndarray) -> str:
    segments, _ = model.transcribe(audio, vad_filter=True, condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segments).strip()


def ask_garvis(conv: Conversation, text: str) -> tuple[str, float]:
    t0 = time.perf_counter()
    r = requests.post(
        API_URL,
        json={"text": text, "source": "voice", "session_id": conv.session_id, "metadata": {}},
        timeout=HTTP_TIMEOUT_S,
    )
    dt = time.perf_counter() - t0
    r.raise_for_status()
    return (r.json().get("response_text") or "I did not get a response."), dt


def is_stop_word(text: str) -> bool:
    return text.lower().strip(" .!?,") in STOP_WORDS


# ----------------------------------------------------------------------------
# Main state machine
# ----------------------------------------------------------------------------
def main() -> None:
    print("=" * 64)
    print("  GARVIS — Continuous Conversation (state machine)")
    print("=" * 64)

    log_state(State.IDLE, "loading Whisper…")
    try:
        model = load_stt()
    except Exception as exc:
        print(f"❌ STT load failed: {exc}"); sys.exit(1)

    conv = Conversation()
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))

    try:
        stream = open_stream()
    except Exception as exc:
        print(f"❌ Microphone unavailable: {exc}"); sys.exit(1)
    noise_floor = calibrate_noise_floor(stream)
    log_state(State.IDLE, f"ready · noise floor ~{noise_floor:.4f} · say 'goodbye' to exit")

    turn = 0
    user_text = ""
    reply = ""
    stt_dt = rt_dt = 0.0
    state = State.LISTENING

    while not stop["flag"]:
        try:
            if state == State.LISTENING:
                log_state(State.LISTENING, "waiting for speech…")
                audio = listen_utterance(stream, noise_floor)
                if audio is None:
                    state = State.COOLDOWN
                    continue
                t0 = time.perf_counter()
                state = State.TRANSCRIBING

            if state == State.TRANSCRIBING:
                log_state(State.TRANSCRIBING, "transcribing…")
                user_text = transcribe(model, audio)
                stt_dt = time.perf_counter() - t0
                if not user_text:
                    log_state(State.TRANSCRIBING, "empty transcript")
                    state = State.COOLDOWN
                    continue
                print(f"  🗣️  You: {user_text}")
                if is_stop_word(user_text):
                    speak_isolated(stream, "Goodbye.")
                    break
                state = State.THINKING

            if state == State.THINKING:
                log_state(State.THINKING, "GARVIS is thinking…")
                reply, rt_dt = ask_garvis(conv, user_text)
                print(f"  🤖 GARVIS: {reply}")
                state = State.SPEAKING

            if state == State.SPEAKING:
                log_state(State.SPEAKING, "mic paused, speaking…")
                t0 = time.perf_counter()
                spoke = speak_isolated(stream, reply)
                tts_dt = time.perf_counter() - t0
                if not spoke:
                    log_state(State.ERROR_RECOVERY, "TTS failed — continuing")
                conv.add(user_text, reply)
                turn += 1
                print(f"     ⏱  stt {stt_dt:.1f}s · runtime {rt_dt:.1f}s · tts {tts_dt:.1f}s · turn #{turn}")
                state = State.COOLDOWN

            if state == State.COOLDOWN:
                log_state(State.COOLDOWN, f"{int(COOLDOWN_S*1000)}ms…")
                time.sleep(COOLDOWN_S)
                try:
                    for _ in range(int(0.2 / (FRAME_MS / 1000))):
                        stream.read(FRAME_LEN)          # drain buffered audio
                    noise_floor = calibrate_noise_floor(stream, frames=10)
                except Exception:
                    stream = recover_stream(stream)
                state = State.LISTENING

        except requests.Timeout:
            log_state(State.ERROR_RECOVERY, "runtime timeout")
            speak_isolated(stream, "That took too long. Let us try again.")
            state = State.COOLDOWN
        except Exception as exc:
            log_state(State.ERROR_RECOVERY, f"{type(exc).__name__}: {exc}")
            stream = recover_stream(stream)
            state = State.COOLDOWN

    close_stream(stream)
    print(f"\n  Conversation ended — {turn} turn(s).")


if __name__ == "__main__":
    main()
