"""Tests for Mission Control Command Center and Ecosystem Observability.

Tests cover:
- Command center overview
- Ecosystem views (governance, cognition, resilience, continuity)
- Operational analytics
- Command execution
- Project governance API

All tests use mock data and follow the observational-only principle.
"""

from __future__ import annotations

import pytest

from mission_control.command_center import CommandCenter
from mission_control.controller import MissionControl
from mission_control.ecosystem import EcosystemObservability
from analytics.overview import AnalyticsOverview
from monitoring.topology import SystemTopology
from monitoring.alerts import AlertEngine


# ============================================================================
#  Fixtures
# ============================================================================


@pytest.fixture
def mission_control():
    """Create a fresh MissionControl instance."""
    return MissionControl()


@pytest.fixture
def analytics():
    """Create a fresh AnalyticsOverview instance."""
    return AnalyticsOverview()


@pytest.fixture
def topology():
    """Create a fresh SystemTopology instance."""
    return SystemTopology()


@pytest.fixture
def alert_engine():
    """Create a fresh AlertEngine instance."""
    return AlertEngine()


@pytest.fixture
def command_center(mission_control, analytics, topology, alert_engine):
    """Create a fresh CommandCenter instance."""
    return CommandCenter(mission_control, analytics, topology, alert_engine)


@pytest.fixture
def ecosystem():
    """Create a fresh EcosystemObservability instance."""
    return EcosystemObservability()


# ============================================================================
#  Test: Command Center Overview
# ============================================================================


class TestCommandCenterOverview:
    """Test the Command Center overview functionality."""

    def test_full_overview_returns_dict(self, command_center):
        """get_full_overview returns a dictionary."""
        overview = command_center.get_full_overview()
        assert isinstance(overview, dict)

    def test_full_overview_has_all_sections(self, command_center):
        """Overview contains all expected sections."""
        overview = command_center.get_full_overview()
        expected_keys = {
            "projects", "governance", "cognition", "workflows",
            "alerts", "topology", "ecosystem", "health", "timestamp",
        }
        assert expected_keys.issubset(overview.keys())

    def test_full_overview_has_seven_projects(self, command_center):
        """Overview contains all 7 projects."""
        overview = command_center.get_full_overview()
        assert len(overview["projects"]) == 7

    def test_project_ids_are_correct(self, command_center):
        """All 7 expected project IDs are present."""
        overview = command_center.get_full_overview()
        project_ids = {p["id"] for p in overview["projects"]}
        expected = {"garvis", "alphaflow", "nova", "teachflow", "bella", "youtube", "ops"}
        assert project_ids == expected

    def test_governance_section_has_status(self, command_center):
        """Governance section contains status info."""
        overview = command_center.get_full_overview()
        assert "fail_closed_mode" in overview["governance"]
        assert overview["governance"]["fail_closed_mode"] is True

    def test_cognition_section_is_observational(self, command_center):
        """Cognition section indicates observational mode."""
        overview = command_center.get_full_overview()
        assert overview["cognition"]["state"] == "observational"

    def test_workflows_section_has_pending_count(self, command_center):
        """Workflows section has pending approvals count."""
        overview = command_center.get_full_overview()
        assert "pending_approvals" in overview["workflows"]
        assert isinstance(overview["workflows"]["pending_approvals"], int)

    def test_alerts_section_is_list(self, command_center):
        """Alerts section returns a list of active alerts."""
        overview = command_center.get_full_overview()
        assert isinstance(overview["alerts"]["alerts"], list)

    def test_topology_section_has_counts(self, command_center):
        """Topology section has node and edge counts."""
        overview = command_center.get_full_overview()
        assert isinstance(overview["topology"]["nodes"], int)
        assert isinstance(overview["topology"]["edges"], int)
        assert overview["topology"]["nodes"] > 0

    def test_health_section_has_score(self, command_center):
        """Health section has a score."""
        overview = command_center.get_full_overview()
        assert "score" in overview["health"]
        assert 0.0 <= overview["health"]["score"] <= 1.0

    def test_health_status_is_valid(self, command_center):
        """Health status is one of the valid values."""
        overview = command_center.get_full_overview()
        assert overview["health"]["status"] in {"healthy", "degraded", "critical"}

    def test_timestamp_is_present(self, command_center):
        """Overview includes a timestamp."""
        overview = command_center.get_full_overview()
        assert isinstance(overview["timestamp"], str)
        assert len(overview["timestamp"]) > 0


