"""
Autonomy loop - the SAFE, approval-gated engine that closes the loop:

    due queue -> execute safe tasks -> auto-review -> self-learn -> (brief)

- run_due()        : execute due queue items via an injected read-only run_fn. DRY-RUN by
                     default; runs only when execute=True. Honors a kill switch, a task cap,
                     and a wall-clock budget. Failures are captured (retry policy).
- background_once(): one full cycle (run_due + auto_review + learn). DRY-RUN by default.
- run_loop()       : a BOUNDED, explicitly-approved scheduled loop (NOT a daemon). Runs a
                     cycle function at most max_cycles times with an interval, checking the
                     kill switch before every cycle. Finite by construction.

Everything is injectable (queue, run_fn, memory, history, audit, sleep_fn) so it is fully
testable offline. No daemon, no hidden loops, no background process, no network here - the
CLI supplies a read-only research run_fn. Audit events are emitted at every step.
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
EV_LOOP_PREVIEW = "loop_preview"
EV_LOOP_CYCLE = "loop_cycle_completed"
EV_LOOP_STOPPED = "loop_stopped"
EV_LOOP_COMPLETED = "loop_completed"

# Hard safety bounds for the scheduled loop (no infinite loops, ever).
MAX_CYCLES_LIMIT = 10
MIN_INTERVAL = 5
MAX_INTERVAL = 3600


def _emit(audit, kind, **data):
    if audit is not None:
        audit.event(kind, **data)


def run_due(queue, run_fn=None, *, memory=None, history=None, audit=None,
            execute: bool = False, max_tasks: int = 5, max_seconds: float | None = None,
            disabled: bool = False, rewrite_fn=None) -> dict:
    """Execute due queue items (DRY-RUN unless execute=True AND run_fn given).

    run_fn(goal) -> dict with at least {"run_id": ...} (and optionally findings/status).
    rewrite_fn(goal) -> improved query; when it differs, the original + rewritten goal are
    persisted as queue metadata and the rewritten query is what gets researched.
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
    ran, failed, skipped, rewrites = [], [], [], []
    start = time.time()
    for q in plan:
        if max_seconds is not None and (time.time() - start) > max_seconds:
            skipped.append(q["id"])
            continue
        goal = q["goal"]
        if rewrite_fn is not None:                     # persist self-learned rewrite metadata
            eff = rewrite_fn(goal)
            if eff and eff != goal:
                if hasattr(queue, "annotate"):
                    queue.annotate(q["id"], original_goal=goal, rewritten_goal=eff)
                rewrites.append({"id": q["id"], "from": goal, "to": eff})
                goal = eff
        try:
            r = run_fn(goal) or {}
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
          skipped=len(skipped), rewrites=len(rewrites))
    return {"executed": True, "mode": "live", "ran": ran, "failed": failed,
            "skipped": skipped, "rewrites": rewrites}


def background_once(queue, run_fn=None, *, memory=None, history=None, audit=None,
                    execute: bool = False, max_tasks: int = 5,
                    max_seconds: float | None = None, disabled: bool = False,
                    rewrite_fn=None) -> dict:
    """One full autonomy cycle: run_due -> auto_review -> learn. DRY-RUN by default."""
    rd = run_due(queue, run_fn, memory=memory, history=history, audit=audit,
                 execute=execute, max_tasks=max_tasks, max_seconds=max_seconds,
                 disabled=disabled, rewrite_fn=rewrite_fn)
    reviewed, lessons = 0, []
    if execute and rd.get("executed") and memory is not None and history is not None:
        reviewed = auto_review(history, memory).get("reviewed", 0)
        lessons = selflearn.learn(history, audit, memory)
    _emit(audit, EV_BG_COMPLETED, executed=bool(execute and rd.get("executed")),
          reviewed=reviewed, lessons=len(lessons))
    return {"mode": "live" if (execute and rd.get("executed")) else "dry-run",
            "run_due": rd, "reviewed": reviewed, "lessons": lessons}


def validate_loop_params(max_cycles, interval) -> list[str]:
    """Hard safety validation for the scheduled loop. Returns a list of error strings."""
    errors = []
    if max_cycles is None:
        errors.append("--max-cycles is required")
    elif not isinstance(max_cycles, int) or isinstance(max_cycles, bool) or max_cycles < 1:
        errors.append("--max-cycles must be an integer >= 1")
    elif max_cycles > MAX_CYCLES_LIMIT:
        errors.append(f"--max-cycles exceeds safe limit ({MAX_CYCLES_LIMIT})")
    if interval is None:
        errors.append("--interval is required")
    elif not isinstance(interval, (int, float)) or isinstance(interval, bool) or interval < MIN_INTERVAL:
        errors.append(f"--interval must be a number >= {MIN_INTERVAL}s")
    elif interval > MAX_INTERVAL:
        errors.append(f"--interval must be <= {MAX_INTERVAL}s")
    return errors


def run_loop(cycle_fn, *, max_cycles, interval, execute: bool = False,
             disabled_fn=None, audit=None, sleep_fn=None) -> dict:
    """Bounded, explicitly-approved scheduled loop. NOT a daemon: a foreground, finite loop
    that runs cycle_fn at most max_cycles times, sleeping `interval` between cycles.

    Safety:
    - validates max_cycles/interval against hard bounds (refuses otherwise)
    - DRY-RUN unless execute=True
    - checks the kill switch (disabled_fn) BEFORE every cycle, stopping between cycles
    - stops on any cycle error (safety stop); never an infinite retry
    - sleep_fn is injectable so it is testable without real waiting
    """
    errors = validate_loop_params(max_cycles, interval)
    if errors:
        _emit(audit, EV_LOOP_STOPPED, reason="validation", errors=errors)
        return {"started": False, "errors": errors}
    _emit(audit, EV_LOOP_PREVIEW, max_cycles=max_cycles, interval=interval, execute=execute)
    if not execute:
        return {"started": False, "mode": "dry-run", "max_cycles": max_cycles,
                "interval": interval,
                "plan": f"would run up to {max_cycles} approved cycle(s), every {interval}s"}
    disabled_fn = disabled_fn or (lambda: False)
    cycles, stopped = [], None
    for i in range(max_cycles):
        if disabled_fn():                              # kill switch checked BEFORE each cycle
            stopped = "kill switch engaged"
            _emit(audit, EV_LOOP_STOPPED, cycle=i, reason=stopped)
            break
        try:
            summary = cycle_fn()
        except Exception as exc:                       # safety stop; no infinite retry
            stopped = f"safety error: {type(exc).__name__}"
            _emit(audit, EV_LOOP_STOPPED, cycle=i, reason=stopped)
            break
        cycles.append(summary)
        _emit(audit, EV_LOOP_CYCLE, cycle=i)
        if i < max_cycles - 1 and sleep_fn is not None:
            sleep_fn(interval)
    _emit(audit, EV_LOOP_COMPLETED, ran=len(cycles), stopped=stopped, max_cycles=max_cycles)
    return {"started": True, "mode": "live", "cycles_run": len(cycles),
            "max_cycles": max_cycles, "stopped_reason": stopped, "summaries": cycles}
