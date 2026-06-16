# Voice Closeout — fastest working path

> Stop fighting local capture/TTS plumbing. This is the recommended path to a reliable
> Hebrew/English/Russian voice, plus exact safe steps. See
> `PREMIUM_VOICE_STACK_AUDIT.md` for the full analysis. **WDM-KS is forbidden** (BSOD
> 0x10D); do not run the old `garvis_conversation.py` until safe capture is proven.

## Recommended fastest working voice path
1. **STT — local faster-whisper** (already works on this machine; he/ru/en; free, private).
2. **TTS — ElevenLabs** (paid, cloud) for product-grade Hebrew/Russian/English with
   streaming. Keep **Piper (EN) / pyttsx3** as offline/debug fallback.
3. **Capture — safe WASAPI persistent stream only** (never WDM-KS). If the HyperX reads
   too low on safe backends even with speech + gain, select the Intel mic array or accept
   cloud STT — do not chase local capture forever.

## ElevenLabs POC — ready to run
`poc_elevenlabs_tts.py` is present and graceful (exits cleanly if no key). It generates a
short he/en/ru JARVIS phrase, saves audio to `voice_client/poc_out/` (gitignored), and
reports TTFB/total latency + a rough cost estimate.

### Set the key (env only — never hardcode, never commit)
PowerShell (current shell only):
```
$env:ELEVENLABS_API_KEY = "your-key-here"
```
PowerShell (persist for your user):
```
setx ELEVENLABS_API_KEY "your-key-here"     # opens a NEW shell to take effect
```
Then:
```
python voice_client/poc_elevenlabs_tts.py
```
- The key is read **only** from `ELEVENLABS_API_KEY` and is **never printed**.
- Generated audio in `poc_out/` is **gitignored** — do **not** commit it.
- Optional: `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL` (default `eleven_multilingual_v2`).

## STT POCs (safe, ≤10s, no WDM-KS)
- `poc_realtimestt.py` — needs `pip install RealtimeSTT` (pulls torch ~2.5 GB); exits
  cleanly if absent. Pins a non-WDM-KS device.
- `poc_vosk.py` — needs a Vosk model (no Hebrew model exists); exits cleanly if absent.
- For he/ru/en, **faster-whisper remains the recommended local STT** (no extra install).

## Decision
- **Pay for ElevenLabs now** — fastest path to reliable trilingual voice; sidesteps the
  Python 3.14 local-wheel problems (e.g. `piper-phonemize`).
- **Keep STT local** (faster-whisper). Revisit local TTS (XTTS/MMS) only after the product
  voice works, to cut cloud cost later.

## Next implementation step (separate, future)
Add `TTS_ENGINE=elevenlabs` to the client with automatic Piper/pyttsx3 fallback
(NEXT_30 T3) — after you audition the ElevenLabs samples.