# ============================================================================
#  Test: Project Command View
# ============================================================================


class TestProjectCommandView:
    """Test project-specific command views."""

    def test_valid_project_returns_dict(self, command_center):
        """get_project_command_view returns a dict for valid project."""
        view = command_center.get_project_command_view("garvis")
        assert isinstance(view, dict)
        assert view.get("status") != "error"

    def test_invalid_project_returns_error(self, command_center):
        """get_project_command_view returns error for invalid project."""
        view = command_center.get_project_command_view("nonexistent")
        assert view["status"] == "error"

    def test_project_view_has_all_sections(self, command_center):
        """Project view contains all expected sections."""
        view = command_center.get_project_command_view("garvis")
        expected_keys = {"project", "workflows", "governance", "operational_memory", "analytics", "timestamp"}
        assert expected_keys.issubset(view.keys())

    def test_project_view_workflows_has_score(self, command_center):
        """Project view workflows section has readiness score."""
        view = command_center.get_project_command_view("garvis")
        assert "score" in view["workflows"]

    def test_project_view_governance_has_status(self, command_center):
        """Project view governance section has governance status."""
        view = command_center.get_project_command_view("garvis")
        assert "governance_active" in view["governance"]

    def test_active_project_has_partial_readiness(self, command_center):
        """Active project (garvis) has partial readiness."""
        view = command_center.get_project_command_view("garvis")
        score = view["workflows"]["score"]
        assert score > 0.0

    def test_ops_project_is_active(self, command_center):
        """Ops project has active status."""
        view = command_center.get_project_command_view("ops")
        assert view["project"]["status"] == "active"

    def test_all_seven_projects_are_accessible(self, command_center):
        """All 7 projects can be queried."""
        project_ids = ["garvis", "alphaflow", "nova", "teachflow", "bella", "youtube", "ops"]
        for pid in project_ids:
            view = command_center.get_project_command_view(pid)
            assert view.get("status") != "error", f"Project {pid} should be accessible"


# ============================================================================
#  Test: Cognition Command View
# ============================================================================


class TestCognitionCommandView:
    """Test cognition command view."""

    def test_returns_dict(self, command_center):
        """get_cognition_command_view returns a dict."""
        view = command_center.get_cognition_command_view()
        assert isinstance(view, dict)

    def test_mode_is_observational(self, command_center):
        """Cognition mode is observational."""
        view = command_center.get_cognition_command_view()
        assert view["cognition_state"]["mode"] == "observational"

    def test_autonomous_execution_is_false(self, command_center):
        """Autonomous execution is disabled."""
        view = command_center.get_cognition_command_view()
        assert view["cognition_state"]["autonomous_execution"] is False

    def test_operator_approval_required(self, command_center):
        """Operator approval is required for all actions."""
        view = command_center.get_cognition_command_view()
        assert view["cognition_state"]["operator_approval_required"] is True

    def test_has_capabilities_section(self, command_center):
        """Cognition view has capabilities section."""
        view = command_center.get_cognition_command_view()
        assert "capabilities" in view

    def test_has_governance_context(self, command_center):
        """Cognition view has governance context."""
        view = command_center.get_cognition_command_view()
        assert "governance_context" in view
        assert view["governance_context"]["fail_closed"] is True


# ============================================================================
#  Test: Governance Command View
# ============================================================================


class TestGovernanceCommandView:
    """Test governance command view."""

    def test_returns_dict(self, command_center):
        """get_governance_command_view returns a dict."""
        view = command_center.get_governance_command_view()
        assert isinstance(view, dict)

    def test_has_summary(self, command_center):
        """Governance view has summary section."""
        view = command_center.get_governance_command_view()
        assert "summary" in view

    def test_has_all_projects(self, command_center):
        """Governance view covers all 7 projects."""
        view = command_center.get_governance_command_view()
        assert len(view["projects"]) == 7

    def test_enforcement_has_hard_stop(self, command_center):
        """Enforcement includes hard_stop."""
        view = command_center.get_governance_command_view()
        assert view["enforcement"]["hard_stop"] is True

    def test_fail_closed_global_is_true(self, command_center):
        """Global fail-closed is always true."""
        view = command_center.get_governance_command_view()
        assert view["summary"]["fail_closed_global"] is True

    def test_active_governance_count(self, command_center):
        """Active governance count matches active projects."""
        view = command_center.get_governance_command_view()
        assert view["summary"]["active_governance"] == 2  # garvis and ops


# ============================================================================
#  Test: Operational Cognition Map
# ============================================================================


