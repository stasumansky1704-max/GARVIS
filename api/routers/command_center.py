"""Command Center API Router — api/routers/command_center.py

API endpoints for the Mission Control Command Center.

All endpoints follow the observational-only principle:
- GET endpoints return data for operator review
- POST endpoints record operator decisions (commands)
- No endpoint executes workflows autonomously
- ALL commands require operator_id for audit
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("garvis.api.command_center")

router = APIRouter()

# ---------------------------------------------------------------------------
# Singleton instances (lazy initialization)
# ---------------------------------------------------------------------------

_command_center = None
_ecosystem_observability = None


def _get_cc():
    """Lazy initialization of CommandCenter."""
    global _command_center
    if _command_center is None:
        from mission_control.controller import MissionControl
        from analytics.overview import AnalyticsOverview
        from monitoring.topology import SystemTopology
        from monitoring.alerts import AlertEngine
        from mission_control.command_center import CommandCenter

        mission = MissionControl()
        analytics = AnalyticsOverview()
        topology = SystemTopology()
        alerts = AlertEngine()
        _command_center = CommandCenter(mission, analytics, topology, alerts)
    return _command_center


def _get_eco():
    """Lazy initialization of EcosystemObservability."""
    global _ecosystem_observability
    if _ecosystem_observability is None:
        from mission_control.ecosystem import EcosystemObservability
        _ecosystem_observability = EcosystemObservability()
    return _ecosystem_observability


# ---------------------------------------------------------------------------
# Command Center Overview
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=dict[str, Any])
async def get_full_overview() -> dict[str, Any]:
    """Get complete Mission Control overview.

    Returns unified view of all projects, governance status,
    cognition state, workflows, alerts, topology, ecosystem, and health.
    """
    cc = _get_cc()
    return cc.get_full_overview()


# ---------------------------------------------------------------------------
# Project Command Views
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/command", response_model=dict[str, Any])
async def get_project_command_view(project_id: str) -> dict[str, Any]:
    """Get command view for a specific project.

    Includes: status, workflows, governance, memory, analytics.
    """
    cc = _get_cc()
    result = cc.get_project_command_view(project_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("reason", "Project not found"))
    return result


# ---------------------------------------------------------------------------
# Cognition Command View
# ---------------------------------------------------------------------------

@router.get("/cognition/command", response_model=dict[str, Any])
async def get_cognition_command_view() -> dict[str, Any]:
    """Get cognition command view.

    Current state, active sessions, governance context.
    """
    cc = _get_cc()
    return cc.get_cognition_command_view()


# ---------------------------------------------------------------------------
# Governance Command View
# ---------------------------------------------------------------------------

@router.get("/governance/command", response_model=dict[str, Any])
async def get_governance_command_view() -> dict[str, Any]:
    """Get governance command view.

    Active schemas, violations, pressure, enforcement.
    """
    cc = _get_cc()
    return cc.get_governance_command_view()


# ---------------------------------------------------------------------------
# Operational Cognition Map
# ---------------------------------------------------------------------------

@router.get("/operational-map", response_model=dict[str, Any])
async def get_operational_cognition_map() -> dict[str, Any]:
    """Get real-time operational cognition map.

    Active workflows, memory operations, governance checks.
    """
    cc = _get_cc()
    return cc.get_operational_cognition_map()


# ---------------------------------------------------------------------------
# Ecosystem Traceability
# ---------------------------------------------------------------------------

@router.get("/ecosystem/traceability", response_model=dict[str, Any])
async def get_ecosystem_traceability() -> dict[str, Any]:
    """Get ecosystem-wide traceability.

    Traces flowing through all layers and projects.
    """
    cc = _get_cc()
    return cc.get_ecosystem_traceability()


# ---------------------------------------------------------------------------
# Ecosystem Topology
# ---------------------------------------------------------------------------

@router.get("/ecosystem/topology", response_model=dict[str, Any])
async def get_cognition_topology() -> dict[str, Any]:
    """Get cognition ecosystem topology.

    Nodes and edges showing relationships.
    """
    cc = _get_cc()
    return cc.get_cognition_topology()


# ---------------------------------------------------------------------------
# Ecosystem Sub-views
# ---------------------------------------------------------------------------

@router.get("/ecosystem/governance", response_model=dict[str, Any])
async def get_governance_ecosystem() -> dict[str, Any]:
    """Get governance ecosystem.

    Schema interactions, enforcement patterns, cross-project inheritance.
    """
    eco = _get_eco()
    return eco.get_governance_ecosystem()


@router.get("/ecosystem/cognition", response_model=dict[str, Any])
async def get_cognition_ecosystem() -> dict[str, Any]:
    """Get cognition ecosystem.

    Component dependencies and influence flows.
    """
    eco = _get_eco()
    return eco.get_cognition_ecosystem()


@router.get("/ecosystem/resilience", response_model=dict[str, Any])
async def get_resilience_ecosystem() -> dict[str, Any]:
    """Get resilience ecosystem.

    Degradation patterns and recovery flows.
    """
    eco = _get_eco()
    return eco.get_resilience_ecosystem()


@router.get("/ecosystem/continuity", response_model=dict[str, Any])
async def get_continuity_ecosystem() -> dict[str, Any]:
    """Get continuity ecosystem.

    Session continuity and alignment persistence.
    """
    eco = _get_eco()
    return eco.get_continuity_ecosystem()


@router.get("/ecosystem/full", response_model=dict[str, Any])
async def get_full_ecosystem() -> dict[str, Any]:
    """Get complete ecosystem view.

    All sub-ecosystems combined with project context.
    """
    eco = _get_eco()
    return eco.get_full_ecosystem()


# ---------------------------------------------------------------------------
# Operational Analytics
# ---------------------------------------------------------------------------

@router.get("/analytics/operational", response_model=dict[str, Any])
async def get_operational_analytics() -> dict[str, Any]:
    """Get reflective operational analytics.

    Governance durability, alignment survivability, workflow integrity.
    """
    eco = _get_eco()
    return eco.get_operational_analytics()


# ---------------------------------------------------------------------------
# Command Execution
# ---------------------------------------------------------------------------

@router.post("/command/execute", response_model=dict[str, Any])
async def execute_command(
    command: str = Query(..., description="Command to execute"),
    params: dict[str, Any] | None = None,
    operator_id: str = Query(..., description="Operator ID executing the command"),
) -> dict[str, Any]:
    """Execute an operator command.

    Valid commands:
    - switch_project: Switch active project context
    - activate_schema: Activate a governance schema
    - deactivate_schema: Deactivate a governance schema
    - acknowledge_alert: Acknowledge an alert
    - approve_workflow: Approve a workflow proposal
    - run_health_check: Run full health check
    - generate_report: Generate operational report

    ALL commands are audited. operator_id is required.
    """
    if params is None:
        params = {}

    cc = _get_cc()
    result = cc.execute_command(command, params, operator_id)

    if result.get("status") == "error":
        raise HTTPException(
            status_code=400,
            detail=result.get("reason", "Command execution failed"),
        )

    logger.info(
        "Command '%s' executed by operator '%s' — status: %s",
        command, operator_id, result.get("status"),
    )
    return result
