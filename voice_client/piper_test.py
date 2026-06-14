"""
Standalone Piper TTS test for JARVIS.

Run:
    python voice_client/piper_test.py
    python voice_client/piper_test.py "custom text to speak"

Verifies:
  - piper.exe is found and the English voice model loads
  - Piper speaks an English line (calm cadence)
  - the language router sends Hebrew to pyttsx3 (Piper has no Hebrew voice)
  - pyttsx3 fallback still works

ASCII status output; the spoken Hebrew line itself is Unicode.
"""
from __future__ import annotations

import sys

try:
    from garvis_conversation import (
        PIPER_EXE, TTS_VOICE, TTS_ENGINE, PIPER_LENGTH_SCALE,
        piper_available, speak_piper, speak_pyttsx3, speak, _is_hebrew, _is_cyrillic,
    )
except ImportError:
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from garvis_conversation import (
        PIPER_EXE, TTS_VOICE, TTS_ENGINE, PIPER_LENGTH_SCALE,
        piper_available, speak_piper, speak_pyttsx3, speak, _is_hebrew, _is_cyrillic,
    )


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 60)
    print("  JARVIS Piper TTS test")
    print("=" * 60)
    print(f"  TTS_ENGINE        : {TTS_ENGINE}")
    print(f"  PIPER_EXE         : {PIPER_EXE}")
    print(f"  TTS_VOICE (model) : {TTS_VOICE}")
    print(f"  length-scale      : {PIPER_LENGTH_SCALE} (>1 = slower/calmer)")
    print(f"  piper_available() : {piper_available()}")
    print()

    custom = " ".join(sys.argv[1:]).strip()

    # 1. English via Piper
    en = custom or "Hello Stas. I am JARVIS, your local assistant. Everything is running smoothly."
    print(f"[1] English via Piper: {en!r}")
    if piper_available():
        ok = speak_piper(en)
        print(f"    piper spoke: {ok}")
        if not ok:
            print("    falling back to pyttsx3...")
            speak_pyttsx3(en)
    else:
        print("    piper NOT available -> pyttsx3 fallback")
        speak_pyttsx3(en)
    print()

    # 2. Hebrew -> routed to pyttsx3 (Piper has no Hebrew voice)
    he = "שלום סטס, אני ג'רוויס, העוזר המקומי שלך."
    print(f"[2] Hebrew via dispatcher (expect pyttsx3 route): is_hebrew={_is_hebrew(he)}")
    speak(he)
    print()

    # 3. Russian via Piper RU voice (may fail on Python 3.14 -> pyttsx3 fallback)
    ru = "Здравствуйте, Стас. Я ваш локальный помощник. Всё работает нормально."
    print(f"[3] Russian via dispatcher (Cyrillic -> Piper ru): is_cyrillic={_is_cyrillic(ru)}")
    speak(ru)
    print()

    # 4. pyttsx3 fallback path directly
    print("[4] pyttsx3 fallback path directly")
    speak_pyttsx3("This is the pyttsx3 fallback voice.")
    print()
    print("Done. #1 English (Piper), #2 Hebrew (pyttsx3), #3 Russian (Piper ru if the")
    print("phonemizer works, else fallback), #4 pyttsx3. Fallbacks keep the loop alive.")


if __name__ == "__main__":
    main()
