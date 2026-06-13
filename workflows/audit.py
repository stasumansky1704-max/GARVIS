"""Workflow Audit Pipeline — workflows/audit.py

Audit pipeline specifically for workflows.

Tracks:
- Workflow proposals
- Approval decisions
- Step execution (start, complete, failure)
- Governance checks per step
- Rollback operations
- Workflow completion

All audit events are recorded through the central AuditPipeline
for persistent, immutable logging.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from models.audit import AuditEvent
from models.governance import GovernanceCheckResult
from traceability.audit import AuditPipeline
from workflows.models import WorkflowInstance, WorkflowStepResult

logger = logging.getLogger("garvis.workflows.audit")


# ---------------------------------------------------------------------------
# WorkflowAudit — workflow-specific audit pipeline
# ---------------------------------------------------------------------------


class WorkflowAudit:
    """Audit pipeline specifically for workflows.

    Tracks:
    - Workflow proposals
    - Approval decisions
    - Step execution
    - Governance checks per step
    - Rollback operations

    All events are logged through the central AuditPipeline.
    """

    def __init__(self, audit_pipeline: AuditPipeline) -> None:
        self.audit = audit_pipeline
        self._workflow_events: dict[str, list[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Workflow proposal
    # ------------------------------------------------------------------

    async def log_proposal(self, proposal: dict[str, Any]) -> None:
        """Log a workflow proposal.

        Args:
            proposal: The proposal dict from the approval framework.
        """
        proposal_id = proposal.get("proposal_id", "unknown")
        workflow_id = proposal.get("workflow_id", "unknown")
        workflow_name = proposal.get("workflow_name", "unknown")
        risk_level = proposal.get("risk_level", "unknown")

        event = AuditEvent(
            event_type="workflow_proposal",
            severity="info",
            component="workflow_engine",
            details={
                "proposal_id": proposal_id,
                "workflow_id": workflow_id,
                "workflow_name": workflow_name,
                "project_id": proposal.get("project_id", "unknown"),
                "operator_id": proposal.get("operator_id", "unknown"),
                "risk_level": risk_level,
                "required_approval": proposal.get("required_approval", "unknown"),
                "status": "proposed",
            },
        )

        try:
            await self.audit.log_event(event)
        except Exception as exc:
            logger.error("Failed to log proposal: %s", exc)

        # Store in local buffer
        instance_events = self._workflow_events.setdefault(proposal_id, [])
        instance_events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "proposal",
            "proposal_id": proposal_id,
            "workflow_id": workflow_id,
            "risk_level": risk_level,
        })

        logger.debug(
            "Logged workflow proposal: %s (workflow=%s, risk=%s)",
            proposal_id,
            workflow_name,
            risk_level,
        )

    # ------------------------------------------------------------------
    # Approval decision
    # ------------------------------------------------------------------

    async def log_approval(self, approval: dict[str, Any]) -> None:
        """Log an approval decision.

        Args:
            approval: Dict with proposal_id, workflow_id, operator_id, etc.
        """
        proposal_id = approval.get("proposal_id", "unknown")
        operator_id = approval.get("operator_id", "unknown")
        workflow_id = approval.get("workflow_id", "unknown")
        instance_id = approval.get("instance_id", "unknown")

        event = AuditEvent(
            event_type="workflow_approval",
            severity="info",
            component="workflow_engine",
            details={
                "proposal_id": proposal_id,
                "workflow_id": workflow_id,
                "instance_id": instance_id,
                "operator_id": operator_id,
                "action": "approved",
            },
        )

        try:
            await self.audit.log_event(event)
        except Exception as exc:
            logger.error("Failed to log approval: %s", exc)

        instance_events = self._workflow_events.setdefault(instance_id, [])
        instance_events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "approval",
            "proposal_id": proposal_id,
            "operator_id": operator_id,
        })

        logger.debug(
            "Logged workflow approval: %s by operator=%s",
            proposal_id,
            operator_id,
        )

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    async def log_step_start(self, instance_id: str, step_id: str) -> None:
        """Log step execution start.

        Args:
            instance_id: The workflow instance ID.
            step_id: The step being executed.
        """
        event = AuditEvent(
            event_type="workflow_step_start",
            severity="info",
            component="workflow_engine",
            details={
                "instance_id": instance_id,
                "step_id": step_id,
                "status": "executing",
            },
        )

        try:
            await self.audit.log_event(event)
        except Exception as exc:
            logger.error("Failed to log step start: %s", exc)

        instance_events = self._workflow_events.setdefault(instance_id, [])
        instance_events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "step_start",
            "step_id": step_id,
        })

    async def log_step_complete(
        self,
        instance_id: str,
        step_id: str,
        result: WorkflowStepResult,
    ) -> None:
        """Log step execution completion.

        Args:
            instance_id: The workflow instance ID.
            step_id: The completed step ID.
            result: The step execution result.
        """
        severity = "info" if result.status == "completed" else "warning"

        # Count governance checks
        checks_passed = sum(1 for c in result.governance_checks if c.passed)
        checks_total = len(result.governance_checks)

        event = AuditEvent(
            event_type="workflow_step_complete",
            severity=severity,
            component="workflow_engine",
            details={
                "instance_id": instance_id,
                "step_id": step_id,
                "status": result.status,
                "governance_checks_passed": checks_passed,
                "governance_checks_total": checks_total,
                "result_keys": list(result.result.keys()),
                "error": result.error,
            },
        )

        try:
            await self.audit.log_event(event)
        except Exception as exc:
            logger.error("Failed to log step complete: %s", exc)

        instance_events = self._workflow_events.setdefault(instance_id, [])
        instance_events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "step_complete",
            "step_id": step_id,
            "status": result.status,
            "governance_passed": checks_passed,
            "governance_total": checks_total,
        })

    async def log_step_failure(
        self,
        instance_id: str,
        step_id: str,
        error: str,
    ) -> None:
        """Log step execution failure.

        Args:
            instance_id: The workflow instance ID.
            step_id: The failed step ID.
            error: The error message.
        """
        event = AuditEvent(
            event_type="workflow_step_failure",
            severity="critical",
            component="workflow_engine",
            details={
                "instance_id": instance_id,
                "step_id": step_id,
                "error": error,
                "status": "failed",
            },
        )

        try:
            await self.audit.log_event(event)
        except Exception as exc:
            logger.error("Failed to log step failure: %s", exc)

        instance_events = self._workflow_events.setdefault(instance_id, [])
        instance_events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "step_failure",
            "step_id": step_id,
            "error": error,
        })

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    async def log_rollback(
        self,
        instance_id: str,
        operator_id: str,
    ) -> None:
        """Log workflow rollback.

        Args:
            instance_id: The workflow instance being rolled back.
            operator_id: The operator requesting rollback.
        """
        event = AuditEvent(
            event_type="workflow_rollback",
            severity="warning",
            component="workflow_engine",
            details={
                "instance_id": instance_id,
                "operator_id": operator_id,
                "action": "rollback",
            },
        )

        try:
            await self.audit.log_event(event)
        except Exception as exc:
            logger.error("Failed to log rollback: %s", exc)

        instance_events = self._workflow_events.setdefault(instance_id, [])
        instance_events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "rollback",
            "operator_id": operator_id,
        })

        logger.info(
            "Logged workflow rollback: instance=%s, operator=%s",
            instance_id,
            operator_id,
        )

    # ------------------------------------------------------------------
    # Workflow completion
    # ------------------------------------------------------------------

    async def log_workflow_complete(self, instance: WorkflowInstance) -> None:
        """Log workflow completion.

        Args:
            instance: The completed workflow instance.
        """
        severity = (
            "info"
            if instance.status == "completed"
            else "warning"
            if instance.status == "rolled_back"
            else "critical"
        )

        steps_completed = instance.steps_completed_count()
        steps_failed = instance.steps_failed_count()

        event = AuditEvent(
            event_type="workflow_complete",
            severity=severity,
            component="workflow_engine",
            details={
                "instance_id": str(instance.instance_id),
                "workflow_id": instance.workflow_id,
                "project_id": instance.project_id,
                "operator_id": instance.operator_id,
                "status": instance.status,
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,
                "governance_context": instance.governance_context,
                "trace_id": str(instance.trace_id),
                "started_at": (
                    instance.started_at.isoformat() if instance.started_at else None
                ),
                "completed_at": (
                    instance.completed_at.isoformat()
                    if instance.completed_at
                    else None
                ),
            },
        )

        try:
            await self.audit.log_event(event)
        except Exception as exc:
            logger.error("Failed to log workflow complete: %s", exc)

        instance_events = self._workflow_events.setdefault(
            str(instance.instance_id), []
        )
        instance_events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "workflow_complete",
            "workflow_id": instance.workflow_id,
            "status": instance.status,
            "steps_completed": steps_completed,
            "steps_failed": steps_failed,
        })

        logger.info(
            "Logged workflow completion: instance=%s, status=%s, "
            "completed=%d, failed=%d",
            instance.instance_id,
            instance.status,
            steps_completed,
            steps_failed,
        )

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    async def get_workflow_audit_trail(
        self,
        instance_id: str,
    ) -> list[dict[str, Any]]:
        """Get complete audit trail for a workflow instance.

        Args:
            instance_id: The workflow instance ID.

        Returns:
            List of audit trail events for the instance.
        """
        events = self._workflow_events.get(instance_id, [])

        if not events:
            # Try to fetch from central audit
            try:
                central_events = await self.audit.get_events(
                    event_type="workflow_",
                    limit=1000,
                )
                events = [
                    {
                        "timestamp": e.timestamp.isoformat(),
                        "event_type": e.event_type,
                        "details": e.details,
                    }
                    for e in central_events
                    if e.details.get("instance_id") == instance_id
                ]
            except Exception as exc:
                logger.warning("Failed to fetch central audit events: %s", exc)

        return events

    async def get_workflow_statistics(
        self,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Get workflow execution statistics.

        Args:
            project_id: Filter by project (None = all).

        Returns:
            Dict with workflow statistics.
        """
        events = []
        for instance_events in self._workflow_events.values():
            events.extend(instance_events)

        if not events:
            return {
                "total_executions": 0,
                "by_status": {},
                "by_project": {},
                "steps_completed_total": 0,
                "steps_failed_total": 0,
                "rollbacks": 0,
                "project_id": project_id,
            }

        by_status: dict[str, int] = {}
        by_project: dict[str, int] = {}
        steps_completed_total = 0
        steps_failed_total = 0
        rollbacks = 0

        for event in events:
            event_type = event.get("event_type", "")

            if event_type == "workflow_complete":
                status = event.get("status", "unknown")
                by_status[status] = by_status.get(status, 0) + 1
                steps_completed_total += event.get("steps_completed", 0)
                steps_failed_total += event.get("steps_failed", 0)

                proj_id = event.get("project_id")
                if proj_id:
                    by_project[proj_id] = by_project.get(proj_id, 0) + 1

            elif event_type == "rollback":
                rollbacks += 1

        return {
            "total_executions": sum(by_status.values()),
            "by_status": by_status,
            "by_project": by_project,
            "steps_completed_total": steps_completed_total,
            "steps_failed_total": steps_failed_total,
            "rollbacks": rollbacks,
            "project_id": project_id,
        }

    # ------------------------------------------------------------------
    # Reset (for testing)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all workflow events. For testing only."""
        self._workflow_events.clear()
        logger.warning("WorkflowAudit reset — all events cleared")
