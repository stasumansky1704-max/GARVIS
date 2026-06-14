"""
Headless logic tests for the conversation client (Phase 8, no-mic CI).

Exercises the pure-logic parts that don't need a microphone:
  - VAD segmentation over synthetic audio (silence / speech / trailing silence)
  - MIN_SPEECH_S rejection of blips
  - Conversation session state (context retention, last turn)
  - Stop-word detection
  - ask_garvis() against the live backend (real runtime round-trip)

Run: python voice_client/test_conversation_logic.py
"""
from __future__ import annotations

import sys
import numpy as np

import garvis_conversation as gc

_passed = True


def ok(msg):  print(f"  [PASS] {msg}")
def bad(msg):
    global _passed; _passed = False; print(f"  [FAIL] {msg}")


class FakeStream:
    """Feeds pre-built frames to listen_utterance/calibrate via .read()."""
    def __init__(self, frames):
        self._frames = list(frames); self._i = 0
    def read(self, n):
        if self._i >= len(self._frames):
            return np.zeros((n, 1), dtype=np.float32), None
        f = self._frames[self._i]; self._i += 1
        return f.reshape(-1, 1), None


def _frame(amp):
    return (np.random.randn(gc.FRAME_LEN).astype(np.float32) * amp)


def test_vad_detects_and_stops():
    floor = 0.001
    # 5 silence (preroll) + ~1.0s speech + ~1.2s silence (> SILENCE_TIMEOUT_S)
    speech_frames = int(1.0 / (gc.FRAME_MS / 1000))
    sil_frames = int(1.2 / (gc.FRAME_MS / 1000))
    frames = [_frame(0.0005) for _ in range(5)] \
        + [_frame(0.05) for _ in range(speech_frames)] \
        + [_frame(0.0005) for _ in range(sil_frames)]
    audio = gc.listen_utterance(FakeStream(frames), floor)
    if audio is not None and len(audio) > gc.SAMPLE_RATE * 0.8:
        ok(f"VAD captured speech & stopped on silence ({len(audio)/gc.SAMPLE_RATE:.1f}s)")
    else:
        bad(f"VAD capture wrong: {None if audio is None else len(audio)}")


def test_vad_rejects_blip():
    floor = 0.001
    speech_frames = int(0.2 / (gc.FRAME_MS / 1000))  # < MIN_SPEECH_S
    sil_frames = int(1.2 / (gc.FRAME_MS / 1000))
    frames = [_frame(0.0005) for _ in range(3)] \
        + [_frame(0.05) for _ in range(speech_frames)] \
        + [_frame(0.0005) for _ in range(sil_frames)]
    audio = gc.listen_utterance(FakeStream(frames), floor)
    if audio is None:
        ok("VAD rejected sub-minimum blip")
    else:
        bad(f"VAD should have rejected blip, got {len(audio)} samples")


def test_session_state():
    conv = gc.Conversation()
    conv.add("hello", "hi there")
    conv.add("how are you", "good")
    if conv.last == ("how are you", "good") and len(conv.turns) == 2 and conv.session_id == gc.SESSION_ID:
        ok("session state retains turns + stable session_id")
    else:
        bad(f"session state wrong: {conv.turns}")


def test_stop_words():
    if "goodbye" in gc.STOP_WORDS and "exit" in gc.STOP_WORDS:
        ok("stop-words configured")
    else:
        bad("stop-words missing")


def test_live_runtime():
    conv = gc.Conversation(session_id="logic-test")
    try:
        reply, dt = gc.ask_garvis(conv, "Reply with one short word.")
        if reply and dt > 0:
            ok(f"live runtime round-trip OK ({dt:.1f}s) -> {reply[:40]!r}")
        else:
            bad("runtime returned empty")
    except Exception as exc:
        bad(f"runtime call failed: {exc}")


if __name__ == "__main__":
    print("=" * 56)
    print("  Conversation logic tests (no mic)")
    print("=" * 56)
    test_vad_detects_and_stops()
    test_vad_rejects_blip()
    test_session_state()
    test_stop_words()
    test_live_runtime()
    print("=" * 56)
    print("  ALL PASSED" if _passed else "  SOME FAILED")
    sys.exit(0 if _passed else 1)
