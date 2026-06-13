"""Workflow Registry — workflows/registry.py

Registry of all defined workflows.

Workflows are registered by operators, validated by governance,
and activated only after passing governance checks.
Only activated workflows can be proposed for execution.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from models.governance import GovernanceCheckResult, GovernanceViolation
from workflows.models import WorkflowDefinition

logger = logging.getLogger("garvis.workflows.registry")


# ---------------------------------------------------------------------------
# WorkflowRegistry — registry of all defined workflows
# ---------------------------------------------------------------------------


class WorkflowRegistry:
    """Registry of all defined workflows.

    Workflows are registered by operators, validated by governance,
    and activated only after passing governance checks.

    Key operations:
    - register: Add a new workflow (starts inactive)
    - activate: Enable a workflow after governance validation
    - deactivate: Soft-disable a workflow
    - validate: Run full governance validation on a workflow
    """

    # Valid risk levels (must match WorkflowApprovalFramework)
    VALID_RISK_LEVELS: set[str] = {"low", "medium", "high", "critical"}

    # Valid approval levels
    VALID_APPROVAL_LEVELS: set[str] = {
        "self",
        "operator",
        "operator_explicit",
        "operator_multi",
    }

    # Valid action types for workflow steps
    VALID_ACTION_TYPES: set[str] = {
        "ollama_inference",
        "memory_store",
        "memory_retrieve",
        "governance_check",
        "audit_log",
        "external_call",
    }

    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._registration_log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        definition: WorkflowDefinition,
        operator_id: str,
    ) -> WorkflowDefinition:
        """Register a new workflow definition.

        Validates against governance before registration.
        Workflow starts as inactive — requires governance validation.

        Args:
            definition: The workflow definition to register.
            operator_id: The operator registering the workflow.

        Returns:
            The registered workflow definition.

        Raises:
            ValueError: If validation fails.
        """
        # Validate the definition structure
        errors = self._validate_structure(definition)
        if errors:
            raise ValueError(
                f"Workflow validation failed: {'; '.join(errors)}"
            )

        # Set metadata
        definition.created_by = operator_id
        definition.active = False  # Always start inactive

        # Store
        self._workflows[definition.workflow_id] = definition

        # Log registration
        log_entry = {
            "action": "registered",
            "workflow_id": definition.workflow_id,
            "workflow_name": definition.name,
            "operator_id": operator_id,
            "project_id": definition.project_id,
            "risk_level": definition.risk_level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._registration_log.append(log_entry)

        logger.info(
            "Workflow '%s' (id=%s) registered by operator '%s' for project '%s' "
            "(risk=%s, steps=%d, status=INACTIVE)",
            definition.name,
            definition.workflow_id,
            operator_id,
            definition.project_id,
            definition.risk_level,
            len(definition.steps),
        )

        return definition

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self, workflow_id: str, operator_id: str) -> bool:
        """Activate a workflow after governance validation.

        Only activated workflows can be proposed for execution.
        Activation requires the workflow to pass governance validation.

        Args:
            workflow_id: The workflow to activate.
            operator_id: The operator activating the workflow.

        Returns:
            True if activation succeeded, False otherwise.
        """
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            logger.warning(
                "Activation failed: workflow '%s' not found", workflow_id
            )
            return False

        # Run governance validation
        check_results = self.validate(workflow_id)
        failed_checks = [c for c in check_results if not c.passed]
        if failed_checks:
            logger.warning(
                "Activation failed: workflow '%s' has %d failed governance checks",
                workflow_id,
                len(failed_checks),
            )
            return False

        # Activate
        workflow.active = True

        # Log activation
        self._registration_log.append({
            "action": "activated",
            "workflow_id": workflow_id,
            "operator_id": operator_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "governance_checks_passed": len(check_results),
        })

        logger.info(
            "Workflow '%s' (id=%s) ACTIVATED by operator '%s' "
            "(%d governance checks passed)",
            workflow.name,
            workflow_id,
            operator_id,
            len(check_results),
        )

        return True

    def deactivate(self, workflow_id: str, operator_id: str) -> bool:
        """Deactivate a workflow (soft-disable, not delete).

        A deactivated workflow cannot be proposed for execution.
        It remains in the registry and can be reactivated.

        Args:
            workflow_id: The workflow to deactivate.
            operator_id: The operator deactivating the workflow.

        Returns:
            True if deactivation succeeded, False otherwise.
        """
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            logger.warning(
                "Deactivation failed: workflow '%s' not found", workflow_id
            )
            return False

        workflow.active = False

        self._registration_log.append({
            "action": "deactivated",
            "workflow_id": workflow_id,
            "operator_id": operator_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(
            "Workflow '%s' (id=%s) DEACTIVATED by operator '%s'",
            workflow.name,
            workflow_id,
            operator_id,
        )

        return True

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get(self, workflow_id: str) -> WorkflowDefinition | None:
        """Get a workflow definition by ID.

        Args:
            workflow_id: The workflow identifier.

        Returns:
            The workflow definition, or None if not found.
        """
        return self._workflows.get(workflow_id)

    def list(
        self,
        project_id: str | None = None,
        active_only: bool = True,
    ) -> list[WorkflowDefinition]:
        """List workflows with optional filtering.

        Args:
            project_id: Filter by project (None = all projects).
            active_only: If True, only return active workflows.

        Returns:
            List of workflow definitions matching the filters.
        """
        workflows = list(self._workflows.values())

        if project_id is not None:
            workflows = [w for w in workflows if w.project_id == project_id]

        if active_only:
            workflows = [w for w in workflows if w.active]

        return sorted(workflows, key=lambda w: w.created_at)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, workflow_id: str) -> list[GovernanceCheckResult]:
        """Run full governance validation on a workflow.

        Checks:
        1. Risk level validity
        2. Approval level validity
        3. Step action types validity
        4. Step dependency validity (no cycles, all refs exist)
        5. Workflow has at least one step
        6. All governance schemas referenced exist

        Args:
            workflow_id: The workflow to validate.

        Returns:
            List of governance check results.
        """
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            return [
                GovernanceCheckResult(
                    schema_id="workflow_validation",
                    policy_id="workflow_exists",
                    passed=False,
                    violation=GovernanceViolation(
                        schema_id="workflow_validation",
                        policy_id="workflow_exists",
                        severity="critical",
                        description=f"Workflow '{workflow_id}' not found in registry",
                    ),
                )
            ]

        results: list[GovernanceCheckResult] = []

        # Check 1: Risk level
        results.append(
            GovernanceCheckResult(
                schema_id="workflow_validation",
                policy_id="valid_risk_level",
                passed=workflow.risk_level in self.VALID_RISK_LEVELS,
                violation=(
                    GovernanceViolation(
                        schema_id="workflow_validation",
                        policy_id="valid_risk_level",
                        severity="critical",
                        description=(
                            f"Invalid risk level '{workflow.risk_level}'. "
                            f"Must be one of: {self.VALID_RISK_LEVELS}"
                        ),
                    )
                    if workflow.risk_level not in self.VALID_RISK_LEVELS
                    else None
                ),
            )
        )

        # Check 2: Approval level
        results.append(
            GovernanceCheckResult(
                schema_id="workflow_validation",
                policy_id="valid_approval_level",
                passed=workflow.required_approval in self.VALID_APPROVAL_LEVELS,
                violation=(
                    GovernanceViolation(
                        schema_id="workflow_validation",
                        policy_id="valid_approval_level",
                        severity="critical",
                        description=(
                            f"Invalid approval level '{workflow.required_approval}'. "
                            f"Must be one of: {self.VALID_APPROVAL_LEVELS}"
                        ),
                    )
                    if workflow.required_approval not in self.VALID_APPROVAL_LEVELS
                    else None
                ),
            )
        )

        # Check 3: Has at least one step
        results.append(
            GovernanceCheckResult(
                schema_id="workflow_validation",
                policy_id="has_steps",
                passed=len(workflow.steps) > 0,
                violation=(
                    GovernanceViolation(
                        schema_id="workflow_validation",
                        policy_id="has_steps",
                        severity="critical",
                        description="Workflow must have at least one step",
                    )
                    if len(workflow.steps) == 0
                    else None
                ),
            )
        )

        # Check 4: Step action types
        for step in workflow.steps:
            valid_action = step.action_type in self.VALID_ACTION_TYPES
            results.append(
                GovernanceCheckResult(
                    schema_id="workflow_validation",
                    policy_id=f"valid_action_type_{step.step_id}",
                    passed=valid_action,
                    violation=(
                        GovernanceViolation(
                            schema_id="workflow_validation",
                            policy_id="valid_action_type",
                            severity="high",
                            description=(
                                f"Step '{step.step_id}' has invalid action type "
                                f"'{step.action_type}'. Must be one of: "
                                f"{self.VALID_ACTION_TYPES}"
                            ),
                        )
                        if not valid_action
                        else None
                    ),
                )
            )

        # Check 5: Step dependencies (no missing refs, no cycles)
        dep_errors = workflow.validate_dependencies()
        results.append(
            GovernanceCheckResult(
                schema_id="workflow_validation",
                policy_id="valid_dependencies",
                passed=len(dep_errors) == 0,
                violation=(
                    GovernanceViolation(
                        schema_id="workflow_validation",
                        policy_id="valid_dependencies",
                        severity="high",
                        description="; ".join(dep_errors),
                    )
                    if dep_errors
                    else None
                ),
            )
        )

        # Check 6: No dependency cycles
        has_cycle = self._detect_cycle(workflow)
        results.append(
            GovernanceCheckResult(
                schema_id="workflow_validation",
                policy_id="no_dependency_cycles",
                passed=not has_cycle,
                violation=(
                    GovernanceViolation(
                        schema_id="workflow_validation",
                        policy_id="no_dependency_cycles",
                        severity="critical",
                        description="Workflow has circular step dependencies",
                    )
                    if has_cycle
                    else None
                ),
            )
        )

        logger.info(
            "Validation of workflow '%s': %d/%d checks passed",
            workflow_id,
            sum(1 for r in results if r.passed),
            len(results),
        )

        return results

    # ------------------------------------------------------------------
    # Internal validation helpers
    # ------------------------------------------------------------------

    def _validate_structure(self, definition: WorkflowDefinition) -> list[str]:
        """Validate the structural integrity of a workflow definition.

        Returns a list of error messages (empty if valid).
        """
        errors: list[str] = []

        if not definition.workflow_id:
            errors.append("workflow_id is required")

        if not definition.name:
            errors.append("name is required")

        if not definition.project_id:
            errors.append("project_id is required")

        if definition.risk_level not in self.VALID_RISK_LEVELS:
            errors.append(
                f"Invalid risk_level '{definition.risk_level}'. "
                f"Must be one of: {self.VALID_RISK_LEVELS}"
            )

        if definition.required_approval not in self.VALID_APPROVAL_LEVELS:
            errors.append(
                f"Invalid required_approval '{definition.required_approval}'. "
                f"Must be one of: {self.VALID_APPROVAL_LEVELS}"
            )

        if not definition.steps:
            errors.append("Workflow must have at least one step")

        # Validate step IDs are unique
        step_ids = [s.step_id for s in definition.steps]
        if len(step_ids) != len(set(step_ids)):
            errors.append("Duplicate step_id values found")

        # Validate step action types
        for step in definition.steps:
            if step.action_type not in self.VALID_ACTION_TYPES:
                errors.append(
                    f"Step '{step.step_id}' has invalid action_type "
                    f"'{step.action_type}'"
                )

        # Validate dependencies
        dep_errors = definition.validate_dependencies()
        errors.extend(dep_errors)

        # Check for cycles
        if self._detect_cycle(definition):
            errors.append("Circular step dependencies detected")

        return errors

    @staticmethod
    def _detect_cycle(workflow: WorkflowDefinition) -> bool:
        """Detect if the workflow has circular step dependencies.

        Uses DFS-based cycle detection.
        """
        visited: set[str] = set()
        recursion_stack: set[str] = set()

        step_map = {s.step_id: s for s in workflow.steps}

        def has_cycle_from(step_id: str) -> bool:
            visited.add(step_id)
            recursion_stack.add(step_id)

            step = step_map.get(step_id)
            if step:
                for dep_id in step.depends_on:
                    if dep_id not in visited:
                        if has_cycle_from(dep_id):
                            return True
                    elif dep_id in recursion_stack:
                        return True

            recursion_stack.remove(step_id)
            return False

        for step in workflow.steps:
            if step.step_id not in visited:
                if has_cycle_from(step.step_id):
                    return True

        return False

    # ------------------------------------------------------------------
    # Registration log
    # ------------------------------------------------------------------

    def get_registration_log(
        self,
        workflow_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get the registration log.

        Args:
            workflow_id: Filter by workflow (None = all).

        Returns:
            List of registration log entries.
        """
        if workflow_id:
            return [
                e for e in self._registration_log
                if e.get("workflow_id") == workflow_id
            ]
        return list(self._registration_log)

    def count(self) -> int:
        """Return the total number of registered workflows."""
        return len(self._workflows)

    def reset(self) -> None:
        """Clear all workflows. For testing only."""
        self._workflows.clear()
        self._registration_log.clear()
        logger.warning("WorkflowRegistry reset — all workflows cleared")
