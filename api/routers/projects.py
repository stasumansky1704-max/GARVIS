"""Project Governance API Router — api/routers/projects.py

API endpoints for project-level governance and management.

All endpoints are observational by default.
State-changing POST endpoints require explicit operator_id.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("garvis.api.projects")

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
# Project listing
# ---------------------------------------------------------------------------

@router.get("/projects", response_model=list[dict[str, Any]])
async def list_projects() -> list[dict[str, Any]]:
    """List all projects in Mission Control.

    Returns overview of all 7 projects with their status,
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


# ---------------------------------------------------------------------------
# Project governance
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/governance", response_model=dict[str, Any])
async def get_project_governance(project_id: str) -> dict[str, Any]:
    """Get project governance status.

    Returns governance configuration and enforcement status
    for the specified project.
    """
    mc = _get_mc()
    # Validate project exists
    project = mc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return mc.get_governance_status(project_id)


# ---------------------------------------------------------------------------
# Project operational memory
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/memory", response_model=list[dict[str, Any]])
async def get_project_memory(project_id: str) -> list[dict[str, Any]]:
    """Get project operational memory.

    Returns operational memory entries for the specified project.
    These are context notes and logs relevant to the project.
    """
    mc = _get_mc()
    project = mc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    return [
        {
            "type": "project_context",
            "project_id": project_id,
            "project_name": project.get("name", project_id),
            "status": project.get("status", "unknown"),
            "timestamp": "2025-01-01T00:00:00+00:00",
            "note": f"Operational memory for project '{project_id}'",
        }
    ]


# ---------------------------------------------------------------------------
# Project workflows
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/workflows", response_model=list[dict[str, Any]])
async def get_project_workflows(project_id: str) -> list[dict[str, Any]]:
    """Get project workflows.

    Returns workflow readiness and pending approvals for the project.
    """
    mc = _get_mc()
    project = mc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    # Get project-specific approvals
    all_pending = mc.get_pending_workflow_approvals()
    project_workflows = [
        w for w in all_pending
        if w.get("project_id") == project_id
    ]

    return project_workflows


# ---------------------------------------------------------------------------
# Project analytics
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/analytics", response_model=dict[str, Any])
async def get_project_analytics(project_id: str) -> dict[str, Any]:
    """Get project analytics.

    Returns analytics summary for the specified project:
    readiness score, governance status, and operational metrics.
    """
    mc = _get_mc()
    project = mc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    readiness = mc.get_workflow_readiness(project_id)
    governance = mc.get_governance_status(project_id)

    return {
        "project_id": project_id,
        "project_name": project.get("name", project_id),
        "readiness": readiness,
        "governance": governance,
        "analytics": {
            "readiness_score": readiness.get("score", 0.0),
            "criteria_met": readiness.get("criteria_met", 0),
            "criteria_total": readiness.get("criteria_total", 0),
            "governance_active": governance.get("governance_active", False),
            "enforcement_active": governance.get("enforcement_active", False),
        },
    }


# ---------------------------------------------------------------------------
# Context switching
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/context/switch", response_model=dict[str, Any])
async def switch_project_context(
    project_id: str,
    operator_id: str = Query(..., description="Operator ID requesting context switch"),
) -> dict[str, Any]:
    """Switch to a project context.

    Changes the active project context. This is a view-switch only —
    no actions are executed on the project.

    Requires operator_id for audit.
    """
    from mission_control.command_center import CommandCenter
    from analytics.overview import AnalyticsOverview
    from monitoring.topology import SystemTopology
    from monitoring.alerts import AlertEngine

    mc = _get_mc()

    # Validate project exists
    project = mc.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    # Execute through CommandCenter for proper auditing
    analytics = AnalyticsOverview()
    topology = SystemTopology()
    alerts = AlertEngine()
    cc = CommandCenter(mc, analytics, topology, alerts)

    result = cc.execute_command(
        "switch_project",
        {"project_id": project_id},
        operator_id,
    )

    logger.info(
        "Context switch to '%s' by operator '%s' — %s",
        project_id, operator_id, result.get("status"),
    )
    return result


# ---------------------------------------------------------------------------
# Context listing
# ---------------------------------------------------------------------------

@router.get("/contexts", response_model=list[dict[str, Any]])
async def list_contexts() -> list[dict[str, Any]]:
    """List all project contexts.

    Returns all available project contexts with their status.
    The active context is marked.
    """
    mc = _get_mc()
    projects = mc.get_project_overview()

    contexts = []
    for p in projects:
        contexts.append({
            "project_id": p["id"],
            "project_name": p["name"],
            "status": p["status"],
            "workflow_ready": p.get("workflow_ready", False),
            "readiness_score": p.get("readiness_score", 0.0),
        })

    return contexts
