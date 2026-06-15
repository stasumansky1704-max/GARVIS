# Windows Audio Capture Remediation — Replace WDM-KS with a Safe Persistent Backend

> **Status:** design only. No code, no behavior change. Captured here for the record
> following the BugCheck `0x0000010D` (WDF_VIOLATION) investigation.

## Background — why this is needed
The Windows voice client (`garvis_conversation.py`) captured audio from the HyperX
QuadCast via **device 21 = WDM-KS**, using **`sd.rec()` blocking chunks** (a fresh
stream opened/closed every ~100 ms inside the VAD loop).

This produced **three identical kernel crashes in two days**, all
`BugCheck 0x0000010D` (WDF_VIOLATION), same signature (Param1 `0x5`, Param3 `0x1200`):

| When | Bugcheck | Dump |
|---|---|---|
| Jun 14 12:13 | 0x10D | 061426-14593 |
| Jun 14 22:19 | 0x10D | 061426-14343 |
| Jun 15 14:25 | 0x10D | 061526-14765 |

`0x10D` = the Kernel-Mode Driver Framework caught a **kernel driver violating a
framework rule** (a driver bug, not application code). Driver Verifier was **off**, so
this is a genuine fault under normal use. The HyperX runs on the Microsoft **USB Audio
2.0** class driver (`usbaudio2.sys`), with **Intel SST USB Audio** also in the stack.

**Root cause (trigger):** WDM-KS is the kernel-streaming path, and our per-chunk
open/close hammered the USB-audio KMDF driver with rapid stream churn — a classic way
to drive a USB-audio driver into a power/PnP/IO-target rule violation. User-mode Python
cannot directly BSOD; it *triggered* a latent driver bug.

## Objective
Remove **both** trigger behaviors:
1. **WDM-KS** → use an audio-engine-routed host API (WASAPI / DirectSound / MME).
2. **Per-chunk open/close** → use **one persistent stream** opened once at startup.

Everything downstream is preserved: **Whisper STT, JARVIS identity/prompt, runtime
stack, Piper TTS, VAD logic, Hebrew/Russian fallbacks**. Only the *audio source* changes.

## Architecture — persistent stream + ring buffer

```
[ Persistent sd.InputStream (callback) ]   <- opened ONCE at startup, never per-chunk
            |  (audio-engine routed: WASAPI / DirectSound / MME, NOT WDM-KS)
            v
   callback enqueues frames  ->  [ thread-safe bounded ring buffer ]
                                              |
                                              v
        listen_utterance() consumes ~CHUNK_MS windows from the buffer
                                              |  (same hysteresis VAD + voiced-time)
                                              v
   resample_to_stt -> transcribe (Whisper) -> ask_jarvis (runtime) -> speak (Piper/pyttsx3)
```

- **Capture thread:** the InputStream callback does *only* enqueue frames (fast, no heavy
  work). Bounded buffer drops oldest frames on overflow to cap memory.
- **Consumer:** `listen_utterance` pulls ~100 ms windows from the buffer instead of
  calling `rec_chunk`. Idle = drain the buffer (no backlog); during an utterance =
  accumulate.
- **Lifecycle:** stream opened once after Whisper loads; closed once at shutdown.
  **Zero open/close churn during listening.**
- **Isolation:** a small `Capture` abstraction hides the backend so `listen_utterance`,
  `calibrate_noise_floor`, and `mic_level_test` consume one interface — VAD/STT/runtime/
  TTS code stays untouched.

### Pluggable, self-selecting backend
A single `CAPTURE_BACKEND` setting (`wasapi` | `directsound` | `mme`) selects the host
API; the HyperX is still resolved **by name** on that API. At startup the client
**auto-validates and falls back: WASAPI -> DirectSound -> MME**, choosing the first that
opens cleanly *and* yields a usable calibrated peak.

## Design options

| # | Backend | Path | Latency | Stability | Notes |
|---|---|---|---|---|---|
| 1 (primary) | WASAPI shared, persistent | audiodg engine | lowest (~10-30 ms) | highest (path every Windows app uses) | shared mode may apply AGC/AEC; mitigated by gain + calibration |
| 2 (fallback) | DirectSound, persistent | engine (DS -> WASAPI) | ~30-50 ms | high | legacy but robust |
| 3 (last resort) | MME (waveIn), persistent | engine | ~50-100 ms | high | empirically captured strongest on this exact mic |

