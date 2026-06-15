"""
POC: ElevenLabs cloud TTS for English / Hebrew / Russian.

SAFETY / SECRETS:
  - API key is read ONLY from the environment variable ELEVENLABS_API_KEY.
  - The key is NEVER printed and MUST NEVER be committed.
  - If the key is not set, this prints instructions and exits cleanly.
  - No microphone, no backend calls, no WDM-KS. (This is a TTS-only test.)

Saves audio to voice_client/poc_out/ (gitignored) and reports latency + a rough
cost estimate. Uses the streaming endpoint to measure time-to-first-byte (TTFB).

Run (PowerShell):
    $env:ELEVENLABS_API_KEY = "..."   # do not hardcode, do not commit
    python voice_client/poc_elevenlabs_tts.py
"""
from __future__ import annotations

import os
import sys
import time

import requests

# Multilingual model (covers Hebrew + Russian + English). For lower latency, try
# eleven_turbo_v2_5 or eleven_flash_v2_5. Voice can be overridden via env.
MODEL_ID = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # public "Rachel"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poc_out")

SAMPLES = [
    ("en", "Hello Stas, I am JARVIS, your local assistant. Everything is running smoothly."),
    ("he", "שלום סטס, אני ג'רוויס, העוזר המקומי שלך. הכל פועל כשורה."),
    ("ru", "Здравствуйте, Стас. Я ваш локальный помощник. Всё работает нормально."),
]

# Rough public pricing anchor (verify before relying on it): Creator plan ~$22 for
# ~100k chars => ~$0.00022/char. Lower at scale, higher on tiny plans.
USD_PER_CHAR = 0.00022


def synth(api_key: str, lang: str, text: str) -> dict:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    body = {"text": text, "model_id": MODEL_ID,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"elevenlabs_{lang}.mp3")
    t0 = time.perf_counter()
    ttfb = None
    nbytes = 0
    try:
        with requests.post(url, headers=headers, json=body, stream=True, timeout=60) as r:
            if r.status_code != 200:
                return {"ok": False, "status": r.status_code,
                        "msg": r.text[:160]}
            with open(out, "wb") as f:
                for chunk in r.iter_content(chunk_size=4096):
                    if not chunk:
                        continue
                    if ttfb is None:
                        ttfb = time.perf_counter() - t0
                    f.write(chunk); nbytes += len(chunk)
        total = time.perf_counter() - t0
        return {"ok": True, "file": out, "ttfb": ttfb or total, "total": total,
                "bytes": nbytes, "chars": len(text)}
    except Exception as exc:
        return {"ok": False, "status": 0, "msg": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=" * 60)
    print("  POC: ElevenLabs TTS (EN / HE / RU)")
    print("=" * 60)

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("ELEVENLABS_API_KEY is not set. Set it (do NOT hardcode/commit):")
        print('    PowerShell:  $env:ELEVENLABS_API_KEY = "your-key"')
        print("Then re-run. Exiting cleanly. (Key is read from env only and never printed.)")
        return 0

    print(f"  model: {MODEL_ID}   voice: {VOICE_ID}   out: {OUT_DIR}")
    total_chars = 0
    for lang, text in SAMPLES:
        res = synth(api_key, lang, text)
        if res["ok"]:
            total_chars += res["chars"]
            print(f"  [{lang}] OK  ttfb={res['ttfb']:.2f}s total={res['total']:.2f}s "
                  f"{res['bytes']} bytes -> {os.path.basename(res['file'])}")
        else:
            print(f"  [{lang}] FAIL status={res['status']} {res['msg']!r}")

    if total_chars:
        print(f"\n  chars synthesized: {total_chars}  "
              f"~est cost: ${total_chars * USD_PER_CHAR:.4f} (verify pricing)")
    print("  [OK] done. Listen to the files in poc_out/ to judge quality.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