class TestOperationalCognitionMap:
    """Test operational cognition map."""

    def test_returns_dict(self, command_center):
        """get_operational_cognition_map returns a dict."""
        m = command_center.get_operational_cognition_map()
        assert isinstance(m, dict)

    def test_no_active_workflows(self, command_center):
        """No workflows are active autonomously."""
        m = command_center.get_operational_cognition_map()
        assert m["active_workflows"]["count"] == 0

    def test_operator_required(self, command_center):
        """Operator is required for all actions."""
        m = command_center.get_operational_cognition_map()
        assert m["operator_required"] is True

    def test_no_autonomous_activity(self, command_center):
        """No autonomous activity is occurring."""
        m = command_center.get_operational_cognition_map()
        assert m["autonomous_activity"] is False

    def test_has_governance_checks(self, command_center):
        """Map includes governance checks section."""
        m = command_center.get_operational_cognition_map()
        assert "governance_checks" in m

    def test_governance_all_clear(self, command_center):
        """Governance status is all clear."""
        m = command_center.get_operational_cognition_map()
        assert m["governance_checks"]["status"] == "all_clear"


# ============================================================================
#  Test: Ecosystem Traceability
# ============================================================================


class TestEcosystemTraceability:
    """Test ecosystem traceability view."""

    def test_returns_dict(self, command_center):
        """get_ecosystem_traceability returns a dict."""
        t = command_center.get_ecosystem_traceability()
        assert isinstance(t, dict)

    def test_has_traceability_layers(self, command_center):
        """Traceability has layers section."""
        t = command_center.get_ecosystem_traceability()
        assert "traceability_layers" in t
        assert len(t["traceability_layers"]) > 0

    def test_has_data_flow_path(self, command_center):
        """Traceability has data flow path."""
        t = command_center.get_ecosystem_traceability()
        assert "data_flow_path" in t
        assert len(t["data_flow_path"]) > 0

    def test_audit_coverage_is_full(self, command_center):
        """Audit coverage is full."""
        t = command_center.get_ecosystem_traceability()
        assert t["audit_coverage"]["all_layers_covered"] is True

    def test_lineage_is_fully_traced(self, command_center):
        """Lineage is fully traced."""
        t = command_center.get_ecosystem_traceability()
        assert t["lineage"]["request_to_response"] == "fully_traced"


# ============================================================================
#  Test: Cognition Topology
# ============================================================================


class TestCognitionTopology:
    """Test cognition topology view."""

    def test_returns_dict(self, command_center):
        """get_cognition_topology returns a dict."""
        t = command_center.get_cognition_topology()
        assert isinstance(t, dict)

    def test_has_summary(self, command_center):
        """Topology has summary section."""
        t = command_center.get_cognition_topology()
        assert "summary" in t

    def test_nodes_greater_than_zero(self, command_center):
        """Topology has positive node count."""
        t = command_center.get_cognition_topology()
        assert t["summary"]["total_nodes"] > 0

    def test_edges_greater_than_zero(self, command_center):
        """Topology has positive edge count."""
        t = command_center.get_cognition_topology()
        assert t["summary"]["total_edges"] > 0

    def test_has_critical_nodes(self, command_center):
        """Topology has critical nodes section."""
        t = command_center.get_cognition_topology()
        assert "critical_nodes" in t
        assert len(t["critical_nodes"]) > 0

    def test_has_edge_types(self, command_center):
        """Topology has edge types."""
        t = command_center.get_cognition_topology()
        assert "edge_types" in t
        assert len(t["edge_types"]) > 0

    def test_has_nodes_by_layer(self, command_center):
        """Topology breaks down nodes by layer."""
        t = command_center.get_cognition_topology()
        assert "nodes_by_layer" in t
        assert len(t["nodes_by_layer"]) > 0

    def test_has_critical_paths(self, command_center):
        """Topology has critical paths."""
        t = command_center.get_cognition_topology()
        assert "critical_paths" in t


# ============================================================================
#  Test: Ecosystem Observability — Governance
# ============================================================================


