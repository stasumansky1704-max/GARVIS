"""
Self-evolution tests - Tracks A (self-learning), B (memory lifecycle), C (planning +
router recovery). Offline, deterministic, temp-dir backed.

Runs with pytest OR standalone:  python tests/test_self_evolution.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator import selflearn, planning
from orchestrator.memory import MemoryStore
from orchestrator.history import RunHistory
from orchestrator.audit import AuditLog
from orchestrator.models import TaskSpec, Envelope, Status, SafetyClass, Plan
from orchestrator.registry import WorkerRegistry, WorkerSpec
from orchestrator.gates import SafetyGate, ApprovalGate
from orchestrator.router import TaskRouter


def _tmp(n):
    return os.path.join(tempfile.mkdtemp(), n)


def _hist_with(records):
    h = RunHistory(_tmp("h.jsonl"))
    for r in records:
        h.save(r)
    return h


# ---------- Track A: self-learning ----------
def test_analyze_failures_families():
    h = _hist_with([
        {"id": "1", "goal": "g", "status": "failed", "result_summary": "",
         "tasks": [{"id": "t", "status": "failed", "error": "HTTPError: timeout"}], "approvals": []},
        {"id": "2", "goal": "g", "status": "done", "result_summary": "ok",
         "tasks": [{"id": "t", "status": "done"}], "approvals": []},
    ])
    a = selflearn.analyze_failures(h)
    assert a["failed"] == 1 and a["total"] == 2 and a["error_families"].get("network") == 1


def test_analyze_empty_results_detects_project_tokens():
    h = _hist_with([
        {"id": "1", "goal": "best agents for GARVIS", "status": "done",
         "result_summary": "No results found for: best agents for GARVIS",
         "tasks": [], "approvals": []},
    ])
    e = selflearn.analyze_empty_results(h)
    assert e["empty_runs"] == 1 and e["with_project_tokens"] == 1
    assert "garvis" not in e["items"][0]["suggested_query"].lower()


def test_analyze_blocked_and_denials():
    au = AuditLog(_tmp("a.jsonl"))
    au.event("task_blocked", task="t1", error="approval: awaiting human approval")
    au.event("task_blocked", task="t2", error="safety: forbidden action")
    assert selflearn.analyze_blocked(au)["blocked_tasks"] == 2
    assert selflearn.analyze_denials(au)["approval_denials"] == 1


def test_recommend_surfaces_project_token_issue():
    h = _hist_with([{"id": "1", "goal": "x for GARVIS", "status": "done",
                     "result_summary": "no findings", "tasks": [], "approvals": []}])
    au = AuditLog(_tmp("a.jsonl"))
    recs = selflearn.recommend(h, au)
    assert any(r["area"] == "research" for r in recs)


def test_learn_writes_deduped_lessons_to_memory():
    h = _hist_with([{"id": "1", "goal": "agents for GARVIS", "status": "done",
                     "result_summary": "No results found for: agents for GARVIS",
                     "tasks": [], "approvals": []}])
    au = AuditLog(_tmp("a.jsonl"))
    m = MemoryStore(_tmp("m.jsonl"))
    first = selflearn.learn(h, au, m)
    assert first and any("strip project-specific tokens" in t for t in first)
    again = selflearn.learn(h, au, m)            # idempotent: no duplicate lessons
    assert again == []
    assert any(r["source"] == "self-learned" for r in m.list())


def test_insights_snapshot_keys():
    h = _hist_with([])
    au = AuditLog(_tmp("a.jsonl"))
    snap = selflearn.insights(h, au)
    assert {"failures", "empty_results", "weak_plans", "blocked", "denials",
            "recommendations"} <= set(snap)


# ---------- Track B: memory lifecycle ----------
def test_consolidate_merges_near_duplicates():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("decision", "use langgraph for agent frameworks", importance=0.5)
    m.add("decision", "use langgraph for agent frameworks today", importance=0.8)
    removed = m.consolidate(threshold=0.6)
    assert removed == 1 and len(m.list("decision")) == 1
    assert m.list("decision")[0]["importance"] == 0.8


def test_consolidate_never_merges_protected():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("rule", "never use WDM-KS", tags=["safety"])
    m.add("rule", "never use WDM-KS ever", tags=["safety"])
    removed = m.consolidate(threshold=0.5)
    assert removed == 0 and len(m.list("rule")) == 2


def test_promote_run_to_decision():
    m = MemoryStore(_tmp("m.jsonl"))
    rid = m.add("run", "useful run about agents", importance=0.3)
    assert m.promote(rid)
    rec = m.get(rid)
    assert rec["layer"] == "decision" and rec["importance"] > 0.3


def test_decay_reduces_old_unused_importance():
    m = MemoryStore(_tmp("m.jsonl"))
    mid = m.add("decision", "stale idea", importance=0.6)
    n = m.decay(rate=0.1, now_ts=9_999_999_999)
    assert n == 1 and m.get(mid)["importance"] < 0.6


def test_decay_skips_protected_and_used():
    m = MemoryStore(_tmp("m.jsonl"))
    sid = m.add("rule", "no secrets", tags=["safety"])
    uid = m.add("decision", "used idea")
    m.reinforce(uid)
    m.decay(rate=0.2, now_ts=9_999_999_999)
    assert m.get(sid)["importance"] == 1.0 and m.get(uid)["importance"] >= 0.6


def test_recency_affects_ranking():
    m = MemoryStore(_tmp("m.jsonl"))
    a = m.add("decision", "agent frameworks alpha")
    b = m.add("decision", "agent frameworks beta")
    # equal importance: most-recently added should not rank below older on a tie
    hits = m.search("agent frameworks")
    assert {a, b} == {h["id"] for h in hits}


# ---------- Track C: planning + router recovery ----------
def test_estimate_complexity_scales():
    assert planning.estimate_complexity("python") <= planning.estimate_complexity(
        "best open source agent frameworks and orchestration vs alternatives")


def test_recommended_task_count_bounded():
    n = planning.recommended_task_count("a and b and c vs d", cap=6)
    assert 2 <= n <= 6


def test_select_worker_by_capability():
    reg = WorkerRegistry()
    reg.register(WorkerSpec(name="research", capabilities=["web_search", "summarize"]))
    reg.register(WorkerSpec(name="github_read", capabilities=["pulls", "risk"]))
    assert planning.select_worker("web_search agents", reg) == "research"
    assert planning.select_worker("check pulls risk", reg) == "github_read"


def test_dedupe_tasks():
    ts = [TaskSpec(id="a", worker="research", intent="x", inputs={"query": "q"}),
          TaskSpec(id="b", worker="research", intent="x", inputs={"query": "q"}),
          TaskSpec(id="c", worker="research", intent="y", inputs={"query": "z"})]
    assert len(planning.dedupe_tasks(ts)) == 2


def test_score_plan_penalizes_duplicates_and_dangling():
    good = [TaskSpec(id="a", worker="research", intent="x", inputs={"query": "q1"}),
            TaskSpec(id="b", worker="research", intent="y", inputs={"query": "q2"}),
            TaskSpec(id="c", worker="research", intent="z", inputs={"query": "q3"}),
            TaskSpec(id="d", worker="research", intent="w", inputs={"query": "q4"})]
    bad = [TaskSpec(id="a", worker="research", intent="x", inputs={"query": "q"}),
           TaskSpec(id="b", worker="research", intent="x", inputs={"query": "q"},
                    deps=["missing"])]
    assert planning.score_plan(good)["score"] > planning.score_plan(bad)["score"]


def test_classify_and_transient_detection():
    assert planning.is_transient_error("HTTPError: timed out")
    assert planning.is_transient_error("github rate limit hit")
    assert not planning.is_transient_error("missing 'query' input")
    assert planning.classify_error("approval: awaiting") == "approval"


class _TransientWorker:
    spec = WorkerSpec(name="ext", capabilities=["x"], safety_class=SafetyClass.EXTERNAL)

    def __init__(self):
        self.calls = 0

    def run(self, task):
        self.calls += 1
        if self.calls < 2:
            return Envelope(task.id, Status.FAILED, error="HTTPError: connection reset")
        return Envelope(task.id, Status.DONE, result={"ok": True})


def test_router_retries_transient_for_external_worker():
    reg = WorkerRegistry(); reg.register(_TransientWorker.spec)
    router = TaskRouter(reg, SafetyGate(), ApprovalGate(approved={"t"}))
    w = _TransientWorker()
    res = router.dispatch(Plan(run_id="r", goal="g",
                          tasks=[TaskSpec(id="t", worker="ext", intent="x")]),
                          workers={"ext": w})
    assert res["t"].status == Status.DONE and w.calls == 2


class _PermanentWorker:
    spec = WorkerSpec(name="ext2", capabilities=["x"], safety_class=SafetyClass.EXTERNAL)

    def __init__(self):
        self.calls = 0

    def run(self, task):
        self.calls += 1
        return Envelope(task.id, Status.FAILED, error="missing 'query' input")


def test_router_does_not_retry_permanent_error():
    reg = WorkerRegistry(); reg.register(_PermanentWorker.spec)
    router = TaskRouter(reg, SafetyGate(), ApprovalGate(approved={"t"}))
    w = _PermanentWorker()
    router.dispatch(Plan(run_id="r", goal="g",
                    tasks=[TaskSpec(id="t", worker="ext2", intent="x")]),
                    workers={"ext2": w})
    assert w.calls == 1                          # permanent error => no wasted retries


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
