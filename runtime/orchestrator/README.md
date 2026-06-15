# runtime/orchestrator — WORKING MVP (still ISOLATED)

> **Status: working manual orchestration MVP, fully isolated.** The flow
> `ManualPlanner → TaskRouter (Safety + Approval gates) → Worker.run → ResultMerger`
> executes end-to-end with **no network, no LLM, no audio, and no backend wiring**.
> It imports nothing from `api/` or `runtime/execution/`, and **nothing imports it**, so
> it has **zero effect on backend runtime behavior**.

Do not wire this into `api/` or `runtime/execution/` without explicit approval (that
would be a backend runtime change).

## Run it safely (isolated)
```
python runtime/orchestrator/demo.py          # demo: research (read) + docs (write, approval-gated)
python tests/test_orchestrator_mvp.py        # unit + end-to-end tests (also pytest-compatible)
```

## Modules
- `models.py`   — `TaskSpec`, `Envelope`, `Plan`, `Run` + `Status`/`SafetyClass`.
- `registry.py` — `WorkerSpec` + in-memory `WorkerRegistry` (capability catalog).
- `gates.py`    — `SafetyGate` (hard rules as data: no WDM-KS, no merges, no branch deletes,
  no secret printing, no prod/Docker/GPU changes) + `ApprovalGate` (manual approval set).
- `planner.py`  — **`ManualPlanner`** (working: validate+assemble tasks) + `Planner` (future LLM, stub).
- `router.py`   — **`TaskRouter.dispatch`** (working: deps + gates + worker run + kill switch).
- `merger.py`   — **`ResultMerger.merge`** (working: fold envelopes + derive run status).
- `engine.py`   — **`Orchestrator`** facade tying it together (`run_manual`).
- `store.py`    — `RunStore` protocol + `InMemoryRunStore`.
- `workers/`    — `Worker` base + **`DocsWorker`** (write, dry-run) + **`ResearchWorker`** (read, dry-run).

## What is intentionally inert in this MVP
- Workers are **dry-run**: they describe the action and return an `Envelope` but perform
  **no external action** (no file writes, no PRs, no network). Real behavior is gated for
  later tasks (NEXT_30 T13/T14).
- `Planner` (LLM) is still a stub — MVP uses `ManualPlanner` (caller supplies the tasks).
- `store` is in-memory — postgres backing is a later task (T12/T21, needs approval).

## Next steps (docs/GARVIS_NEXT_30_TASKS.md)
T7 LLM Planner · T12 postgres RunStore · T13 real DocsWorker (branch+draft PR) ·
T14 real ResearchWorker (Browser Use/MCP) · T16 guarded API endpoint (**approval — backend**).
