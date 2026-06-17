"""
Autonomy loop - the SAFE, approval-gated engine that closes the loop:

    due queue -> execute safe tasks -> auto-review -> self-learn -> (brief)

- run_due()        : execute due queue items via an injected read-only run_fn. DRY-RUN by
                     default; runs only when execute=True. Honors a kill switch, a task cap,
                     and a wall-clock budget. Failures are captured (retry policy).
- background_once(): one full cycle (run_due + auto_review + learn). DRY-RUN by default.

Everything is injectable (queue, run_fn, memory, history, audit) so it is fully testable
offline. No daemon, no hidden loops, no network here - the CLI supplies a read-only
research run_fn. Audit events are emitted at every step.
"""
from __future__ import annotations

import time

from . import scheduler
from . import selflearn
from .brief import auto_review

# Audit event names (stable identifiers).
EV_PREVIEW = "run_due_preview"
EV_STARTED = "run_due_started"
EV_TASK_DONE = "run_due_task_completed"
EV_TASK_BLOCKED = "run_due_task_blocked"
EV_COMPLETED = "run_due_completed"
EV_BG_COMPLETED = "background_cycle_completed"


def _emit(audit, kind, **data):
    if audit is not None:
        audit.event(kind, **data)


def run_due(queue, run_fn=None, *, memory=None, history=None, audit=None,
            execute: bool = False, max_tasks: int = 5, max_seconds: float | None = None,
            disabled: bool = False) -> dict:
    """Execute due queue items (DRY-RUN unless execute=True AND run_fn given).

    run_fn(goal) -> dict with at least {"run_id": ...} (and optionally findings/status).
    Safety: capped at max_tasks, stops at max_seconds, refuses when disabled (kill switch).
    """
    plan = scheduler.plan_due(queue)[:max_tasks]
    _emit(audit, EV_PREVIEW, count=len(plan), ids=[q["id"] for q in plan])
    if not execute or run_fn is None:
        return {"executed": False, "mode": "dry-run", "would_run": len(plan),
                "plan": [q["id"] for q in plan]}
    if disabled:
        _emit(audit, EV_COMPLETED, executed=False, reason="kill switch")
        return {"executed": False, "mode": "disabled", "reason": "kill switch engaged"}
    _emit(audit, EV_STARTED, count=len(plan), max_tasks=max_tasks)
    ran, failed, skipped = [], [], []
    start = time.time()
    for q in plan:
        if max_seconds is not None and (time.time() - start) > max_seconds:
            skipped.append(q["id"])
            continue
        try:
            r = run_fn(q["goal"]) or {}
            queue.mark_done(q["id"], run_id=r.get("run_id"))
            ran.append({"id": q["id"], "run_id": r.get("run_id"),
                        "findings": len(r.get("findings", []))})
            _emit(audit, EV_TASK_DONE, id=q["id"], run=r.get("run_id"),
                  findings=len(r.get("findings", [])))
        except Exception as exc:                       # capture; never crash the loop
            state = queue.mark_failed(q["id"], f"{type(exc).__name__}: {exc}")
            failed.append({"id": q["id"], **state})
            _emit(audit, EV_TASK_BLOCKED, id=q["id"], error=f"{type(exc).__name__}")
    _emit(audit, EV_COMPLETED, executed=True, ran=len(ran), failed=len(failed),
          skipped=len(skipped))
    return {"executed": True, "mode": "live", "ran": ran, "failed": failed,
            "skipped": skipped}


def background_once(queue, run_fn=None, *, memory=None, history=None, audit=None,
                    execute: bool = False, max_tasks: int = 5,
                    max_seconds: float | None = None, disabled: bool = False) -> dict:
    """One full autonomy cycle: run_due -> auto_review -> learn. DRY-RUN by default."""
    rd = run_due(queue, run_fn, memory=memory, history=history, audit=audit,
                 execute=execute, max_tasks=max_tasks, max_seconds=max_seconds,
                 disabled=disabled)
    reviewed, lessons = 0, []
    if execute and rd.get("executed") and memory is not None and history is not None:
        reviewed = auto_review(history, memory).get("reviewed", 0)
        lessons = selflearn.learn(history, audit, memory)
    _emit(audit, EV_BG_COMPLETED, executed=bool(execute and rd.get("executed")),
          reviewed=reviewed, lessons=len(lessons))
    return {"mode": "live" if (execute and rd.get("executed")) else "dry-run",
            "run_due": rd, "reviewed": reviewed, "lessons": lessons}
