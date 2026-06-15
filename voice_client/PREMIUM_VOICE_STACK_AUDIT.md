# Premium Voice Stack Audit + POC for JARVIS

> Audit + safe POC only. No production voice client replaced, no WDM-KS, no backend/
> GPU/Docker/dashboard changes, no committed keys. POC scripts:
> `poc_realtimestt.py`, `poc_vosk.py`, `poc_elevenlabs_tts.py`.

## TL;DR
- **STT:** keep **local Whisper (faster-whisper)** — it already works on this machine and
  is the only strong **Hebrew+Russian+English** local option. Vosk has **no Hebrew**;
  Parakeet is English-centric (future RTX option).
- **TTS:** **pay for ElevenLabs now.** It is the fastest path to reliable, product-grade
  **HE/RU/EN** voice with streaming. Keep **Piper(EN)/pyttsx3** as offline fallback.
- This combo (local STT + cloud TTS) stops the local-plumbing time sink and is
  product-ready.

## Environment reality (a finding in itself)
- **Python 3.14.5** — bleeding edge. It is hostile to parts of the local voice
  ecosystem (e.g. `piper-phonemize` has no 3.14 wheel, which broke local Russian Piper).
- Wheels that DO exist on 3.14 (verified via pip dry-run): `soundfile`, `elevenlabs`,
  `vosk`, `webrtcvad`, and `RealtimeSTT` — **but RealtimeSTT pulls `torch`+`torchaudio`
  (~2.5 GB)**.
- `faster-whisper` already works on 3.14. **Cloud TTS sidesteps the 3.14 wheel problem
  entirely** — another reason it accelerates.

## STT evaluation
| Option | HE | RU | EN | Local | Notes |
|---|---|---|---|---|---|
| **faster-whisper** (current) | ✅ | ✅ | ✅ | yes | Already working; best multilingual local STT; free; private. |
| **RealtimeSTT** | ✅ (Whisper) | ✅ | ✅ | yes | Wraps faster-whisper + VAD + optional wake word; Windows-first; MIT. **Cost: torch ~2.5 GB.** Robust capture, but our safe WASAPI capture already exists. |
| **Vosk** | ❌ **no model** | ✅ | ✅ | yes | Tiny/offline/fast, Apache-2.0, but **no Hebrew** -> disqualified for our trilingual goal. |
| **NVIDIA Parakeet** (future) | ✖ | ✖ | ✅✅ | yes (GPU) | Excellent EN accuracy/speed on RTX 5090 via NeMo; English-centric. Note for future EN-only speed. |

**STT conclusion:** stay on **Whisper**. RealtimeSTT is an optional robustness wrapper
(only if we want its VAD/wake bundle and accept torch). Vosk is out (no Hebrew).

## TTS evaluation
| Option | HE | RU | EN | Local/Cloud | Quality | Notes |
|---|---|---|---|---|---|---|
| **ElevenLabs** | ✅ | ✅ | ✅ | cloud (paid) | **best, product-grade** | `eleven_multilingual_v2` covers HE/RU/EN; streaming (WS + chunked) with low TTFB (turbo/flash ~75-300 ms). Key via env only. |
| **Piper** | ❌ | ⚠️ (3.14 phonemizer broken) | ✅ | local/free | good (EN) | Keep as **offline EN fallback**. |
| **pyttsx3 / SAPI** | ⚠️ (needs RU/HE SAPI voice) | ⚠️ | ✅ | local/free | robotic | Last-resort fallback. |
| **XTTS / MMS** (future) | ✅ (MMS heb) | ✅ (XTTS) | ✅ | local | high | Future local multilingual to cut cloud COGS (see MULTILINGUAL_TTS_PLAN.md). |

**TTS conclusion:** **ElevenLabs now** for quality + Hebrew; Piper/pyttsx3 stay as
offline fallback; XTTS+MMS later for cost control.

## POC results (what was actually executed)
Run safely on Py3.14 (headless, so no live speech and no API key were available - those
require you to run them):
- **Scripts:** all three compile; all **graceful-degrade** (no crash) when a dep/model/
  key is missing; **never print the key**.
