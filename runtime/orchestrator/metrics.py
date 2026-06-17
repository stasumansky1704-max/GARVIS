"""
Unified self-observation metrics - one surface that aggregates real measurements across
planner / worker / queue / goal / learning / memory / autonomy / execution / quality /
system-health. Read-only; composes existing modules. Not vanity metrics - every number is
something GARVIS can act on.
"""
from __future__ import annotations

from . import monitor, selflearn
from .router import _READ_RETRIES, _MAX_TRANSIENT_RETRIES


def planner_metrics(memory) -> dict:
    from . import planning
    central = planning.topic_centrality(memory)
    return {"topics": len(central),
            "top_topics": [c["topic"] for c in central[:3]],
            "graph": memory.graph_stats()}


def worker_metrics() -> dict:
    """Known worker classes + the router's retry posture (execution reliability config)."""
    return {"workers": ["research", "docs", "github_read", "github_draft_pr"],
            "read_retries": _READ_RETRIES,
            "transient_retries": _MAX_TRANSIENT_RETRIES}


def queue_metrics(queue) -> dict:
    return monitor.queue_metrics(queue)


def goal_metrics(goals) -> dict:
    return goals.metrics()


def learning_metrics(history, audit, memory) -> dict:
    return selflearn.learning_diagnostics(history, audit, memory)


def memory_metrics(memory) -> dict:
    return memory.health_report()


def execution_metrics(history) -> dict:
    return monitor.run_metrics(history)


def quality_metrics(history) -> dict:
    """Output-quality proxy from run history: share of runs that produced real signal."""
    rm = monitor.run_metrics(history)
    total = rm["total"]
    productive = total - rm["empty_runs"] - rm["by_status"].get("failed", 0) \
        - rm["by_status"].get("blocked", 0)
    return {"runs": total, "productive": max(0, productive),
            "productive_rate": round(max(0, productive) / total, 3) if total else 0.0,
            "empty_rate": rm["empty_result_rate"]}


def autonomy_metrics(history, queue, audit) -> dict:
    loop_cycles = len([e for e in audit.list() if e.get("kind") == "loop_cycle_completed"])
    sched_enq = len([e for e in audit.list() if e.get("kind") == "loop_schedules_enqueued"])
    return {"loop_cycles_run": loop_cycles, "schedule_enqueue_events": sched_enq,
            "queue_pending": len(queue.pending()), "queue_due": len(queue.due_now())}


def system_health() -> dict:
    from . import ops
    return ops.health()


def dashboard(history=None, memory=None, goals=None, queue=None, audit=None) -> dict:
    """Full self-observation snapshot. Components included depend on stores supplied."""
    out = {"system_health": system_health(), "worker": worker_metrics()}
    if memory is not None:
        out["planner"] = planner_metrics(memory)
        out["memory"] = memory_metrics(memory)
    if history is not None:
        out["execution"] = execution_metrics(history)
        out["quality"] = quality_metrics(history)
    if goals is not None:
        out["goals"] = goal_metrics(goals)
    if queue is not None:
        out["queue"] = queue_metrics(queue)
    if history is not None and audit is not None and memory is not None:
        out["learning"] = learning_metrics(history, audit, memory)
    if history is not None and queue is not None and audit is not None:
        out["autonomy"] = autonomy_metrics(history, queue, audit)
    out["healthy"] = bool(out["system_health"]["ok"])
    return out
