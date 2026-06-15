"""Task router (INERT SCAFFOLDING). Dispatches ready tasks within budgets + kill switch."""
from __future__ import annotations

from .gates import SafetyGate, ApprovalGate
from .models import Plan, Envelope
from .registry import WorkerRegistry


class TaskRouter:
    def __init__(self, registry: WorkerRegistry, safety: SafetyGate,
                 approval: ApprovalGate) -> None:
        self.registry = registry
        self.safety = safety
        self.approval = approval
        self.kill = False                      # global kill switch (placeholder)

    def dispatch(self, plan: Plan, budget: dict | None = None) -> dict[str, Envelope]:
        # Real impl (T11): for each task whose deps are satisfied, run SafetyGate.check_task,
        # then ApprovalGate if write/external, then invoke the worker; enforce budgets; honor
        # self.kill; collect Envelopes. Idempotent tasks retry with backoff.
        raise NotImplementedError("TaskRouter.dispatch: implement per T11")
