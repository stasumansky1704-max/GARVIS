"""
Orchestrator engine (facade).

Wires the flow end-to-end: Planner -> TaskRouter (Safety + Approval gates) -> Worker.run
-> ResultMerger -> RunStore (+ optional RunHistory). No backend wiring, no network of its
own (workers do their own read-only I/O). Two entrypoints:
  - run_manual(goal, tasks, ...)         : caller supplies the task list
  - run_goal(goal, planner=..., ...)     : a planner produces the task graph
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from .gates import SafetyGate, ApprovalGate
from .merger import ResultMerger
from .models import Run, Plan, TaskSpec
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

    def _execute(self, run_id: str, goal: str, plan: Plan,
                 approvals: set[str] | None, history) -> Run:
        run = Run(id=run_id, goal=goal)
        results = self.router.dispatch(plan, self.workers, approvals)
        run = self.merger.merge(run, results)
        self.store.save(run)
        if history is not None:
            from .history import run_to_record
            history.save(run_to_record(run, approvals))
        return run

    def run_manual(self, goal: str, tasks: list[TaskSpec],
                   approvals: set[str] | None = None, history=None) -> Run:
        run_id = uuid.uuid4().hex[:12]
        plan = self.planner.plan(run_id, goal, tasks)
        return self._execute(run_id, goal, plan, approvals, history)

    def run_goal(self, goal: str, planner=None, fallback_tasks: list[TaskSpec] | None = None,
                 approvals: set[str] | None = None, history=None) -> Run:
        run_id = uuid.uuid4().hex[:12]
        plan: Plan
        if planner is not None and hasattr(planner, "plan"):
            try:
                plan = planner.plan(run_id, goal, fallback_tasks=fallback_tasks)
            except TypeError:                       # planner without fallback_tasks kw
                plan = self.planner.plan(run_id, goal, fallback_tasks or [])
        else:
            plan = self.planner.plan(run_id, goal, fallback_tasks or [])
        if not plan.tasks and fallback_tasks:       # graceful: never run an empty plan
            plan = self.planner.plan(run_id, goal, fallback_tasks)
        return self._execute(run_id, goal, plan, approvals, history)
