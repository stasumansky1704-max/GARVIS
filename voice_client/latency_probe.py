"""
GARVIS Voice — Latency Probe (Phase 5)

Measures the stages that do NOT need a microphone, so latency can be tracked
in CI / headless environments. The mic + STT + TTS stages are measured live
by garvis_conversation.py (printed per turn).

Usage:
    python voice_client/latency_probe.py
"""
from __future__ import annotations

import time
import statistics
import requests

API_URL = "http://localhost:8000/api/v1/runtime/command"
HEALTH = "http://localhost:8000/api/v1/status/health"
PROMPTS = [
    "Say hello in three words.",
    "What is two plus two?",
    "Give me a one sentence status.",
]


def main() -> None:
    print("=== GARVIS runtime latency probe ===")
    try:
        h = requests.get(HEALTH, timeout=8)
        print(f"backend health: {h.status_code} {h.json().get('status')}")
    except Exception as exc:
        print(f"backend unreachable: {exc}")
        return

    samples = []
    for p in PROMPTS:
        t0 = time.perf_counter()
        try:
            r = requests.post(
                API_URL,
                json={"text": p, "source": "voice", "session_id": "latency-probe", "metadata": {}},
                timeout=90,
            )
            dt = time.perf_counter() - t0
            ok = r.status_code == 200
            reply = r.json().get("response_text", "") if ok else r.text[:60]
            samples.append(dt)
            print(f"  [{r.status_code}] {dt:5.2f}s  «{p}» -> {reply[:50]!r}")
        except Exception as exc:
            print(f"  [ERR] {p}: {exc}")

    if samples:
        print(f"\nruntime+ollama: min {min(samples):.2f}s · "
              f"median {statistics.median(samples):.2f}s · max {max(samples):.2f}s")
        print("note: STT (~0.3–1.0s base model) and TTS (pyttsx3, near-instant) "
              "measured live per-turn in garvis_conversation.py")


if __name__ == "__main__":
    main()
