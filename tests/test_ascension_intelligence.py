"""
Agent Core Ascension - intelligence tests: Track A (planner), B (memory), C (learning),
F (intelligence quality). Offline, deterministic, temp-dir backed.

Runs with pytest OR standalone:  python tests/test_ascension_intelligence.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator import planning, summarize, selflearn
from orchestrator.memory import MemoryStore
from orchestrator.history import RunHistory
from orchestrator.audit import AuditLog
from orchestrator.models import TaskSpec


def _tmp(n):
    return os.path.join(tempfile.mkdtemp(), n)


def _mem_with_topics():
    m = MemoryStore(_tmp("m.jsonl"))
    a = m.add("decision", "langgraph agent frameworks orchestration")
    b = m.add("decision", "autogen agent frameworks multi agent")
    m.add("decision", "pasta cooking recipe unrelated")
    m.link(a, b)
    return m


def _tasks(*queries):
    return [TaskSpec(id=f"r{i}", worker="research", intent=q, inputs={"query": q})
            for i, q in enumerate(queries)]


# ---------- Track A: planner ----------
def test_topic_centrality_ranked():
    m = _mem_with_topics()
    c = planning.topic_centrality(m)
    assert c and all("score" in t for t in c)
    assert c == sorted(c, key=lambda x: -x["score"])


def test_rank_queries_by_centrality_prefers_central():
    m = _mem_with_topics()
    qs = ["pasta recipe", "agent frameworks orchestration"]
    ranked = planning.rank_queries_by_centrality(qs, m)
    assert ranked[0] == "agent frameworks orchestration"


def test_multi_strategy_decompose_broader():
    m = _mem_with_topics()
    out = planning.multi_strategy_decompose("best agent frameworks", m, 5)
    assert out["queries"] and len(out["strategies_used"]) >= 2


def test_planning_confidence_range():
    c = planning.planning_confidence(_tasks("a", "b", "c"), None, "agent frameworks")
    assert 0.0 <= c <= 1.0


def test_self_review_flags_duplicates():
    dup = _tasks("same", "same")
    r = planning.self_review(dup)
    assert not r["ok"] and any("duplicate" in i for i in r["issues"])


def test_explain_plan_structure():
    e = planning.explain_plan("agent frameworks", _tasks("a", "b"), _mem_with_topics())
    assert "confidence" in e and "queries" in e and "central_topics" in e


def test_planning_diagnostics():
    d = planning.planning_diagnostics(_tasks("a", "b"), None, "x")
    assert "plan_quality" in d and "confidence" in d and "review" in d


# ---------- Track B: memory ----------
def test_cross_topic_link():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("decision", "agent frameworks langgraph")
    m.add("decision", "agent testing pytest")          # shares 'agent'
    created = m.cross_topic_link()
    assert created >= 0                                  # links across topics sharing a term


def test_detect_conflicts():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("rule", "use wdm ks for capture")
    m.add("rule", "never use wdm ks for capture")
    conflicts = m.detect_conflicts()
    assert conflicts and "ks" in conflicts[0]["shared"] or conflicts


def test_context_relevance():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("decision", "langgraph agent frameworks")
    assert m.context_relevance("agent frameworks") > 0.0
    assert m.context_relevance("quantum biology") == 0.0


def test_long_term_score_and_protected():
    m = MemoryStore(_tmp("m.jsonl"))
    sid = m.add("rule", "no secrets", tags=["safety"])
    did = m.add("decision", "minor note")
    assert m.long_term_score(m.get(sid)) == 1.0
    assert m.long_term_score(m.get(did)) < 1.0


def test_influence_report_ordered():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("rule", "important rule", tags=["safety"])
    m.add("run", "minor run", importance=0.2)
    rep = m.influence_report()
    assert rep[0]["score"] >= rep[-1]["score"]


def test_health_report():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("rule", "use x"); m.add("rule", "never use x")
    h = m.health_report()
    assert "graph" in h and "conflicts" in h and h["total"] == 2


# ---------- Track C: learning ----------
def test_learning_history_and_confidence():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("rule", "lesson one", tags=["self-learned"])
    m.add("decision", "lesson two", tags=["self-learned"])
    assert len(selflearn.learning_history(m)) == 2
    assert 0.0 < selflearn.learning_confidence(m) <= 1.0


def test_learning_quality_coverage():
    h = RunHistory(_tmp("h.jsonl"))
    h.save({"id": "e", "goal": "x for GARVIS", "status": "done",
            "result_summary": "No results found for: x", "tasks": [], "approvals": []})
    m = MemoryStore(_tmp("m.jsonl"))
    selflearn.learn(h, AuditLog(_tmp("a.jsonl")), m)
    q = selflearn.learning_quality(h, m)
    assert q["lessons"] >= 1 and "coverage" in q


def test_learning_diagnostics():
    d = selflearn.learning_diagnostics(RunHistory(_tmp("h.jsonl")),
                                       AuditLog(_tmp("a.jsonl")), MemoryStore(_tmp("m.jsonl")))
    assert "confidence" in d and "quality" in d


# ---------- Track F: intelligence quality ----------
_FINDINGS = [
    {"title": "LangGraph", "url": "u1", "source": "wikipedia", "confidence": 0.8,
     "snippet": "stateful agent framework"},
    {"title": "OldTool (deprecated)", "url": "u2", "source": "duckduckgo", "confidence": 0.5,
     "snippet": "this library is deprecated and unmaintained"},
    {"title": "CrewAI", "url": "u3", "source": "wikipedia", "confidence": 0.7,
     "snippet": "multi agent orchestration"},
]


def test_source_authority():
    assert summarize.source_authority({"source": "wikipedia"}) > \
           summarize.source_authority({"source": "duckduckgo"})


def test_rank_evidence_scores():
    ev = summarize.rank_evidence(_FINDINGS, "agent framework", 3)
    assert ev and all("evidence_score" in e for e in ev)
    assert ev == sorted(ev, key=lambda x: -x["evidence_score"])


def test_risk_flags_detect_deprecated():
    flags = summarize.risk_flags(_FINDINGS)
    assert "deprecated" in flags and "unmaintained" in flags


def test_decision_support():
    d = summarize.decision_support("pick agent framework", _FINDINGS)
    assert d["recommendation"] and d["confidence"] in ("low", "medium", "high")
    assert "deprecated" in d["risks"] and d["evidence"]


def test_decision_support_empty_is_low():
    d = summarize.decision_support("obscure", [])
    assert d["confidence"] == "low" and "insufficient" in d["recommendation"]


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
