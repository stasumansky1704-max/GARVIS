"""Mission Control — Preparation layer for future workflow integration.

This is PREPARATION ONLY. It does NOT execute workflows.
It shows what COULD be done, pending operator approval.

Features:
- Project overview
- Workflow readiness status
- Governance status for each project
- Action approval queue
- Windmill integration readiness
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from mission_control.workflow_approval import WorkflowApprovalFramework

logger = logging.getLogger("garvis.mission_control")


# ---------------------------------------------------------------------------
# MissionControl — project preparation and overview
# ---------------------------------------------------------------------------


class MissionControl:
    """Mission Control preparation layer for future workflow integration.

    This is PREPARATION ONLY. It does NOT execute workflows.
    It shows what COULD be done, pending operator approval.

    Features:
    - Project overview
    - Workflow readiness status
    - Governance status for each project
    - Action approval queue
    - Windmill integration readiness
    """

    PROJECTS: list[dict[str, str]] = [
        {
            "id": "garvis",
            "name": "GARVIS",
            "status": "active",
            "description": "Governance runtime — the core governance-aware system",
        },
        {
            "id": "alphaflow",
            "name": "AlphaFlow",
            "status": "planned",
            "description": "Workflow engine preparation — structured task automation",
        },
        {
            "id": "nova",
            "name": "NOVA",
            "status": "planned",
            "description": "Analytics platform preparation — data analysis and insights",
        },
        {
            "id": "teachflow",
            "name": "TeachFlow",
            "status": "planned",
            "description": "Education platform preparation — structured learning",
        },
        {
            "id": "bella",
            "name": "Bella & Friends",
            "status": "planned",
            "description": "Character system preparation — interactive characters",
        },
        {
            "id": "youtube",
            "name": "YouTube Engine",
            "status": "planned",
            "description": "Content engine preparation — video content automation",
        },
        {
            "id": "ops",
            "name": "General Ops",
            "status": "active",
            "description": "General operations — monitoring, maintenance, reporting",
        },
    ]

    # Workflow readiness criteria per project
    READINESS_CRITERIA: dict[str, list[str]] = {
        "garvis": [
            "governance_schemas_loaded",
            "state_machine_operational",
            "health_monitoring_active",
            "audit_logging_configured",
        ],
        "alphaflow": [
            "windmill_instance_detected",
            "workflow_templates_defined",
            "governance_constraints_mapped",
            "approval_framework_active",
        ],
        "nova": [
            "data_sources_connected",
            "analytics_pipelines_defined",
            "dashboard_configured",
            "metrics_collection_active",
        ],
        "teachflow": [
            "curriculum_schemas_defined",
            "assessment_framework_ready",
            "progress_tracking_configured",
        ],
        "bella": [
            "character_profiles_defined",
            "interaction_patterns_mapped",
            "response_governance_active",
        ],
        "youtube": [
            "content_templates_defined",
            "upload_pipeline_configured",
            "metadata_governance_active",
        ],
        "ops": [
            "monitoring_dashboard_active",
            "alert_rules_configured",
            "backup_procedures_defined",
        ],
    }

    def __init__(self) -> None:
        self._workflow_approval = WorkflowApprovalFramework()
        self._action_queue: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Project overview
    # ------------------------------------------------------------------

    def get_project_overview(self) -> list[dict[str, Any]]:
        """Get overview of all projects.

        Returns:
            List of project dicts with status and readiness info.
        """
        overview = []
        for project in self.PROJECTS:
            readiness = self.get_workflow_readiness(project["id"])
            overview.append({
                **project,
                "workflow_ready": readiness.get("ready", False),
                "readiness_score": readiness.get("score", 0.0),
                "pending_approvals": len([
                    a for a in self._workflow_approval.get_pending_approvals()
                    if a.get("project_id") == project["id"]
                ]),
            })
        return overview

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Get a specific project by ID.

        Args:
            project_id: Project identifier.

        Returns:
            Project dict or None if not found.
        """
        for project in self.PROJECTS:
            if project["id"] == project_id:
                return {
                    **project,
                    "readiness": self.get_workflow_readiness(project_id),
                    "governance": self.get_governance_status(project_id),
                }
        return None

    # ------------------------------------------------------------------
    # Workflow readiness
    # ------------------------------------------------------------------

    def get_workflow_readiness(self, project_id: str) -> dict[str, Any]:
        """Check if a project is ready for workflow integration.

        Evaluates readiness criteria and returns a score.

        Args:
            project_id: Project identifier.

        Returns:
            Readiness assessment dict.
        """
        criteria = self.READINESS_CRITERIA.get(project_id, [])
        if not criteria:
            return {
                "project_id": project_id,
                "ready": False,
                "score": 0.0,
                "reason": "No readiness criteria defined for this project",
                "criteria": [],
                "met": [],
                "missing": [],
            }

        # Check which criteria are met (simulated — in production these
        # would be actual system checks)
        met: list[str] = []
        missing: list[str] = []

        for criterion in criteria:
            # For active projects, simulate some criteria as met
            project = next(
                (p for p in self.PROJECTS if p["id"] == project_id), None
            )
            if project and project.get("status") == "active":
                # Active projects have partial readiness
                if criterion in (
                    "governance_schemas_loaded",
                    "health_monitoring_active",
                    "monitoring_dashboard_active",
                ):
                    met.append(criterion)
                else:
                    missing.append(criterion)
            else:
                # Planned projects have no criteria met yet
                missing.append(criterion)

        score = len(met) / len(criteria) if criteria else 0.0

        return {
            "project_id": project_id,
            "ready": score >= 0.8,
            "score": round(score, 2),
            "criteria_total": len(criteria),
            "criteria_met": len(met),
            "criteria_missing": len(missing),
            "met": met,
            "missing": missing,
            "assessment": (
                "ready" if score >= 0.8
                else "partial" if score >= 0.4
                else "not_ready"
            ),
        }

    # ------------------------------------------------------------------
    # Governance status per project
    # ------------------------------------------------------------------

    def get_governance_status(self, project_id: str) -> dict[str, Any]:
        """Get governance status for a project.

        Args:
            project_id: Project identifier.

        Returns:
            Governance status dict.
        """
        project = next(
            (p for p in self.PROJECTS if p["id"] == project_id), None
        )
        if project is None:
            return {
                "project_id": project_id,
                "status": "error",
                "reason": "Project not found",
            }

        # Governance status varies by project phase
        if project_id == "garvis":
            return {
                "project_id": project_id,
                "governance_active": True,
                "schemas_loaded": True,
                "enforcement_active": True,
                "fail_closed": True,
                "approval_framework": "active",
                "risk_classification": "enabled",
            }

        if project_id == "ops":
            return {
                "project_id": project_id,
                "governance_active": True,
                "schemas_loaded": True,
                "enforcement_active": True,
                "fail_closed": True,
                "approval_framework": "active",
                "risk_classification": "enabled",
            }

        # Planned projects have governance prepared but not fully active
        return {
            "project_id": project_id,
            "governance_active": False,
            "schemas_loaded": False,
            "enforcement_active": False,
            "fail_closed": True,  # Always fail-closed
            "approval_framework": "prepared",
            "risk_classification": "prepared",
            "note": (
                "Governance is prepared but not active. "
                "Will be activated when project moves to 'active' status."
            ),
        }

    # ------------------------------------------------------------------
    # Approval queue
    # ------------------------------------------------------------------

    def get_approval_queue(self) -> list[dict[str, Any]]:
        """Get pending workflow approvals.

        Returns:
            List of pending approval records.
        """
        return self._workflow_approval.get_pending_approvals()

    # ------------------------------------------------------------------
    # Windmill integration
    # ------------------------------------------------------------------

    def check_windmill_readiness(self) -> dict[str, Any]:
        """Check Windmill integration readiness.

        This ONLY DETECTS — it does not configure or connect.

        Returns:
            Dict with:
            - available: Whether Windmill appears to be available
            - url: Detected Windmill URL
            - status: Detection status
            - prepared_slots: Which projects have prepared slots
        """
        import subprocess

        # Try to detect Windmill
        windmill_detected = False
        windmill_url = "http://localhost:8000"  # Default Windmill port

        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 f"{windmill_url}/api/users/whoami"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip() in ("200", "401"):
                windmill_detected = True
                windmill_url = windmill_url
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass

        # Also check common alternative port
        if not windmill_detected:
            alt_url = "http://localhost:3000"
            try:
                result = subprocess.run(
                    ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                     f"{alt_url}/api/users/whoami"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip() in ("200", "401"):
                    windmill_detected = True
                    windmill_url = alt_url
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                pass

        # Which projects have prepared workflow slots
        prepared_slots = [
            p["id"] for p in self.PROJECTS
            if p["status"] in ("active", "planned")
            and p["id"] not in ("garvis", "ops")
        ]

        return {
            "available": windmill_detected,
            "url": windmill_url if windmill_detected else None,
            "status": (
                "detected" if windmill_detected
                else "not_detected"
            ),
            "prepared_slots": prepared_slots,
            "integration_note": (
                "Windmill detected but NOT integrated. "
                "Integration requires explicit operator approval."
                if windmill_detected else
                "Windmill not detected. Install and start Windmill, "
                "then re-check readiness."
            ),
            "approval_required": True,
        }

    # ------------------------------------------------------------------
    # Night-ops readiness
    # ------------------------------------------------------------------

    def get_night_ops_readiness(self) -> dict[str, Any]:
        """Get night-ops preparation status.

        Shows scheduling visibility, approval gates, task queue preview,
        audit requirements — but NO autonomous scheduling.

        Returns:
            Night-ops readiness dict.
        """
        return {
            "status": "preparation_only",
            "autonomous_scheduling": False,
            "scheduling_visible": True,
            "approval_gates": {
                "all_workflows_require_approval": True,
                "no_autonomous_execution": True,
                "operator_must_trigger": True,
                "audit_required": True,
            },
            "task_queue_preview": {
                "available": True,
                "note": (
                    "Task queue preview shows what COULD be scheduled. "
                    "Nothing executes without operator trigger."
                ),
                "sample_tasks": [
                    {
                        "name": "Daily health check",
                        "risk": "low",
                        "auto_permitted": False,
                        "requires": "operator_trigger",
                    },
                    {
                        "name": "Log rotation",
                        "risk": "low",
                        "auto_permitted": False,
                        "requires": "operator_trigger",
                    },
                    {
                        "name": "Backup snapshot",
                        "risk": "medium",
                        "auto_permitted": False,
                        "requires": "operator_approval",
                    },
                ],
            },
            "audit_requirements": {
                "all_night_ops_logged": True,
                "operator_action_required": True,
                "no_unattended_execution": True,
            },
            "note": (
                "Night-ops is VISIBILITY ONLY. No autonomous scheduling. "
                "Operator must review and manually trigger every task."
            ),
        }

    # ------------------------------------------------------------------
    # Workflow proposal
    # ------------------------------------------------------------------

    def propose_workflow(
        self, project_id: str, workflow: dict[str, Any]
    ) -> dict[str, Any]:
        """Propose a workflow for operator approval.

        Returns proposal with risk classification and required approval level.
        Does NOT execute — only proposes.

        Args:
            project_id: Target project ID.
            workflow: The workflow dict to propose.

        Returns:
            Proposal result dict.
        """
        # Validate project exists
        project = next(
            (p for p in self.PROJECTS if p["id"] == project_id), None
        )
        if project is None:
            return {
                "status": "error",
                "reason": f"Project '{project_id}' not found",
            }

        # Submit through the approval framework
        workflow["project_id"] = project_id
        proposal = self._workflow_approval.submit_for_approval(workflow)

        logger.info(
            "Workflow proposed for project '%s': '%s' (risk: %s, approval: %s)",
            project_id,
            workflow.get("name", "unnamed"),
            proposal.get("risk_level", "unknown"),
            proposal.get("required_approval", "unknown"),
        )

        return {
            "status": "proposed",
            "project_id": project_id,
            "project_name": project["name"],
            "proposal": proposal,
            "note": (
                "Workflow is PROPOSED only. It does NOT execute. "
                "Operator must approve before any action is taken."
            ),
        }

    # ------------------------------------------------------------------
    # Workflow approval passthrough
    # ------------------------------------------------------------------

    def approve_workflow(self, proposal_id: str, operator_id: str) -> dict[str, Any]:
        """Approve a workflow proposal (operator action).

        Args:
            proposal_id: Proposal ID to approve.
            operator_id: Operator approving.

        Returns:
            Approval result.
        """
        return self._workflow_approval.approve_workflow(proposal_id, operator_id)

    def reject_workflow(
        self, proposal_id: str, operator_id: str, reason: str
    ) -> dict[str, Any]:
        """Reject a workflow proposal (operator action).

        Args:
            proposal_id: Proposal ID to reject.
            operator_id: Operator rejecting.
            reason: Reason for rejection.

        Returns:
            Rejection result.
        """
        return self._workflow_approval.reject_workflow(
            proposal_id, operator_id, reason
        )

    def get_pending_workflow_approvals(self) -> list[dict[str, Any]]:
        """Get all pending workflow approvals.

        Returns:
            List of pending approval records.
        """
        return self._workflow_approval.get_pending_approvals()

    def get_workflow_approval_history(self) -> list[dict[str, Any]]:
        """Get workflow approval history.

        Returns:
            List of approval history records.
        """
        return self._workflow_approval.get_approval_history()
