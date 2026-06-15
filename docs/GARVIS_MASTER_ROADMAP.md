# GARVIS / JARVIS Master Roadmap

> Strategy doc produced in the autonomy sprint. Living document — update as phases land.
> Companion docs: `GARVIS_ORCHESTRATOR_ARCHITECTURE.md`, `GARVIS_WORKER_SYSTEM.md`,
> `GARVIS_MEMORY_ARCHITECTURE.md`, `GARVIS_NEXT_30_TASKS.md`, and the voice work in
> `voice_client/PREMIUM_VOICE_STACK_AUDIT.md` (PR #19).

## 1. Current state (verified)
- **main is stable** (`e2e4ae2`).
- **JARVIS identity is live**: voice prompt grounds JARVIS as Stas's local assistant,
  mirrors he/en/ru, forbids sci-fi roleplay. Deployed and verified via the runtime API.
- **GPU runtime works** (RTX 5090); **Ollama `llama3.1` is fast** (sub-second replies).
- **Backend/API healthy**: FastAPI, `GET /api/v1/status/health -> 200`
  (postgres + ollama healthy). Runtime command endpoint `POST /api/v1/runtime/command`.
- **Dashboard works** (living-core HUD, JARVIS branding).
- **Voice**: proof-of-concept only. Safe persistent capture (WASAPI/DS/MME, **WDM-KS
  excluded**) exists (PR #18) but HyperX peak is very low on engine-routed backends, so
  it is NOT yet enough for full conversation. STT = faster-whisper (base). TTS = Piper
  (EN) + pyttsx3 fallback; Hebrew/Russian local TTS unsolved.
- **Forbidden**: WDM-KS capture — caused kernel BugCheck `0x0000010D` (BSOD). See
  `voice_client/WINDOWS_AUDIO_CAPTURE_REMEDIATION.md` (PR #17).
- **Environment caveat**: Python **3.14.5** lacks wheels for parts of the local voice
  ecosystem (e.g. `piper-phonemize`) — a recurring time sink that argues for cloud TTS.
- **Open PRs (do not merge without approval):** #17 docs remediation, #18 safe capture,
  #19 premium voice POC (draft).

## 2. Voice MVP closeout
The voice MVP is the one workstream blocked on a real decision. Recommended close:
1. **STT stays local**: faster-whisper on the safe WASAPI capture (free, private, he/ru/en).
2. **TTS goes cloud (paid)**: **ElevenLabs** for product-grade Hebrew/Russian/English with
   streaming. Piper(EN)/pyttsx3 remain offline/debug fallback.
3. **Capture decision**: if HyperX stays near-silent on safe backends even with gain +
   speech, either (a) select the Intel mic array, (b) force a backend, or (c) accept
   cloud STT. Resolve with a short manual `safe_mic_test`/`poc_*` run WITH speech.
4. **Definition of done**: 5 clean conversation turns (he/en/ru), no BSOD, latency within
   budget (STT + LLM + TTS), automatic TTS fallback on cloud failure.

## 3. Orchestrator plan (summary)
A Planner -> Worker Registry -> Task Router -> Result Merger pipeline, gated by an
Approval Gate and a Safety Gate, with tool permissions and audit logs. Reuses the
existing `runtime/` executor and `mission_control/` + `governance/`. Full design in
`GARVIS_ORCHESTRATOR_ARCHITECTURE.md`. MVP = single planner + 2 workers + approval gate.

## 4. Worker system plan (summary)
Independent, permissioned workers behind a uniform contract. First set: Research,
GitHub, Coding, Docs, Memory, Voice, Market; Calendar/Gmail as future connectors. Full
design in `GARVIS_WORKER_SYSTEM.md`.

## 5. Memory system plan (summary)
Layered memory: user / project / decision / business / task / safety-rules, with a
retrieval strategy and strict secrets handling. Full design in
`GARVIS_MEMORY_ARCHITECTURE.md`. Reuses existing `memory/` (episodic) + postgres.

## 6. Background jobs plan
- **Need**: scheduled and long-running work (research crawls, market pulls, memory
  consolidation, report generation) decoupled from the request path.
- **Reuse**: the repo already ships **Windmill** (`windmill/`) and a `workflows/` dir —
  use Windmill as the job runner rather than building a scheduler.
- **MVP**: a job contract `{id, type, payload, schedule, status}` persisted in postgres;
  workers enqueue/consume; Windmill runs cron + long tasks; results flow back through the
  Result Merger. No always-on Python loops on the client.
- **Safety**: jobs are sandboxed, time-boxed, and pass the Safety Gate; no endless loops.

## 7. Autonomy engine plan
- A controlled loop: Planner decomposes a goal -> tasks -> Router dispatches to workers ->
  results merged -> Planner re-plans until done or blocked.
- **Guardrails first**: every external/irreversible action passes the Approval Gate;
  every action is audit-logged; budgets (time, tokens, $) are enforced; a kill switch
  stops the loop.
- Build only after Orchestrator MVP + 2-3 workers are solid. Autonomy without the gates
  is the single biggest risk.

## 8. Productization plan
- **Wedge**: a reliable multilingual (he/en/ru) voice assistant + autonomous research/
  GitHub/coding workers, running locally with a cloud-quality voice.
- **Path**: (a) make voice reliable (ElevenLabs) -> (b) ship 2-3 workers with approval
  gate -> (c) package as a product (auth, per-user memory, usage metering) -> (d) hosted
  option.
- **Revenue levers**: subscription (assistant + workers), usage-metered premium voice,
  team/agent seats. Cloud voice COGS must be modeled (see cost/benefit in voice audit).

## 9. Paid tools worth using (spend to save weeks)
| Tool | Use | Why pay |
|---|---|---|
| **ElevenLabs** | TTS (he/ru/en, streaming) | Fastest path to product-grade Hebrew/Russian voice; sidesteps Py3.14 local-wheel mess. |
| **Cloud STT** (Deepgram / AssemblyAI / ElevenLabs Scribe) | optional STT | Only if local Whisper accuracy/latency is insufficient; otherwise keep local. |
| Hosted vector DB (optional) | memory retrieval at scale | Only when local pgvector outgrows a single box. |

## 10. Open-source worth integrating (reuse, don't rebuild)
| Project | Use | Notes |
|---|---|---|
| **faster-whisper** (have) | local STT | Already working; he/ru/en. Keep. |
| **OpenWakeWord** | "hey jarvis" wake word | Apache-2.0, CPU, ships a "hey jarvis" model; reads our safe buffer. |
| **RealtimeSTT** | optional STT+VAD+wake bundle | MIT, Windows-first; cost = torch ~2.5 GB. |
| **RealtimeTTS** | multi-engine TTS facade | MIT; unifies Piper/SAPI + adds XTTS; good when going hybrid. |
| **Windmill** (have) | background jobs / workflows | Use as the job runner. |
| **Nous Hermes** (LLM, via Ollama) | tool/function-calling brain | Stronger JSON/tool calls than vanilla llama for the orchestrator. |
| **Meta MMS / XTTS** | future local he/ru TTS | Only after cloud voice works; for COGS/offline. |

## 11. What to avoid
- **WDM-KS** capture (BSOD `0x10D`).
- Running the old `garvis_conversation.py` until safe capture is proven with speech.
- Adopting full frameworks (OpenVoiceOS, Mycroft, Home Assistant) — they force a rewrite.
- Building local Hebrew TTS first — slow path; use ElevenLabs now.
- Always-on Python audio/background loops on the client.
- Autonomy loops without Approval + Safety gates and budgets.
- Fighting Python 3.14 native-wheel gaps — prefer cloud or a pinned interpreter for
  local-heavy components.

## 12. Risk analysis
| Risk | Severity | Mitigation |
|---|---|---|
| WDM-KS / driver BSOD | Critical | Forbidden; safe backends only; no per-chunk open/close. |
| HyperX low level on safe backends | High | Manual speech test; fallback device/backend; or cloud STT. |
| Py3.14 wheel gaps | Medium | Cloud TTS; pin a 3.11/3.12 venv for local-heavy pieces if needed. |
| Autonomy doing irreversible actions | High | Approval Gate + Safety Gate + audit + budgets + kill switch. |
| Cloud voice COGS at scale | Medium | Meter usage; migrate hot paths to local XTTS/MMS later. |
| Secret leakage | High | Env-only keys; never commit/print; secrets memory rules. |
| Scope creep / perfection traps | Medium | Ship MVP per phase; timeboxed tasks (see NEXT_30). |

## 13. Top 20 implementation tasks
1. ElevenLabs TTS audition (manual run of `poc_elevenlabs_tts.py` with key + speech).
2. Add `TTS_ENGINE=elevenlabs` to the client with Piper/pyttsx3 fallback (design first).
3. Manual `safe_mic_test`/`poc` with SPEECH to settle HyperX-on-safe-backend level.
4. OpenWakeWord "hey jarvis" spike reading the safe capture buffer.
5. Orchestrator MVP: Planner + Worker Registry + Task Router (in `runtime/orchestrator/`).
6. Approval Gate + Safety Gate wrappers (reuse `governance/` + `mission_control/`).
7. Worker contract/base class + registry.
8. Research Worker (read-only web + summarize).
9. GitHub Worker (PR/issue ops via API, draft-PR only by default).
10. Docs Worker (generate/update repo docs).
11. Memory Worker + schema (pgvector) per `GARVIS_MEMORY_ARCHITECTURE.md`.
12. Coding Worker (scoped edits + tests, behind approval).
13. Background jobs contract + Windmill wiring.
14. Audit log store + viewer (reuse `audit/` + dashboard).
15. Budgets/limits (tokens/$/time) + kill switch.
16. Voice Worker wrapping STT->LLM->TTS as an orchestrator worker.
17. Market Worker (read-only data pulls) as a research-style worker.
18. Nous Hermes function-calling model evaluation in Ollama.
19. Per-user auth + memory namespacing (productization).
20. Usage metering for premium voice (productization).

## 14. Recommended order
**Track 1 (voice reliability, parallelizable):** 1 -> 3 -> 2 -> 4 -> 16.
**Track 2 (autonomy foundation):** 5 -> 6 -> 7 -> 8/9/10 -> 11 -> 13 -> 14 -> 15 -> 12.
**Track 3 (product):** 18 -> 19 -> 20.
Do Track 1 and the first half of Track 2 first; they unblock everything else.
