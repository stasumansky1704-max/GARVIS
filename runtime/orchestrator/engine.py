"""
Orchestrator engine (WORKING MVP facade).

Wires the manual flow end-to-end: ManualPlanner -> TaskRouter (Safety + Approval gates)
-> Worker.run -> ResultMerger -> RunStore. No network, no LLM, no backend wiring.

Usage (isolated):
    orch = Orchestrator(registry, workers)        # workers: {name: Worker instance}
    run = orch.run_manual(goal, tasks, approvals={"t2"})
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from .gates import SafetyGate, ApprovalGate
from .merger import ResultMerger
from .models import Run, TaskSpec
from .planner import ManualPlanner
from .registry import WorkerRegistry
from .router import TaskRouter
from .store import InMemoryRunStore

if TYPE_CHECKING:
    from .workers.base import Worker


class Orchestrator:
    def __init__(self, registry: WorkerRegistry, workers: dict[str, "Worker"],
                 safety: SafetyGate | None = None, approval: ApprovalGate | None = None,
                 store: InMemoryRunStore | None = None) -> None:
        self.registry = registry
        self.workers = workers
        self.safety = safety or SafetyGate()
        self.approval = approval or ApprovalGate()
        self.router = TaskRouter(registry, self.safety, self.approval)
        self.merger = ResultMerger()
        self.store = store or InMemoryRunStore()
        self.planner = ManualPlanner(registry)

    def run_manual(self, goal: str, tasks: list[TaskSpec],
                   approvals: set[str] | None = None) -> Run:
        run_id = uuid.uuid4().hex[:12]
        plan = self.planner.plan(run_id, goal, tasks)
        run = Run(id=run_id, goal=goal)
        results = self.router.dispatch(plan, self.workers, approvals)
        run = self.merger.merge(run, results)
        self.store.save(run)
        return run
