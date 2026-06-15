"""
Safe mic test (self-contained) - pick a NON-WDM-KS input by NAME and measure level.

Why this exists: earlier auto-selection fell back to the LOUDEST IDLE device when no
device beat the threshold at idle (no speech). HyperX reads ~0 at idle, so the Intel
Microphone Array (slightly noisier at idle) won. This script instead selects by NAME
(default "HyperX"), so the intended mic is used; you then SPEAK to confirm the level.

SAFETY: WDM-KS is excluded; one persistent stream; max 10 seconds; no endless loop;
no backend import; no sd.rec.

Run (PowerShell):
    python voice_client/safe_mic_test.py                 # default name = HyperX
    python voice_client/safe_mic_test.py "HyperX"        # name substring as arg
    $env:MIC_NAME="HyperX"; python voice_client/safe_mic_test.py
    $env:MIC_LIST="1"; python voice_client/safe_mic_test.py     # just list devices, no stream
    $env:MIC_SECONDS="3"; python voice_client/safe_mic_test.py  # shorter run (<=10s)
"""
from __future__ import annotations

import os
import sys
import time

EXCLUDED = ("wdm-ks",)                       # NEVER use WDM-KS (caused BSOD 0x10D)
PREFERENCE = ("windows wasapi", "windows directsound", "mme")
USABLE_PEAK = float(os.getenv("USABLE_PEAK", "0.015"))
MAX_SECONDS = min(10.0, float(os.getenv("MIC_SECONDS", "6")))   # hard cap 10s


def list_inputs():
    import sounddevice as sd
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) <= 0:
            continue
        api = sd.query_hostapis()[d["hostapi"]]["name"]
        if any(x in api.lower() for x in EXCLUDED):          # drop WDM-KS
            continue
        out.append((i, d["name"], int(d.get("default_samplerate", 48000)), api))
    return out


def openable(device, rate) -> bool:
    import sounddevice as sd
    try:
        sd.check_input_settings(device=device, samplerate=rate, channels=1, dtype="float32")
        return True
    except Exception:
        return False


def pick(devs, name):
    """Select by NAME first (backend-ranked), else backend default. Returns (cand, reason)."""
    name = (name or "").lower()
    if name:
        for pref in PREFERENCE:
            for c in devs:
                if pref in c[3].lower() and name in c[1].lower():
                    return c, f"name '{name}' on {c[3]}"
        for c in devs:
            if name in c[1].lower():
                return c, f"name '{name}' (any backend)"
    for pref in PREFERENCE:                                   # no name match -> backend default
        for c in devs:
            if pref in c[3].lower():
                return c, f"backend default ({c[3]}) - name not found"
    return (devs[0] if devs else None), "first available"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import numpy as np
    import sounddevice as sd

    print("=" * 62)
    print("  JARVIS safe mic test (name-based, WDM-KS excluded, <=10s)")
    print("=" * 62)

    devs = list_inputs()
    print("Input devices (WDM-KS excluded):")
    for i, n, sr, api in devs:
        print(f"  [{i}] {n[:42]:<42} {api}  {sr}Hz")
    if os.getenv("MIC_LIST"):
        print("\n(MIC_LIST set: listing only, no stream opened.)")
        return 0

    name = sys.argv[1] if len(sys.argv) > 1 else os.getenv("MIC_NAME", "HyperX")
    sel, reason = pick(devs, name)
    if sel is None:
        print("[ERROR] no safe (non-WDM-KS) input device found")
        return 1
    i, n, sr, api = sel
    if "wdm-ks" in api.lower():                               # belt-and-suspenders
        print("[FAIL] refusing WDM-KS device"); return 2
    rate = sr if openable(i, sr) else next((r for r in (48000, 44100, 16000) if openable(i, r)), None)
    if rate is None:
        print(f"[ERROR] device [{i}] not openable at any safe rate"); return 1

    print(f"\nSelected via {reason}")
    print(f"  [{i}] {n} @ {rate} Hz  ({api})")

    import queue
    q: "queue.Queue[float]" = queue.Queue()

    def cb(indata, frames, time_info, status):
        q.put(float(np.max(np.abs(indata[:, 0]))) if indata.size else 0.0)

    peak = 0.0
    t0 = time.time()
    try:
        with sd.InputStream(samplerate=rate, channels=1, dtype="float32",
                            device=i, blocksize=0, callback=cb):
            print(f"\n  SPEAK now... reading up to {MAX_SECONDS:.0f}s")
            while time.time() - t0 < MAX_SECONDS:
                try:
                    peak = max(peak, q.get(timeout=0.5))
                except queue.Empty:
                    pass
    except Exception as exc:
        print(f"[ERROR] open/read failed: {type(exc).__name__}: {exc}")
        return 1

    print(f"\n[CAPTURE_BACKEND] {api}")
    print(f"[CAPTURE_DEVICE]  [{i}] {n}")
    print(f"[CAPTURE_RATE]    {rate} Hz")
    print(f"[CAPTURE_PEAK]    {peak:.5f} (need > {USABLE_PEAK})")
    print(f"[HOSTAPI]         {api} -> WDM-KS={'YES' if 'wdm-ks' in api.lower() else 'no (safe)'}")
    print("  RESULT:", "PASS - usable level" if peak > USABLE_PEAK
          else "LOW - speak louder, raise Windows input level, or unmute the HyperX")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
