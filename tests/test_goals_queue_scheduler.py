"""
Group D - goals / queue / scheduler tests (offline, deterministic, temp-dir backed).

Covers goal priority/due/tags/deps/blockers/progress/review/readiness, queue priority
ordering + retry policy + failure capture + dry-run, and the safe dry-run scheduler
(no background daemon) plus weekly brief.

Runs with pytest OR standalone:  python tests/test_goals_queue_scheduler.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator.goals import GoalRegistry
from orchestrator.queue import ResearchQueue
from orchestrator import scheduler
from orchestrator.brief import weekly_brief, daily_brief_full
from orchestrator.memory import MemoryStore
from orchestrator.history import RunHistory


def _tmp(name):
    return os.path.join(tempfile.mkdtemp(), name)


# ---- goals ----
def test_goal_priority_and_prioritized_order():
    g = GoalRegistry(_tmp("g.jsonl"))
    g.add("low", priority=5)
    hi = g.add("high", priority=1)
    assert g.prioritized()[0]["id"] == hi


def test_goal_due_tags_deps_stored():
    g = GoalRegistry(_tmp("g.jsonl"))
    gid = g.add("ship", due="2026-07-01T00:00:00", tags=["release"], deps=["dep1"])
    r = g.review(gid)
    assert r["due"].startswith("2026-07") and "release" in r["tags"] and r["deps"] == ["dep1"]


def test_goal_progress_and_done_sets_100():
    g = GoalRegistry(_tmp("g.jsonl"))
    gid = g.add("x")
    g.set_progress(gid, 40)
    assert g.review(gid)["progress"] == 40
    g.set_status(gid, "done")
    assert g.review(gid)["progress"] == 100


def test_goal_blockers_and_readiness():
    g = GoalRegistry(_tmp("g.jsonl"))
    gid = g.add("blocked goal")
    g.add_blocker(gid, "waiting on API key")
    assert g.review(gid)["blockers"] and not g.is_ready(gid)
    g.clear_blockers(gid)
    assert g.is_ready(gid)


def test_goal_dependency_readiness():
    g = GoalRegistry(_tmp("g.jsonl"))
    dep = g.add("dependency")
    main = g.add("dependent", deps=[dep])
    assert not g.is_ready(main)
    g.set_status(dep, "done")
    assert g.is_ready(main)


# ---- queue ----
def test_queue_priority_ordering():
    q = ResearchQueue(_tmp("q.jsonl"))
    q.enqueue("low", priority=5)
    hi = q.enqueue("high", priority=1)
    assert q.prioritized_due()[0]["id"] == hi


def test_queue_retry_policy_and_failure_capture():
    q = ResearchQueue(_tmp("q.jsonl"))
    qid = q.enqueue("flaky", max_retries=1)
    r1 = q.mark_failed(qid, "boom")
    assert r1["will_retry"] and r1["status"] == "pending"
    r2 = q.mark_failed(qid, "boom again")
    assert not r2["will_retry"] and r2["status"] == "failed"
    assert q.failed() and q.failed()[0]["errors"] == ["boom", "boom again"]


def test_queue_dry_run_lists_without_executing():
    q = ResearchQueue(_tmp("q.jsonl"))
    q.enqueue("a"); q.enqueue("b")
    plan = q.dry_run()
    assert len(plan) == 2 and all("goal" in p for p in plan)


# ---- scheduler ----
def test_scheduler_dry_run_default_no_execution():
    q = ResearchQueue(_tmp("q.jsonl"))
    q.enqueue("research X")
    out = scheduler.execute_due(q, run_fn=lambda g: "RUN1", execute=False)
    assert out["executed"] is False and out["would_run"] == 1
    assert q.pending()                                       # nothing consumed


def test_scheduler_executes_only_when_explicit():
    q = ResearchQueue(_tmp("q.jsonl"))
    qid = q.enqueue("research Y")
    out = scheduler.execute_due(q, run_fn=lambda g: "RUN2", execute=True)
    assert out["executed"] is True and out["ran"][0]["run_id"] == "RUN2"
    assert not q.pending()                                   # consumed -> done


def test_scheduler_captures_failures_into_queue():
    q = ResearchQueue(_tmp("q.jsonl"))
    q.enqueue("research Z", max_retries=0)

    def boom(_):
        raise RuntimeError("nope")

    out = scheduler.execute_due(q, run_fn=boom, execute=True)
    assert out["failed"] and q.failed()


def test_scheduler_plan_due_is_priority_ordered():
    q = ResearchQueue(_tmp("q.jsonl"))
    q.enqueue("low", priority=5)
    hi = q.enqueue("high", priority=1)
    assert scheduler.plan_due(q)[0]["id"] == hi


# ---- briefs ----
def test_weekly_brief_includes_throughput_and_goals():
    h = RunHistory(_tmp("h.jsonl"))
    h.save({"id": "r1", "timestamp": "t", "goal": "g", "status": "done",
            "tasks": [], "result_summary": "", "approvals": []})
    m = MemoryStore(_tmp("m.jsonl")); m.add("rule", "no WDM-KS")
    g = GoalRegistry(_tmp("g.jsonl")); gid = g.add("x"); g.set_status(gid, "done")
    brief = weekly_brief(h, m, g)
    assert "weekly brief" in brief and "Throughput" in brief and "no WDM-KS" in brief


def test_daily_brief_full_includes_goals_and_queue():
    h = RunHistory(_tmp("h.jsonl"))
    m = MemoryStore(_tmp("m.jsonl"))
    g = GoalRegistry(_tmp("g.jsonl")); g.add("active goal", priority=1)
    q = ResearchQueue(_tmp("q.jsonl")); q.enqueue("due item")
    brief = daily_brief_full(h, m, g, q)
    assert "Active goals" in brief and "Due research queue" in brief


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
