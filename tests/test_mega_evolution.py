"""
Mega evolution sprint - tests (offline, deterministic, temp-dir backed).

Tracks: A persisted scheduling, B CI activation (git hook), C memory graph/topics,
D queue dependency gating, E vault + guardian (mini-PC readiness), F history/audit
workflow expansion, G repeat-failure self-learning.

Runs with pytest OR standalone:  python tests/test_mega_evolution.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator.schedule import ScheduleStore, in_window, parse_window, MIN_INTERVAL
from orchestrator.vault import VaultStore
from orchestrator import guardian, ops, selflearn
from orchestrator.queue import ResearchQueue
from orchestrator.memory import MemoryStore
from orchestrator.history import RunHistory
from orchestrator.audit import AuditLog


def _tmp(n):
    return os.path.join(tempfile.mkdtemp(), n)


# ---------- Track A: persisted scheduling ----------
def test_schedule_add_and_survives_reload():
    p = _tmp("s.jsonl")
    s1 = ScheduleStore(p)
    sid = s1.add("research X", interval=3600, now_ts=1000.0)
    s2 = ScheduleStore(p)                                   # fresh instance == "after restart"
    assert s2.get(sid) is not None and s2.get(sid)["goal"] == "research X"


def test_schedule_interval_validation():
    s = ScheduleStore(_tmp("s.jsonl"))
    try:
        s.add("x", interval=MIN_INTERVAL - 1)
        assert False, "should reject tiny interval"
    except ValueError:
        pass


def test_schedule_due_and_mark_run():
    s = ScheduleStore(_tmp("s.jsonl"))
    sid = s.add("g", interval=100, now_ts=1000.0)          # next_due = 1100
    assert s.due(now_ts=1050.0) == []
    assert any(d["id"] == sid for d in s.due(now_ts=1200.0))
    s.mark_run(sid, now_ts=1200.0)                          # next_due -> 1300
    assert s.due(now_ts=1250.0) == []


def test_schedule_remove():
    s = ScheduleStore(_tmp("s.jsonl"))
    sid = s.add("g", interval=100)
    assert s.remove(sid) and s.get(sid) is None


def test_schedule_window_parsing_and_wraparound():
    assert parse_window("09:00-17:00") == (540, 1020)
    # wrap-around window 22:00-06:00: 23:00 inside, 12:00 outside
    import time
    base = time.mktime(time.struct_time((2026, 1, 1, 23, 0, 0, 0, 1, -1)))
    assert in_window("22:00-06:00", base)
    noon = time.mktime(time.struct_time((2026, 1, 1, 12, 0, 0, 0, 1, -1)))
    assert not in_window("22:00-06:00", noon)


def test_schedule_enqueue_due_feeds_queue():
    s = ScheduleStore(_tmp("s.jsonl"))
    q = ResearchQueue(_tmp("q.jsonl"))
    s.add("recurring goal", interval=100, now_ts=1000.0)
    enq = s.enqueue_due(q, now_ts=2000.0)
    assert len(enq) == 1 and len(q.pending()) == 1
    assert s.enqueue_due(q, now_ts=2050.0) == []            # advanced; not due again yet


# ---------- Track B: CI activation (git hook) ----------
def test_install_git_hook(tmp_path=None):
    d = tempfile.mkdtemp()
    res = ops.install_git_hook(hooks_dir=d)
    assert res["installed"] is True
    content = open(os.path.join(d, "pre-push"), encoding="utf-8").read()
    assert "ci-check" in content


def test_install_git_hook_missing_dir():
    res = ops.install_git_hook(hooks_dir="/nonexistent/hooks/xyz")
    assert res["installed"] is False


# ---------- Track C: memory graph ----------
def test_memory_link_and_related():
    m = MemoryStore(_tmp("m.jsonl"))
    a = m.add("decision", "langgraph for agents")
    b = m.add("decision", "autogen for agents")
    assert m.link(a, b, "related")
    assert b in [r["id"] for r in m.related(a)]


def test_memory_link_requires_existing():
    m = MemoryStore(_tmp("m.jsonl"))
    a = m.add("decision", "x")
    assert m.link(a, "nope") is False


def test_memory_auto_link_and_topics():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("decision", "agent frameworks comparison langgraph")
    m.add("decision", "agent frameworks autogen crewai")
    m.add("decision", "unrelated cooking pasta recipe")
    created = m.auto_link(threshold=0.2)
    assert created >= 1
    topics = m.topics(min_size=2)
    assert any("agent" in t["topic"] or "frameworks" in t["topic"] for t in topics)


def test_memory_graph_stats():
    m = MemoryStore(_tmp("m.jsonl"))
    a = m.add("decision", "a topic")
    b = m.add("decision", "a topic too")
    m.link(a, b)
    st = m.graph_stats()
    assert st["nodes"] == 2 and st["edges"] == 1


# ---------- Track D: queue dependency gating ----------
def test_queue_deps_gating():
    q = ResearchQueue(_tmp("q.jsonl"))
    dep = q.enqueue("dependency")
    main = q.enqueue("dependent", deps=[dep])
    due_ids = [d["id"] for d in q.due_now()]
    assert dep in due_ids and main not in due_ids           # main blocked by dep
    q.mark_done(dep)
    assert main in [d["id"] for d in q.due_now()]            # now unblocked


# ---------- Track E: vault + guardian ----------
def test_vault_register_presence_no_values():
    env = {"MY_KEY": "secret-value-should-never-leak"}
    v = VaultStore(_tmp("v.jsonl"), env=env)
    v.register("my-service", "MY_KEY", "test key")
    status = v.status()
    assert status["my-service"] is True
    # presence is a bool; the value never appears anywhere in the output
    assert "secret-value" not in str(status)


def test_vault_missing_required():
    v = VaultStore(_tmp("v.jsonl"), env={})
    v.register("svc", "ABSENT_VAR", required=True)
    assert v.missing() == ["svc"] and v.ready() is False


def test_vault_optional_not_missing():
    v = VaultStore(_tmp("v.jsonl"), env={})
    v.register("opt", "ABSENT", required=False)
    assert v.missing() == [] and v.ready() is True


def test_guardian_kill_switch_check():
    assert guardian.check_kill_switch()["ok"] is True


def test_guardian_readiness_report_structure():
    v = VaultStore(_tmp("v.jsonl"), env={})
    rep = guardian.readiness_report(vault=v, min_free_mb=0)
    assert "ready" in rep and rep["deployment"].startswith("not performed")
    names = {c["name"] for c in rep["checks"]}
    assert {"disk", "writable", "kill_switch", "safety", "vault"} <= names


def test_guardian_vault_check_flags_missing():
    v = VaultStore(_tmp("v.jsonl"), env={})
    v.register("needed", "ABSENT", required=True)
    assert guardian.check_vault(v)["ok"] is False


# ---------- Track F: history/audit workflow expansion ----------
def test_history_search_and_filter_and_stats():
    h = RunHistory(_tmp("h.jsonl"))
    h.save({"id": "1", "goal": "agent frameworks", "status": "done",
            "result_summary": "found langgraph", "tasks": [], "approvals": []})
    h.save({"id": "2", "goal": "cooking", "status": "failed",
            "result_summary": "", "tasks": [], "approvals": []})
    assert [r["id"] for r in h.search("agent")] == ["1"]
    assert [r["id"] for r in h.filter("failed")] == ["2"]
    st = h.stats()
    assert st["total"] == 2 and st["by_status"]["done"] == 1


def test_audit_query_and_summary():
    a = AuditLog(_tmp("a.jsonl"))
    a.event("run_started", run="r1")
    a.event("run_started", run="r2")
    a.event("run_completed", run="r1")
    assert len(a.query("run_started")) == 2
    s = a.summary()
    assert s["total"] == 3 and s["by_kind"]["run_started"] == 2


# ---------- Track G: repeat-failure self-learning ----------
def test_analyze_repeat_failures():
    h = RunHistory(_tmp("h.jsonl"))
    for i in range(2):
        h.save({"id": f"f{i}", "goal": "stubborn goal", "status": "failed",
                "result_summary": "", "tasks": [], "approvals": []})
    rf = selflearn.analyze_repeat_failures(h)
    assert rf["repeat_goals"] == 1 and rf["items"][0]["count"] == 2


def test_repeat_failures_in_recommendations():
    h = RunHistory(_tmp("h.jsonl"))
    for i in range(2):
        h.save({"id": f"f{i}", "goal": "stubborn goal", "status": "failed",
                "result_summary": "", "tasks": [], "approvals": []})
    recs = selflearn.recommend(h, AuditLog(_tmp("a.jsonl")))
    assert any(r["area"] == "self-improvement" for r in recs)


def test_insights_includes_repeat_failures():
    snap = selflearn.insights(RunHistory(_tmp("h.jsonl")), AuditLog(_tmp("a.jsonl")))
    assert "repeat_failures" in snap


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
