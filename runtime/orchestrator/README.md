# runtime/orchestrator — INERT SCAFFOLDING

> **Status: scaffolding only.** These modules are pure stubs (stdlib dataclasses + typed
> signatures). They import nothing from the existing backend, and **nothing imports them**,
> so they have **zero effect on backend runtime behavior**. They exist to make the design
> in `docs/GARVIS_ORCHESTRATOR_ARCHITECTURE.md` concrete and ready to implement.

Do not wire these into `api/` or `runtime/execution/` without explicit approval (that
would be a backend runtime change).

## Modules
- `models.py`   — `TaskSpec`, `Envelope`, `Plan`, `Run` dataclasses (I/O contracts).
- `registry.py` — `WorkerSpec` + in-memory `WorkerRegistry`.
- `gates.py`    — `SafetyGate` (encodes the hard rules: no WDM-KS, no merges, no branch
  deletes, no secret printing, no prod/Docker/GPU changes) + `ApprovalGate` stub.
- `planner.py`  — `Planner.plan(goal) -> Plan` (stub).
- `router.py`   — `TaskRouter.dispatch(...)` (stub, budget/kill-switch placeholders).
- `merger.py`   — `ResultMerger.merge(...)` (stub).
- `store.py`    — `RunStore` protocol + `InMemoryRunStore` (stub persistence).

## Next steps (see docs/GARVIS_NEXT_30_TASKS.md, T6–T12)
Fill stubs, back `store` with postgres, implement `Planner` against Ollama, add the
Docs + Research workers, then expose a guarded endpoint (needs approval — backend change).
