"""
Microphone level test - verify your input device actually captures audio.

Run:
    python voice_client/mic_level_test.py

Lists all input devices with a quick peak sample, shows which device the
conversation client will auto-select, then records ~4s from it while you speak
and prints MAX / AVG. You want MAX > 0.02 while speaking.
"""
from __future__ import annotations

import numpy as np

try:
    from garvis_conversation import (
        list_input_devices, select_input_device, _peak_for_device,
    )
except ImportError:
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from garvis_conversation import (
        list_input_devices, select_input_device, _peak_for_device,
    )


def main() -> None:
    import sounddevice as sd
    print("=" * 60)
    print("  GARVIS microphone level test")
    print("=" * 60)

    print("\nInput devices (quick 0.4s peak each):")
    for i, name, sr in list_input_devices():
        peak = _peak_for_device(i, sr, seconds=0.4)
        mark = "  <- silent?" if peak < 0.005 else ""
        print(f"  [{i}] {name[:40]:<40} {sr:>6}Hz  peak={peak:.5f}{mark}")

    idx, rate, name = select_input_device()
    print(f"\nSelected device: [{idx}] {name} @ {rate} Hz")

    seconds = 4
    print(f"\n[mic] Recording {seconds}s - SPEAK NOW...")
    rec = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype="float32", device=idx)
    sd.wait()
    rec = rec.reshape(-1)
    mx = float(np.max(np.abs(rec))) if rec.size else 0.0
    avg = float(np.mean(np.abs(rec))) if rec.size else 0.0
    print(f"\n  MAX={mx:.6f}  AVG={avg:.6f}")
    if mx > 0.02:
        print("  [OK] PASS - mic is capturing your voice.")
    else:
        print("  [ERROR] LOW - mic level too low. Try a different device index in")
        print("     garvis_conversation.py (MIC_DEVICE / MIC_NAME_HINT).")


if __name__ == "__main__":
    main()
