"""
Self-monitoring + self-audit - observability for the agent core (offline, read-only).

- run_metrics    : throughput, success rate, empty-result rate from run history
- queue_metrics / goal_metrics / memory_metrics : autonomy-store health
- self_audit     : runs the ops safety checks and returns a pass/fail snapshot
- dashboard      : one-call aggregate health view (used by the CLI `monitor` command)

Pure read-only aggregation; never executes runs or mutates state.
"""
from __future__ import annotations


def run_metrics(history) -> dict:
    runs = history.list()
    by_status: dict[str, int] = {}
    empty = 0
    for r in runs:
        st = r.get("status", "?")
        by_status[st] = by_status.get(st, 0) + 1
        s = (r.get("result_summary") or "").lower()
        if st == "done" and (not s or "no results found" in s or "no findings" in s):
            empty += 1
    total = len(runs)
    done = by_status.get("done", 0)
    return {"total": total, "by_status": by_status,
            "success_rate": round(done / total, 3) if total else 0.0,
            "empty_result_rate": round(empty / total, 3) if total else 0.0,
            "empty_runs": empty}


def queue_metrics(queue) -> dict:
    items = queue.list()
    counts: dict[str, int] = {}
    for q in items:
        counts[q.get("status", "pending")] = counts.get(q.get("status", "pending"), 0) + 1
    return {"total": len(items), "by_status": counts,
            "due_now": len(queue.due_now()), "failed": len(queue.failed())}


def goal_metrics(goals) -> dict:
    return goals.metrics()


def memory_metrics(memory) -> dict:
    return memory.inspect()


def self_audit() -> dict:
    """Run the safety verification and return a compact pass/fail snapshot."""
    from . import ops
    v = ops.verify()
    return {"ok": v["ok"],
            "checks": {c["name"]: c["ok"] for c in v["checks"]},
            "failing": [c["name"] for c in v["checks"] if not c["ok"]]}


def dashboard(history=None, memory=None, goals=None, queue=None) -> dict:
    out = {"self_audit": self_audit()}
    if history is not None:
        out["runs"] = run_metrics(history)
    if queue is not None:
        out["queue"] = queue_metrics(queue)
    if goals is not None:
        out["goals"] = goal_metrics(goals)
    if memory is not None:
        out["memory"] = memory_metrics(memory)
    out["healthy"] = bool(out["self_audit"]["ok"])
    return out
