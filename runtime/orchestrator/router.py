"""
Task router. WORKING MVP: dispatch ready tasks (deps satisfied) through the Safety Gate
then the Approval Gate, then invoke the worker. No network, no backend wiring — workers
run in their own (inert) implementations. Honors a kill switch.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .gates import SafetyGate, ApprovalGate
from .models import Plan, Envelope, Status
from .registry import WorkerRegistry

if TYPE_CHECKING:
    from .workers.base import Worker


class TaskRouter:
    def __init__(self, registry: WorkerRegistry, safety: SafetyGate,
                 approval: ApprovalGate) -> None:
        self.registry = registry
        self.safety = safety
        self.approval = approval
        self.kill = False                       # global kill switch

    def _run_one(self, task, workers: dict[str, "Worker"]) -> Envelope:
        spec = self.registry.get(task.worker)
        if spec is None:
            return Envelope(task.id, Status.FAILED, error=f"unknown worker {task.worker!r}")
        sd = self.safety.check_task(task)        # pre-call policy (cannot be bypassed)
        if not sd.allowed:
            return Envelope(task.id, Status.BLOCKED, error=f"safety: {sd.reason}")
        ad = self.approval.decide(task, spec.safety_class)
        if not ad.allowed:
            return Envelope(task.id, Status.BLOCKED, error=f"approval: {ad.reason}")
        worker = workers.get(task.worker)
        if worker is None:
            return Envelope(task.id, Status.FAILED, error=f"no worker impl for {task.worker!r}")
        try:
            return worker.run(task)
        except Exception as exc:                 # never let a worker crash the run
            return Envelope(task.id, Status.FAILED, error=f"{type(exc).__name__}: {exc}")

    def dispatch(self, plan: Plan, workers: dict[str, "Worker"],
                 approvals: set[str] | None = None) -> dict[str, Envelope]:
        if approvals:
            self.approval.approved |= set(approvals)
        results: dict[str, Envelope] = {}
        done: set[str] = set()
        remaining = list(plan.tasks)
        progressed = True
        while remaining and progressed and not self.kill:
            progressed = False
            for task in list(remaining):
                if not all(d in done for d in task.deps):
                    continue                     # deps not satisfied yet
                env = self._run_one(task, workers)
                results[task.id] = env
                remaining.remove(task)
                progressed = True
                if env.status == Status.DONE:
                    done.add(task.id)
        for task in remaining:                   # deps blocked/failed or kill switch hit
            results[task.id] = Envelope(task.id, Status.BLOCKED,
                                        error="not run (dependency blocked or kill switch)")
        return results