- **Safe capture picker:** selects **`[12] HyperX QuadCast` on WASAPI**, `WDM-KS=False`.
  Confirms the POCs honor "no WDM-KS."
- **RealtimeSTT POC:** not installed (avoided the ~2.5 GB torch pull); script prints the
  install note and exits cleanly. Ready to run after `pip install RealtimeSTT`.
- **Vosk POC:** `vosk` installed; **no model present** -> prints model-download guidance
  and exits. Confirms Vosk has **no Hebrew model**.
- **ElevenLabs POC:** SDK installed; `ELEVENLABS_API_KEY` **not set** -> prints
  env-setup guidance and exits. Ready to run once the key is set.

**Not measurable headless (you must run):** live transcription accuracy (needs speech);
ElevenLabs voice quality/latency/cost (needs the key + speech). The scripts measure and
print TTFB, total latency, bytes, char count, and a rough cost estimate when run.

## Answers to the questions
- **Fastest path to reliable HE/RU/EN voice:** local Whisper STT + **ElevenLabs TTS**.
- **Best product quality:** ElevenLabs TTS + Whisper STT.
- **Easiest to integrate now:** ElevenLabs (HTTP/SDK behind the existing `TTS_ENGINE`
  switch) + the safe WASAPI capture we already have.
- **What costs money but saves major time:** **ElevenLabs** - eliminates weeks of
  fighting local Hebrew/Russian TTS (and the Py3.14 wheel mess).
- **Keep local:** STT (Whisper), capture, TTS fallback (Piper/pyttsx3) - free, private,
  offline-capable.
- **Cloud/API:** TTS (ElevenLabs) for quality, especially Hebrew.

## Cost / benefit
- **ElevenLabs:** ~$22/mo Creator (~100k chars) to ~$99/mo Pro (~500k chars);
  ~$0.0002-0.0003/char. A spoken reply ~100-200 chars = **fractions of a cent**. MVP/demo
  cost is negligible; at high volume, migrate hot paths to local XTTS/MMS. *(Verify live
  pricing before committing.)*
- **Whisper STT local:** $0, already working, private. No reason to pay for STT now.
- **RealtimeSTT torch (~2.5 GB):** robustness, but not required since safe capture +
  faster-whisper already work. Optional.

## Recommendations
1. **Recommended near-term stack:** safe WASAPI capture (done) -> **faster-whisper** STT
   (local) -> **ElevenLabs** TTS (paid) with Piper/pyttsx3 fallback.
2. **Recommended long-term stack:** same STT (optionally **Parakeet** for EN speed on the
   5090) -> **hybrid TTS**: ElevenLabs premium + local **XTTS(RU/EN)+MMS(HE)** for
   offline/COGS control.
3. **Pay for now:** ElevenLabs (single highest-leverage spend).
4. **Keep local:** STT, capture, TTS fallback.
5. **Avoid:** WDM-KS (BSOD); Vosk for Hebrew (no model); building local Hebrew TTS first;
   RealtimeSTT's torch weight unless its bundle is needed.

## Integration plan (no rewrite; future PRs)
1. **You:** set `ELEVENLABS_API_KEY` (env/secret), run `poc_elevenlabs_tts.py`, listen to
   `poc_out/elevenlabs_{en,he,ru}.mp3`, confirm quality/latency.
2. Add **ElevenLabs as a `TTS_ENGINE` option** (`elevenlabs|piper|pyttsx3`) in the client,
   streaming, with automatic Piper/pyttsx3 fallback on error/offline.
3. Keep **faster-whisper** on the safe WASAPI capture; trial RealtimeSTT only if its
   VAD/wake bundle is wanted.
4. Later: local **XTTS+MMS** to reduce cloud spend for offline/high-volume use.

## Safety honored
STT POCs are bounded to <=10s with no endless loop; no backend calls; no TTS in STT
tests; no WDM-KS; ElevenLabs key strictly from `ELEVENLABS_API_KEY`, never printed or
committed. `poc_out/` and `vosk-model/` are gitignored.
