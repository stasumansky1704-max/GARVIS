"""
Mock loop test — exercises the state-machine logic WITHOUT a microphone.

Run:
    python voice_client/test_loop_mock.py

Covers: VAD segmentation over synthetic frames, blip rejection, VAD timeout,
stop-word detection, mic stop/start isolation around speak, TTS error -> reset ->
retry path, and a live runtime round-trip. No audio hardware required.
"""
from __future__ import annotations

import sys
import numpy as np

import garvis_conversation as gc

_passed = True
def ok(m):  print(f"  [PASS] {m}")
def bad(m):
    global _passed; _passed = False; print(f"  [FAIL] {m}")


class FakeStream:
    """Feeds pre-built frames; records stop()/start() so we can assert mic isolation."""
    def __init__(self, frames):
        self._frames = list(frames); self._i = 0
        self.events = []
    def read(self, n):
        if self._i >= len(self._frames):
            return np.zeros((n, 1), dtype=np.float32), None
        f = self._frames[self._i]; self._i += 1
        return f.reshape(-1, 1), None
    def start(self): self.events.append("start")
    def stop(self): self.events.append("stop")
    def close(self): self.events.append("close")


def frame(amp): return (np.random.randn(gc.FRAME_LEN).astype(np.float32) * amp)


def test_vad_capture_and_stop():
    sp = int(1.0 / (gc.FRAME_MS/1000)); sil = int(1.2 / (gc.FRAME_MS/1000))
    frames = [frame(0.0005)]*5 + [frame(0.05)]*sp + [frame(0.0005)]*sil
    a = gc.listen_utterance(FakeStream(frames), 0.001)
    if a is not None and len(a) > gc.SAMPLE_RATE*0.8: ok(f"VAD captured + stopped on silence ({len(a)/gc.SAMPLE_RATE:.1f}s)")
    else: bad(f"VAD capture wrong: {None if a is None else len(a)}")


def test_vad_reject_blip():
    sp = int(0.2 / (gc.FRAME_MS/1000)); sil = int(1.2 / (gc.FRAME_MS/1000))
    frames = [frame(0.0005)]*3 + [frame(0.05)]*sp + [frame(0.0005)]*sil
    a = gc.listen_utterance(FakeStream(frames), 0.001)
    if a is None: ok("VAD rejected sub-minimum blip")
    else: bad("VAD should reject blip")


def test_vad_timeout():
    # all silence, longer than MAX_LISTEN_S worth of frames
    n = int(gc.MAX_LISTEN_S / (gc.FRAME_MS/1000)) + 5
    a = gc.listen_utterance(FakeStream([frame(0.0005)]*n), 0.001)
    if a is None: ok("VAD timeout returns None on prolonged silence")
    else: bad("VAD should time out")


def test_stop_words():
    cases = {"goodbye": True, "Exit.": True, "stop": True, "quit": True, "what time is it": False}
    good = all(gc.is_stop_word(k) == v for k, v in cases.items())
    ok("stop-word detection correct") if good else bad("stop-word detection wrong")


def test_speak_isolation(monkey=True):
    # speak() replaced so no real audio; assert mic stop happens BEFORE speak, start AFTER
    order = []
    orig = gc.speak
    gc.speak = lambda t: (order.append("speak"), True)[1]
    s = FakeStream([])
    gc.speak_isolated(s, "hello")
    gc.speak = orig
    if s.events == ["stop", "start"] and order == ["speak"]:
        ok("mic stopped before speak, restarted after (never listen while speaking)")
    else:
        bad(f"isolation order wrong: stream={s.events} speak={order}")


def test_tts_error_recovery():
    orig = gc._speak_once
    calls = {"n": 0}
    def boom(t): calls["n"] += 1; raise RuntimeError("simulated SAPI lockup")
    gc._speak_once = boom
    r = gc.speak("fails twice")
    gc._speak_once = orig
    if r is False and calls["n"] == 2:
        ok("TTS failure -> reset -> retry once -> returns False (no crash)")
    else:
        bad(f"TTS recovery wrong: returned {r}, attempts {calls['n']}")


def test_live_runtime():
    try:
        reply, dt = gc.ask_garvis(gc.Conversation(session_id="mock-test"), "Reply with one short word.")
        ok(f"live runtime round-trip ({dt:.1f}s) -> {reply[:40]!r}") if reply else bad("runtime empty")
    except Exception as e:
        bad(f"runtime call failed: {e}")


if __name__ == "__main__":
    print("="*56); print("  GARVIS mock loop test (no mic)"); print("="*56)
    test_vad_capture_and_stop()
    test_vad_reject_blip()
    test_vad_timeout()
    test_stop_words()
    test_speak_isolation()
    test_tts_error_recovery()
    test_live_runtime()
    print("="*56); print("  ALL PASSED" if _passed else "  SOME FAILED"); print("="*56)
    sys.exit(0 if _passed else 1)
