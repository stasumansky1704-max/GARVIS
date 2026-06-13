"""Mission Control API Router — api/routers/mission_control.py

API endpoints for Mission Control project management and workflow approval.

All endpoints follow the observational-only principle:
- GET endpoints return data for operator review
- POST endpoints record operator decisions (approval/rejection)
- No endpoint executes workflows autonomously
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("garvis.api.mission_control")

router = APIRouter()

# ---------------------------------------------------------------------------
# Singleton Mission Control instance
# ---------------------------------------------------------------------------

_mission_control = None

def _get_mc():
    """Lazy initialization of MissionControl."""
    global _mission_control
    if _mission_control is None:
        from mission_control.controller import MissionControl
        _mission_control = MissionControl()
    return _mission_control


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------

@router.get("/projects", response_model=list[dict[str, Any]])
async def get_projects() -> list[dict[str, Any]]:
    """List all projects in Mission Control.

    Returns overview of all projects with their status,
    workflow readiness, and pending approvals.
    """
    mc = _get_mc()
    return mc.get_project_overview()


@router.get("/projects/{project_id}", response_model=dict[str, Any])
async def get_project(project_id: str) -> dict[str, Any]:
    """Get project details.

    Returns detailed information about a specific project including
    readiness and governance status.
    """
    mc = _get_mc()
    project = mc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project


@router.get("/projects/{project_id}/readiness", response_model=dict[str, Any])
async def get_project_readiness(project_id: str) -> dict[str, Any]:
    """Check workflow readiness for a project.

    Returns readiness assessment with criteria breakdown.
    """
    mc = _get_mc()
    # Validate project exists
    project = mc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return mc.get_workflow_readiness(project_id)


@router.get("/projects/{project_id}/governance", response_model=dict[str, Any])
async def get_project_governance(project_id: str) -> dict[str, Any]:
    """Get governance status for a project.

    Returns governance configuration and enforcement status.
    """
    mc = _get_mc()
    project = mc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return mc.get_governance_status(project_id)


# ---------------------------------------------------------------------------
# Approval endpoints
# ---------------------------------------------------------------------------

@router.get("/approvals", response_model=list[dict[str, Any]])
async def get_pending_approvals() -> list[dict[str, Any]]:
    """Get pending workflow approvals.

    Returns all workflows awaiting operator approval.
    """
    mc = _get_mc()
    return mc.get_approval_queue()


@router.post("/approvals/{proposal_id}/approve", response_model=dict[str, Any])
async def approve_workflow(
    proposal_id: str,
    operator_id: str = Query(..., description="Operator ID approving the workflow"),
) -> dict[str, Any]:
    """Approve a workflow proposal.

    The workflow status changes to 'approved' but is NOT executed.
    Execution requires a separate manual trigger.
    """
    mc = _get_mc()
    result = mc.approve_workflow(proposal_id, operator_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("reason", "Approval failed"))
    return result


@router.post("/approvals/{proposal_id}/reject", response_model=dict[str, Any])
async def reject_workflow(
    proposal_id: str,
    operator_id: str = Query(..., description="Operator ID rejecting the workflow"),
    reason: str = Query(..., description="Reason for rejection"),
) -> dict[str, Any]:
    """Reject a workflow proposal.

    Records the rejection with reason for audit purposes.
    """
    mc = _get_mc()
    result = mc.reject_workflow(proposal_id, operator_id, reason)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("reason", "Rejection failed"))
    return result


# ---------------------------------------------------------------------------
# Windmill integration
# ---------------------------------------------------------------------------

@router.get("/windmill/status", response_model=dict[str, Any])
async def get_windmill_status() -> dict[str, Any]:
    """Check Windmill integration readiness.

    Returns detection status only — no integration is performed.
    Integration requires explicit operator approval.
    """
    mc = _get_mc()
    return mc.check_windmill_readiness()


# ---------------------------------------------------------------------------
# Night-ops
# ---------------------------------------------------------------------------

@router.get("/night-ops/readiness", response_model=dict[str, Any])
async def get_night_ops_readiness() -> dict[str, Any]:
    """Get night-ops preparation status.

    Returns visibility into night-ops capabilities.
    NO autonomous scheduling — operator must trigger all tasks.
    """
    mc = _get_mc()
    return mc.get_night_ops_readiness()


# ---------------------------------------------------------------------------
# Workflow proposal
# ---------------------------------------------------------------------------

@router.post("/workflows/propose", response_model=dict[str, Any])
async def propose_workflow(
    project_id: str = Query(..., description="Target project ID"),
    workflow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Propose a workflow for approval. Does NOT execute.

    Submits a workflow for operator review and approval.
    The workflow is classified by risk level and requires
    appropriate operator approval before execution.
    """
    if workflow is None:
        raise HTTPException(status_code=400, detail="Workflow body is required")

    mc = _get_mc()
    result = mc.propose_workflow(project_id, workflow)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("reason", "Proposal failed"))
    return result