class TestGovernanceEcosystem:
    """Test governance ecosystem view."""

    def test_returns_dict(self, ecosystem):
        """get_governance_ecosystem returns a dict."""
        g = ecosystem.get_governance_ecosystem()
        assert isinstance(g, dict)

    def test_has_schema_counts(self, ecosystem):
        """Governance ecosystem has schema counts."""
        g = ecosystem.get_governance_ecosystem()
        assert "total_schemas" in g
        assert "active_schemas" in g
        assert "hard_stop_schemas" in g

    def test_has_schemas_list(self, ecosystem):
        """Governance ecosystem has schemas list."""
        g = ecosystem.get_governance_ecosystem()
        assert "schemas" in g
        assert len(g["schemas"]) > 0

    def test_has_influence_edges(self, ecosystem):
        """Governance ecosystem has influence edges."""
        g = ecosystem.get_governance_ecosystem()
        assert "influence_edges" in g
        assert len(g["influence_edges"]) > 0

    def test_enforcement_pattern_is_fail_closed(self, ecosystem):
        """Enforcement pattern is fail-closed."""
        g = ecosystem.get_governance_ecosystem()
        assert g["enforcement_pattern"] == "fail_closed"

    def test_garvis_governs_all(self, ecosystem):
        """GARVIS governance inheritance model."""
        g = ecosystem.get_governance_ecosystem()
        assert g["inheritance_model"] == "garvis_governs_all"

    def test_hard_stop_schemas_non_negative(self, ecosystem):
        """Hard stop schema count is non-negative."""
        g = ecosystem.get_governance_ecosystem()
        assert g["hard_stop_schemas"] >= 0

    def test_total_schemas_greater_than_active(self, ecosystem):
        """Total schemas >= active schemas."""
        g = ecosystem.get_governance_ecosystem()
        assert g["total_schemas"] >= g["active_schemas"]

    def test_all_schemas_have_id(self, ecosystem):
        """Every schema has an id field."""
        g = ecosystem.get_governance_ecosystem()
        for schema in g["schemas"]:
            assert "id" in schema

    def test_all_schemas_have_project_id(self, ecosystem):
        """Every schema has a project_id field."""
        g = ecosystem.get_governance_ecosystem()
        for schema in g["schemas"]:
            assert "project_id" in schema


# ============================================================================
#  Test: Ecosystem Observability — Cognition
# ============================================================================


class TestCognitionEcosystem:
    """Test cognition ecosystem view."""

    def test_returns_dict(self, ecosystem):
        """get_cognition_ecosystem returns a dict."""
        c = ecosystem.get_cognition_ecosystem()
        assert isinstance(c, dict)

    def test_has_components(self, ecosystem):
        """Cognition ecosystem has components list."""
        c = ecosystem.get_cognition_ecosystem()
        assert "components" in c
        assert len(c["components"]) > 0

    def test_has_dependency_edges(self, ecosystem):
        """Cognition ecosystem has dependency edges."""
        c = ecosystem.get_cognition_ecosystem()
        assert "dependency_edges" in c
        assert len(c["dependency_edges"]) > 0

    def test_has_central_nodes(self, ecosystem):
        """Cognition ecosystem identifies central nodes."""
        c = ecosystem.get_cognition_ecosystem()
        assert "central_nodes" in c
        assert len(c["central_nodes"]) > 0

    def test_has_flow_direction(self, ecosystem):
        """Cognition ecosystem has flow direction."""
        c = ecosystem.get_cognition_ecosystem()
        assert "flow_direction" in c
        assert isinstance(c["flow_direction"], str)

    def test_each_component_has_id(self, ecosystem):
        """Each component has an id field."""
        c = ecosystem.get_cognition_ecosystem()
        for comp in c["components"]:
            assert "id" in comp

    def test_each_component_has_layer(self, ecosystem):
        """Each component has a layer field."""
        c = ecosystem.get_cognition_ecosystem()
        for comp in c["components"]:
            assert "layer" in comp

    def test_state_machine_is_central(self, ecosystem):
        """State machine is identified as central node."""
        c = ecosystem.get_cognition_ecosystem()
        assert "state_machine" in c["central_nodes"]

    def test_total_components_positive(self, ecosystem):
        """Total components count is positive."""
        c = ecosystem.get_cognition_ecosystem()
        assert c["total_components"] > 0


# ============================================================================
#  Test: Ecosystem Observability — Traceability
# ============================================================================


