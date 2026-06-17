"""
Scheduler foundation - SAFE DRY-RUN ONLY. No background daemon, no hidden loops.

plan_due()   : returns the ordered list of queue items that are due now (priority-sorted).
dry_run()    : returns a human-readable execution plan WITHOUT running anything.
execute_due(): runs due items ONLY when run_fn is supplied AND execute=True (explicit);
               default is dry-run. Failures are captured back into the queue (retry policy).

This is the foundation a future explicit `run-due` command (or an approved daemon) builds
on. By itself it performs no research and opens no PRs.
"""
from __future__ import annotations


def plan_due(queue) -> list[dict]:
    """Ordered due items (priority then due date). Read-only."""
    return queue.prioritized_due()


def dry_run(queue) -> dict:
    """Describe what would run now, without side effects."""
    items = plan_due(queue)
    return {"due": len(items), "mode": "dry-run",
            "plan": [{"id": q["id"], "goal": q["goal"],
                      "priority": q.get("priority", 3),
                      "attempts": q.get("attempts", 0)} for q in items]}


def execute_due(queue, run_fn=None, execute: bool = False, limit: int = 5) -> dict:
    """Default DRY-RUN. Only executes when execute=True AND a run_fn is given.

    run_fn(goal) -> run_id (or raises). Failures are captured via queue.mark_failed
    (retry policy applies). Returns a summary of actions taken.
    """
    items = plan_due(queue)[:limit]
    if not execute or run_fn is None:
        return {"executed": False, "mode": "dry-run", "would_run": len(items),
                "plan": [q["id"] for q in items]}
    ran, failed = [], []
    for q in items:
        try:
            run_id = run_fn(q["goal"])
            queue.mark_done(q["id"], run_id=run_id)
            ran.append({"id": q["id"], "run_id": run_id})
        except Exception as exc:                       # capture, never crash the scheduler
            state = queue.mark_failed(q["id"], f"{type(exc).__name__}: {exc}")
            failed.append({"id": q["id"], **state})
    return {"executed": True, "mode": "live", "ran": ran, "failed": failed}
