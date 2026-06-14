# JARVIS Multilingual TTS Improvement Plan (Hebrew + Russian + English)

Goal: pick the best **long-term, local, free** neural voice stack covering **Hebrew,
Russian, and English** with natural, calm output. This is a research/decision document
only — it does **not** replace the current working system (Piper EN + pyttsx3 fallback).

## Why this is needed
- **English:** Piper `en_US-lessac-medium` works well (10/10 reliable, natural, calm).
- **Russian:** Piper has a Russian voice, but on this machine (Python 3.14) the bundled
  espeak phonemizer fails (0/10) and there is no `piper-phonemize` wheel for 3.14.
- **Hebrew:** Piper has **no** Hebrew voice at all; pyttsx3/SAPI has no Hebrew voice
  installed. Hebrew currently has no good local neural option in the stack.

So the long-term gap is really **Hebrew** (hardest) and a **reliable Russian** path.

## Candidate audit

| Engine | EN | RU | **HE** | Naturalness | Local/Offline | License | GPU need |
|---|---|---|---|---|---|---|---|
| **Piper** (current) | ✅ excellent | ⚠️ flaky here | ❌ none | good | yes | MIT-ish (permissive) | none (ONNX, CPU) |
| **XTTS-v2** (Coqui) | ✅ excellent | ✅ native | ❌ none | **excellent** + voice clone | yes | CPML (non-commercial) | yes (mid) |
| **OpenVoice v2** | ✅ | ❌ not base | ❌ | very good (tone clone) | yes | MIT | yes |
| **MeloTTS** | ✅ fast | ❌ | ❌ | good | yes | MIT | CPU-realtime |
| **F5-TTS** | ✅ | ⚠️ community finetunes | ❌ rare | **top-tier** zero-shot | yes | weights often CC-BY-NC | yes (heavier) |
| **Meta MMS-TTS** | ✅ (eng) | ✅ (rus) | ✅ **(heb)** | modest (VITS, flat) | yes | CC-BY-NC-4.0 | yes (light) |

### Notes per engine
- **XTTS-v2** — 17 languages incl. **Russian**; superb naturalness and 6-second voice
  cloning. **No Hebrew.** License is non-commercial (fine for a personal assistant).
- **OpenVoice v2 / MeloTTS** — strong for EN/ES/FR/ZH/JA/KO; **no Hebrew, no Russian**
  in base. Great cloning/tone but wrong language coverage for us. Rule out for HE/RU.
- **F5-TTS** — best-in-class zero-shot naturalness, base is EN+ZH. Russian via community
  finetunes; **Hebrew effectively unavailable.** Heaviest to run. Keep as an EN/RU
  "premium voice" option, not a Hebrew solution.
- **Meta MMS-TTS** — the **only** candidate with native **Hebrew** (`mms-tts-heb`),
  plus `mms-tts-rus` and `mms-tts-eng`. Per-language VITS checkpoints via HF
  `transformers` (`VitsModel`/`VitsTokenizer`). Quality is intelligible but flatter than
  XTTS/F5. This is the realistic local Hebrew option.

## Recommendation

**Best long-term stack = hybrid, by language, behind the existing `TTS_ENGINE` switch:**

1. **English** → keep **Piper** (great, lightweight) — or upgrade to XTTS-v2 for a single
   consistent cloned voice across languages.
2. **Russian** → **XTTS-v2** (native, very natural) — or Piper RU once a working
   phonemizer is available. Fallback: MMS-rus.
3. **Hebrew** → **Meta MMS-TTS `mms-tts-heb`** (the only viable local Hebrew neural
   voice). This is the key unlock.

**If a single engine is preferred** for simplicity: **Meta MMS-TTS** covers all three
(eng/rus/heb) in one framework — accept flatter prosody as the trade-off.

For one **consistent natural voice identity** across EN+RU (cloned), **XTTS-v2** is the
strongest, with **MMS** bolted on solely for Hebrew.

## Licensing reality
- Piper: permissive (safe for any future use).
- XTTS-v2 (CPML) and MMS (CC-BY-NC) are **non-commercial** — fine for Stas's personal
  local assistant; revisit if JARVIS ever ships commercially.

## Runtime / architecture
- XTTS-v2, F5, MMS are PyTorch + GPU. The RTX 5090 handles them easily (sub-second).
- Cleanest integration: a **small local TTS micro-service** (FastAPI) on the GPU/WSL
  side exposing `POST /tts {text, lang} -> wav`, so the Windows voice client stays light
  and just plays the returned audio. The client already has a `TTS_ENGINE` plug point;
  add `xtts` / `mms` engines that call this service, keeping Piper/pyttsx3 as fallback.

## Proposed phased rollout (separate future PRs)
1. **Phase 1 — Hebrew unlock:** stand up MMS-TTS service with `mms-tts-heb`; route
   Hebrew there (replaces pyttsx3 Hebrew). Lowest risk, biggest gap closed.
2. **Phase 2 — Natural Russian:** add XTTS-v2 for Russian (and optionally English) with
   one chosen calm voice; keep Piper EN as fallback.
3. **Phase 3 — Unified voice (optional):** move English to the same XTTS voice so EN+RU
   share one identity; MMS remains Hebrew-only.
4. Each phase keeps the current Piper/pyttsx3 path as automatic fallback.

## Out of scope for now
No engine is installed by this plan. Current shipped behavior is unchanged:
English/Russian → Piper (Russian pending phonemizer), Hebrew → pyttsx3, with fallback.