class TestTraceabilityEcosystem:
    """Test traceability ecosystem view."""

    def test_returns_dict(self, ecosystem):
        """get_traceability_ecosystem returns a dict."""
        t = ecosystem.get_traceability_ecosystem()
        assert isinstance(t, dict)

    def test_has_trace_flow(self, ecosystem):
        """Traceability has trace flow list."""
        t = ecosystem.get_traceability_ecosystem()
        assert "trace_flow" in t
        assert len(t["trace_flow"]) > 0

    def test_coverage_is_full(self, ecosystem):
        """Traceability coverage is full."""
        t = ecosystem.get_traceability_ecosystem()
        assert t["coverage"] == "full"

    def test_no_gaps(self, ecosystem):
        """Traceability has no gaps."""
        t = ecosystem.get_traceability_ecosystem()
        assert t["gaps"] == []

    def test_audit_completeness_is_one(self, ecosystem):
        """Audit completeness is 1.0."""
        t = ecosystem.get_traceability_ecosystem()
        assert t["audit_completeness"] == 1.0

    def test_each_flow_stage_has_stage(self, ecosystem):
        """Each flow stage has a stage field."""
        t = ecosystem.get_traceability_ecosystem()
        for stage in t["trace_flow"]:
            assert "stage" in stage

    def test_each_flow_stage_has_component(self, ecosystem):
        """Each flow stage has a component field."""
        t = ecosystem.get_traceability_ecosystem()
        for stage in t["trace_flow"]:
            assert "component" in stage

    def test_each_flow_stage_is_traced(self, ecosystem):
        """Each flow stage has traced=True."""
        t = ecosystem.get_traceability_ecosystem()
        for stage in t["trace_flow"]:
            assert stage["traced"] is True


# ============================================================================
#  Test: Ecosystem Observability — Resilience
# ============================================================================


class TestResilienceEcosystem:
    """Test resilience ecosystem view."""

    def test_returns_dict(self, ecosystem):
        """get_resilience_ecosystem returns a dict."""
        r = ecosystem.get_resilience_ecosystem()
        assert isinstance(r, dict)

    def test_has_degradation_patterns(self, ecosystem):
        """Resilience has degradation patterns."""
        r = ecosystem.get_resilience_ecosystem()
        assert "degradation_patterns" in r
        assert len(r["degradation_patterns"]) > 0

    def test_has_recovery_flows(self, ecosystem):
        """Resilience has recovery flows."""
        r = ecosystem.get_resilience_ecosystem()
        assert "recovery_flows" in r
        assert len(r["recovery_flows"]) > 0

    def test_resilience_score_is_one(self, ecosystem):
        """Resilience score is 1.0 (all healthy)."""
        r = ecosystem.get_resilience_ecosystem()
        assert r["resilience_score"] == 1.0

    def test_health_is_healthy(self, ecosystem):
        """Overall health is healthy."""
        r = ecosystem.get_resilience_ecosystem()
        assert r["overall_health"] == "healthy"

    def test_fail_closed_readiness(self, ecosystem):
        """Fail-closed readiness is True."""
        r = ecosystem.get_resilience_ecosystem()
        assert r["fail_closed_readiness"] is True

    def test_no_patterns_detected(self, ecosystem):
        """No degradation patterns detected."""
        r = ecosystem.get_resilience_ecosystem()
        assert r["patterns_detected"] == 0

    def test_operator_escalation_required(self, ecosystem):
        """Operator escalation is required."""
        r = ecosystem.get_resilience_ecosystem()
        assert r["operator_escalation_required"] is True

    def test_each_pattern_has_name(self, ecosystem):
        """Each degradation pattern has a pattern name."""
        r = ecosystem.get_resilience_ecosystem()
        for pattern in r["degradation_patterns"]:
            assert "pattern" in pattern

    def test_each_recovery_has_steps(self, ecosystem):
        """Each recovery flow has steps."""
        r = ecosystem.get_resilience_ecosystem()
        for recovery in r["recovery_flows"]:
            assert "steps" in recovery
            assert len(recovery["steps"]) > 0


# ============================================================================
#  Test: Ecosystem Observability — Continuity
# ============================================================================


