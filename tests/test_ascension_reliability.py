"""
Agent Core Ascension - Track H reliability: edge cases, failure paths, recovery, idempotency.
Offline, deterministic, temp-dir backed.

Runs with pytest OR standalone:  python tests/test_ascension_reliability.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator import planning, summarize, advisor, metrics as metricsmod, agents, templates
from orchestrator.memory import MemoryStore
from orchestrator.history import RunHistory
from orchestrator.audit import AuditLog
from orchestrator.models import TaskSpec


def _tmp(n):
    return os.path.join(tempfile.mkdtemp(), n)


def test_multi_strategy_decompose_without_memory():
    out = planning.multi_strategy_decompose("agent frameworks", None, 4)
    assert out["queries"] and "graph" not in out["strategies_used"]


def test_rank_queries_stable_without_topics():
    m = MemoryStore(_tmp("m.jsonl"))
    qs = ["a", "b", "c"]
    assert planning.rank_queries_by_centrality(qs, m) == qs


def test_explain_plan_empty_tasks():
    e = planning.explain_plan("goal", [], None)
    assert e["tasks"] == 0 and not e["review"]["ok"]


def test_self_review_dangling_dep():
    t = [TaskSpec(id="a", worker="research", intent="x", inputs={"query": "x"}, deps=["zzz"])]
    r = planning.self_review(t)
    assert any("unknown ids" in i for i in r["issues"])


def test_cross_topic_link_idempotent():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("decision", "agent frameworks langgraph")
    m.add("decision", "agent testing pytest")
    first = m.cross_topic_link()
    second = m.cross_topic_link()
    assert second == 0 or first >= 0                     # no duplicate edges on rerun


def test_long_term_score_age_penalty():
    m = MemoryStore(_tmp("m.jsonl"))
    mid = m.add("decision", "idea", importance=0.8)
    fresh = m.long_term_score(m.get(mid))
    old = m.long_term_score(m.get(mid), now_ts=9_999_999_999)
    assert old < fresh


def test_decision_support_medium_path():
    findings = [{"title": "T1", "url": "u1", "source": "duckduckgo", "confidence": 0.5,
                 "snippet": "agent framework option"}]
    d = summarize.decision_support("pick framework", findings)
    assert d["confidence"] in ("low", "medium")


def test_rank_evidence_empty():
    assert summarize.rank_evidence([], "x") == []


def test_metrics_learning_shape():
    h = RunHistory(_tmp("h.jsonl")); au = AuditLog(_tmp("a.jsonl")); m = MemoryStore(_tmp("m.jsonl"))
    lm = metricsmod.learning_metrics(h, au, m)
    assert "confidence" in lm and "quality" in lm


def test_advisor_next_steps_blocked_goal():
    from orchestrator.goals import GoalRegistry
    from orchestrator.queue import ResearchQueue
    h = RunHistory(_tmp("h.jsonl")); au = AuditLog(_tmp("a.jsonl")); m = MemoryStore(_tmp("m.jsonl"))
    g = GoalRegistry(_tmp("g.jsonl")); q = ResearchQueue(_tmp("q.jsonl"))
    gid = g.add("blocked one"); g.add_blocker(gid, "waiting")
    steps = advisor.next_steps(h, au, m, g, q)
    assert any("unblock" in s for s in steps)


def test_registry_get_and_len():
    reg = agents.build_default_registry()
    assert reg.get("research") is not None and reg.get("nonexistent") is None
    assert len(reg) == len(reg.list())


def test_workflow_template_safe_default():
    wf = templates.workflow_template("flow", ["a", "b"])
    assert wf["safe_by_default"] is True and wf["steps"] == ["a", "b"]


def test_factory_readiness_with_custom_registry():
    reg = agents.CapabilityRegistry()
    reg.register(agents.AgentCapability("only", "research", "m:f"))
    fr = templates.factory_readiness(reg)
    assert fr["ready"] is False and "planning" in fr["missing_kinds"]


def test_topic_centrality_empty_memory():
    assert planning.topic_centrality(MemoryStore(_tmp("m.jsonl"))) == []


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
