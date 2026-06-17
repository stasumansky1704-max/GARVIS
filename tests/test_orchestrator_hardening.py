"""
Hardening + new-component tests for the orchestrator (no network, no LLM, no backend).

LLMPlanner._call_ollama is monkeypatched so NO real Ollama/network is used.
Runs with pytest OR standalone:  python tests/test_orchestrator_hardening.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator.models import TaskSpec, Status, SafetyClass
from orchestrator.registry import WorkerRegistry, WorkerSpec
from orchestrator.gates import SafetyGate, ApprovalGate
from orchestrator.router import TaskRouter
from orchestrator.merger import ResultMerger
from orchestrator.models import Run
from orchestrator.llm_planner import LLMPlanner
from orchestrator.workers.research_worker import ResearchWorker


def _registry():
    r = WorkerRegistry()
    r.register(WorkerSpec(name="research", capabilities=["web_search"], safety_class=SafetyClass.READ))
    r.register(WorkerSpec(name="docs", capabilities=["write_docs"], safety_class=SafetyClass.WRITE))
    return r


# ---------- LLM planner ----------
def _planner_returning(raw: str) -> LLMPlanner:
    p = LLMPlanner(_registry())
    p._call_ollama = lambda system, prompt: raw          # monkeypatch transport
    return p


def test_llm_planner_valid_json_builds_plan():
    raw = json.dumps({"tasks": [
        {"id": "t1", "worker": "research", "intent": "find", "inputs": {"query": "x"}},
        {"id": "t2", "worker": "docs", "intent": "doc", "deps": ["t1"], "needs_approval": True},
    ]})
    plan = _planner_returning(raw).plan("run1", "goal")
    assert [t.id for t in plan.tasks] == ["t1", "t2"]
    assert plan.tasks[1].needs_approval is True


def test_llm_planner_unknown_worker_falls_back_empty():
    raw = json.dumps({"tasks": [{"id": "t1", "worker": "ghost", "intent": "x"}]})
    plan = _planner_returning(raw).plan("run1", "goal")
    assert plan.tasks == []                               # graceful: empty no-op plan


def test_llm_planner_bad_json_uses_manual_fallback_when_given():
    p = _planner_returning("not json at all")
    fb = [TaskSpec(id="t1", worker="research", intent="x", inputs={"query": "q"})]
    plan = p.plan("run1", "goal", fallback_tasks=fb)
    assert [t.id for t in plan.tasks] == ["t1"]           # ManualPlanner fallback


def test_llm_planner_never_executes():
    # plan() returns a Plan, not Envelopes; no worker is invoked.
    raw = json.dumps({"tasks": [{"id": "t1", "worker": "research", "intent": "x"}]})
    plan = _planner_returning(raw).plan("run1", "goal")
    assert hasattr(plan, "tasks") and not hasattr(plan, "results")


# ---------- Research worker (read-only) ----------
def test_research_worker_mock_returns_structured_findings():
    env = ResearchWorker(mock=True).run(TaskSpec(id="t1", worker="research", intent="r",
                                                 inputs={"query": "best tts"}))
    assert env.status == Status.DONE
    for k in ("query", "findings", "sources", "summary", "mock"):
        assert k in env.result
    assert env.result["mock"] is True


def test_research_worker_missing_query_fails():
    env = ResearchWorker(mock=True).run(TaskSpec(id="t1", worker="research", intent="r"))
    assert env.status == Status.FAILED


def test_research_worker_real_mode_blocks_safely():
    env = ResearchWorker(mock=False).run(TaskSpec(id="t1", worker="research", intent="r",
                                                  inputs={"query": "q"}))
    assert env.status == Status.BLOCKED            # real backend intentionally not wired


# ---------- Router resilience ----------
def test_router_unknown_worker_is_failed():
    reg = _registry()
    router = TaskRouter(reg, SafetyGate(), ApprovalGate())
    from orchestrator.models import Plan
    plan = Plan(run_id="r", goal="g", tasks=[TaskSpec(id="t1", worker="ghost", intent="x")])
    res = router.dispatch(plan, workers={})
    assert res["t1"].status == Status.FAILED


def test_router_dependency_cycle_blocks():
    reg = _registry()
    router = TaskRouter(reg, SafetyGate(), ApprovalGate())
    from orchestrator.models import Plan
    plan = Plan(run_id="r", goal="g", tasks=[
        TaskSpec(id="t1", worker="research", intent="x", deps=["t2"]),
        TaskSpec(id="t2", worker="research", intent="x", deps=["t1"]),
    ])
    res = router.dispatch(plan, workers={"research": ResearchWorker(mock=True)})
    assert res["t1"].status == Status.BLOCKED and "cycle" in res["t1"].error.lower()


def test_router_kill_switch_blocks_all():
    reg = _registry()
    router = TaskRouter(reg, SafetyGate(), ApprovalGate())
    router.kill = True
    from orchestrator.models import Plan
    plan = Plan(run_id="r", goal="g", tasks=[TaskSpec(id="t1", worker="research", intent="x")])
    res = router.dispatch(plan, workers={"research": ResearchWorker(mock=True)})
    assert res["t1"].status == Status.BLOCKED and "kill" in res["t1"].error.lower()


# ---------- Merger ----------
def test_merger_empty_results_is_pending():
    run = ResultMerger().merge(Run(id="r", goal="g"), {})
    assert run.status == Status.PENDING


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