class TestContinuityEcosystem:
    """Test continuity ecosystem view."""

    def test_returns_dict(self, ecosystem):
        """get_continuity_ecosystem returns a dict."""
        c = ecosystem.get_continuity_ecosystem()
        assert isinstance(c, dict)

    def test_has_dimensions(self, ecosystem):
        """Continuity has dimensions list."""
        c = ecosystem.get_continuity_ecosystem()
        assert "dimensions" in c
        assert len(c["dimensions"]) > 0

    def test_overall_score_is_one(self, ecosystem):
        """Overall continuity score is 1.0."""
        c = ecosystem.get_continuity_ecosystem()
        assert c["overall_score"] == 1.0

    def test_health_is_healthy(self, ecosystem):
        """Health status is healthy."""
        c = ecosystem.get_continuity_ecosystem()
        assert c["health_status"] == "healthy"

    def test_alignment_drift_is_zero(self, ecosystem):
        """Alignment drift is 0.0."""
        c = ecosystem.get_continuity_ecosystem()
        assert c["alignment_drift"] == 0.0

    def test_governance_durability_is_one(self, ecosystem):
        """Governance durability is 1.0."""
        c = ecosystem.get_continuity_ecosystem()
        assert c["governance_durability"] == 1.0

    def test_memory_integrity_is_one(self, ecosystem):
        """Memory integrity is 1.0."""
        c = ecosystem.get_continuity_ecosystem()
        assert c["memory_integrity"] == 1.0

    def test_each_dimension_has_name(self, ecosystem):
        """Each dimension has a name."""
        c = ecosystem.get_continuity_ecosystem()
        for dim in c["dimensions"]:
            assert "dimension" in dim

    def test_each_dimension_has_score(self, ecosystem):
        """Each dimension has a score."""
        c = ecosystem.get_continuity_ecosystem()
        for dim in c["dimensions"]:
            assert "score" in dim


# ============================================================================
#  Test: Full Ecosystem
# ============================================================================


class TestFullEcosystem:
    """Test full ecosystem view."""

    def test_returns_dict(self, ecosystem):
        """get_full_ecosystem returns a dict."""
        f = ecosystem.get_full_ecosystem()
        assert isinstance(f, dict)

    def test_has_all_sub_ecosystems(self, ecosystem):
        """Full ecosystem has all 5 sub-ecosystems."""
        f = ecosystem.get_full_ecosystem()
        expected = {"governance", "cognition", "traceability", "resilience", "continuity"}
        assert expected.issubset(f.keys())

    def test_has_projects(self, ecosystem):
        """Full ecosystem has projects list."""
        f = ecosystem.get_full_ecosystem()
        assert "projects" in f

    def test_has_seven_projects(self, ecosystem):
        """Full ecosystem has 7 projects."""
        f = ecosystem.get_full_ecosystem()
        assert f["project_count"] == 7

    def test_active_projects_is_two(self, ecosystem):
        """2 projects are active (garvis and ops)."""
        f = ecosystem.get_full_ecosystem()
        assert f["active_projects"] == 2

    def test_health_is_healthy(self, ecosystem):
        """Ecosystem health is healthy."""
        f = ecosystem.get_full_ecosystem()
        assert f["ecosystem_health"] == "healthy"

    def test_has_timestamp(self, ecosystem):
        """Full ecosystem has timestamp."""
        f = ecosystem.get_full_ecosystem()
        assert "timestamp" in f


# ============================================================================
#  Test: Operational Analytics
# ============================================================================


class TestOperationalAnalytics:
    """Test operational analytics."""

    def test_returns_dict(self, ecosystem):
        """get_operational_analytics returns a dict."""
        a = ecosystem.get_operational_analytics()
        assert isinstance(a, dict)

    def test_has_governance_durability(self, ecosystem):
        """Analytics has governance durability."""
        a = ecosystem.get_operational_analytics()
        assert "governance_durability" in a

    def test_has_alignment_survivability(self, ecosystem):
        """Analytics has alignment survivability."""
        a = ecosystem.get_operational_analytics()
        assert "alignment_survivability" in a

    def test_has_workflow_integrity(self, ecosystem):
        """Analytics has workflow integrity."""
        a = ecosystem.get_operational_analytics()
        assert "workflow_integrity" in a

    def test_has_schema_coverage(self, ecosystem):
        """Analytics has schema coverage."""
        a = ecosystem.get_operational_analytics()
        assert "schema_coverage" in a

    def test_has_enforcement_strength(self, ecosystem):
        """Analytics has enforcement strength."""
        a = ecosystem.get_operational_analytics()
        assert "enforcement_strength" in a

    def test_workflow_integrity_score_is_one(self, ecosystem):
        """Workflow integrity score is 1.0."""
        a = ecosystem.get_operational_analytics()
        assert a["workflow_integrity"]["score"] == 1.0

    def test_workflow_approval_required(self, ecosystem):
        """Workflow approval is required."""
        a = ecosystem.get_operational_analytics()
        assert a["workflow_integrity"]["approval_required"] is True

    def test_autonomous_execution_false(self, ecosystem):
        """Autonomous execution is False."""
        a = ecosystem.get_operational_analytics()
        assert a["workflow_integrity"]["autonomous_execution"] is False

    def test_governance_durability_has_score(self, ecosystem):
        """Governance durability has score field."""
        a = ecosystem.get_operational_analytics()
        assert "score" in a["governance_durability"]

    def test_alignment_survivability_no_drift(self, ecosystem):
        """Alignment survivability shows no drift."""
        a = ecosystem.get_operational_analytics()
        assert a["alignment_survivability"]["drift_detected"] is False

    def test_overall_health_is_healthy(self, ecosystem):
        """Overall operational health is healthy."""
        a = ecosystem.get_operational_analytics()
        assert a["overall_operational_health"] == "healthy"

    def test_has_timestamp(self, ecosystem):
        """Operational analytics has timestamp."""
        a = ecosystem.get_operational_analytics()
        assert "timestamp" in a


