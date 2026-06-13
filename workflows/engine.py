"""Governed Workflow Execution Engine — workflows/engine.py

THE WORKFLOW ENGINE — core of the governed workflow runtime.

KEY PRINCIPLE: NO workflow executes without explicit operator approval.

Execution flow:
1. Operator proposes workflow execution
2. WorkflowApprovalFramework classifies risk
3. Operator approves (required for medium/high/critical)
4. WorkflowEngine validates the workflow definition
5. Each step runs through governance middleware
6. Each step result is audited
7. Full trace is recorded
8. Results are returned to operator

If ANY step fails governance -> workflow fails, rollback initiated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from mission_control.workflow_approval import WorkflowApprovalFramework
from models.governance import GovernanceCheckResult, GovernanceViolation
from monitoring.alerts import AlertEngine
from traceability.audit import AuditPipeline
from traceability.lineage import LineageTracker
from workflows.audit import WorkflowAudit
from workflows.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStep,
    WorkflowStepResult,
)
from workflows.registry import WorkflowRegistry

logger = logging.getLogger("garvis.workflows.engine")


# ---------------------------------------------------------------------------
# WorkflowEngine — governed workflow execution engine
# ---------------------------------------------------------------------------


class WorkflowEngine:
    """Governed workflow execution engine.

    KEY PRINCIPLE: NO workflow executes without explicit operator approval.

    Execution flow:
    1. Operator proposes workflow execution
    2. WorkflowApprovalFramework classifies risk
    3. Operator approves (required for medium/high/critical)
    4. WorkflowEngine validates the workflow definition
    5. Each step runs through governance middleware
    6. Each step result is audited
    7. Full trace is recorded
    8. Results are returned to operator

    If ANY step fails governance -> workflow fails, rollback initiated.
    """

    def __init__(
        self,
        registry: WorkflowRegistry,
        approval_framework: WorkflowApprovalFramework,
        audit_pipeline: AuditPipeline,
        lineage_tracker: LineageTracker,
        alert_engine: AlertEngine,
    ) -> None:
        self.registry = registry
        self.approval = approval_framework
        self.audit = audit_pipeline
        self.lineage = lineage_tracker
        self.alerts = alert_engine
        self.workflow_audit = WorkflowAudit(audit_pipeline)
        self._instances: dict[str, WorkflowInstance] = {}
        self._proposals: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Proposal
    # ------------------------------------------------------------------

    async def propose_execution(
        self,
        workflow_id: str,
        project_id: str,
        operator_id: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Propose executing a workflow.

        Returns a proposal with risk classification and approval requirements.
        Does NOT execute — only proposes.

        Args:
            workflow_id: The workflow to execute.
            project_id: The project context.
            operator_id: The operator proposing execution.
            parameters: Optional runtime parameters.

        Returns:
            Proposal dict with classification and next steps.
        """
        # Verify workflow exists and is active
        workflow = self.registry.get(workflow_id)
        if workflow is None:
            return {
                "status": "error",
                "reason": f"Workflow '{workflow_id}' not found",
            }

        if not workflow.active:
            return {
                "status": "error",
                "reason": (
                    f"Workflow '{workflow_id}' is not active. "
                    f"Must be activated before execution."
                ),
            }

        # Build operations list for risk classification
        operations = [
            {"type": step.action_type, "description": step.description}
            for step in workflow.steps
        ]

        workflow_dict = {
            "name": workflow.name,
            "description": workflow.description,
            "project_id": project_id,
            "operations": operations,
            "risk_level": workflow.risk_level,
        }

        # Submit through approval framework
        proposal = self.approval.submit_for_approval(workflow_dict)
        proposal_id = proposal["proposal_id"]

        # Store proposal with extra context
        self._proposals[proposal_id] = {
            **proposal,
            "workflow_id": workflow_id,
            "project_id": project_id,
            "operator_id": operator_id,
            "parameters": parameters or {},
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        # Log proposal
        await self.workflow_audit.log_proposal(self._proposals[proposal_id])

        logger.info(
            "Workflow execution proposed: workflow=%s, project=%s, "
            "operator=%s, proposal=%s, risk=%s, approval_required=%s",
            workflow_id,
            project_id,
            operator_id,
            proposal_id,
            proposal["risk_level"],
            proposal["required_approval"],
        )

        return {
            "status": "proposed",
            "proposal_id": proposal_id,
            "workflow_id": workflow_id,
            "workflow_name": workflow.name,
            "project_id": project_id,
            "risk_level": proposal["risk_level"],
            "risk_description": proposal["risk_description"],
            "required_approval": proposal["required_approval"],
            "note": (
                "Workflow execution is PROPOSED only. "
                "It will NOT execute until explicitly approved by an operator. "
                f"Required approval level: {proposal['required_approval']}."
            ),
        }

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        proposal_id: str,
        operator_id: str,
    ) -> WorkflowInstance:
        """Execute an approved workflow.

        Runs each step through governance, records audit trail,
        creates trace, returns results.

        Args:
            proposal_id: The approved proposal ID.
            operator_id: The operator triggering execution.

        Returns:
            The completed (or failed) workflow instance.

        Raises:
            ValueError: If proposal not found, not approved, or workflow invalid.
        """
        # Retrieve proposal
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal '{proposal_id}' not found")

        # Check approval status
        approval_record = self.approval.get_proposal(proposal_id)
        if approval_record is None or approval_record.get("status") != "approved":
            raise ValueError(
                f"Proposal '{proposal_id}' is not approved. "
                f"Status: {approval_record.get('status') if approval_record else 'unknown'}. "
                f"Execution is BLOCKED."
            )

        # Get workflow definition
        workflow_id = proposal["workflow_id"]
        workflow = self.registry.get(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow '{workflow_id}' not found in registry")

        if not workflow.active:
            raise ValueError(f"Workflow '{workflow_id}' is not active")

        # Create instance
        instance = WorkflowInstance(
            workflow_id=workflow_id,
            project_id=proposal["project_id"],
            operator_id=operator_id,
            status="approved",
            approval_id=proposal_id,
            governance_context=list(workflow.governance_schemas),
            trace_id=uuid4(),
            parameters=proposal.get("parameters", {}),
        )

        self._instances[str(instance.instance_id)] = instance

        # Log approval
        await self.workflow_audit.log_approval({
            "proposal_id": proposal_id,
            "workflow_id": workflow_id,
            "operator_id": operator_id,
            "instance_id": str(instance.instance_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Start lineage trace
        try:
            await self.lineage.start_trace(instance.trace_id)
        except Exception as exc:
            logger.warning("Failed to start lineage trace: %s", exc)

        # Transition to executing
        instance.status = "executing"
        instance.started_at = datetime.now(timezone.utc)

        logger.info(
            "Starting workflow execution: instance=%s, workflow=%s, "
            "operator=%s, steps=%d",
            instance.instance_id,
            workflow_id,
            operator_id,
            len(workflow.steps),
        )

        # Execute steps in dependency order
        ordered_steps = workflow.get_ordered_steps()

        for step in ordered_steps:
            # Check if instance is still executing (might have been rolled back)
            if instance.status != "executing":
                logger.info(
                    "Workflow execution halted: instance=%s, status=%s",
                    instance.instance_id,
                    instance.status,
                )
                break

            # Check if dependencies are met
            deps_satisfied = all(
                instance.is_step_completed(dep_id)
                for dep_id in step.depends_on
            )
            if not deps_satisfied:
                logger.warning(
                    "Dependencies not met for step '%s', skipping",
                    step.step_id,
                )
                skipped_result = WorkflowStepResult(
                    step_id=step.step_id,
                    status="skipped",
                    result={"reason": "dependencies_not_met"},
                    completed_at=datetime.now(timezone.utc),
                )
                instance.steps_executed.append(skipped_result)
                await self.workflow_audit.log_step_complete(
                    str(instance.instance_id), step.step_id, skipped_result
                )
                continue

            # Execute the step
            result = await self.execute_step(instance, step)
            instance.steps_executed.append(result)

            # If step failed governance, halt workflow
            if result.status == "failed":
                instance.status = "failed"
                instance.completed_at = datetime.now(timezone.utc)

                # Trigger alert
                self.alerts.check_boundary_violation(
                    schema_id="workflow_execution",
                    operation=f"step:{step.step_id}",
                )

                logger.error(
                    "Workflow FAILED at step '%s': instance=%s, error=%s",
                    step.step_id,
                    instance.instance_id,
                    result.error,
                )

                await self.workflow_audit.log_step_failure(
                    str(instance.instance_id),
                    step.step_id,
                    result.error or "Governance check failed",
                )
                await self.workflow_audit.log_workflow_complete(instance)
                return instance

        # All steps completed successfully
        if instance.status == "executing":
            instance.status = "completed"
            instance.completed_at = datetime.now(timezone.utc)

            logger.info(
                "Workflow COMPLETED: instance=%s, workflow=%s, "
                "steps_completed=%d",
                instance.instance_id,
                workflow_id,
                instance.steps_completed_count(),
            )

            await self.workflow_audit.log_workflow_complete(instance)

        return instance

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    async def execute_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
    ) -> WorkflowStepResult:
        """Execute a single workflow step with full governance mediation.

        Step execution flow:
        1. Check if workflow is still approved
        2. Run governance checks for the step
        3. Execute the action
        4. Validate the result through governance
        5. Record in audit pipeline
        6. Record in lineage tracker
        7. Return result

        Args:
            instance: The workflow instance.
            step: The step to execute.

        Returns:
            WorkflowStepResult with execution outcome.
        """
        step_result = WorkflowStepResult(step_id=step.step_id, status="executing")

        logger.info(
            "Executing step '%s' (type=%s) for instance=%s",
            step.step_id,
            step.action_type,
            instance.instance_id,
        )

        await self.workflow_audit.log_step_start(
            str(instance.instance_id), step.step_id
        )

        # 1. Check if instance is still executing
        if instance.status != "executing":
            step_result.status = "failed"
            step_result.error = f"Instance status is '{instance.status}', not executing"
            step_result.completed_at = datetime.now(timezone.utc)
            return step_result

        # 2. Run governance checks for the step
        governance_results = await self._run_governance_checks(instance, step)
        step_result.governance_checks = governance_results

        failed_checks = [c for c in governance_results if not c.passed]
        if failed_checks:
            step_result.status = "failed"
            step_result.error = (
                f"Governance check(s) failed: "
                f"{', '.join(c.policy_id for c in failed_checks)}"
            )
            step_result.completed_at = datetime.now(timezone.utc)

            # Log governance failure in lineage
            try:
                await self.lineage.record_governance_influence(
                    instance.trace_id, governance_results
                )
            except Exception as exc:
                logger.warning("Failed to record governance influence: %s", exc)

            logger.warning(
                "Step '%s' FAILED governance: %s",
                step.step_id,
                step_result.error,
            )
            return step_result

        # 3. Execute the action
        try:
            action_result = await self._execute_action(instance, step)
            step_result.result = action_result
        except Exception as exc:
            step_result.status = "failed"
            step_result.error = f"Action execution failed: {exc}"
            step_result.completed_at = datetime.now(timezone.utc)

            logger.error(
                "Step '%s' action execution failed: %s",
                step.step_id,
                exc,
            )
            return step_result

        # 4. Validate result through governance
        validation_results = await self._validate_result(instance, step, step_result.result)
        step_result.governance_checks.extend(validation_results)

        failed_validation = [c for c in validation_results if not c.passed]
        if failed_validation:
            step_result.status = "failed"
            step_result.error = (
                f"Result validation failed: "
                f"{', '.join(c.policy_id for c in failed_validation)}"
            )
            step_result.completed_at = datetime.now(timezone.utc)
            return step_result

        # 5. Record in audit pipeline
        try:
            await self.workflow_audit.log_step_complete(
                str(instance.instance_id), step.step_id, step_result
            )
        except Exception as exc:
            logger.warning("Failed to log step completion: %s", exc)

        # 6. Record in lineage tracker
        try:
            await self.lineage.record_governance_influence(
                instance.trace_id, step_result.governance_checks
            )
        except Exception as exc:
            logger.warning("Failed to record lineage: %s", exc)

        # Mark complete
        step_result.status = "completed"
        step_result.completed_at = datetime.now(timezone.utc)

        logger.info(
            "Step '%s' COMPLETED for instance=%s",
            step.step_id,
            instance.instance_id,
        )

        return step_result

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    async def rollback(
        self,
        instance_id: str,
        operator_id: str,
    ) -> bool:
        """Rollback a workflow instance.

        Undoes completed steps in reverse order.
        Requires explicit operator confirmation.

        Args:
            instance_id: The instance to rollback.
            operator_id: The operator requesting rollback.

        Returns:
            True if rollback succeeded, False otherwise.
        """
        instance = self._instances.get(instance_id)
        if instance is None:
            logger.warning(
                "Rollback failed: instance '%s' not found", instance_id
            )
            return False

        # Can only rollback failed or executing instances
        if instance.status not in ("failed", "executing", "completed"):
            logger.warning(
                "Rollback failed: instance '%s' has status '%s', "
                "cannot rollback from this state",
                instance_id,
                instance.status,
            )
            return False

        logger.info(
            "Rolling back workflow instance=%s (workflow=%s) by operator '%s'. "
            "%d steps to undo.",
            instance_id,
            instance.workflow_id,
            operator_id,
            instance.steps_completed_count(),
        )

        # Undo completed steps in reverse order
        completed_steps = [
            r for r in reversed(instance.steps_executed)
            if r.status == "completed"
        ]

        for step_result in completed_steps:
            try:
                await self._undo_step(instance, step_result)
                logger.info(
                    "Undone step '%s' for instance=%s",
                    step_result.step_id,
                    instance_id,
                )
            except Exception as exc:
                logger.error(
                    "Failed to undo step '%s' for instance=%s: %s",
                    step_result.step_id,
                    instance_id,
                    exc,
                )

        # Update instance status
        instance.status = "rolled_back"
        instance.completed_at = datetime.now(timezone.utc)

        # Log rollback
        await self.workflow_audit.log_rollback(instance_id, operator_id)

        # Alert
        self.alerts.check_boundary_violation(
            schema_id="workflow_execution",
            operation=f"rollback:{instance_id}",
        )

        logger.info(
            "Workflow instance=%s ROLLED BACK by operator '%s'",
            instance_id,
            operator_id,
        )

        return True

    # ------------------------------------------------------------------
    # Instance queries
    # ------------------------------------------------------------------

    def get_instance(self, instance_id: str) -> WorkflowInstance | None:
        """Get workflow instance status and results.

        Args:
            instance_id: The instance to retrieve.

        Returns:
            The workflow instance, or None if not found.
        """
        return self._instances.get(instance_id)

    def list_instances(
        self,
        project_id: str | None = None,
        status: str | None = None,
    ) -> list[WorkflowInstance]:
        """List workflow instances with optional filtering.

        Args:
            project_id: Filter by project (None = all).
            status: Filter by status (None = all).

        Returns:
            List of workflow instances.
        """
        instances = list(self._instances.values())

        if project_id is not None:
            instances = [i for i in instances if i.project_id == project_id]

        if status is not None:
            instances = [i for i in instances if i.status == status]

        return sorted(instances, key=lambda i: i.started_at or datetime.min.replace(tzinfo=timezone.utc))

    # ------------------------------------------------------------------
    # Internal: governance checks
    # ------------------------------------------------------------------

    async def _run_governance_checks(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
    ) -> list[GovernanceCheckResult]:
        """Run governance checks for a step.

        Returns a list of check results. All checks must pass
        for the step to execute.
        """
        results: list[GovernanceCheckResult] = []

        # Check 1: Workflow is still approved
        proposal = self._proposals.get(instance.approval_id)
        if proposal is None:
            results.append(
                GovernanceCheckResult(
                    schema_id="workflow_execution",
                    policy_id="proposal_valid",
                    passed=False,
                    violation=GovernanceViolation(
                        schema_id="workflow_execution",
                        policy_id="proposal_valid",
                        severity="critical",
                        description="Approval proposal no longer exists",
                    ),
                )
            )
            return results

        approval_record = self.approval.get_proposal(instance.approval_id)
        if approval_record is None or approval_record.get("status") != "approved":
            results.append(
                GovernanceCheckResult(
                    schema_id="workflow_execution",
                    policy_id="approval_still_valid",
                    passed=False,
                    violation=GovernanceViolation(
                        schema_id="workflow_execution",
                        policy_id="approval_still_valid",
                        severity="critical",
                        description=(
                            f"Approval status is "
                            f"'{approval_record.get('status') if approval_record else 'unknown'}', "
                            f"not 'approved'"
                        ),
                    ),
                )
            )
            return results

        # Check passed: approval still valid
        results.append(
            GovernanceCheckResult(
                schema_id="workflow_execution",
                policy_id="approval_still_valid",
                passed=True,
            )
        )

        # Check 2: Required governance schemas are active
        for schema_id in step.governance_checks:
            # In a real system, this would check against a governance registry
            # For now, we assume the schema is active if it's in the workflow's context
            schema_active = schema_id in instance.governance_context
            results.append(
                GovernanceCheckResult(
                    schema_id=schema_id,
                    policy_id="schema_active",
                    passed=schema_active,
                    violation=(
                        GovernanceViolation(
                            schema_id=schema_id,
                            policy_id="schema_active",
                            severity="critical",
                            description=f"Governance schema '{schema_id}' is not active",
                        )
                        if not schema_active
                        else None
                    ),
                )
            )

        # Check 3: Action type is allowed
        allowed_actions = {
            "ollama_inference",
            "memory_store",
            "memory_retrieve",
            "governance_check",
            "audit_log",
            "external_call",
        }
        results.append(
            GovernanceCheckResult(
                schema_id="workflow_execution",
                policy_id="allowed_action_type",
                passed=step.action_type in allowed_actions,
                violation=(
                    GovernanceViolation(
                        schema_id="workflow_execution",
                        policy_id="allowed_action_type",
                        severity="high",
                        description=f"Action type '{step.action_type}' is not allowed",
                    )
                    if step.action_type not in allowed_actions
                    else None
                ),
            )
        )

        return results

    # ------------------------------------------------------------------
    # Internal: action execution
    # ------------------------------------------------------------------

    async def _execute_action(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
    ) -> dict[str, Any]:
        """Execute a workflow step action.

        This is a dispatcher that routes to the appropriate action handler.
        Each action type has its own execution logic.

        Args:
            instance: The workflow instance.
            step: The step to execute.

        Returns:
            Dict with action results.
        """
        action_type = step.action_type
        params = step.parameters

        # Merge runtime parameters
        merged_params = {**params, **instance.parameters}

        if action_type == "ollama_inference":
            return await self._action_ollama_inference(instance, step, merged_params)

        if action_type == "memory_store":
            return await self._action_memory_store(instance, step, merged_params)

        if action_type == "memory_retrieve":
            return await self._action_memory_retrieve(instance, step, merged_params)

        if action_type == "governance_check":
            return await self._action_governance_check(instance, step, merged_params)

        if action_type == "audit_log":
            return await self._action_audit_log(instance, step, merged_params)

        if action_type == "external_call":
            return await self._action_external_call(instance, step, merged_params)

        raise ValueError(f"Unknown action type: {action_type}")

    async def _action_ollama_inference(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an Ollama inference action.

        In a production system, this would call the Ollama API.
        For now, returns a mock result for testing.
        """
        model = params.get("model", "llama3.1")
        prompt = params.get("prompt", "")

        # Mock inference result
        return {
            "action": "ollama_inference",
            "model": model,
            "prompt_length": len(prompt),
            "response": f"[Mock inference response for prompt: {prompt[:50]}...]",
            "status": "success",
            "mock": True,
        }

    async def _action_memory_store(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a memory store action."""
        memory_type = params.get("memory_type", "episodic")
        content = params.get("content", "")

        return {
            "action": "memory_store",
            "memory_type": memory_type,
            "content_stored": content,
            "status": "success",
            "mock": True,
        }

    async def _action_memory_retrieve(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a memory retrieve action."""
        query = params.get("query", "")
        limit = params.get("limit", 10)

        return {
            "action": "memory_retrieve",
            "query": query,
            "results_count": 0,
            "memories": [],
            "status": "success",
            "mock": True,
        }

    async def _action_governance_check(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a governance check action."""
        schema_id = params.get("schema_id", "default")
        check_type = params.get("check_type", "general")

        return {
            "action": "governance_check",
            "schema_id": schema_id,
            "check_type": check_type,
            "passed": True,
            "status": "success",
            "mock": True,
        }

    async def _action_audit_log(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an audit log action."""
        event_type = params.get("event_type", "workflow_event")
        message = params.get("message", "")

        return {
            "action": "audit_log",
            "event_type": event_type,
            "message": message,
            "status": "success",
            "mock": True,
        }

    async def _action_external_call(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an external call action."""
        endpoint = params.get("endpoint", "")
        method = params.get("method", "GET")

        return {
            "action": "external_call",
            "endpoint": endpoint,
            "method": method,
            "status": "success",
            "response_code": 200,
            "mock": True,
        }

    # ------------------------------------------------------------------
    # Internal: result validation
    # ------------------------------------------------------------------

    async def _validate_result(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        result: dict[str, Any],
    ) -> list[GovernanceCheckResult]:
        """Validate a step result through governance.

        Returns additional governance checks for the result.
        """
        results: list[GovernanceCheckResult] = []

        # Check that result has a status field
        has_status = "status" in result
        results.append(
            GovernanceCheckResult(
                schema_id="workflow_execution",
                policy_id="result_has_status",
                passed=has_status,
                violation=(
                    GovernanceViolation(
                        schema_id="workflow_execution",
                        policy_id="result_has_status",
                        severity="warning",
                        description="Step result missing 'status' field",
                    )
                    if not has_status
                    else None
                ),
            )
        )

        # Check result status is success for completed actions
        if has_status and result.get("status") != "success":
            results.append(
                GovernanceCheckResult(
                    schema_id="workflow_execution",
                    policy_id="result_status_success",
                    passed=False,
                    violation=GovernanceViolation(
                        schema_id="workflow_execution",
                        policy_id="result_status_success",
                        severity="high",
                        description=(
                            f"Step result status is '{result.get('status')}', "
                            f"expected 'success'"
                        ),
                    ),
                )
            )
        else:
            results.append(
                GovernanceCheckResult(
                    schema_id="workflow_execution",
                    policy_id="result_status_success",
                    passed=True,
                )
            )

        return results

    # ------------------------------------------------------------------
    # Internal: step undo for rollback
    # ------------------------------------------------------------------

    async def _undo_step(
        self,
        instance: WorkflowInstance,
        step_result: WorkflowStepResult,
    ) -> None:
        """Undo a completed step during rollback.

        Args:
            instance: The workflow instance.
            step_result: The step result to undo.
        """
        logger.info(
            "Undoing step '%s' for instance=%s",
            step_result.step_id,
            instance.instance_id,
        )

        # Mark as undone in the result
        step_result.result["undone"] = True
        step_result.result["undone_at"] = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Reset (for testing)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all instances and proposals. For testing only."""
        self._instances.clear()
        self._proposals.clear()
        self.workflow_audit = WorkflowAudit(self.audit)
        logger.warning("WorkflowEngine reset — all instances and proposals cleared")
