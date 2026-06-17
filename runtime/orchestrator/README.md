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

## CLI runbook (real research agent)
```
# Research a goal end-to-end (LLM planner + deterministic decomposition fallback ->
# real read-only web research -> merge -> markdown report + history + audit):
python runtime/orchestrator/cli.py research "best open source AI agent frameworks"

# Add an approval-gated docs task (blocked unless approved; writes to gitignored artifacts):
python runtime/orchestrator/cli.py research "..." --doc
python runtime/orchestrator/cli.py research "..." --doc --approve docs

# Run history + a single run summary:
python runtime/orchestrator/cli.py history
python runtime/orchestrator/cli.py show <run_id>

# Explicit LIVE smoke (network); secret scan of generated artifacts:
python runtime/orchestrator/cli.py smoke "hello world"
python runtime/orchestrator/cli.py secret-scan

# Kill switch (refuses to run):
GARVIS_ORCHESTRATOR_DISABLED=1 python runtime/orchestrator/cli.py research "..."

# Memory-aware actionable agent commands:
python runtime/orchestrator/cli.py autodemo "best open source AI agent frameworks"
#   ^ goal -> research -> memory -> proposal.md + draft-PR content (json) -> goal done -> review
python runtime/orchestrator/cli.py memory list|search <q>|add <layer> <text>|compress
python runtime/orchestrator/cli.py memory inspect|export|expire|delete <id> --approve-delete
python runtime/orchestrator/cli.py goal add|priority <id> <n>|progress <id> <pct>|block <id> <why>|review <id>|next|metrics
python runtime/orchestrator/cli.py queue add <goal>|dry-run
python runtime/orchestrator/cli.py scheduler                   # SAFE dry-run (no daemon)
python runtime/orchestrator/cli.py brief [weekly]
python runtime/orchestrator/cli.py review <run_id> <rating> [note]
python runtime/orchestrator/cli.py github branches|pulls|commits|issues|risk <pr#>|status <pr#>|comments <pr#>|cleanup
python runtime/orchestrator/cli.py propose "<goal>"           # research -> change proposal
python runtime/orchestrator/cli.py artifacts [search <q>]

# Draft PR (close-the-loop). DEFAULT = dry-run preview (no branch/file/PR created):
python runtime/orchestrator/cli.py draft-pr "best python testing frameworks"
# Create the REAL draft PR (new branch + proposal file + DRAFT PR; never main/merge/delete):
python runtime/orchestrator/cli.py draft-pr "..." --approve-draft-pr
#   empty proposals are blocked unless you pass --allow-empty-proposal

# Operational safety + self-check (offline):
python runtime/orchestrator/cli.py verify                     # isolation/no-WDM-KS/no-sd.rec/gitignored/config
python runtime/orchestrator/cli.py validate|health|version
python runtime/orchestrator/cli.py config explain|doctor

# Composed end-to-end workflows (safe by default; no live PR creation):
python runtime/orchestrator/cli.py workflow safe-demo "<goal>"
python runtime/orchestrator/cli.py workflow research-to-report|research-to-proposal|draft-pr-preview "<goal>"
python runtime/orchestrator/cli.py workflow goal-to-queue "<goal>" | queue-to-brief | planner-context "<goal>" | pr-risk <pr#>
```
The Draft-PR worker only ever creates a NEW `draft/garvis/*` branch off main, commits a
`docs/proposals/*.md` file, and opens a **draft** PR - never main, never merge, never delete.
Config: `runtime/orchestrator/orchestrator_config.json` (non-secret: limits, source
toggles, default planner). Outputs go to gitignored `_artifacts/` and `_runs/`.
CI: `runtime/orchestrator/ci/orchestrator.yml` (copy to `.github/workflows/` to activate)
runs py_compile + `verify` + secret-scan + all offline suites + safe CLI smoke (never
touches backend/Docker/GPU/dashboard/audio).
All tests (168 total, offline): `test_orchestrator_mvp/_hardening/_sprint`,
`test_real_agent_capabilities`, `test_super_sprint`, `test_draft_pr`,
`test_research_quality`, `test_draftpr_workflow`, `test_github_hardening`,
`test_memory_evolution`, `test_goals_queue_scheduler`, `test_ops_commands`,
`test_user_workflows`.

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
- `workers/`    — `Worker` base + **`DocsWorker`** + **`ResearchWorker`** (real read-only web
  research) + **`GitHubReadWorker`** (read) + **`GitHubDraftPRWorker`** (approval-gated draft PR).
- `research_quality.py` — query clean/expand/broaden, dedup/rank, quality/coverage scoring.
- `draftpr.py`  — title/slug, proposal-quality + empty-block, rollback, dry-run diff, dup detection.
- `memory.py`   — importance, TTL/expire, ranked retrieval, export/import/inspect, protected rules.
- `goals.py` / `queue.py` / `scheduler.py` — goals (priority/deps/blockers) + retrying queue
  + SAFE dry-run scheduler (no daemon).
- `ops.py`      — isolation/no-WDM-KS/no-sd.rec/gitignored/config self-checks + verify/health.
- `workflows.py`— composed, CLI-executable end-to-end user workflows (safe by default).

## What is intentionally inert in this MVP
- Workers are **dry-run**: they describe the action and return an `Envelope` but perform
  **no external action** (no file writes, no PRs, no network). Real behavior is gated for
  later tasks (NEXT_30 T13/T14).
- `Planner` (LLM) is still a stub — MVP uses `ManualPlanner` (caller supplies the tasks).
- `store` is in-memory — postgres backing is a later task (T12/T21, needs approval).

## Next steps (docs/GARVIS_NEXT_30_TASKS.md)
T7 LLM Planner · T12 postgres RunStore · T13 real DocsWorker (branch+draft PR) ·
T14 real ResearchWorker (Browser Use/MCP) · T16 guarded API endpoint (**approval — backend**).
