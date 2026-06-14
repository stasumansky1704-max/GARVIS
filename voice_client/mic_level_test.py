"""
Microphone level test (rec-based) - verify your input device captures audio.

Run:
    python voice_client/mic_level_test.py

Lists real input devices, shows which device the conversation client selects,
then records ~4s from it while you SPEAK and prints MAX / AVG.
You want MAX > 0.02 while speaking. ASCII-only output (no emoji).
"""
from __future__ import annotations

import numpy as np

try:
    from garvis_conversation import (
        list_input_devices, select_device, measure_peak, rec_chunk, peak_of,
        USABLE_PEAK,
    )
except ImportError:
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from garvis_conversation import (
        list_input_devices, select_device, measure_peak, rec_chunk, peak_of,
        USABLE_PEAK,
    )


def main() -> None:
    print("=" * 60)
    print("  JARVIS microphone level test")
    print("=" * 60)

    print("\nInput devices (quick 0.4s peak each - speak to see levels):")
    for i, name, sr in list_input_devices():
        p = measure_peak(i, sr, seconds=0.4)
        mark = "  <- silent?" if p < 0.005 else ""
        print(f"  [{i}] {name[:40]:<40} {sr:>6}Hz  peak={p:.5f}{mark}")

    idx, rate, name = select_device()
    print(f"\nSelected device: [{idx}] {name} @ {rate} Hz")

    print("\n[mic] Recording 4s - SPEAK NOW...")
    rec = rec_chunk(4.0, idx, rate)
    mx = peak_of(rec)
    avg = float(np.mean(np.abs(rec))) if rec.size else 0.0
    print(f"\n  MAX={mx:.6f}  AVG={avg:.6f}")
    if mx > USABLE_PEAK:
        print("  [OK] PASS - mic is capturing your voice.")
    else:
        print(f"  [LOW] MAX < {USABLE_PEAK}. Check HyperX mute button + Windows input level,")
        print("        or set MIC_DEVICE in garvis_conversation.py.")


if __name__ == "__main__":
    main()
