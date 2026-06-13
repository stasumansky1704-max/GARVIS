# GARVIS Voice — Continuous Conversation Mode (Sprint 1.0)

Natural, hands-free-ish conversation on top of the **existing** working voice stack.
Nothing was rebuilt — this reuses faster-whisper (STT), sounddevice (mic),
pyttsx3 (TTS) and the verified `POST /api/v1/runtime/command` endpoint.

## What changed vs the old `garvis_voice_client.py`
| Old (push-to-talk demo) | New (`garvis_conversation.py`) |
|---|---|
| Fixed 5-second recording | **VAD** — records while you speak, stops on ~1s silence |
| One shot, then exits | **Continuous loop** — listening resumes automatically after each answer |
| Whisper reloaded each run | Model loaded **once**, reused every turn |
| No session continuity | Stable `session_id` + last-turn context |
| Crashes on errors | **Graceful recovery** for mic/STT/runtime/timeout/TTS failures |
| No status feedback | **Voice states**: IDLE / LISTENING / THINKING / SPEAKING |

## Requirements (already installed on the Windows host)
`faster-whisper`, `sounddevice`, `pyttsx3`, `numpy`, `requests` — no new deps.
GARVIS backend must be healthy on `http://localhost:8000`.

## Run (on the Windows machine — it has the mic)
```bash
python voice_client/garvis_conversation.py
```
Speak naturally. Pause to send. GARVIS answers, then listens again.
Say **"goodbye"** (or Ctrl+C) to exit.

## Tuning (top of garvis_conversation.py)
- `SILENCE_TIMEOUT_S` — how long a pause ends your turn (default 1.0s)
- `MIN_SPEECH_S` — ignore blips shorter than this (0.4s)
- `START_ENERGY_MULT` — speech sensitivity vs ambient noise (3.0)
- `WHISPER_MODEL` — `tiny`/`base`/`small` (accuracy vs speed)

## Latency probe (headless — no mic needed)
```bash
python voice_client/latency_probe.py
```
Measures backend runtime+Ollama latency. STT/TTS are printed live per-turn by the
conversation client.

## Notes
- VAD is energy-based (pure numpy) — zero new dependencies, works offline.
- Dominant latency is Ollama generation (~several seconds), not the voice layer.