All three reuse the **same persistent-callback + ring-buffer** design — only the device /
host API differs. None use WDM-KS.

## Risk analysis

| Risk | Likelihood | Mitigation |
|---|---|---|
| 0x10D recurrence | Very low | Removes both triggers (WDM-KS + churn). WASAPI shared is the most-tested kernel path on Windows. |
| Low capture level (WASAPI read near-silence here before) | Medium | `MIC_GAIN` + startup calibration + auto-fallback to MME, which previously produced a strong signal (peak 0.759 @ 48 kHz) on this HyperX. |
| Shared-mode AGC/AEC altering VAD | Low-Med | Calibrated thresholds adapt; optionally disable endpoint enhancements (OS-level, not code). |
| Callback overrun/underrun | Low | Keep callback trivial (enqueue only); bounded buffer; log `status` flags. |
| VAD/STT regression | Low | Only the frame *source* changes; VAD/resample/STT/runtime/TTS unchanged. |
| Python 3.14 native instability (separate `ucrtbase` crashes observed) | Med | Parallel watch item; out of scope for this remediation. |

**Honest data point:** non-KS endpoints were inconsistent on this machine — WASAPI
(dev 12) read near-silence once, while **MME (dev 1 @ 48 kHz) read 0.759**. WASAPI is the
theoretically best (lowest latency, safest), but **MME has proven the strongest capture
on this specific mic**. The auto-select + calibration design lands on whichever works;
MME is a fully viable primary if WASAPI underperforms.

## Expected microphone quality
- **WASAPI shared:** good for 16 kHz Whisper; clean engine resampling; level via gain;
  possible mild enhancement processing.
- **MME:** proven strong on this mic (0.759 peak); excellent for Whisper.
- **Net:** with gain + calibration, expected to meet or exceed the current usable peak
  (> 0.02) with materially lower crash risk.

## Expected latency
- Added capture latency: ~10-30 ms (WASAPI) to ~50-100 ms (MME) of engine buffering,
  plus the existing ~100 ms VAD window — negligible for conversation.
- End-of-turn still governed by `SILENCE_TIMEOUT_S` (1.0 s), unchanged.
- Removing per-chunk open/close removes prior overhead -> responsiveness equal or better.
- Total turn latency stays dominated by STT + LLM (GPU) + TTS — unchanged.

## Migration plan (phased; implement only when approved)
1. Add a `Capture` abstraction (persistent `sd.InputStream` callback + bounded ring
   buffer) behind the existing consume interface.
2. Add `CAPTURE_BACKEND` config (default `wasapi`) + name-based device resolution per
   host API; retire WDM-KS as default (keep behind a disabled flag for reference).
3. Repoint `listen_utterance` / `calibrate_noise_floor` / `mic_level_test` to read from
   the buffer; leave VAD, resample, Whisper, runtime, JARVIS prompt, Piper untouched.
4. Startup auto-select + validate: open stream once; calibrate peak; if low/unopenable,
   fall back WASAPI -> DirectSound -> MME; log the chosen backend.
5. Controlled test protocol (crash risk demands care): short runs first; confirm no
   0x10D, usable peak, VAD start/stop, Whisper transcribes, 5-turn loop, EN/HE/RU intact.
6. Acceptance criteria: zero 0x10D across repeated runs; peak > `USABLE_PEAK`; full
   conversation loop works; latency within current envelope.
7. Ship as a PR (no merge) for review; merge after stability is confirmed.

## Out-of-code mitigations to consider in parallel (machine-side, not code)
- Update/repair the USB Audio 2.0 driver.
- Try a rear USB port / different USB controller.
- Check whether Intel SST USB Audio is intercepting the HyperX.
- Update HyperX firmware (NGENUITY).

## Scope guard
Design only. No code, no behavior change, no backend/GPU/Docker/dashboard changes, no
voice testing. Implementation is a separate, future, approved task.