# ============================================================================
#  Test: Command Execution
# ============================================================================


class TestCommandExecution:
    """Test command execution through CommandCenter."""

    def test_valid_switch_project(self, command_center):
        """switch_project command succeeds for valid project."""
        result = command_center.execute_command(
            "switch_project", {"project_id": "ops"}, "operator_test"
        )
        assert result["status"] == "success"

    def test_invalid_project_switch(self, command_center):
        """switch_project fails for invalid project."""
        result = command_center.execute_command(
            "switch_project", {"project_id": "nonexistent"}, "operator_test"
        )
        assert result["status"] == "error"

    def test_switch_project_has_project_name(self, command_center):
        """switch_project result includes project name."""
        result = command_center.execute_command(
            "switch_project", {"project_id": "garvis"}, "operator_test"
        )
        assert "project_name" in result

    def test_activate_schema(self, command_center):
        """activate_schema command succeeds."""
        result = command_center.execute_command(
            "activate_schema",
            {"schema_id": "test_schema", "project_id": "garvis"},
            "operator_test",
        )
        assert result["status"] == "success"

    def test_deactivate_schema(self, command_center):
        """deactivate_schema command succeeds."""
        result = command_center.execute_command(
            "deactivate_schema",
            {"schema_id": "test_schema", "project_id": "garvis"},
            "operator_test",
        )
        assert result["status"] == "success"

    def test_acknowledge_alert(self, command_center):
        """acknowledge_alert command succeeds."""
        result = command_center.execute_command(
            "acknowledge_alert", {"alert_id": "alert_123"}, "operator_test"
        )
        assert result["status"] == "success"

    def test_run_health_check(self, command_center):
        """run_health_check command succeeds."""
        result = command_center.execute_command(
            "run_health_check", {}, "operator_test"
        )
        assert result["status"] == "success"
        assert "health" in result

    def test_generate_report(self, command_center):
        """generate_report command succeeds."""
        result = command_center.execute_command(
            "generate_report", {"report_type": "operational"}, "operator_test"
        )
        assert result["status"] == "success"
        assert result["report_type"] == "operational"

    def test_invalid_command(self, command_center):
        """Invalid command returns error."""
        result = command_center.execute_command(
            "invalid_command", {}, "operator_test"
        )
        assert result["status"] == "error"

    def test_valid_commands_listed_in_error(self, command_center):
        """Error response includes list of valid commands."""
        result = command_center.execute_command(
            "invalid_command", {}, "operator_test"
        )
        assert "valid_commands" in result
        assert "switch_project" in result["valid_commands"]

    def test_command_is_audited(self, command_center):
        """Commands are recorded in audit log."""
        initial_count = len(command_center.get_audit_log())
        command_center.execute_command(
            "run_health_check", {}, "audit_test_operator"
        )
        new_count = len(command_center.get_audit_log())
        assert new_count == initial_count + 1

    def test_audit_log_has_command_name(self, command_center):
        """Audit log entry contains command name."""
        command_center.execute_command(
            "generate_report", {"report_type": "test"}, "audit_operator"
        )
        log = command_center.get_audit_log()
        assert log[-1]["command"] == "generate_report"

    def test_audit_log_has_operator_id(self, command_center):
        """Audit log entry contains operator_id."""
        command_center.execute_command(
            "run_health_check", {}, "specific_operator"
        )
        log = command_center.get_audit_log()
        assert log[-1]["operator_id"] == "specific_operator"

    def test_switch_all_seven_projects(self, command_center):
        """Can switch to all 7 projects."""
        project_ids = ["garvis", "alphaflow", "nova", "teachflow", "bella", "youtube", "ops"]
        for pid in project_ids:
            result = command_center.execute_command(
                "switch_project", {"project_id": pid}, "operator_test"
            )
            assert result["status"] == "success", f"Failed to switch to {pid}"


