# GARVIS Architecture Debt

> Honest snapshot of weak points, missing pieces, debt, and risks as of the LLM-planner
> mega-sprint. Companion: `GARVIS_MASTER_ROADMAP.md`, `GARVIS_NEXT_50_TASKS.md`.

## Weak points (current)
| Area | Weakness | Impact |
|---|---|---|
| Voice capture | HyperX level on safe backends **unverified with speech** (idle ~0); STT local-vs-cloud undecided | Voice loop may be unreliable until confirmed |
| Hebrew TTS | **No provider selected** (ElevenLabs Hebrew = gibberish) | No Hebrew voice output |
| Python 3.14 | Bleeding edge; missing native wheels (`piper-phonemize`, etc.) | Local voice/STT fragility; recurring time sink |
| Orchestrator integration | Orchestrator is **isolated/inert**; not wired to `api/`/`runtime/execution` | Two parallel worlds; no real autonomy yet |
| Workers | Docs/Research workers are **dry-run/mock** (no real effects) | No actual work performed |
| Planner | `LLMPlanner` not wired into any runtime; no schema lib (manual validation) | Plans not produced in production |
| Persistence | `RunStore` is **in-memory**; approvals are an in-memory set; **no audit log store** | No durability, no traceability across restarts |
| Budgets | `TaskSpec.budget` field exists but **not enforced** by the router | No token/$/time ceilings yet |
| CI | **No CI** in the repo (tests run manually) | Regressions can land silently |
| Secrets | Env-only; **no Secrets Broker**; relies on discipline | Future multi-worker secret handling risk |
| Memory | **Not implemented** (design only) | No durable context |
| Cross-boundary | Windows voice client + WSL backend + Docker | Operational complexity; setup drift |
| Docs sprawl | Many strategy/design docs | Drift risk; needs an index |

## Missing pieces
- Real Planner→Worker→Tool execution against live services (gated).
- Postgres-backed run/audit/memory stores (+ pgvector).
- A guarded orchestrator API endpoint (`POST /api/v1/orchestrator/run`).
- Budgets + kill-switch wired end-to-end; persisted approvals.
- Real workers: GitHub (draft-PR), Coding (Aider), Memory (Mem0/Graphiti), Voice.
- Background-jobs runner (Windmill) integration.
- CI (py_compile + unit tests on PRs).
- A docs index (`docs/README.md`).

## Technical debt
- Manual JSON validation in `LLMPlanner` (consider **PydanticAI**/pydantic schemas).
- Two closeout docs (`VOICE_CLOSEOUT.md` vs `VOICE_MVP_CLOSEOUT.md`) — consolidate.
- `garvis_conversation.py` end-to-end (safe capture + ElevenLabs routing) **never run/verified** as a full loop.
- Several merged feature branches retained (intentional) — periodic cleanup decision needed (owner-gated).
- Orchestrator `store.py` / budgets are placeholders.

## Future risks
- **Autonomy without gates wired end-to-end** = highest risk (mitigated: gates exist but aren't in a live loop yet).
- Cloud TTS **COGS** at scale (ElevenLabs per-char).
- Vendor lock-in (ElevenLabs) for EN/RU; Hebrew still open.
- Py3.14 ecosystem gaps may force a pinned 3.11/3.12 venv for local-heavy components.
- Secret leakage if workers gain real tool access before a Secrets Broker exists.

## Recommended fixes (priority order)
1. **Add CI** (py_compile + `tests/test_orchestrator_*.py`) — cheap, stops regressions.
2. **Verify voice loop** manually (HyperX speech test + ElevenLabs EN/RU audition); pick STT path.
3. **Pick Hebrew TTS provider** (Azure he-IL / Google he-IL / Meta MMS).
4. **Wire LLM Planner + Research worker** behind a guarded entrypoint (no backend prod change; isolated module) → first real (read-only) autonomy.
5. **Postgres-backed RunStore + audit** (needs approval — DB) before any write-worker autonomy.
6. **Budgets + persisted approvals + kill switch** wired in the router.
7. **Adopt reuse** (LangGraph/Aider/Mem0/Browser Use) instead of building — see `GARVIS_REUSE_AUDIT.md`.
8. **Consolidate docs** + add `docs/README.md` index; merge the two voice closeout docs.
9. **Secrets Broker** before workers get real credentials.
10. **Pin a 3.11/3.12 venv** for local-heavy voice components if Py3.14 keeps blocking.
