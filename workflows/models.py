"""Workflow Pydantic models for GARVIS.

Defines the core data structures for the governed workflow runtime:
- WorkflowDefinition: A workflow template, governance-bound and operator-created
- WorkflowStep: A single step within a workflow
- WorkflowInstance: A running execution of a workflow
- WorkflowStepResult: The outcome of executing one step
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from models.governance import GovernanceCheckResult

logger = logging.getLogger("garvis.workflows.models")


# ---------------------------------------------------------------------------
# WorkflowStep — a single step in a workflow
# ---------------------------------------------------------------------------


class WorkflowStep(BaseModel):
    """A single step in a workflow.

    Each step declares its action type, parameters, governance checks,
    timeout, retry policy, and dependencies on other steps.
    """

    step_id: str
    name: str
    description: str
    action_type: str  # "ollama_inference", "memory_store", "memory_retrieve", "governance_check", "audit_log", "external_call"
    parameters: dict = Field(default_factory=dict)
    governance_checks: list[str] = Field(default_factory=list)
    timeout_seconds: int = 30
    retry_count: int = 0
    depends_on: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# WorkflowStepResult — result of executing a single step
# ---------------------------------------------------------------------------


class WorkflowStepResult(BaseModel):
    """Result of executing a single workflow step.

    Tracks the execution status, timing, output, governance checks,
    and any error that occurred.
    """

    step_id: str
    status: str = "pending"  # pending | executing | completed | failed | skipped
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    result: dict = Field(default_factory=dict)
    governance_checks: list[GovernanceCheckResult] = Field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# WorkflowDefinition — a defined workflow template
# ---------------------------------------------------------------------------


class WorkflowDefinition(BaseModel):
    """A defined workflow template — operator-created, governance-bound.

    A workflow definition is the blueprint for workflow execution.
    It is created by an operator, validated by governance, and only
    activated after passing all governance checks.
    """

    workflow_id: str
    name: str
    description: str
    project_id: str
    risk_level: str  # low | medium | high | critical
    steps: list[WorkflowStep]
    required_approval: str  # self | operator | operator_explicit | operator_multi
    governance_schemas: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = ""
    active: bool = False

    def get_step(self, step_id: str) -> WorkflowStep | None:
        """Get a step by its ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_ordered_steps(self) -> list[WorkflowStep]:
        """Return steps in dependency order (topological sort).

        Steps with no dependencies come first. Steps that depend on
        others come after their dependencies.
        """
        ordered: list[WorkflowStep] = []
        visited: set[str] = set()

        def visit(step: WorkflowStep) -> None:
            if step.step_id in visited:
                return
            visited.add(step.step_id)
            # Visit dependencies first
            for dep_id in step.depends_on:
                dep_step = self.get_step(dep_id)
                if dep_step:
                    visit(dep_step)
            ordered.append(step)

        for s in self.steps:
            visit(s)

        return ordered

    def validate_dependencies(self) -> list[str]:
        """Validate that all dependency references exist.

        Returns a list of error messages for missing dependencies.
        """
        step_ids = {s.step_id for s in self.steps}
        errors: list[str] = []
        for step in self.steps:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    errors.append(
                        f"Step '{step.step_id}' depends on unknown step '{dep_id}'"
                    )
        return errors


# ---------------------------------------------------------------------------
# WorkflowInstance — a running instance of a workflow
# ---------------------------------------------------------------------------


class WorkflowInstance(BaseModel):
    """A running instance of a workflow — created after approval.

    An instance represents a single execution of a workflow definition.
    It tracks execution progress, step results, governance context,
    and timing. Instances are immutable after completion.
    """

    instance_id: UUID = Field(default_factory=uuid4)
    workflow_id: str
    project_id: str
    operator_id: str
    status: str = "pending"  # pending | approved | executing | completed | failed | rolled_back
    approval_id: str = ""
    steps_executed: list[WorkflowStepResult] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    governance_context: list[str] = Field(default_factory=list)
    trace_id: UUID = Field(default_factory=uuid4)
    parameters: dict = Field(default_factory=dict)

    def get_step_result(self, step_id: str) -> WorkflowStepResult | None:
        """Get the result for a specific step."""
        for result in self.steps_executed:
            if result.step_id == step_id:
                return result
        return None

    def is_step_completed(self, step_id: str) -> bool:
        """Check if a step has been completed."""
        result = self.get_step_result(step_id)
        return result is not None and result.status == "completed"

    def all_steps_succeeded(self) -> bool:
        """Check if all executed steps succeeded."""
        if not self.steps_executed:
            return False
        return all(r.status == "completed" for r in self.steps_executed)

    def has_failed_steps(self) -> bool:
        """Check if any step failed."""
        return any(r.status == "failed" for r in self.steps_executed)

    def steps_completed_count(self) -> int:
        """Count completed steps."""
        return sum(1 for r in self.steps_executed if r.status == "completed")

    def steps_failed_count(self) -> int:
        """Count failed steps."""
        return sum(1 for r in self.steps_executed if r.status == "failed")

    def model_post_init(self, __context: Any) -> None:
        """Ensure started_at is set when status transitions to executing."""
        if self.status == "executing" and self.started_at is None:
            self.started_at = datetime.now(timezone.utc)
