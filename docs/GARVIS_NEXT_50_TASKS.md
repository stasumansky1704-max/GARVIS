# GARVIS — Next 50 Tasks (ROI-sorted)

> Columns: **Pri** (P0 highest) · **Deps** · **Risk** (L/M/H) · **Value** · **Effort** (S/M/L).
> Sorted by ROI (high value / low effort, low risk first). "approval" = touches
> backend/DB/Docker/dashboard → STOP for owner approval. Supersedes
> `GARVIS_NEXT_30_TASKS.md` (kept for history).

## Tier 1 — Highest ROI (do first)
| # | Task | Pri | Deps | Risk | Value | Effort |
|---|---|---|---|---|---|---|
| 1 | Add CI: py_compile + run `tests/test_orchestrator_*` on PRs | P0 | — | L | stops regressions | S |
| 2 | Manual voice verify: HyperX speech test (peak>0.015) | P0 | — | L | unblocks STT decision | S |
| 3 | ElevenLabs EN/RU audition with chosen voice IDs | P0 | key | L | confirms voice quality | S |
| 4 | Pick Hebrew TTS provider (Azure/Google/MMS) — decision doc | P0 | — | L | closes Hebrew gap | S |
| 5 | Consolidate voice closeout docs + add `docs/README.md` index | P1 | — | L | reduces drift | S |
| 6 | ADR: LangGraph as orchestration core (vs thin engine) | P0 | — | L | avoids rebuild | S |
| 7 | ADR: PydanticAI/pydantic for typed planning | P1 | — | L | reliability | S |
| 8 | Pin a 3.11/3.12 venv for local voice components | P1 | — | L | ends wheel pain | S |

## Tier 2 — Core autonomy (isolated, no prod change)
| # | Task | Pri | Deps | Risk | Value | Effort |
|---|---|---|---|---|---|---|
| 9 | Wire `LLMPlanner` into `Orchestrator` (isolated demo path) | P0 | 6,7 | L | real plans | M |
| 10 | Replace planner manual JSON validation w/ pydantic schema | P1 | 7,9 | L | robustness | M |
| 11 | Research worker real backend (Browser Use, read-only) | P0 | — | M | real info | M |
| 12 | Nous Hermes model eval for tool/JSON calling (Ollama) | P1 | — | L | better planning | M |
| 13 | Budgets (tokens/$/time) enforced in router | P0 | — | M | cost control | M |
| 14 | Persisted approvals (file/json) + kill-switch flag file | P1 | — | M | durable HITL | M |
| 15 | Audit log (append-only file) for plans/tasks/gates | P0 | — | L | traceability | M |
| 16 | Orchestrator smoke CLI (`demo.py` extended scenarios) | P2 | 9 | L | confidence | S |
| 17 | Worker timeouts + retry policy (idempotent only) | P1 | 13 | M | resilience | M |
| 18 | Capability/permission enforcement per worker in router | P1 | — | M | least-privilege | M |

## Tier 3 — Real workers (gated where they write)
| # | Task | Pri | Deps | Risk | Value | Effort |
|---|---|---|---|---|---|---|
| 19 | GitHub worker: read repo/PRs/issues (read-only first) | P0 | — | M | self-service | M |
| 20 | GitHub worker: branch + commit + DRAFT PR (approval) | P0 | 19 | H | autonomy | M |
| 21 | Docs worker real: write to branch + draft PR | P1 | 20 | M | self-docs | M |
| 22 | Coding worker via Aider (scoped, approval) | P1 | 20 | H | autonomous coding | L |
| 23 | Market worker (read-only data pulls) | P2 | 11 | M | insights | M |
| 24 | Voice worker wraps STT→LLM→TTS as orchestrator worker | P1 | 2,3 | M | voice in orchestrator | M |
| 25 | OpenWakeWord "hey jarvis" gating (reads safe buffer) | P2 | 2 | L | hands-free | M |

## Tier 4 — Memory (design done; impl gated)
| # | Task | Pri | Deps | Risk | Value | Effort |
|---|---|---|---|---|---|---|
| 26 | `memories`+`rules` migrations (pgvector) | P1 | — | M(approval-DB) | durable context | M |
| 27 | Memory worker via Mem0 (read/write/consolidate) | P1 | 26 | M | persistence | M |
| 28 | Secrets redaction on memory write (+ tests) | P0 | 27 | M | no leakage | S |
| 29 | Planner memory retrieval (hybrid, layer-weighted) | P1 | 27 | M | context-aware | M |
| 30 | Seed rules layer from existing decisions | P2 | 26 | L | guardrails | S |
| 31 | Graphiti eval for decision/business graph | P3 | 27 | M | relations | M |

## Tier 5 — Backend integration (all approval-gated)
| # | Task | Pri | Deps | Risk | Value | Effort |
|---|---|---|---|---|---|---|
| 32 | Postgres-backed RunStore | P1 | 26 | H(approval) | durability | M |
| 33 | Guarded `POST /api/v1/orchestrator/run` | P1 | 15,32 | H(approval) | usable surface | M |
| 34 | Dashboard: audit/run viewer (read-only) | P2 | 15,33 | M(approval) | visibility | M |
| 35 | Background jobs contract + Windmill runner | P2 | 32 | M | unattended work | M |
| 36 | Daily briefing job (PRs/CI/market) | P2 | 35,11 | L | daily value | M |
| 37 | Autonomy re-plan loop (Planner↔Merger) behind gates | P2 | 13,14,15,33 | H | true autonomy | L |

## Tier 6 — Product / hardening
| # | Task | Pri | Deps | Risk | Value | Effort |
|---|---|---|---|---|---|---|
| 38 | Usage/$ metering store | P2 | 13 | L | cost/billing | M |
| 39 | Per-user auth + memory namespacing | P3 | 26,33 | H(approval) | multi-tenant | L |
| 40 | Premium voice metering (ElevenLabs chars/$) | P3 | 24,38 | L | monetization | S |
| 41 | Secrets Broker (scoped, short-lived caps) | P1 | — | M | secret safety | M |
| 42 | Local TTS (XTTS RU/EN, MMS HE) to cut COGS | P3 | 4 | M | offline/cost | L |
| 43 | NVIDIA Parakeet eval (EN STT on 5090) | P3 | — | L | speed | M |

## Tier 7 — Cleanups / ops
| # | Task | Pri | Deps | Risk | Value | Effort |
|---|---|---|---|---|---|---|
| 44 | Merge two voice closeout docs into one | P2 | 5 | L | clarity | S |
| 45 | Branch cleanup policy (owner-gated) | P3 | — | L | hygiene | S |
| 46 | Lint/format config (ruff) + pre-commit | P2 | 1 | L | quality | S |
| 47 | `tests/` runner doc + make target | P2 | 1 | L | DX | S |
| 48 | Error taxonomy for envelopes (typed failures) | P2 | 17 | L | debuggability | M |
| 49 | Observability: structured logs for orchestrator | P2 | 15 | L | ops | M |
| 50 | Threat model / safety review of autonomy loop | P1 | 37 | M | risk reduction | M |

## Recommended order
**Now:** 1–8 (cheap unblockers). **Then:** 9–18 (isolated autonomy core). **Then:** 19–21
(read-only + draft-PR workers), 26–29 (memory). **Approval-gated backend:** 32–34, then
35–37 (jobs + autonomy loop) with 41 (Secrets Broker) and 50 (safety review) alongside.
