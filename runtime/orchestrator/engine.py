"""
Orchestrator engine (facade).

Flow: Planner -> TaskRouter (Safety + Approval gates, budgets) -> Worker.run ->
ResultMerger -> RunStore (+ optional RunHistory + AuditLog). Enforces a conservative
RunBudget and an env kill switch (GARVIS_ORCHESTRATOR_DISABLED=1). No backend wiring.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .gates import SafetyGate, ApprovalGate
from .merger import ResultMerger
from .models import Run, Plan, TaskSpec, Status
from .planner import ManualPlanner
from .registry import WorkerRegistry
from .router import TaskRouter
from .store import InMemoryRunStore

if TYPE_CHECKING:
    from .workers.base import Worker

KILL_ENV = "GARVIS_ORCHESTRATOR_DISABLED"


def is_disabled() -> bool:
    return os.getenv(KILL_ENV, "").strip().lower() in ("1", "true", "yes", "on")


@dataclass
class RunBudget:
    max_tasks: int = 8
    max_findings: int = 5
    max_external_requests: int = 12
    max_seconds: float = 120.0

    @classmethod
    def from_config(cls, cfg: dict) -> "RunBudget":
        lim = cfg.get("limits", {})
        return cls(max_tasks=lim.get("max_tasks", 8),
                   max_findings=lim.get("max_findings", 5),
                   max_external_requests=lim.get("max_external_requests", 12),
                   max_seconds=float(lim.get("max_seconds", 120)))


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

    def _apply_budget(self, plan: Plan, budget: RunBudget) -> Plan:
        plan.tasks = plan.tasks[: budget.max_tasks]          # cap plan size
        for w in self.workers.values():                      # per-run worker limits
            if hasattr(w, "request_budget"):
                w.request_budget = budget.max_external_requests
            if hasattr(w, "max_findings") and budget.max_findings:
                w.max_findings = budget.max_findings
        return plan

    def _execute(self, run_id, goal, plan, approvals, history, budget, audit) -> Run:
        budget = budget or RunBudget()
        self.router.kill = False                             # reset per run
        if audit is not None:
            audit.event("run_started", run=run_id, goal=goal, planned_tasks=len(plan.tasks))
        plan = self._apply_budget(plan, budget)
        run = Run(id=run_id, goal=goal)
        if is_disabled():                                    # env kill switch
            run.status = Status.BLOCKED
            if audit is not None:
                audit.event("run_blocked", run=run_id, reason="GARVIS_ORCHESTRATOR_DISABLED")
            self.store.save(run)
            return run
        results = self.router.dispatch(plan, self.workers, approvals,
                                       max_seconds=budget.max_seconds, audit=audit)
        run = self.merger.merge(run, results)
        self.store.save(run)
        if history is not None:
            from .history import run_to_record
            history.save(run_to_record(run, approvals))
        if audit is not None:
            audit.event("run_completed", run=run_id,
                        status=getattr(run.status, "value", str(run.status)))
        return run

    def run_manual(self, goal, tasks, approvals=None, history=None,
                   budget: RunBudget | None = None, audit=None) -> Run:
        run_id = uuid.uuid4().hex[:12]
        plan = self.planner.plan(run_id, goal, tasks)
        return self._execute(run_id, goal, plan, approvals, history, budget, audit)

    def run_goal(self, goal, planner=None, fallback_tasks=None, approvals=None,
                 history=None, budget: RunBudget | None = None, audit=None,
                 memory_context: dict | None = None) -> Run:
        run_id = uuid.uuid4().hex[:12]
        plan: Plan
        if planner is not None and hasattr(planner, "plan"):
            try:
                plan = planner.plan(run_id, goal, memory=memory_context,
                                    fallback_tasks=fallback_tasks)
            except TypeError:
                plan = self.planner.plan(run_id, goal, fallback_tasks or [])
        else:
            plan = self.planner.plan(run_id, goal, fallback_tasks or [])
        if not plan.tasks and fallback_tasks:
            plan = self.planner.plan(run_id, goal, fallback_tasks)
        return self._execute(run_id, goal, plan, approvals, history, budget, audit)
