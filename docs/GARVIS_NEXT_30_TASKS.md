# GARVIS — Next 30 Implementation Tasks

> Backlog with: goal · files likely affected · risk · dependencies · validation · value.
> Risk = Low/Med/High. Sequenced in tracks (see Master Roadmap §14). "approval" = needs
> explicit human approval before running (per sprint safety rules).

## Track 1 — Voice MVP closeout

**T1. ElevenLabs TTS audition**
- Goal: judge he/en/ru quality + latency + cost. Files: run `voice_client/poc_elevenlabs_tts.py`.
- Risk: Low. Deps: `ELEVENLABS_API_KEY`. Validation: 3 MP3s in `poc_out/`, TTFB logged.
- Value: unblocks the entire voice decision.

**T2. HyperX-on-safe-backend speech test**
- Goal: confirm usable peak with real speech on WASAPI/DS/MME. Files: `voice_client/safe_mic_test.py`.
- Risk: Low (no WDM-KS). Deps: none. Validation: peak > 0.015 while speaking, no BSOD.
- Value: settles capture viability vs cloud STT.

**T3. ElevenLabs TTS engine in client (design+impl)**
- Goal: `TTS_ENGINE=elevenlabs` with Piper/pyttsx3 fallback. Files: `voice_client/garvis_conversation.py` (new tts module). Risk: Med. Deps: T1.
- Validation: unit test of dispatcher fallback; no key in code. Value: product-grade voice.

**T4. OpenWakeWord "hey jarvis" spike**
- Goal: wake-gate listening from the safe buffer. Files: new `voice_client/wake.py` (POC). Risk: Low. Deps: T2.
- Validation: detects "hey jarvis" in a ≤10s bounded test. Value: hands-free + less capture exposure.

**T5. Voice Worker wrapper**
- Goal: STT→LLM→TTS as an orchestrator worker. Files: `runtime/orchestrator/workers/voice.py`. Risk: Med. Deps: T3, O-track.
- Validation: 5 turns he/en/ru, fallback works. Value: voice usable by the orchestrator.

## Track 2 — Orchestrator + workers

**T6. Orchestrator package skeleton**
- Goal: `planner/registry/router/merger/gates/models/store`. Files: `runtime/orchestrator/*`. Risk: Low (no wiring). Deps: none.
- Validation: `py_compile`; import test. Value: foundation for all autonomy.

**T7. Planner Agent (JSON task graph)**
- Goal: goal→task graph via Ollama, schema-validated. Files: `runtime/orchestrator/planner.py`. Risk: Med. Deps: T6.
- Validation: unit test on a fixed goal → valid graph. Value: core of orchestration.

**T8. Worker contract + registry**
- Goal: base `Worker`, pydantic envelopes, registry. Files: `runtime/orchestrator/registry.py`, `models.py`. Risk: Low. Deps: T6.
- Validation: register + lookup test. Value: uniform, swappable workers.

**T9. Safety Gate (policy, pre-call)**
- Goal: enforce `governance/policies` + forbidden actions (WDM-KS, merges, branch-delete, secret print). Files: `runtime/orchestrator/gates.py`, `governance/*`. Risk: Med. Deps: T6.
- Validation: unit tests for each forbidden action → blocked. Value: hard safety floor.

**T10. Approval Gate (human-in-loop)**
- Goal: pause write/external tasks for approval. Files: `gates.py`, reuse `mission_control/workflow_approval.py`, `approvals` table. Risk: Med. Deps: T6.
- Validation: gated task stays pending until approved. Value: prevents irreversible actions.

**T11. Task Router + budgets + kill switch**
- Goal: dispatch ready tasks, enforce token/$/time caps, global stop flag. Files: `router.py`. Risk: Med. Deps: T7,T8,T9.
- Validation: budget-exceed → stop; kill flag halts dispatch. Value: controlled execution.

**T12. Result Merger + run store**
- Goal: normalize envelopes, resolve deps, checkpoint to postgres. Files: `merger.py`, `store.py`, schema. Risk: Med. Deps: T8.
- Validation: multi-task merge test; resume from checkpoint. Value: reliable multi-step runs.

**T13. Docs Worker (first end-to-end)**
- Goal: generate/update docs via branch+draft PR. Files: `workers/docs.py`. Risk: Low. Deps: T8–T12.
- Validation: produces a draft PR with a doc. Value: proves the full pipeline at low risk.

**T14. Research Worker (read-only web)**
- Goal: search+fetch+summarize w/ citations. Files: `workers/research.py` (Browser Use/MCP). Risk: Low (read-only). Deps: T8.
- Validation: returns cited summary on a query. Value: feeds planning + market.