# ============================================================================
#  Test: Audit Log
# ============================================================================


class TestAuditLog:
    """Test command audit log functionality."""

    def test_audit_log_returns_list(self, command_center):
        """get_audit_log returns a list."""
        log = command_center.get_audit_log()
        assert isinstance(log, list)

    def test_audit_log_entries_have_timestamp(self, command_center):
        """Each audit log entry has timestamp."""
        command_center.execute_command("run_health_check", {}, "op")
        log = command_center.get_audit_log()
        assert "timestamp" in log[-1]

    def test_audit_log_entries_have_command(self, command_center):
        """Each audit log entry has command."""
        command_center.execute_command("generate_report", {}, "op")
        log = command_center.get_audit_log()
        assert "command" in log[-1]

    def test_audit_log_entries_have_operator(self, command_center):
        """Each audit log entry has operator_id."""
        command_center.execute_command("run_health_check", {}, "test_op")
        log = command_center.get_audit_log()
        assert "operator_id" in log[-1]

    def test_audit_log_entries_have_params(self, command_center):
        """Each audit log entry has params."""
        command_center.execute_command("generate_report", {"type": "test"}, "op")
        log = command_center.get_audit_log()
        assert "params" in log[-1]

    def test_audit_log_entries_have_result_status(self, command_center):
        """Each audit log entry has result_status."""
        command_center.execute_command("run_health_check", {}, "op")
        log = command_center.get_audit_log()
        assert "result_status" in log[-1]

    def test_audit_log_entries_have_sequence(self, command_center):
        """Each audit log entry has command_sequence."""
        command_center.execute_command("run_health_check", {}, "op")
        log = command_center.get_audit_log()
        assert "command_sequence" in log[-1]

    def test_command_sequence_increments(self, command_center):
        """Command sequence increments with each command."""
        log_before = len(command_center.get_audit_log())
        command_center.execute_command("run_health_check", {}, "op")
        command_center.execute_command("generate_report", {}, "op")
        log = command_center.get_audit_log()
        assert log[-2]["command_sequence"] + 1 == log[-1]["command_sequence"]


# ============================================================================
#  Test: Project Governance API (router-level)
# ============================================================================


class TestProjectGovernanceAPI:
    """Test project governance patterns."""

    def test_mission_control_has_seven_projects(self, mission_control):
        """MissionControl has 7 projects."""
        assert len(mission_control.PROJECTS) == 7

    def test_mission_control_project_ids(self, mission_control):
        """All expected project IDs are present."""
        ids = {p["id"] for p in mission_control.PROJECTS}
        expected = {"garvis", "alphaflow", "nova", "teachflow", "bella", "youtube", "ops"}
        assert ids == expected

    def test_garvis_governance_is_active(self, mission_control):
        """GARVIS project has active governance."""
        gov = mission_control.get_governance_status("garvis")
        assert gov["governance_active"] is True

    def test_ops_governance_is_active(self, mission_control):
        """Ops project has active governance."""
        gov = mission_control.get_governance_status("ops")
        assert gov["governance_active"] is True

    def test_planned_project_governance_is_inactive(self, mission_control):
        """Planned project has inactive governance."""
        gov = mission_control.get_governance_status("alphaflow")
        assert gov["governance_active"] is False

    def test_all_projects_fail_closed(self, mission_control):
        """All projects have fail_closed=True."""
        for p in mission_control.PROJECTS:
            gov = mission_control.get_governance_status(p["id"])
            assert gov["fail_closed"] is True

    def test_garvis_readiness_partial(self, mission_control):
        """GARVIS has partial readiness."""
        readiness = mission_control.get_workflow_readiness("garvis")
        assert 0.0 < readiness["score"] < 1.0

    def test_nonexistent_project_governance(self, mission_control):
        """Nonexistent project returns error."""
        gov = mission_control.get_governance_status("nonexistent")
        assert gov["status"] == "error"

    def test_workflow_approval_required(self, mission_control):
        """Workflow approval is required."""
        result = mission_control.propose_workflow("garvis", {
            "name": "test_workflow",
            "operations": [{"type": "process"}],
        })
        assert result["status"] == "proposed"

    def test_workflow_risk_classification(self, mission_control):
        """Workflows are classified by risk level."""
        result = mission_control.propose_workflow("garvis", {
            "name": "test_workflow",
            "operations": [{"type": "process"}],
        })
        assert "proposal" in result
        assert "risk_level" in result["proposal"]
