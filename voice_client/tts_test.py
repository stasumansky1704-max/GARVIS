"""
Standalone TTS reliability test for the GARVIS voice client.

Proves the fix for the pyttsx3 engine-reuse lockup: speaks 5 consecutive
utterances using the SAME speak() path the conversation client uses.

Run:
    py voice_client/tts_test.py
    (or: python voice_client/tts_test.py)

Expected: you HEAR all 5 lines, and see TTS_START/TTS_DONE for each.
If any fails, it prints TTS_ERROR with the exact exception and keeps going.
"""
from __future__ import annotations

import time

# import the real speak() from the conversation client so we test the exact code path
try:
    from garvis_conversation import speak
except ImportError:
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from garvis_conversation import speak


LINES = [
    "JARVIS text to speech test, line one.",
    "This is the second consecutive reply.",
    "Third reply — the engine is created fresh each time.",
    "Fourth reply, still speaking without locking up.",
    "Fifth and final reply. If you heard all five, the fix works.",
]


def main() -> None:
    print("=" * 56)
    print("  GARVIS TTS reliability test — 5 consecutive replies")
    print("=" * 56)
    ok = 0
    for i, line in enumerate(LINES, 1):
        print(f"\n[{i}/5]")
        success = speak(line)
        ok += 1 if success else 0
        time.sleep(0.3)  # mimic the conversation loop's between-turn gap
    print("\n" + "=" * 56)
    print(f"  RESULT: {ok}/5 spoken successfully")
    print("  PASS" if ok == 5 else "  CHECK ERRORS ABOVE")
    print("=" * 56)


if __name__ == "__main__":
    main()
