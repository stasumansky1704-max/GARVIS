"""
Agent Core Ascension - systems tests: Track G (metrics), E (advisor/autonomy reporting),
I (agent capability registry), J (factory templates), H (reliability edge cases).
Offline, deterministic, temp-dir backed.

Runs with pytest OR standalone:  python tests/test_ascension_systems.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator import metrics as metricsmod
from orchestrator import advisor, agents, templates, selflearn, planning
from orchestrator.memory import MemoryStore
from orchestrator.history import RunHistory
from orchestrator.audit import AuditLog
from orchestrator.goals import GoalRegistry
from orchestrator.queue import ResearchQueue


def _tmp(n):
    return os.path.join(tempfile.mkdtemp(), n)


def _stores():
    d = tempfile.mkdtemp()
    return (MemoryStore(os.path.join(d, "m.jsonl")), GoalRegistry(os.path.join(d, "g.jsonl")),
            ResearchQueue(os.path.join(d, "q.jsonl")), RunHistory(os.path.join(d, "h.jsonl")),
            AuditLog(os.path.join(d, "a.jsonl")))


# ---------- Track G: metrics ----------
def test_metrics_worker_and_system():
    assert "workers" in metricsmod.worker_metrics()
    assert "ok" in metricsmod.system_health()


def test_metrics_quality_and_execution():
    _, _, _, h, _ = _stores()
    h.save({"id": "1", "goal": "g", "status": "done", "result_summary": "found x",
            "tasks": [], "approvals": []})
    h.save({"id": "2", "goal": "g", "status": "done",
            "result_summary": "No results found for: g", "tasks": [], "approvals": []})
    q = metricsmod.quality_metrics(h)
    assert q["runs"] == 2 and 0.0 <= q["productive_rate"] <= 1.0
    assert metricsmod.execution_metrics(h)["total"] == 2


def test_metrics_dashboard_full():
    mem, goals, queue, h, au = _stores()
    mem.add("decision", "agent frameworks note")
    goals.add("ship"); queue.enqueue("research")
    d = metricsmod.dashboard(h, mem, goals, queue, au)
    for k in ("system_health", "worker", "planner", "memory", "execution", "quality",
              "goals", "queue", "learning", "autonomy"):
        assert k in d, f"missing {k}"
    assert "healthy" in d


def test_autonomy_metrics_counts_events():
    mem, goals, queue, h, au = _stores()
    au.event("loop_cycle_completed", cycle=0)
    au.event("loop_schedules_enqueued", count=1)
    m = metricsmod.autonomy_metrics(h, queue, au)
    assert m["loop_cycles_run"] == 1 and m["schedule_enqueue_events"] == 1


# ---------- Track E: advisor ----------
def test_suggest_goals_from_empty_runs():
    mem, goals, queue, h, au = _stores()
    h.save({"id": "e", "goal": "best agents for GARVIS", "status": "done",
            "result_summary": "No results found for: best agents for GARVIS",
            "tasks": [], "approvals": []})
    sg = advisor.suggest_goals(h, mem)
    assert sg and all("goal" in s and "reason" in s for s in sg)
    assert "garvis" not in sg[0]["goal"].lower()


def test_next_steps_actionable():
    mem, goals, queue, h, au = _stores()
    queue.enqueue("due item")
    goals.add("ready goal", priority=1)
    steps = advisor.next_steps(h, au, mem, goals, queue)
    assert any("due queue" in s for s in steps)


def test_autonomy_report_structure():
    mem, goals, queue, h, au = _stores()
    rep = advisor.autonomy_report(h, au, mem, goals, queue)
    assert "suggested_goals" in rep and "next_steps" in rep and "learning_confidence" in rep


# ---------- Track I: agent capability registry ----------
def test_registry_has_core_capabilities():
    reg = agents.build_default_registry()
    assert len(reg) >= 10
    names = {c.name for c in reg.list()}
    assert {"research", "plan", "learn", "loop", "memory_graph"} <= names


def test_registry_by_kind_and_kinds():
    reg = agents.build_default_registry()
    assert reg.by_kind("planning") and reg.by_kind("autonomy")
    assert set(reg.kinds()) <= set(agents.KINDS)


def test_registry_rejects_bad_kind():
    reg = agents.CapabilityRegistry()
    try:
        reg.register(agents.AgentCapability("x", "not-a-kind", "m:f"))
        assert False
    except ValueError:
        pass


def test_registry_catalog_shape():
    reg = agents.build_default_registry()
    cat = reg.catalog()
    assert cat and all({"name", "kind", "ref", "safety_class"} <= set(c) for c in cat)


# ---------- Track J: factory templates ----------
def test_research_template():
    t = templates.research_template("best agent frameworks", 4)
    assert t["kind"] == "research" and t["read_only"] and len(t["subqueries"]) <= 4


def test_proposal_and_review_templates():
    p = templates.proposal_template("goal")
    r = templates.review_template("subject")
    assert "Recommendation" in p["sections"] and r["checklist"]


def test_agent_template_uses_registry():
    a = templates.agent_template("research-bot", "research")
    assert a["capabilities"] and not a["unknown_capabilities"]


def test_agent_template_flags_unknown():
    a = templates.agent_template("x", "research", capabilities=["research", "nope"])
    assert "nope" in a["unknown_capabilities"] and "research" in a["capabilities"]


def test_factory_readiness_ready():
    fr = templates.factory_readiness()
    assert fr["ready"] is True and fr["missing_kinds"] == []
    assert fr["capabilities_total"] >= 10 and len(fr["templates"]) >= 6


def test_memory_and_learning_templates():
    assert templates.memory_template("agent frameworks")["protected_layer"] == "rule"
    assert "empty_results" in templates.learning_template()["signals"]


# ---------- Track H: reliability / edge cases ----------
def test_planning_confidence_empty_plan():
    assert planning.planning_confidence([], None, "") == planning.planning_confidence([], None, "")


def test_decision_support_handles_none():
    from orchestrator import summarize
    d = summarize.decision_support("g", None)
    assert d["confidence"] == "low"


def test_metrics_dashboard_partial_stores():
    out = metricsmod.dashboard()                     # no stores
    assert "system_health" in out and "worker" in out


def test_suggest_goals_empty_history():
    mem, goals, queue, h, au = _stores()
    assert advisor.suggest_goals(h, mem) == []


def test_memory_detect_conflicts_none_when_clean():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("rule", "use approval gates")
    m.add("decision", "research agent frameworks")
    assert m.detect_conflicts() == []


def test_learning_confidence_empty():
    assert selflearn.learning_confidence(MemoryStore(_tmp("m.jsonl"))) == 0.0


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
