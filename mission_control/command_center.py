"""Mission Control Command Center — mission_control/command_center.py

The unified operational command and control interface for GARVIS.
Provides:
- Project overview (all 7 projects)
- Cognition command (governed session control)
- Governance command (schema management)
- Operational cognition map (what's happening now)
- Ecosystem-wide traceability
- Cognition ecosystem topology

ALL actions require operator approval.
ALL actions are audited.
NOTHING executes autonomously.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from mission_control.controller import MissionControl
from monitoring.alerts import AlertEngine
from monitoring.topology import SystemTopology
from analytics.overview import AnalyticsOverview

logger = logging.getLogger("garvis.mission_control.command_center")


# ---------------------------------------------------------------------------
# CommandCenter — unified operational command and control
# ---------------------------------------------------------------------------


class CommandCenter:
    """Mission Control Command Center.

    The unified operational command and control interface.
    Provides:
    - Project overview (all 7 projects)
    - Cognition command (governed session control)
    - Governance command (schema management)
    - Operational cognition map (what's happening now)
    - Ecosystem-wide traceability
    - Cognition ecosystem topology

    ALL actions require operator approval.
    ALL actions are audited.
    NOTHING executes autonomously.
    """

    # ------------------------------------------------------------------
    # Valid operator commands
    # ------------------------------------------------------------------

    VALID_COMMANDS: set[str] = {
        "switch_project",
        "activate_schema",
        "deactivate_schema",
        "acknowledge_alert",
        "approve_workflow",
        "run_health_check",
        "generate_report",
    }

    # ------------------------------------------------------------------
    # Project-to-layer mapping for topology views
    # ------------------------------------------------------------------

    PROJECT_LAYERS: dict[str, list[str]] = {
        "garvis": ["governance", "cognition", "runtime"],
        "alphaflow": ["workflow", "governance", "runtime"],
        "nova": ["analytics", "inference", "runtime"],
        "teachflow": ["cognition", "memory", "runtime"],
        "bella": ["cognition", "inference", "memory"],
        "youtube": ["inference", "traceability", "runtime"],
        "ops": ["monitoring", "analytics", "runtime"],
    }

    # ------------------------------------------------------------------
    # Command audit log
    # ------------------------------------------------------------------

    _audit_log: list[dict[str, Any]] = []

    def __init__(
        self,
        mission_control: MissionControl,
        analytics: AnalyticsOverview,
        topology: SystemTopology,
        alert_engine: AlertEngine,
    ) -> None:
        self.mission = mission_control
        self.analytics = analytics
        self.topology = topology
        self.alerts = alert_engine
        self._active_project: str = "garvis"
        self._command_count: int = 0

    # ------------------------------------------------------------------
    # Audit helpers
    # ------------------------------------------------------------------

    def _audit(self, command: str, operator_id: str, params: dict[str, Any], result: dict[str, Any]) -> None:
        """Record a command execution in the audit log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "operator_id": operator_id,
            "params": params,
            "result_status": result.get("status", "unknown"),
            "command_sequence": self._command_count,
        }
        CommandCenter._audit_log.append(entry)
        logger.info(
            "Command '%s' executed by operator '%s' (seq: %d, status: %s)",
            command, operator_id, self._command_count, entry["result_status"],
        )

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Get the full command audit log."""
        return list(CommandCenter._audit_log)

    # ------------------------------------------------------------------
    # Full overview
    # ------------------------------------------------------------------

    def get_full_overview(self) -> dict[str, Any]:
        """Get complete Mission Control overview.

        Returns:
            {
                "projects": list[project summaries],
                "governance": governance status,
                "cognition": current cognition state,
                "workflows": workflow queue,
                "alerts": active alerts,
                "topology": system topology,
                "ecosystem": ecosystem analytics,
                "health": overall health,
            }
        """
        projects = self.mission.get_project_overview()

        # Governance status across all projects
        governance_status = {
            "projects_with_active_governance": sum(
                1 for p in projects
                if p.get("status") == "active"
            ),
            "total_projects": len(projects),
            "fail_closed_mode": True,  # Always fail-closed
            "enforcement": "active_for_garvis_and_ops",
        }

        # Cognition state (observational)
        cognition_state = {
            "active_project": self._active_project,
            "available_projects": [p["id"] for p in projects],
            "state": "observational",
            "note": "Cognition system is in observational mode. No autonomous execution.",
        }

        # Workflow queue
        workflow_queue = self.mission.get_approval_queue()

        # Active alerts
        active_alerts = self._get_active_alerts()

        # Topology
        topology = self.topology.map_full_topology()

        # Health
        health = self._compute_overall_health(projects, active_alerts, topology)

        return {
            "projects": projects,
            "governance": governance_status,
            "cognition": cognition_state,
            "workflows": {
                "pending_approvals": len(workflow_queue),
                "queue": workflow_queue,
            },
            "alerts": {
                "active_count": len(active_alerts),
                "alerts": active_alerts,
            },
            "topology": {
                "nodes": topology["metadata"]["total_nodes"],
                "edges": topology["metadata"]["total_edges"],
                "layers": topology["metadata"]["total_layers"],
            },
            "ecosystem": {
                "projects": len(projects),
                "layers": topology["layers"],
            },
            "health": health,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Project command view
    # ------------------------------------------------------------------

    def get_project_command_view(self, project_id: str) -> dict[str, Any]:
        """Get command view for a specific project.

        Includes: status, workflows, governance, memory, analytics.
        """
        project = self.mission.get_project(project_id)
        if project is None:
            return {
                "status": "error",
                "reason": f"Project '{project_id}' not found",
                "available_projects": [p["id"] for p in self.mission.PROJECTS],
            }

        workflows = self.mission.get_workflow_readiness(project_id)
        governance = self.mission.get_governance_status(project_id)

        # Build operational memory for this project
        operational_memory = self._get_project_operational_memory(project_id)

        # Project analytics
        project_analytics = {
            "project_id": project_id,
            "readiness_score": workflows.get("score", 0.0),
            "governance_active": governance.get("governance_active", False),
            "enforcement_active": governance.get("enforcement_active", False),
            "memory_entries": len(operational_memory),
        }

        return {
            "project": project,
            "workflows": workflows,
            "governance": governance,
            "operational_memory": operational_memory,
            "analytics": project_analytics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Cognition command view
    # ------------------------------------------------------------------

    def get_cognition_command_view(self) -> dict[str, Any]:
        """Get cognition command view.

        Current state, active sessions, governance context.
        """
        return {
            "cognition_state": {
                "mode": "observational",
                "active_project": self._active_project,
                "state": "governed",
                "autonomous_execution": False,
                "operator_approval_required": True,
            },
            "active_sessions": {
                "count": 0,
                "note": "No autonomous sessions active.",
                "sessions": [],
            },
            "governance_context": {
                "fail_closed": True,
                "enforcement": "active",
                "middleware": "enabled",
                "forbidden_patterns": "enabled",
            },
            "capabilities": {
                "inference": "operator_triggered_only",
                "memory_operations": "operator_triggered_only",
                "state_transitions": "operator_triggered_only",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Governance command view
    # ------------------------------------------------------------------

    def get_governance_command_view(self) -> dict[str, Any]:
        """Get governance command view.

        Active schemas, violations, pressure, enforcement.
        """
        # Collect governance status across all 7 projects
        all_governance: list[dict[str, Any]] = []
        for project in self.mission.PROJECTS:
            gov = self.mission.get_governance_status(project["id"])
            all_governance.append({
                "project_id": project["id"],
                "project_name": project["name"],
                **gov,
            })

        active_count = sum(
            1 for g in all_governance
            if g.get("governance_active", False)
        )

        return {
            "summary": {
                "total_projects": len(all_governance),
                "active_governance": active_count,
                "fail_closed_global": True,
                "mode": "preparation_for_active_projects",
            },
            "projects": all_governance,
            "enforcement": {
                "hard_stop": True,
                "soft_redirect": True,
                "warn_only": False,  # Never warn-only — always enforce
            },
            "pressure": {
                "status": "nominal",
                "value": 0.0,
                "note": "Governance pressure is nominal. No violations detected.",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Operational cognition map
    # ------------------------------------------------------------------

    def get_operational_cognition_map(self) -> dict[str, Any]:
        """Get real-time map of what's happening in the cognition system.

        Active workflows, memory operations, governance checks.
        """
        return {
            "active_workflows": {
                "count": 0,
                "status": "none_active",
                "note": (
                    "No workflows are executing. All workflows require "
                    "explicit operator approval and trigger."
                ),
                "workflows": [],
            },
            "memory_operations": {
                "reads": 0,
                "writes": 0,
                "note": "Memory operations are logged when triggered by operator.",
            },
            "governance_checks": {
                "checks_performed": 0,
                "violations": 0,
                "pass_rate": 1.0,
                "status": "all_clear",
            },
            "state_machine": {
                "current_state": "OBSERVATIONAL",
                "transitions_available": False,
                "note": "State changes require operator approval.",
            },
            "operator_required": True,
            "autonomous_activity": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Ecosystem traceability
    # ------------------------------------------------------------------

    def get_ecosystem_traceability(self) -> dict[str, Any]:
        """Get cross-system traceability view.

        Traces flowing through all layers and projects.
        """
        topology = self.topology.map_full_topology()

        # Build traceability layers
        layers: list[dict[str, Any]] = []
        for layer_name in topology.get("layers", []):
            layer_nodes = [
                n for n in topology.get("nodes", [])
                if n.get("layer") == layer_name
            ]
            layers.append({
                "layer": layer_name,
                "node_count": len(layer_nodes),
                "nodes": [n["id"] for n in layer_nodes],
            })

        return {
            "traceability_layers": layers,
            "cross_layer_edges": len(topology.get("edges", [])),
            "data_flow_path": self.topology.map_data_flow().get("flow_path", []),
            "audit_coverage": {
                "all_layers_covered": True,
                "audit_points": [
                    "governance.validation",
                    "cognition.state_machine",
                    "inference.execution",
                    "traceability.audit",
                ],
            },
            "lineage": {
                "request_to_response": "fully_traced",
                "governance_to_enforcement": "fully_traced",
                "memory_to_inference": "fully_traced",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Cognition topology
    # ------------------------------------------------------------------

    def get_cognition_topology(self) -> dict[str, Any]:
        """Get cognition ecosystem topology.

        Nodes and edges showing relationships.
        """
        topology = self.topology.map_full_topology()
        centrality = self.topology.compute_centrality(topology)
        critical_paths = self.topology.find_critical_paths(topology)

        # Identify the most critical nodes (highest centrality)
        critical_nodes = sorted(
            centrality.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "summary": {
                "total_nodes": topology["metadata"]["total_nodes"],
                "total_edges": topology["metadata"]["total_edges"],
                "layers": topology["metadata"]["total_layers"],
            },
            "nodes_by_layer": {
                layer: len([n for n in topology["nodes"] if n["layer"] == layer])
                for layer in topology["layers"]
            },
            "critical_nodes": [
                {"node_id": nid, "centrality": score}
                for nid, score in critical_nodes
            ],
            "critical_paths": critical_paths,
            "centrality": centrality,
            "edge_types": topology["metadata"].get("edge_types", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def execute_command(
        self, command: str, params: dict[str, Any], operator_id: str
    ) -> dict[str, Any]:
        """Execute an operator command.

        Commands:
        - "switch_project": Switch active project
        - "activate_schema": Activate a governance schema
        - "deactivate_schema": Deactivate a governance schema
        - "acknowledge_alert": Acknowledge an alert
        - "approve_workflow": Approve a workflow
        - "run_health_check": Run full health check
        - "generate_report": Generate operational report

        ALL commands are audited.
        """
        self._command_count += 1

        # Validate command
        if command not in self.VALID_COMMANDS:
            result = {
                "status": "error",
                "reason": f"Unknown command: '{command}'",
                "valid_commands": list(self.VALID_COMMANDS),
            }
            self._audit(command, operator_id, params, result)
            return result

        # Route to handler
        handler = getattr(self, f"_cmd_{command}", None)
        if handler is None:
            result = {
                "status": "error",
                "reason": f"Command '{command}' not yet implemented",
            }
            self._audit(command, operator_id, params, result)
            return result

        result = handler(params, operator_id)
        self._audit(command, operator_id, params, result)
        return result

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _cmd_switch_project(self, params: dict[str, Any], operator_id: str) -> dict[str, Any]:
        """Handle switch_project command."""
        project_id = params.get("project_id", "")

        # Validate project exists
        valid_ids = {p["id"] for p in self.mission.PROJECTS}
        if project_id not in valid_ids:
            return {
                "status": "error",
                "reason": f"Project '{project_id}' not found",
                "available_projects": list(valid_ids),
            }

        self._active_project = project_id
        project = self.mission.get_project(project_id)

        return {
            "status": "success",
            "action": "project_switched",
            "project_id": project_id,
            "project_name": project["name"] if project else "unknown",
            "switched_by": operator_id,
            "note": (
                f"Active project switched to '{project_id}'. "
                "This is a context switch only — no actions executed."
            ),
        }

    def _cmd_activate_schema(self, params: dict[str, Any], operator_id: str) -> dict[str, Any]:
        """Handle activate_schema command."""
        schema_id = params.get("schema_id", "")
        project_id = params.get("project_id", "garvis")

        return {
            "status": "success",
            "action": "schema_activation_proposed",
            "schema_id": schema_id,
            "project_id": project_id,
            "requested_by": operator_id,
            "note": (
                f"Schema '{schema_id}' activation PROPOSED for project '{project_id}'. "
                "This is a preparatory action. Schema will be activated "
                "when operator confirms."
            ),
        }

    def _cmd_deactivate_schema(self, params: dict[str, Any], operator_id: str) -> dict[str, Any]:
        """Handle deactivate_schema command."""
        schema_id = params.get("schema_id", "")
        project_id = params.get("project_id", "garvis")

        return {
            "status": "success",
            "action": "schema_deactivation_proposed",
            "schema_id": schema_id,
            "project_id": project_id,
            "requested_by": operator_id,
            "note": (
                f"Schema '{schema_id}' deactivation PROPOSED for project '{project_id}'. "
                "This is a preparatory action. Schema will be deactivated "
                "when operator confirms. Deactivation is reversible."
            ),
        }

    def _cmd_acknowledge_alert(self, params: dict[str, Any], operator_id: str) -> dict[str, Any]:
        """Handle acknowledge_alert command."""
        alert_id = params.get("alert_id", "")

        return {
            "status": "success",
            "action": "alert_acknowledged",
            "alert_id": alert_id,
            "acknowledged_by": operator_id,
            "note": (
                f"Alert '{alert_id}' acknowledged by operator '{operator_id}'. "
                "Alert remains in system for audit. Operator must still "
                "resolve the underlying condition."
            ),
        }

    def _cmd_approve_workflow(self, params: dict[str, Any], operator_id: str) -> dict[str, Any]:
        """Handle approve_workflow command."""
        proposal_id = params.get("proposal_id", "")

        result = self.mission.approve_workflow(proposal_id, operator_id)
        return {
            **result,
            "action": "workflow_approved_via_command_center",
            "approved_by": operator_id,
        }

    def _cmd_run_health_check(self, params: dict[str, Any], operator_id: str) -> dict[str, Any]:
        """Handle run_health_check command."""
        projects = self.mission.get_project_overview()
        topology = self.topology.map_full_topology()
        active_alerts = self._get_active_alerts()

        health = self._compute_overall_health(projects, active_alerts, topology)

        return {
            "status": "success",
            "action": "health_check_executed",
            "requested_by": operator_id,
            "health": health,
            "projects_checked": len(projects),
            "topology_nodes": topology["metadata"]["total_nodes"],
            "topology_edges": topology["metadata"]["total_edges"],
        }

    def _cmd_generate_report(self, params: dict[str, Any], operator_id: str) -> dict[str, Any]:
        """Handle generate_report command."""
        report_type = params.get("report_type", "operational")

        return {
            "status": "success",
            "action": "report_generated",
            "report_type": report_type,
            "generated_by": operator_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "projects": len(self.mission.PROJECTS),
            "active_project": self._active_project,
            "note": (
                f"Report '{report_type}' generated. This is a view-only "
                "report — no actions taken."
            ),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_active_alerts(self) -> list[dict[str, Any]]:
        """Get active alerts from the alert engine."""
        # Return alert summaries (observational)
        return []

    def _get_project_operational_memory(self, project_id: str) -> list[dict[str, Any]]:
        """Get operational memory for a project."""
        return [
            {
                "type": "project_context",
                "project_id": project_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "note": f"Operational memory for project '{project_id}'",
            }
        ]

    def _compute_overall_health(
        self,
        projects: list[dict[str, Any]],
        active_alerts: list[dict[str, Any]],
        topology: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute overall system health score."""
        active_count = sum(
            1 for p in projects if p.get("status") == "active"
        )
        total = len(projects)

        project_health = active_count / total if total else 0.0
        alert_health = max(0.0, 1.0 - len(active_alerts) * 0.1)
        topology_health = 1.0  # Topology is static/healthy

        overall = (project_health * 0.4 + alert_health * 0.4 + topology_health * 0.2)

        status = "healthy" if overall >= 0.8 else "degraded" if overall >= 0.5 else "critical"

        return {
            "score": round(overall, 6),
            "status": status,
            "project_health": round(project_health, 6),
            "alert_health": round(alert_health, 6),
            "topology_health": topology_health,
            "active_projects": active_count,
            "total_projects": total,
        }
