"""
Standalone repeat-TTS test — proves the engine lifecycle survives many calls.

Run:
    py voice_client/tts_repeat_test.py

Speaks "test one" ... "test ten" (10 in a row), printing
TTS_INIT / TTS_START / TTS_DONE / TTS_ERROR / TTS_ENGINE_RESET for each.

If this passes (10/10) but the conversation client still goes silent, the
problem is elsewhere (not TTS). If THIS fails, the bug is reproduced standalone.
"""
from __future__ import annotations

import time

try:
    from garvis_conversation import speak, tts_reset
except ImportError:
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from garvis_conversation import speak, tts_reset

WORDS = ["one", "two", "three", "four", "five",
         "six", "seven", "eight", "nine", "ten"]


def main() -> None:
    print("=" * 56)
    print("  GARVIS repeat-TTS test — 10 consecutive messages")
    print("=" * 56)
    ok = 0
    for i, w in enumerate(WORDS, 1):
        print(f"\n[{i}/10]")
        if speak(f"test {w}"):
            ok += 1
        time.sleep(0.25)
    print("\n" + "=" * 56)
    print(f"  RESULT: {ok}/10 spoken")
    print("  PASS — TTS lifecycle is reliable" if ok == 10 else "  FAIL — see TTS_ERROR above")
    print("=" * 56)


if __name__ == "__main__":
    main()
