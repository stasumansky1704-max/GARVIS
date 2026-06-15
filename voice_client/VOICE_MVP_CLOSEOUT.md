# Voice MVP Closeout (Phase 0)

> Goal: lock the smallest reliable Speak → Understand → Respond path and stop fighting
> fragile local plumbing. **WDM-KS is permanently forbidden** (caused BugCheck 0x10D).

## Final recommended Phase 0 stack
- **TTS: ElevenLabs** (cloud, paid) — product-grade Hebrew/English/Russian, streaming.
- **TTS fallback: Piper (EN) / pyttsx3** — offline/debug only.
- **STT: local faster-whisper** *only if HyperX capture proves stable* (peak > 0.015 while
  speaking on a safe backend). **Otherwise use cloud STT** — do not keep fighting local capture.
- **Capture: safe persistent WASAPI** stream on the **HyperX** (selected by name). Never WDM-KS.

## ElevenLabs status
- `poc_elevenlabs_tts.py` is present and ready (key read from `ELEVENLABS_API_KEY` only,
  never printed; audio saved to gitignored `poc_out/`).
- **Key not yet visible** to running processes. `setx` only affects **new** shells.

Set it, then open a NEW terminal:
```powershell
setx ELEVENLABS_API_KEY "PASTE_KEY_HERE"
# close and reopen PowerShell, then:
python voice_client/poc_elevenlabs_tts.py
```
Do **not** hardcode or commit the key; do **not** commit generated audio.

## Safe mic capture status
- ✅ Safe capture runs **without crash**, **WDM-KS excluded**, bounded ≤10s.
- ✅ **Device selection fixed**: `safe_mic_test.py` now selects by **name (HyperX)**, not the
  loudest-idle device.
- ⚠️ **Level unverified with speech**: headless idle peak on HyperX/WASAPI ≈ 0.0008
  (< 0.015). Whether speaking clears the threshold must be confirmed manually.

## HyperX vs Intel Microphone Array finding
- **Symptom:** earlier `safe_mic_test` selected *Intel Microphone Array* with
  `CAPTURE_PEAK ≈ 0.00024`, not the HyperX.
- **Root cause:** the old auto-selection, when **no** device beat the threshold **at idle**
  (no speech), fell back to the **loudest idle** device. HyperX reads ~0.000 at idle; the
  Intel array idles slightly noisier (~0.0015), so it "won" — a wrong-device pick, not an
  STT problem.
- **Fix:** select **by name (default "HyperX")** regardless of idle level; the user speaks
  to confirm. Verified: it now selects `[12] HyperX QuadCast` on WASAPI.

## Exact safe commands to test HyperX (PowerShell)
```powershell
# list safe input devices (no stream opened)
$env:MIC_LIST="1"; python voice_client/safe_mic_test.py; Remove-Item Env:MIC_LIST

# 6-second HyperX capture test — SPEAK during it; want CAPTURE_PEAK > 0.015
python voice_client/safe_mic_test.py

# force a specific mic by name substring
python voice_client/safe_mic_test.py "HyperX"

# shorter run
$env:MIC_SECONDS="3"; python voice_client/safe_mic_test.py; Remove-Item Env:MIC_SECONDS
```
All runs are ≤10s, WDM-KS excluded, no endless loop.

## What passed
- `python -m py_compile voice_client/safe_mic_test.py` → OK.
- Device listing + **name-based selection picks HyperX** (WASAPI), WDM-KS excluded, no crash.
- ElevenLabs POC present and key-safe (env-only, never printed).

## What remains manual (yours)
1. **HyperX speech level test:** run `python voice_client/safe_mic_test.py`, SPEAK, check
   `CAPTURE_PEAK > 0.015`.
2. **ElevenLabs audition:** `setx` the key, new shell, run `poc_elevenlabs_tts.py`, judge
   he/en/ru quality + latency.

## Permanently forbidden
- **WDM-KS** capture (BSOD 0x10D).
- Running the old `garvis_conversation.py` until safe capture is proven with speech.
- Printing or committing API keys; committing generated audio.

## Phase 0 decision
**Done enough to proceed — conditionally.** Safe, crash-free capture and correct device
selection are in place; the TTS direction (ElevenLabs) is chosen. Proceed to wiring
ElevenLabs TTS now. STT routing depends on ONE manual check:
- **If** the HyperX speech test reads **> 0.015** → use **local faster-whisper STT**.
- **If not** → switch to **cloud STT** and proceed. 

## STOP condition (do not over-invest)
**Do not keep fighting local capture.** If the manual HyperX speech test still reads
< 0.015 after checking mute/Windows input level, **stop tuning local capture and adopt
cloud STT.** Phase 0 success is a reliable conversation, not a perfect local mic.