**T15. GitHub Worker (draft-PR only)**
- Goal: repo/PR/issue read + branch/commit/draft-PR. Files: `workers/github.py` (GitHub MCP/API). Risk: Med (approval for merge/delete). Deps: T8–T10.
- Validation: opens a draft PR; refuses merge/delete without approval. Value: self-service repo ops.

**T16. Orchestrator API endpoint (guarded)**
- Goal: `POST /api/v1/orchestrator/run` (approval; no autonomy loop yet). Files: `api/` (**approval — backend change**). Risk: High (backend). Deps: T7–T12.
- Validation: run a 2-task plan through approvals. Value: usable orchestrator surface.

**T17. Audit log store + dashboard view**
- Goal: immutable audit of plans/tasks/tools/approvals. Files: `audit/`, `dashboard/` (**approval for dashboard**). Risk: Med. Deps: T12.
- Validation: every action produces an audit row. Value: traceability + trust.

**T18. Coding Worker (Aider, scoped, approval)**
- Goal: test-backed scoped edits on a branch. Files: `workers/coding.py` (wrap Aider). Risk: High. Deps: T8–T10,T15.
- Validation: edit + tests + draft PR; no main writes. Value: autonomous coding.

**T19. Evaluate LangGraph as orchestration core**
- Goal: decide build-on-LangGraph vs our skeleton. Files: `docs/` ADR. Risk: Low. Deps: T6.
- Validation: ADR with decision + migration cost. Value: avoid reinventing orchestration.

**T20. Evaluate Nous Hermes for tool-calling**
- Goal: compare vs llama3.1 for JSON/tool calls. Files: `docs/` ADR; Ollama pull (local). Risk: Low. Deps: none.
- Validation: tool-call accuracy on a fixed suite. Value: more reliable planning/tools.

## Track 3 — Memory

**T21. Memory schema (pgvector)**
- Goal: `memories` + `rules` tables + indexes. Files: `database/migrations/*` (**approval — DB**). Risk: Med. Deps: postgres.
- Validation: migration applies; vector index created. Value: durable memory store.

**T22. Memory Worker via Mem0**
- Goal: write/read/consolidate behind the worker contract. Files: `workers/memory.py`. Risk: Med. Deps: T8,T21.
- Validation: store→retrieve roundtrip; dedup works. Value: persistent context.

**T23. Secrets redaction on memory write**
- Goal: block key-like strings/PII before persist. Files: `workers/memory.py`, util. Risk: Med. Deps: T22.
- Validation: secrets test corpus → all redacted/blocked. Value: no secret leakage.

**T24. Planner memory retrieval**
- Goal: hybrid, layer-weighted, token-budgeted injection. Files: `planner.py`. Risk: Med. Deps: T7,T22.
- Validation: relevant memory appears; budget respected. Value: context-aware planning.

**T25. Seed safety/rules memory**
- Goal: load hard rules (WDM-KS forbidden, no auto-merge, etc.). Files: seed script/data. Risk: Low. Deps: T21.
- Validation: rules retrievable + never evicted. Value: durable guardrails.

## Track 4 — Background jobs + product

**T26. Background job contract + Windmill wiring**
- Goal: `jobs` table + Windmill runner for cron/long tasks. Files: `windmill/`, `workflows/`, schema. Risk: Med. Deps: T12.
- Validation: a scheduled job runs + reports via Merger. Value: GARVIS works unattended.

**T27. Daily briefing job**
- Goal: morning summary (PRs/CI/market/news). Files: `workflows/briefing.*` (Research+Market workers). Risk: Low. Deps: T14,T26.
- Validation: produces a briefing artifact. Value: visible daily value.

**T28. Budgets/metering store**
- Goal: persist token/$/time usage per run/user. Files: `store.py`, schema. Risk: Low. Deps: T11.
- Validation: usage rows accumulate. Value: cost control + future billing.

**T29. Per-user auth + memory namespacing**
- Goal: multi-tenant readiness. Files: `api/` (**approval — backend**), memory namespace. Risk: High. Deps: T16,T21.
- Validation: two users isolated. Value: productization.

**T30. Premium voice usage metering**
- Goal: meter ElevenLabs chars/$ per user. Files: voice module + `store.py`. Risk: Low. Deps: T3,T28.
- Validation: per-reply cost recorded. Value: monetization of premium voice.

## Notes
- Tasks marked **approval** touch backend/Docker/GPU/dashboard/DB — STOP and ask first.
- Prefer reuse (LangGraph, Aider, Mem0, Browser Use, MCP) over building (see worker doc).
- Each task should land as commits on a feature branch + a draft PR; no merges without approval.
