"""
Isolated orchestrator MVP tests. No network, no LLM, no audio, no backend wiring.

Runs with pytest OR standalone:
    python tests/test_orchestrator_mvp.py
"""
from __future__ import annotations

import os
import sys

# add repo's runtime/ to path so `import orchestrator...` works without install
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "runtime"))

from orchestrator.gates import SafetyGate, ApprovalGate
from orchestrator.registry import WorkerRegistry
from orchestrator.models import TaskSpec, SafetyClass, Status
from orchestrator.engine import Orchestrator
from orchestrator.workers.docs_worker import DocsWorker
from orchestrator.workers.research_worker import ResearchWorker


def _orch() -> Orchestrator:
    docs, research = DocsWorker(), ResearchWorker()
    reg = WorkerRegistry()
    reg.register(docs.spec)
    reg.register(research.spec)
    return Orchestrator(reg, {docs.spec.name: docs, research.spec.name: research})


def test_safety_gate_blocks_forbidden():
    sg = SafetyGate()
    assert not sg.check_action("use_wdm_ks").allowed
    assert not sg.check_action("merge_pull_request").allowed
    assert not sg.check_action("delete_branch").allowed
    assert sg.check_action("summarize_text").allowed


def test_safety_gate_blocks_task_with_forbidden_action():
    sg = SafetyGate()
    t = TaskSpec(id="x", worker="docs", intent="bad", inputs={"actions": ["use_wdm_ks"]})
    assert not sg.check_task(t).allowed


def test_registry_register_and_get():
    reg = WorkerRegistry()
    reg.register(DocsWorker().spec)
    assert len(reg) == 1
    assert reg.get("docs") is not None
    assert reg.get("nope") is None


def test_approval_required_for_write_not_for_read():
    ag = ApprovalGate()
    write_task = TaskSpec(id="w", worker="docs", intent="write")
    read_task = TaskSpec(id="r", worker="research", intent="read")
    assert ag.requires_approval(write_task, SafetyClass.WRITE)
    assert not ag.requires_approval(read_task, SafetyClass.READ)
    assert not ag.decide(write_task, SafetyClass.WRITE).allowed          # default-deny
    ag.approved.add("w")
    assert ag.decide(write_task, SafetyClass.WRITE).allowed              # explicit approve


def test_end_to_end_blocks_unapproved_write():
    orch = _orch()
    tasks = [
        TaskSpec(id="t1", worker="research", intent="r", inputs={"query": "q"}),
        TaskSpec(id="t2", worker="docs", intent="w", inputs={"title": "d"},
                 deps=["t1"], needs_approval=True),
    ]
    run = orch.run_manual("goal", tasks)                                 # no approvals
    assert run.results["t1"].status == Status.DONE                       # read ran
    assert run.results["t2"].status == Status.BLOCKED                    # write blocked
    assert run.status == Status.BLOCKED


def test_end_to_end_runs_with_approval():
    orch = _orch()
    tasks = [
        TaskSpec(id="t1", worker="research", intent="r", inputs={"query": "q"}),
        TaskSpec(id="t2", worker="docs", intent="w", inputs={"title": "d"},
                 deps=["t1"], needs_approval=True),
    ]
    run = orch.run_manual("goal", tasks, approvals={"t2"})
    assert run.results["t1"].status == Status.DONE
    assert run.results["t2"].status == Status.DONE
    assert run.status == Status.DONE


def test_dependency_blocked_when_parent_blocked():
    orch = _orch()
    # t2 depends on t1; t1 needs approval and is NOT approved -> t1 blocked -> t2 not run
    tasks = [
        TaskSpec(id="t1", worker="docs", intent="w", inputs={"title": "a"}, needs_approval=True),
        TaskSpec(id="t2", worker="research", intent="r", inputs={"query": "q"}, deps=["t1"]),
    ]
    run = orch.run_manual("goal", tasks)
    assert run.results["t1"].status == Status.BLOCKED
    assert run.results["t2"].status == Status.BLOCKED


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); passed += 1
    print(f"\n{passed}/{len(fns)} tests passed")
    return 0 if passed == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
