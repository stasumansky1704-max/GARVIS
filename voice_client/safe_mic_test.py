"""
Safe microphone test for the persistent (non-WDM-KS) capture path.

Run:
    python voice_client/safe_mic_test.py

Opens ONE persistent sd.InputStream on a safe backend (WASAPI -> DirectSound -> MME,
WDM-KS excluded), reads from the ring buffer for AT MOST ~5 seconds, prints the
selected backend/device/rate/peak, then STOPS the stream and exits.

It deliberately does NOT run the full conversation loop, Whisper, or TTS.
"""
from __future__ import annotations

import sys
import time

try:
    import sounddevice as sd
    from garvis_conversation import (
        open_capture, peak_of, _hostapi_name, EXCLUDED_HOSTAPIS, USABLE_PEAK,
    )
except ImportError:
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import sounddevice as sd
    from garvis_conversation import (
        open_capture, peak_of, _hostapi_name, EXCLUDED_HOSTAPIS, USABLE_PEAK,
    )

MAX_SECONDS = 5.0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 60)
    print("  JARVIS safe mic test (persistent stream, WDM-KS excluded)")
    print("=" * 60)

    cap, peak = open_capture()
    if cap is None:
        print("[ERROR] no safe (non-WDM-KS) input device could be opened")
        return 1

    # Confirm the chosen endpoint is NOT a WDM-KS device.
    try:
        api = _hostapi_name(sd.query_devices()[cap.device]["hostapi"])
    except Exception:
        api = "?"
    is_wdmks = any(x.lower() in api.lower() for x in EXCLUDED_HOSTAPIS)

    print(f"[CAPTURE_BACKEND] {cap.backend}")
    print(f"[CAPTURE_DEVICE]  [{cap.device}] {cap.name}")
    print(f"[CAPTURE_RATE]    {cap.rate} Hz")
    print(f"[CAPTURE_PEAK]    {peak:.5f} (need > {USABLE_PEAK})")
    print(f"[HOSTAPI]         {api}  ->  WDM-KS={'YES (UNSAFE!)' if is_wdmks else 'no (safe)'}")

    if is_wdmks:
        print("[FAIL] a WDM-KS device was selected - aborting.")
        cap.stop()
        return 2

    # Read for at most MAX_SECONDS, then stop. (No conversation, no Whisper, no TTS.)
    print(f"\n  Reading from the persistent stream for up to {MAX_SECONDS:.0f}s "
          f"(speak to see the peak rise)...")
    rolling = peak
    deadline = time.time() + MAX_SECONDS
    while time.time() < deadline:
        rolling = max(rolling, peak_of(cap.read(0.5)))
    cap.stop()
    print(f"\n  rolling peak over window: {rolling:.5f}")
    print("  [OK] stream opened, read, and CLOSED. Exiting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
