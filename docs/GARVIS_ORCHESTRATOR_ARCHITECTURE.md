# GARVIS Orchestrator Architecture

> Design doc. No runtime changes yet. Reuses existing `runtime/` (Ollama executor),
> `governance/` (policies), `mission_control/` (controller/approval), and postgres.
> Companion: `GARVIS_WORKER_SYSTEM.md`, `GARVIS_MEMORY_ARCHITECTURE.md`.

## Purpose
Turn a high-level goal into safe, auditable, multi-step execution across specialized
workers — with humans in the loop for anything irreversible.

## High-level flow
```
 goal ──> Planner Agent ──> Task Router ──> [ Worker Registry: workers ]
              ▲                  │                     │
              │             Safety Gate           tool calls
              │                  │                     │
              └── Result Merger <─┴── Approval Gate <───┘
                       │
                  (re-plan or finish)   ── all steps -> Audit Log
```

## Components

### 1. Planner Agent
- Input: goal + relevant memory (user/project/decision) + available worker capabilities.
- Output: an ordered/Dependency-aware **task graph** (`[{id, worker, intent, inputs, deps,
  needs_approval, budget}]`).
- Model: Ollama (start with `llama3.1`; evaluate **Nous Hermes** for stronger JSON/tool
  calls). Strict JSON schema output; reject/repair invalid plans.
- Re-planning: consumes Result Merger output to refine remaining tasks until done/blocked.

### 2. Worker Registry
- Declarative registry of workers: `{name, capabilities, input_schema, output_schema,
  tool_permissions, cost_class, safety_class}`.
- Discovery: the Planner only plans with registered capabilities.
- See `GARVIS_WORKER_SYSTEM.md` for the worker contract.

### 3. Task Router
- Dispatches each ready task (deps satisfied) to the right worker.
- Concurrency: bounded parallelism; respects per-worker and global budgets.
- Retries: idempotent tasks retried with backoff; non-idempotent tasks never auto-retry.

### 4. Result Merger
- Collects worker outputs, normalizes to a common envelope `{task_id, status, result,
  artifacts, cost, logs}`, resolves dependencies, and hands a consolidated state back to
  the Planner.
- Conflict handling: explicit precedence rules; surfaces conflicts instead of guessing.

### 5. Approval Gate (human-in-the-loop)
- Any task flagged `needs_approval` (or whose worker is `safety_class >= write/external`)
  pauses for explicit human approval before execution.
- Reuses `mission_control/workflow_approval.py` patterns.
- Default-deny for: external network writes, money movement, deletions, prod changes,
  driver installs, secret exposure.

### 6. Safety Gate (automated policy)
- Runs BEFORE every tool call, independent of approval.
- Enforces `governance/policies/*`: forbidden actions (WDM-KS, prod/Docker/GPU changes,
  branch deletes, merges, secret printing), budget caps, rate limits, sandbox scope.
- Hard stop + audit entry on violation. The Safety Gate cannot be bypassed by the Planner.

### 7. Tool permissions
- Per-worker allowlist of tools and scopes (e.g. GitHub Worker: `repos:read`, `pulls:write
  (draft only)`; Research Worker: `web:read` only).
- Capabilities are least-privilege; escalation requires approval.

### 8. Audit logs
- Every plan, task, tool call, approval decision, and result is appended to an immutable
  audit store (postgres table + `audit/`), with correlation IDs.
- Surfaced in the dashboard (reuse existing audit feed).

### 9. Failure recovery
- Task-level: typed failures (transient vs permanent); transient -> bounded retry;
  permanent -> mark blocked, continue independent tasks, report.
- Run-level: checkpoint state after each merge so a run can resume.
- Kill switch: a single flag halts dispatch; in-flight tasks finish or time out.
- Budgets: token/$/time ceilings per task and per run; exceeding -> stop + report.

## Data model (MVP)
```
runs(id, goal, status, created_at, budget, owner)
tasks(id, run_id, worker, intent, inputs_json, deps_json, status,
      needs_approval, result_json, cost_json, created_at, updated_at)
approvals(id, task_id, decision, decided_by, decided_at, reason)
audit(id, run_id, task_id, kind, payload_json, ts)
```

## Minimal MVP implementation path
1. `runtime/orchestrator/` package: `planner.py`, `registry.py`, `router.py`,
   `merger.py`, `gates.py` (approval+safety), `models.py` (envelopes), `store.py` (pg).
2. Reuse `runtime/execution/executor.py` for LLM calls; Planner = a prompt + JSON schema.
3. Implement **2 workers** first: Research (read-only) + Docs (write to repo via PR) —
   both low-risk, exercise the full pipeline.
4. Approval Gate as a blocking step persisted in `approvals`; Safety Gate as a pure
   policy function called before each tool call.
5. Expose `POST /api/v1/orchestrator/run` (guarded) + audit viewing; no autonomy loop yet
   (manual approve each gated step).
6. Add the autonomy re-plan loop ONLY after gates + budgets + kill switch are proven.

## Non-goals (for MVP)
- No always-on autonomous loop without gates.
- No irreversible actions without approval.
- No new infra beyond postgres + Windmill (jobs) that the repo already has.
