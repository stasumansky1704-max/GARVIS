"""Workflow Approval Framework — mission_control/workflow_approval.py

Framework for operator-approved workflow execution.

Key principle: ALL workflows require EXPLICIT operator approval.
No workflow executes without approval.

Risk levels:
- low: Read-only operations, monitoring
- medium: Data processing, analytics
- high: External API calls, file modifications
- critical: Destructive operations, schema changes
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger("garvis.mission_control.workflow_approval")


# ---------------------------------------------------------------------------
# WorkflowApprovalFramework — operator approval for all workflows
# ---------------------------------------------------------------------------


class WorkflowApprovalFramework:
    """Framework for operator-approved workflow execution.

    Key principle: ALL workflows require EXPLICIT operator approval.
    No workflow executes without approval.

    Risk levels:
    - low: Read-only operations, monitoring
    - medium: Data processing, analytics
    - high: External API calls, file modifications
    - critical: Destructive operations, schema changes
    """

    RISK_LEVELS: dict[str, dict[str, str]] = {
        "low": {
            "description": "Read-only, no side effects",
            "approval": "self",
        },
        "medium": {
            "description": "Data processing, internal changes",
            "approval": "operator",
        },
        "high": {
            "description": "External calls, file modifications",
            "approval": "operator_explicit",
        },
        "critical": {
            "description": "Destructive, schema changes",
            "approval": "operator_multi",
        },
    }

    def __init__(self) -> None:
        self._proposals: dict[str, dict[str, Any]] = {}
        self._approval_history: list[dict[str, Any]] = []
        self._audit_records: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Risk classification
    # ------------------------------------------------------------------

    def classify_risk(self, workflow: dict[str, Any]) -> str:
        """Classify workflow risk level.

        Analyzes workflow operations to determine risk level.

        Args:
            workflow: The workflow dict with operations list.

        Returns:
            Risk level string: "low", "medium", "high", or "critical".
        """
        operations = workflow.get("operations", [])
        if not operations:
            return "low"

        # Check for critical-risk operations
        critical_ops = {
            "delete", "drop", "truncate", "rm", "purge",
            "schema_change", "disable_guardrail", "rollback",
        }
        for op in operations:
            op_type = op.get("type", "").lower()
            if op_type in critical_ops:
                return "critical"

        # Check for high-risk operations
        high_ops = {
            "api_call", "external_request", "webhook", "upload",
            "download", "send_email", "publish",
        }
        for op in operations:
            op_type = op.get("type", "").lower()
            if op_type in high_ops:
                return "high"

        # Check for medium-risk operations
        medium_ops = {
            "process", "transform", "aggregate", "analyze",
            "backup", "snapshot",
        }
        for op in operations:
            op_type = op.get("type", "").lower()
            if op_type in medium_ops:
                return "medium"

        # Default to low
        return "low"

    # ------------------------------------------------------------------
    # Submit for approval
    # ------------------------------------------------------------------

    def submit_for_approval(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """Submit a workflow for operator approval.

        Returns proposal with:
        - proposal_id
        - risk_level
        - required_approval
        - audit_record_id
        - status: pending_approval

        Args:
            workflow: The workflow dict to submit.

        Returns:
            Proposal result dict.
        """
        proposal_id = str(uuid4())
        audit_record_id = str(uuid4())

        # Classify risk
        risk_level = self.classify_risk(workflow)
        risk_info = self.RISK_LEVELS.get(risk_level, self.RISK_LEVELS["low"])

        # Create proposal record
        proposal = {
            "proposal_id": proposal_id,
            "workflow_name": workflow.get("name", "unnamed"),
            "workflow": workflow,
            "project_id": workflow.get("project_id", "unknown"),
            "risk_level": risk_level,
            "risk_description": risk_info["description"],
            "required_approval": risk_info["approval"],
            "audit_record_id": audit_record_id,
            "status": "pending_approval",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "approved_at": None,
            "approved_by": None,
            "rejected_at": None,
            "rejected_by": None,
            "rejection_reason": None,
        }

        self._proposals[proposal_id] = proposal

        # Create audit record
        self._audit_records[audit_record_id] = {
            "audit_record_id": audit_record_id,
            "proposal_id": proposal_id,
            "workflow_name": workflow.get("name", "unnamed"),
            "risk_level": risk_level,
            "events": [{
                "event": "submitted",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

        logger.info(
            "Workflow '%s' submitted for approval (proposal: %s, risk: %s)",
            workflow.get("name", "unnamed"),
            proposal_id,
            risk_level,
        )

        return {
            "proposal_id": proposal_id,
            "risk_level": risk_level,
            "risk_description": risk_info["description"],
            "required_approval": risk_info["approval"],
            "audit_record_id": audit_record_id,
            "status": "pending_approval",
            "note": (
                "Workflow is PENDING APPROVAL. It will NOT execute "
                "until explicitly approved by an operator."
            ),
        }

    # ------------------------------------------------------------------
    # Approve workflow
    # ------------------------------------------------------------------

    def approve_workflow(
        self, proposal_id: str, operator_id: str
    ) -> dict[str, Any]:
        """Operator approves a workflow proposal.

        Workflow status changes to: approved (but NOT executed yet).

        Args:
            proposal_id: The proposal to approve.
            operator_id: Operator approving.

        Returns:
            Approval result dict.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return {
                "proposal_id": proposal_id,
                "status": "error",
                "reason": "Proposal not found",
            }

        if proposal["status"] != "pending_approval":
            return {
                "proposal_id": proposal_id,
                "status": "error",
                "reason": f"Proposal is not pending approval (status: {proposal['status']})",
            }

        # Update proposal
        now = datetime.now(timezone.utc).isoformat()
        proposal["status"] = "approved"
        proposal["approved_at"] = now
        proposal["approved_by"] = operator_id

        # Update audit record
        audit_record = self._audit_records.get(proposal["audit_record_id"])
        if audit_record:
            audit_record["events"].append({
                "event": "approved",
                "operator_id": operator_id,
                "timestamp": now,
            })

        # Add to history
        self._approval_history.append({
            "proposal_id": proposal_id,
            "workflow_name": proposal["workflow_name"],
            "project_id": proposal["project_id"],
            "risk_level": proposal["risk_level"],
            "action": "approved",
            "operator_id": operator_id,
            "timestamp": now,
        })

        logger.info(
            "Workflow '%s' APPROVED by operator '%s' (proposal: %s)",
            proposal["workflow_name"],
            operator_id,
            proposal_id,
        )

        return {
            "proposal_id": proposal_id,
            "status": "approved",
            "approved_by": operator_id,
            "approved_at": now,
            "risk_level": proposal["risk_level"],
            "note": (
                "Workflow is APPROVED but NOT executed. "
                "Operator must manually trigger execution. "
                "Approval does not imply automatic execution."
            ),
        }

    # ------------------------------------------------------------------
    # Reject workflow
    # ------------------------------------------------------------------

    def reject_workflow(
        self, proposal_id: str, operator_id: str, reason: str
    ) -> dict[str, Any]:
        """Operator rejects a workflow proposal.

        Args:
            proposal_id: The proposal to reject.
            operator_id: Operator rejecting.
            reason: Reason for rejection.

        Returns:
            Rejection result dict.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return {
                "proposal_id": proposal_id,
                "status": "error",
                "reason": "Proposal not found",
            }

        if proposal["status"] != "pending_approval":
            return {
                "proposal_id": proposal_id,
                "status": "error",
                "reason": f"Proposal is not pending approval (status: {proposal['status']})",
            }

        # Update proposal
        now = datetime.now(timezone.utc).isoformat()
        proposal["status"] = "rejected"
        proposal["rejected_at"] = now
        proposal["rejected_by"] = operator_id
        proposal["rejection_reason"] = reason

        # Update audit record
        audit_record = self._audit_records.get(proposal["audit_record_id"])
        if audit_record:
            audit_record["events"].append({
                "event": "rejected",
                "operator_id": operator_id,
                "reason": reason,
                "timestamp": now,
            })

        # Add to history
        self._approval_history.append({
            "proposal_id": proposal_id,
            "workflow_name": proposal["workflow_name"],
            "project_id": proposal["project_id"],
            "risk_level": proposal["risk_level"],
            "action": "rejected",
            "operator_id": operator_id,
            "reason": reason,
            "timestamp": now,
        })

        logger.info(
            "Workflow '%s' REJECTED by operator '%s' (proposal: %s, reason: %s)",
            proposal["workflow_name"],
            operator_id,
            proposal_id,
            reason,
        )

        return {
            "proposal_id": proposal_id,
            "status": "rejected",
            "rejected_by": operator_id,
            "rejected_at": now,
            "reason": reason,
        }

    # ------------------------------------------------------------------
    # Query pending approvals
    # ------------------------------------------------------------------

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get all pending workflow approvals.

        Returns:
            List of pending proposal records.
        """
        pending = [
            {
                "proposal_id": p["proposal_id"],
                "workflow_name": p["workflow_name"],
                "project_id": p["project_id"],
                "risk_level": p["risk_level"],
                "required_approval": p["required_approval"],
                "submitted_at": p["submitted_at"],
            }
            for p in self._proposals.values()
            if p["status"] == "pending_approval"
        ]
        return sorted(pending, key=lambda x: x["submitted_at"])

    # ------------------------------------------------------------------
    # Approval history
    # ------------------------------------------------------------------

    def get_approval_history(self) -> list[dict[str, Any]]:
        """Get approval history.

        Returns:
            List of approval history records.
        """
        return sorted(
            self._approval_history,
            key=lambda x: x["timestamp"],
            reverse=True,
        )

    # ------------------------------------------------------------------
    # Audit workflow execution
    # ------------------------------------------------------------------

    def audit_workflow_execution(self, proposal_id: str) -> dict[str, Any]:
        """Create audit record for workflow execution.

        This creates a record of what WOULD be audited when a workflow
        is eventually executed. It does NOT execute the workflow.

        Args:
            proposal_id: The proposal to audit.

        Returns:
            Audit record dict.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return {
                "proposal_id": proposal_id,
                "status": "error",
                "reason": "Proposal not found",
            }

        audit_record_id = proposal["audit_record_id"]
        audit_record = self._audit_records.get(audit_record_id, {})

        # Add execution audit entry (preparatory)
        now = datetime.now(timezone.utc).isoformat()
        audit_record.setdefault("events", []).append({
            "event": "execution_audit_prepared",
            "timestamp": now,
            "note": (
                "Audit record prepared for workflow execution. "
                "This is a preparatory entry — workflow has not executed."
            ),
        })

        return {
            "proposal_id": proposal_id,
            "audit_record_id": audit_record_id,
            "status": "audit_prepared",
            "workflow_name": proposal["workflow_name"],
            "risk_level": proposal["risk_level"],
            "approval_status": proposal["status"],
            "audit_events": audit_record.get("events", []),
            "note": (
                "Audit record is prepared. When workflow is executed, "
                "all operations will be logged for full traceability."
            ),
        }

    # ------------------------------------------------------------------
    # Proposal lookup
    # ------------------------------------------------------------------

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        """Get a specific proposal by ID.

        Args:
            proposal_id: Proposal identifier.

        Returns:
            Proposal dict or None.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return None
        return {
            "proposal_id": proposal["proposal_id"],
            "workflow_name": proposal["workflow_name"],
            "project_id": proposal["project_id"],
            "risk_level": proposal["risk_level"],
            "required_approval": proposal["required_approval"],
            "status": proposal["status"],
            "submitted_at": proposal["submitted_at"],
            "approved_at": proposal["approved_at"],
            "approved_by": proposal["approved_by"],
            "rejected_at": proposal["rejected_at"],
            "rejected_by": proposal["rejected_by"],
            "rejection_reason": proposal["rejection_reason"],
        }
