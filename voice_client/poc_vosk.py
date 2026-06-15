"""
POC: Vosk offline STT on a SAFE, non-WDM-KS persistent stream.

SAFETY: max ~10 seconds, single bounded loop, no backend calls, no TTS, never WDM-KS.

Vosk needs a language model. Set VOSK_MODEL to a model directory, or drop one under
voice_client/vosk-model/. Models: https://alphacephei.com/vosk/models
  - English (small): vosk-model-small-en-us-0.15
  - Russian (small): vosk-model-small-ru-0.22
  - Hebrew: NOT available from Vosk (key limitation).
If no model is found this script prints instructions and exits cleanly.

Run:
    python voice_client/poc_vosk.py
Speak during the 10-second window.
"""
from __future__ import annotations

import os
import sys
import json
import time


def pick_safe_input():
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


def find_model():
    env = os.getenv("VOSK_MODEL")
    if env and os.path.isdir(env):
        return env
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vosk-model")
    return local if os.path.isdir(local) else None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=" * 60)
    print("  POC: Vosk offline STT (safe capture, <=10s)")
    print("=" * 60)

    import importlib.util
    if importlib.util.find_spec("vosk") is None:
        print("vosk not installed. Install: pip install vosk")
        return 0

    model_dir = find_model()
    if model_dir is None:
        print("No Vosk model found. Download one and set VOSK_MODEL or unzip into")
        print("  voice_client/vosk-model/ , e.g. vosk-model-small-en-us-0.15")
        print("  (Russian: vosk-model-small-ru-0.22 ; Hebrew: NOT available from Vosk)")
        print("Exiting cleanly (no audio opened).")
        return 0

    idx, name, rate, api = pick_safe_input()
    if idx is None:
        print("[ERROR] no safe (non-WDM-KS) input device found")
        return 1
    print(f"[CAPTURE_DEVICE] [{idx}] {name}")
    print(f"[CAPTURE_BACKEND] {api}")
    assert "wdm-ks" not in (api or "").lower(), "refusing WDM-KS"

    import numpy as np
    import sounddevice as sd
    from vosk import Model, KaldiRecognizer

    sr = 16000                                          # Vosk wants 16k mono
    print(f"[CAPTURE_RATE] {sr} Hz (resampled by stream)")
    model = Model(model_dir)
    rec = KaldiRecognizer(model, sr)

    print("\n  SPEAK now. Listening up to 10s...")
    t0 = time.time()
    finals = []
    # ONE persistent InputStream (callback), bounded by a 10s deadline. No sd.rec.
    import queue
    q = queue.Queue()

    def cb(indata, frames, time_info, status):
        q.put(bytes((indata[:, 0] * 32767).astype(np.int16)))

    with sd.InputStream(samplerate=sr, channels=1, dtype="float32",
                        device=idx, blocksize=0, callback=cb):
        while time.time() - t0 < 10.0:                  # hard 10s cap
            try:
                chunk = q.get(timeout=0.5)
            except queue.Empty:
                continue
            if rec.AcceptWaveform(chunk):
                txt = json.loads(rec.Result()).get("text", "")
                if txt:
                    finals.append(txt)
    tail = json.loads(rec.FinalResult()).get("text", "")
    if tail:
        finals.append(tail)

    dt = time.time() - t0
    print(f"\n  transcription: {' '.join(finals)!r}")
    print(f"  elapsed: {dt:.1f}s  model: {os.path.basename(model_dir)}")
    print("  [OK] bounded run complete, stream closed. Exiting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
