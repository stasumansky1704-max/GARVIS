# GARVIS Voice Provider Decision (Phase 0)

> Final Phase 0 decision for the voice stack. Machine-readable form:
> `voice_client/voice_providers.json`. **No API keys here** — the key is read only from
> the `ELEVENLABS_API_KEY` environment variable and is never stored, printed, or committed.

## Context
- ElevenLabs works technically; mic capture works; **HyperX safe capture passed** (WDM-KS
  excluded, persistent WASAPI stream, name-based selection).
- **ElevenLabs Hebrew is unusable** — gibberish, including the cloned Hebrew voice.

## Final decision
| Language | STT | TTS provider | Voice ID | Status |
|---|---|---|---|---|
| **English** | local faster-whisper | **ElevenLabs** | `lUTamkMw7gOzZbFIwmq4` | ✅ adopted |
| **Russian** | local faster-whisper | **ElevenLabs** | `rQOBu7YxCDxGiFdTm28w` | ✅ adopted |
| **Hebrew** | local faster-whisper | **NOT ElevenLabs** | — | ⛔ pending dedicated Hebrew TTS provider |

- **STT:** local **faster-whisper** for all three languages (free, private; he/ru/en).
- **TTS EN/RU:** **ElevenLabs** (`eleven_multilingual_v2`), voice IDs above.
- **TTS HE:** route to a **future dedicated Hebrew TTS provider** (see below). Interim:
  pyttsx3 only if a Hebrew SAPI voice is installed; otherwise Hebrew TTS is unavailable.
- **Capture:** safe persistent **WASAPI** (HyperX), **WDM-KS permanently forbidden**.
- **Fallback (EN):** Piper / pyttsx3 for offline/debug.

## Hebrew status (explicit)
ElevenLabs Hebrew output is **currently unacceptable** (gibberish even with a cloned
Hebrew voice), so Hebrew is **not** routed to ElevenLabs. Hebrew TTS is **deferred** to a
dedicated provider. Candidate Hebrew providers to evaluate later (separate task):
- **Azure AI Speech** (he-IL neural voices) — strong Hebrew, cloud.
- **Google Cloud TTS** (he-IL) — cloud.
- **Meta MMS `mms-tts-heb`** — local/offline option (from `MULTILINGUAL_TTS_PLAN.md`).
Until one is chosen, Hebrew replies fall back to pyttsx3 (if a Hebrew SAPI voice exists).

## Configuration (no secrets)
Non-secret routing + voice IDs live in `voice_client/voice_providers.json`.

### Environment variables
```
# API key (REQUIRED, secret) — set in env only, never commit:
ELEVENLABS_API_KEY=...            # PowerShell:  setx ELEVENLABS_API_KEY "..."  (new shell)

# Voice ID overrides (NON-secret; defaults already in voice_providers.json):
GARVIS_ELEVENLABS_EN_VOICE_ID=lUTamkMw7gOzZbFIwmq4
GARVIS_ELEVENLABS_RU_VOICE_ID=rQOBu7YxCDxGiFdTm28w
```
- Voice IDs are **identifiers, not secrets** (usable only with the account's API key), so
  they are safe to store in the repo.
- The **API key is never** hardcoded, stored, printed, or committed.

## Validation
- `voice_providers.json` parses as valid JSON.
- Markdown sanity: this doc + config are docs/config only; **no scripts changed**, so no
  `py_compile` needed. No audio tests run; `garvis_conversation.py` not run.

## Remaining Phase 0 blockers
1. **Hebrew TTS provider not selected** — the one open product gap (separate eval task).
2. **Manual checks** (yours): mic level with speech (`safe_mic_test.py`, want peak > 0.015)
   and ElevenLabs EN/RU audition with the chosen voice IDs.
3. **Client wiring** of `TTS_ENGINE=elevenlabs` with per-language routing + Piper/pyttsx3
   fallback is a future implementation task (not in this docs-only PR).
