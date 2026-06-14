"""
Piper setup for JARVIS voice (local/free only).

Run:
    python voice_client/piper_setup.py

Does:
  1. Detects piper.exe (pip package 'piper-tts'). Prints install hint if missing.
  2. Downloads the English voice model (en_US-lessac-medium) into ./piper_voices
     if it is not already present.
  3. Reports Hebrew availability (Piper has NO he_IL voice in the official catalog,
     so Hebrew is handled by pyttsx3 in the conversation client).

No paid APIs, no ElevenLabs. Models come from the free rhasspy/piper-voices repo.
"""
from __future__ import annotations

import os
import shutil
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
VOICE_DIR = os.path.join(HERE, "piper_voices")
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

EN_VOICE = "en_US-lessac-medium"
EN_FILES = {
    f"{EN_VOICE}.onnx": f"{BASE}/en/en_US/lessac/medium/{EN_VOICE}.onnx",
    f"{EN_VOICE}.onnx.json": f"{BASE}/en/en_US/lessac/medium/{EN_VOICE}.onnx.json",
}


def find_piper():
    cand = (os.getenv("PIPER_EXE") or shutil.which("piper") or shutil.which("piper.exe")
            or r"C:\Users\staso\AppData\Roaming\Python\Python314\Scripts\piper.exe")
    return cand if cand and os.path.exists(cand) else None


def download(url: str, dest: str) -> None:
    print(f"  downloading {os.path.basename(dest)} ...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "jarvis-piper-setup"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    print(f"    saved {os.path.getsize(dest)} bytes")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 60)
    print("  JARVIS Piper setup")
    print("=" * 60)

    piper = find_piper()
    if piper:
        print(f"[1] piper.exe FOUND: {piper}")
    else:
        print("[1] piper.exe NOT found. Install with:")
        print("        pip install --user piper-tts")
        print("    then re-run this script.")

    os.makedirs(VOICE_DIR, exist_ok=True)
    print(f"[2] English voice model -> {VOICE_DIR}")
    for name, url in EN_FILES.items():
        dest = os.path.join(VOICE_DIR, name)
        if os.path.exists(dest) and os.path.getsize(dest) > 1024:
            print(f"    {name}: already present ({os.path.getsize(dest)} bytes)")
        else:
            download(url, dest)

    print("[3] Hebrew voice: Piper has NO he_IL voice in the official catalog.")
    print("    Hebrew replies are spoken by pyttsx3 (SAPI5) in the conversation client.")
    print()
    print("Done. Test with:  python voice_client/piper_test.py")


if __name__ == "__main__":
    main()
