"""
Safety + Approval gates (INERT SCAFFOLDING).

SafetyGate encodes the project's HARD rules as data so they are testable and impossible
for a planner to bypass. ApprovalGate is a stub for human-in-the-loop. No side effects.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import TaskSpec, SafetyClass

# Hard, non-negotiable rules (mirror the sprint safety boundaries + decision memory).
FORBIDDEN_ACTIONS: tuple[str, ...] = (
    "use_wdm_ks",                 # caused BugCheck 0x10D / BSOD
    "run_old_voice_client",
    "merge_pull_request",         # requires explicit human approval
    "delete_branch",
    "print_secret",
    "commit_secret",
    "change_backend_runtime",     # requires approval
    "change_docker",              # requires approval
    "change_gpu_config",          # requires approval
    "change_dashboard_prod",      # requires approval
    "install_kernel_driver",
)

# Safety classes that always require human approval before execution.
APPROVAL_REQUIRED_CLASSES = (SafetyClass.WRITE, SafetyClass.EXTERNAL, SafetyClass.DANGEROUS)


@dataclass
class GateDecision:
    allowed: bool
    reason: str = ""


class SafetyGate:
    """Pure-policy check run BEFORE every tool call. Cannot be bypassed by the planner."""

    def __init__(self, forbidden: tuple[str, ...] = FORBIDDEN_ACTIONS):
        self.forbidden = tuple(forbidden)

    def check_action(self, action: str) -> GateDecision:
        if action in self.forbidden:
            return GateDecision(False, f"forbidden action: {action}")
        return GateDecision(True)

    def check_task(self, task: TaskSpec) -> GateDecision:
        for a in task.inputs.get("actions", []):
            d = self.check_action(a)
            if not d.allowed:
                return d
        return GateDecision(True)


class ApprovalGate:
    """
    Human-in-the-loop gate. MVP = manual mode: a task that requires approval runs only if
    its id is in `approved`; default-deny otherwise. Future impl persists pending
    approvals + waits on mission_control.
    """

    def __init__(self, approved: set[str] | None = None):
        self.approved: set[str] = set(approved or [])

    def requires_approval(self, task: TaskSpec, safety_class: SafetyClass) -> bool:
        return task.needs_approval or safety_class in APPROVAL_REQUIRED_CLASSES

    def decide(self, task: TaskSpec, safety_class: SafetyClass) -> GateDecision:
        if not self.requires_approval(task, safety_class):
            return GateDecision(True, "no approval required")
        if task.id in self.approved:
            return GateDecision(True, "explicitly approved")
        return GateDecision(False, "awaiting human approval")
