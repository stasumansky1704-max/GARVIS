"""
POC: RealtimeSTT (faster-whisper under the hood) on a SAFE, non-WDM-KS device.

SAFETY: max ~10 seconds, no endless loop, no backend calls, no TTS, never WDM-KS.

RealtimeSTT pulls torch+torchaudio (~2.5 GB). If it is not installed this script
prints an install note and exits cleanly (no error, no audio opened).

Run:
    python voice_client/poc_realtimestt.py
Speak during the 10-second window.
"""
from __future__ import annotations

import sys
import time
import threading


def pick_safe_input():
    """Return (index, name, rate, hostapi) for a non-WDM-KS input. Prefers
    HyperX on WASAPI -> DirectSound -> MME. Never returns a WDM-KS device."""
    import sounddevice as sd
    EXCL = ("wdm-ks",)
    PREF = ("wasapi", "directsound", "mme")
    devs = []
    for i, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) <= 0:
            continue
        api = sd.query_hostapis()[d["hostapi"]]["name"]
        if any(x in api.lower() for x in EXCL):
            continue                                   # NEVER WDM-KS
        devs.append((i, d["name"], int(d.get("default_samplerate", 48000)), api))
    for pref in PREF:
        for c in devs:
            if pref in c[3].lower() and "hyperx" in c[1].lower():
                return c
        for c in devs:
            if pref in c[3].lower():
                return c
    return devs[0] if devs else (None, None, None, None)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=" * 60)
    print("  POC: RealtimeSTT (safe capture, <=10s)")
    print("=" * 60)

    import importlib.util
    if importlib.util.find_spec("RealtimeSTT") is None:
        print("RealtimeSTT is NOT installed.")
        print("Install (pulls torch+torchaudio, ~2.5 GB):")
        print("    pip install RealtimeSTT")
        print("Then re-run. Exiting cleanly (no audio opened).")
        return 0

    idx, name, rate, api = pick_safe_input()
    if idx is None:
        print("[ERROR] no safe (non-WDM-KS) input device found")
        return 1
    print(f"[CAPTURE_DEVICE] [{idx}] {name}")
    print(f"[CAPTURE_BACKEND] {api}")
    print(f"[CAPTURE_RATE] {rate} Hz")
    assert "wdm-ks" not in (api or "").lower(), "refusing WDM-KS"

    from RealtimeSTT import AudioToTextRecorder
    # language="" => Whisper auto-detect (he/en/ru). base model = known-good.
    recorder = AudioToTextRecorder(
        model="base", language="", input_device_index=idx,
        spinner=False, use_microphone=True, enable_realtime_transcription=False,
    )

    result = {"text": None, "t0": time.time()}

    def grab():
        try:
            result["text"] = recorder.text()
        except Exception as exc:
            result["text"] = f"<error: {type(exc).__name__}: {exc}>"

    print("\n  SPEAK now (English / Hebrew / Russian). Listening up to 10s...")
    th = threading.Thread(target=grab, daemon=True)
    th.start()
    th.join(timeout=10.0)                              # hard 10s cap, no endless loop
    dt = time.time() - result["t0"]

    try:
        recorder.shutdown()
    except Exception:
        pass

    print(f"\n  transcription: {result['text']!r}")
    print(f"  elapsed: {dt:.1f}s")
    print("  [OK] bounded run complete, recorder shut down. Exiting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
