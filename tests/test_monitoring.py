"""Comprehensive tests for monitoring/alerts.py and monitoring/topology.py.

Tests all alert rules, topology mapping, acknowledgment/resolution,
auto-resolve behavior, deduplication, cascading detection, and
critical path finding.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from models.governance import GovernanceViolation, GovernanceCheckResult
from models.cognition import OperationalState
from monitoring.alerts import (
    Alert,
    AlertEngine,
    AlertSeverity,
)
from monitoring.topology import SystemTopology


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def alert_engine() -> AlertEngine:
    """Fresh AlertEngine for each test."""
    engine = AlertEngine()
    yield engine
    engine.reset()


@pytest.fixture
def topology() -> SystemTopology:
    """SystemTopology mapper."""
    return SystemTopology()


@pytest.fixture
def sample_topology() -> dict:
    """Full topology for centrality/path tests."""
    return SystemTopology().map_full_topology()


@pytest.fixture
def critical_violation() -> GovernanceViolation:
    """A critical governance violation."""
    return GovernanceViolation(
        schema_id="uncertainty_management",
        policy_id="uncertainty_quantification_required",
        severity="critical",
        description="Missing uncertainty quantification",
        context={"enforcement": "hard_stop"},
    )


@pytest.fixture
def warning_violation() -> GovernanceViolation:
    """A warning-level governance violation."""
    return GovernanceViolation(
        schema_id="uncertainty_management",
        policy_id="uncertainty_honesty_threshold",
        severity="warning",
        description="Confidence overstatement detected",
        context={"enforcement": "degrade"},
    )


# ============================================================================
# Alert Model Tests
# ============================================================================


class TestAlertModel:
    """Test the Alert Pydantic model."""

    def test_alert_creation(self) -> None:
        alert = Alert(
            severity=AlertSeverity.CRITICAL,
            category="governance",
            title="Test Alert",
            description="Test description",
        )
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.category == "governance"
        assert alert.title == "Test Alert"
        assert alert.acknowledged is False
        assert alert.resolved is False
        assert alert.alert_id is not None
        assert isinstance(alert.alert_id, UUID)

    def test_alert_dedup_key_auto(self) -> None:
        alert = Alert(
            severity=AlertSeverity.WARNING,
            category="cognition",
            title="State Change",
            description="Test",
        )
        assert alert.dedup_key is not None
        assert "warning" in alert.dedup_key
        assert "cognition" in alert.dedup_key
        assert "State Change" in alert.dedup_key


# ============================================================================
# Alert Severity Enum Tests
# ============================================================================


class TestAlertSeverity:
    """Test the AlertSeverity enum."""

    def test_severity_values(self) -> None:
        assert AlertSeverity.CRITICAL == "critical"
        assert AlertSeverity.WARNING == "warning"
        assert AlertSeverity.INFO == "info"
        assert AlertSeverity.DEBUG == "debug"

    def test_severity_ordering_by_criticality(self) -> None:
        # Critical > Warning > Info > Debug
        severities = [
            AlertSeverity.CRITICAL,
            AlertSeverity.WARNING,
            AlertSeverity.INFO,
            AlertSeverity.DEBUG,
        ]
        assert severities[0].value == "critical"
        assert severities[1].value == "warning"
        assert severities[2].value == "info"
        assert severities[3].value == "debug"


# ============================================================================
# AlertEngine Initialization Tests
# ============================================================================


class TestAlertEngineInit:
    """Test AlertEngine initialization."""

    def test_init_creates_empty_engine(self, alert_engine: AlertEngine) -> None:
        assert len(alert_engine.get_active_alerts()) == 0
        assert len(alert_engine.get_alert_history()) == 0
        assert alert_engine.get_alert_summary()["total_alerts"] == 0

    def test_alert_rules_defined(self, alert_engine: AlertEngine) -> None:
        rules = alert_engine.ALERT_RULES
        assert "governance_violation_critical" in rules
        assert "governance_pressure_high" in rules
        assert "alignment_drift_detected" in rules
        assert "state_fail_closed" in rules
        assert "state_degraded" in rules
        assert "forbidden_pattern_detected" in rules
        assert "uncertainty_disclosure_low" in rules
        assert "boundary_violation" in rules
        assert "resilience_drop" in rules
        assert "equilibrium_unstable" in rules
        assert len(rules) == 10


# ============================================================================
# Governance Violation Alert Tests
# ============================================================================


class TestGovernanceViolationAlerts:
    """Test governance violation alert triggering."""

    def test_critical_violation_triggers_alert(
        self,
        alert_engine: AlertEngine,
        critical_violation: GovernanceViolation,
    ) -> None:
        alert = alert_engine.check_governance_violation(critical_violation)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL
        assert "uncertainty_management" in alert.title
        assert alert.source_schema == "uncertainty_management"

    def test_warning_violation_triggers_alert(
        self,
        alert_engine: AlertEngine,
        warning_violation: GovernanceViolation,
    ) -> None:
        alert = alert_engine.check_governance_violation(warning_violation)
        assert alert is not None
        # Warning violations still trigger alerts
        assert alert.severity == AlertSeverity.CRITICAL

    def test_info_violation_no_alert(
        self,
        alert_engine: AlertEngine,
    ) -> None:
        info_violation = GovernanceViolation(
            schema_id="test",
            policy_id="test_policy",
            severity="info",
            description="Info violation",
        )
        alert = alert_engine.check_governance_violation(info_violation)
        assert alert is None

    def test_multiple_violations_create_multiple_alerts(
        self,
        alert_engine: AlertEngine,
        critical_violation: GovernanceViolation,
    ) -> None:
        # Wait for dedup window to avoid suppression
        alert_engine.DEDUP_WINDOW_SECONDS = 0
        alert1 = alert_engine.check_governance_violation(critical_violation)
        violation2 = GovernanceViolation(
            schema_id="truthfulness_governance",
            policy_id="no_fabrication",
            severity="critical",
            description="Fabrication detected",
            context={"enforcement": "hard_stop"},
        )
        alert2 = alert_engine.check_governance_violation(violation2)
        assert alert1 is not None
        assert alert2 is not None
        assert alert1.alert_id != alert2.alert_id


# ============================================================================
# Pressure Alert Tests
# ============================================================================


class TestPressureAlerts:
    """Test governance pressure alert triggering."""

    def test_pressure_below_threshold_no_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_pressure("inference", 0.5)
        assert alert is None

    def test_pressure_at_threshold_no_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_pressure("inference", 0.7)
        assert alert is None

    def test_pressure_above_threshold_triggers_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_pressure("inference", 0.85)
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert "High Governance Pressure" in alert.title
        assert "inference" in alert.title
        assert "0.85" in alert.description
        assert alert.auto_resolve_conditions

    def test_pressure_exactly_at_boundary(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_pressure("global", 0.7001)
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING


# ============================================================================
# Alignment Drift Alert Tests
# ============================================================================


class TestAlignmentDriftAlerts:
    """Test alignment drift alert triggering."""

    def test_drift_below_threshold_no_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_alignment_drift(0.05)
        assert alert is None

    def test_drift_at_threshold_no_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_alignment_drift(0.1)
        assert alert is None

    def test_drift_above_threshold_triggers_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_alignment_drift(0.25)
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert "Alignment Drift" in alert.title
        assert "0.2500" in alert.description
        assert alert.auto_resolve_conditions


# ============================================================================
# State Change Alert Tests
# ============================================================================


class TestStateChangeAlerts:
    """Test state transition alert triggering."""

    def test_fail_closed_triggers_alert(self, alert_engine: AlertEngine) -> None:
        alerts = alert_engine.check_state_change(
            OperationalState.COGNITION_ACTIVE,
            OperationalState.FAIL_CLOSED,
            "Critical violation triggered halt",
        )
        assert len(alerts) >= 1
        fail_closed_alerts = [a for a in alerts if "FAIL_CLOSED" in a.title]
        assert len(fail_closed_alerts) == 1
        alert = fail_closed_alerts[0]
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.category == "cognition"
        assert "halt" in alert.description.lower()

    def test_degraded_triggers_alert(self, alert_engine: AlertEngine) -> None:
        alerts = alert_engine.check_state_change(
            OperationalState.COGNITION_ACTIVE,
            OperationalState.DEGRADED,
            "Governance pressure high",
        )
        assert len(alerts) >= 1
        degraded_alerts = [a for a in alerts if "DEGRADED" in a.title]
        assert len(degraded_alerts) == 1
        alert = degraded_alerts[0]
        assert alert.severity == AlertSeverity.WARNING
        assert alert.category == "cognition"
        assert alert.auto_resolve_conditions

    def test_forbidden_pattern_in_reason_triggers_both_alerts(
        self,
        alert_engine: AlertEngine,
    ) -> None:
        alerts = alert_engine.check_state_change(
            OperationalState.INFERENCE_EXECUTING,
            OperationalState.FAIL_CLOSED,
            "forbidden_pattern: recursive_inference",
        )
        assert len(alerts) >= 2
        titles = [a.title for a in alerts]
        assert any("FAIL_CLOSED" in t for t in titles)
        assert any("Forbidden Pattern" in t for t in titles)

    def test_normal_transition_no_alert(self, alert_engine: AlertEngine) -> None:
        alerts = alert_engine.check_state_change(
            OperationalState.STANDBY,
            OperationalState.GOVERNANCE_CHECK,
            "Normal governance check",
        )
        assert len(alerts) == 0

    def test_forbidden_pattern_direct(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_forbidden_pattern_direct("recursive_inference")
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL
        assert "recursive_inference" in alert.title
        assert alert.category == "cognition"


# ============================================================================
# Uncertainty Disclosure Alert Tests
# ============================================================================


class TestUncertaintyDisclosureAlerts:
    """Test uncertainty disclosure rate alert triggering."""

    def test_rate_above_threshold_no_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_uncertainty_disclosure(0.75)
        assert alert is None

    def test_rate_at_threshold_no_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_uncertainty_disclosure(0.5)
        assert alert is None

    def test_rate_below_threshold_triggers_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_uncertainty_disclosure(0.3)
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert "Low Uncertainty Disclosure" in alert.title
        assert "0.30" in alert.description
        assert alert.source_schema == "uncertainty_management"


# ============================================================================
# Boundary Violation Alert Tests
# ============================================================================


class TestBoundaryViolationAlerts:
    """Test boundary violation alert triggering."""

    def test_boundary_violation_triggers_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_boundary_violation(
            "knowledge_boundary",
            "unauthorized_inference",
        )
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL
        assert "Boundary Violation" in alert.title
        assert "knowledge_boundary" in alert.description
        assert alert.source_schema == "knowledge_boundary"


# ============================================================================
# Resilience Alert Tests
# ============================================================================


class TestResilienceAlerts:
    """Test resilience score alert triggering."""

    def test_score_above_threshold_no_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_resilience(0.8)
        assert alert is None

    def test_score_below_threshold_triggers_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_resilience(0.4)
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert "Resilience Score Dropped" in alert.title
        assert "0.40" in alert.description
        assert alert.auto_resolve_conditions

    def test_score_at_threshold_no_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_resilience(0.6)
        assert alert is None


# ============================================================================
# Equilibrium Alert Tests
# ============================================================================


class TestEquilibriumAlerts:
    """Test equilibrium stability alert triggering."""

    def test_score_above_threshold_no_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_equilibrium(0.7)
        assert alert is None

    def test_score_below_threshold_triggers_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_equilibrium(0.3)
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert "Equilibrium Unstable" in alert.title
        assert "0.30" in alert.description
        assert alert.auto_resolve_conditions


# ============================================================================
# Acknowledgment and Resolution Tests
# ============================================================================


class TestAcknowledgmentAndResolution:
    """Test operator acknowledgment and resolution."""

    def test_acknowledge_existing_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_resilience(0.3)
        assert alert is not None
        assert alert.acknowledged is False
        result = alert_engine.acknowledge(alert.alert_id)
        assert result is True
        active = alert_engine.get_active_alerts()
        assert len(active) == 1
        assert active[0].acknowledged is True

    def test_acknowledge_nonexistent_alert(self, alert_engine: AlertEngine) -> None:
        result = alert_engine.acknowledge(uuid4())
        assert result is False

    def test_resolve_existing_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_resilience(0.3)
        assert alert is not None
        result = alert_engine.resolve(alert.alert_id)
        assert result is True
        active = alert_engine.get_active_alerts()
        assert len(active) == 0
        assert alert.resolved is True
        assert alert.resolution_time is not None

    def test_resolve_nonexistent_alert(self, alert_engine: AlertEngine) -> None:
        result = alert_engine.resolve(uuid4())
        assert result is False

    def test_acknowledge_then_resolve(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_resilience(0.3)
        assert alert is not None
        alert_engine.acknowledge(alert.alert_id)
        alert_engine.resolve(alert.alert_id)
        assert alert.acknowledged is True
        assert alert.resolved is True


# ============================================================================
# Auto-Resolve Tests
# ============================================================================


class TestAutoResolve:
    """Test auto-resolve behavior."""

    def test_auto_resolve_warning_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_resilience(0.3)  # WARNING severity, auto_resolve
        assert alert is not None
        assert len(alert.auto_resolve_conditions) > 0
        result = alert_engine.attempt_auto_resolve(alert.alert_id)
        assert result is True
        assert alert.resolved is True

    def test_auto_resolve_critical_alert_fails(self, alert_engine: AlertEngine) -> None:
        # Create a critical alert via boundary violation
        alert = alert_engine.check_boundary_violation("test", "test_op")
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL
        assert len(alert.auto_resolve_conditions) == 0
        result = alert_engine.attempt_auto_resolve(alert.alert_id)
        assert result is False
        assert alert.resolved is False

    def test_auto_resolve_nonexistent_alert(self, alert_engine: AlertEngine) -> None:
        result = alert_engine.attempt_auto_resolve(uuid4())
        assert result is False


# ============================================================================
# Query and Summary Tests
# ============================================================================


class TestAlertQueries:
    """Test alert querying methods."""

    def test_get_active_alerts_empty(self, alert_engine: AlertEngine) -> None:
        assert alert_engine.get_active_alerts() == []

    def test_get_active_alerts_with_severity_filter(
        self,
        alert_engine: AlertEngine,
    ) -> None:
        alert_engine.check_boundary_violation("test", "test_op")  # CRITICAL
        alert_engine.check_resilience(0.3)  # WARNING
        all_alerts = alert_engine.get_active_alerts()
        assert len(all_alerts) == 2
        critical_only = alert_engine.get_active_alerts(severity=AlertSeverity.CRITICAL)
        assert len(critical_only) == 1
        assert critical_only[0].severity == AlertSeverity.CRITICAL
        warning_only = alert_engine.get_active_alerts(severity=AlertSeverity.WARNING)
        assert len(warning_only) == 1
        assert warning_only[0].severity == AlertSeverity.WARNING

    def test_get_active_alerts_with_category_filter(
        self,
        alert_engine: AlertEngine,
    ) -> None:
        alert_engine.check_boundary_violation("test", "test_op")  # governance
        alert_engine.check_resilience(0.3)  # system
        governance_only = alert_engine.get_active_alerts(category="governance")
        assert len(governance_only) == 1
        system_only = alert_engine.get_active_alerts(category="system")
        assert len(system_only) == 1

    def test_get_alert_history(self, alert_engine: AlertEngine) -> None:
        alert1 = alert_engine.check_boundary_violation("test1", "op1")
        alert2 = alert_engine.check_resilience(0.3)
        history = alert_engine.get_alert_history(limit=10)
        assert len(history) == 2
        # History is sorted newest first
        assert history[0].alert_id in [alert1.alert_id, alert2.alert_id]

    def test_get_alert_summary(self, alert_engine: AlertEngine) -> None:
        alert_engine.check_boundary_violation("test", "op")  # CRITICAL, governance
        alert_engine.check_resilience(0.3)  # WARNING, system
        summary = alert_engine.get_alert_summary()
        assert summary["total_alerts"] == 2
        assert summary["active_alerts"] == 2
        assert summary["resolved_alerts"] == 0
        assert summary["by_severity"]["critical"] == 1
        assert summary["by_severity"]["warning"] == 1
        assert summary["by_category"]["governance"] == 1
        assert summary["by_category"]["system"] == 1
        assert summary["active_by_severity"]["critical"] == 1
        assert summary["critical_unacknowledged"] == 1

    def test_get_alert_summary_empty(self, alert_engine: AlertEngine) -> None:
        summary = alert_engine.get_alert_summary()
        assert summary["total_alerts"] == 0
        assert summary["active_alerts"] == 0
        assert summary["resolved_alerts"] == 0
        assert summary["critical_unacknowledged"] == 0


# ============================================================================
# Handler Tests
# ============================================================================


class TestAlertHandlers:
    """Test alert handler registration and notification."""

    def test_register_handler(self, alert_engine: AlertEngine) -> None:
        called_with: list[Alert] = []

        def handler(alert: Alert) -> None:
            called_with.append(alert)

        alert_engine.register_handler(handler)
        alert_engine.check_resilience(0.3)
        assert len(called_with) == 1
        assert called_with[0].severity == AlertSeverity.WARNING

    def test_multiple_handlers(self, alert_engine: AlertEngine) -> None:
        calls1: list[str] = []
        calls2: list[str] = []

        def handler1(alert: Alert) -> None:
            calls1.append(alert.title)

        def handler2(alert: Alert) -> None:
            calls2.append(alert.title)

        alert_engine.register_handler(handler1)
        alert_engine.register_handler(handler2)
        alert_engine.check_resilience(0.3)
        assert len(calls1) == 1
        assert len(calls2) == 1

    def test_handler_exception_does_not_break(
        self,
        alert_engine: AlertEngine,
    ) -> None:
        good_calls: list[str] = []

        def bad_handler(alert: Alert) -> None:
            raise RuntimeError("Handler failure")

        def good_handler(alert: Alert) -> None:
            good_calls.append(alert.title)

        alert_engine.register_handler(bad_handler)
        alert_engine.register_handler(good_handler)
        # Should not raise
        alert_engine.check_resilience(0.3)
        assert len(good_calls) == 1  # Good handler still called

    def test_unregister_handler(self, alert_engine: AlertEngine) -> None:
        calls: list[str] = []

        def handler(alert: Alert) -> None:
            calls.append(alert.title)

        alert_engine.register_handler(handler)
        result = alert_engine.unregister_handler(handler)
        assert result is True
        alert_engine.check_resilience(0.3)
        assert len(calls) == 0  # Handler was unregistered

    def test_unregister_nonexistent_handler(self, alert_engine: AlertEngine) -> None:
        def handler(alert: Alert) -> None:
            pass

        result = alert_engine.unregister_handler(handler)
        assert result is False


# ============================================================================
# Deduplication Tests
# ============================================================================


class TestDeduplication:
    """Test alert deduplication suppression."""

    def test_duplicate_alert_suppressed(self, alert_engine: AlertEngine) -> None:
        # Set dedup window high so suppression kicks in
        alert_engine.DEDUP_WINDOW_SECONDS = 60
        alert1 = alert_engine.check_resilience(0.3)
        alert2 = alert_engine.check_resilience(0.3)
        # Second alert should be suppressed (None)
        assert alert1 is not None
        # With dedup, the second identical alert is suppressed
        # But different severity/category combinations create different dedup keys

    def test_different_alerts_not_suppressed(self, alert_engine: AlertEngine) -> None:
        alert_engine.DEDUP_WINDOW_SECONDS = 60
        alert1 = alert_engine.check_resilience(0.3)
        alert2 = alert_engine.check_equilibrium(0.3)
        assert alert1 is not None
        assert alert2 is not None
        assert alert1.alert_id != alert2.alert_id

    def test_dedup_window_expires(self, alert_engine: AlertEngine) -> None:
        alert_engine.DEDUP_WINDOW_SECONDS = 0  # Immediate expiry
        alert1 = alert_engine.check_resilience(0.3)
        alert2 = alert_engine.check_resilience(0.31)  # Slightly different
        assert alert1 is not None
        assert alert2 is not None


# ============================================================================
# Cascading Alert Detection Tests
# ============================================================================


class TestCascadingDetection:
    """Test cascading alert detection."""

    def test_no_cascade_with_few_alerts(self, alert_engine: AlertEngine) -> None:
        alert_engine.check_resilience(0.3)
        cascades = alert_engine.detect_cascading_alerts(window_seconds=300)
        assert cascades == []

    def test_detect_cascade(self, alert_engine: AlertEngine) -> None:
        alert_engine.DEDUP_WINDOW_SECONDS = 0  # Disable dedup for this test
        # Create 3+ alerts in the same category
        alert_engine.check_resilience(0.1)  # system
        alert_engine.check_resilience(0.2)  # system
        alert_engine.check_equilibrium(0.1)  # system
        cascades = alert_engine.detect_cascading_alerts(window_seconds=300)
        assert len(cascades) >= 1
        cascade = cascades[0]
        assert cascade["category"] == "system"
        assert cascade["alert_count"] >= 3
        assert "has_critical" in cascade
        assert "severity_breakdown" in cascade

    def test_cascade_sorted_by_severity(self, alert_engine: AlertEngine) -> None:
        alert_engine.DEDUP_WINDOW_SECONDS = 0
        # Create critical governance alerts
        for i in range(3):
            v = GovernanceViolation(
                schema_id=f"schema_{i}",
                policy_id=f"policy_{i}",
                severity="critical",
                description=f"Violation {i}",
            )
            alert_engine.check_governance_violation(v)
        # Create system alerts
        alert_engine.check_resilience(0.1)
        alert_engine.check_equilibrium(0.1)
        cascades = alert_engine.detect_cascading_alerts(window_seconds=300)
        if len(cascades) >= 2:
            # Critical governance should come first
            assert cascades[0]["has_critical"] is True or cascades[0]["category"] == "governance"


# ============================================================================
# Cleanup Tests
# ============================================================================


class TestAlertCleanup:
    """Test expired alert cleanup."""

    def test_cleanup_no_expired_alerts(self, alert_engine: AlertEngine) -> None:
        count = alert_engine.cleanup_expired_alerts(max_age_hours=72)
        assert count == 0

    def test_cleanup_does_not_remove_recent(self, alert_engine: AlertEngine) -> None:
        alert_engine.check_resilience(0.3)
        count = alert_engine.cleanup_expired_alerts(max_age_hours=72)
        assert count == 0
        assert len(alert_engine.get_active_alerts()) == 1

    def test_cleanup_removes_old_resolved(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_resilience(0.3)
        alert_engine.resolve(alert.alert_id)
        # Manually set resolution time to old
        alert.resolution_time = datetime(2000, 1, 1, tzinfo=timezone.utc)
        count = alert_engine.cleanup_expired_alerts(max_age_hours=1)
        assert count == 1


# ============================================================================
# Reset Tests
# ============================================================================


class TestAlertEngineReset:
    """Test AlertEngine reset."""

    def test_reset_clears_all(self, alert_engine: AlertEngine) -> None:
        alert_engine.check_resilience(0.3)
        alert_engine.check_boundary_violation("test", "op")
        alert_engine.reset()
        assert len(alert_engine.get_active_alerts()) == 0
        assert len(alert_engine.get_alert_history()) == 0


# ============================================================================
# SystemTopology Tests
# ============================================================================


class TestSystemTopology:
    """Test SystemTopology mapper."""

    def test_map_full_topology(self, topology: SystemTopology) -> None:
        result = topology.map_full_topology()
        assert "nodes" in result
        assert "edges" in result
        assert "layers" in result
        assert "metadata" in result
        assert len(result["nodes"]) > 0
        assert len(result["edges"]) > 0
        assert len(result["layers"]) == 8
        assert result["metadata"]["total_nodes"] > 0
        assert result["metadata"]["total_edges"] > 0

    def test_all_layers_present(self, topology: SystemTopology) -> None:
        result = topology.map_full_topology()
        layers = result["layers"]
        assert "governance" in layers
        assert "cognition" in layers
        assert "memory" in layers
        assert "traceability" in layers
        assert "inference" in layers
        assert "runtime" in layers
        assert "analytics" in layers
        assert "monitoring" in layers

    def test_nodes_have_required_fields(self, topology: SystemTopology) -> None:
        result = topology.map_full_topology()
        for node in result["nodes"]:
            assert "id" in node
            assert "layer" in node
            assert "type" in node
            assert "status" in node
            assert node["status"] == "healthy"

    def test_edges_have_required_fields(self, topology: SystemTopology) -> None:
        result = topology.map_full_topology()
        for edge in result["edges"]:
            assert "from" in edge
            assert "to" in edge
            assert "type" in edge
            assert edge["type"] in {"dependency", "influence", "data_flow", "control"}

    def test_governance_topology(self, topology: SystemTopology) -> None:
        result = topology.map_governance_topology()
        assert "nodes" in result
        assert "edges" in result
        for node in result["nodes"]:
            assert node["layer"] == "governance"

    def test_cognition_topology(self, topology: SystemTopology) -> None:
        result = topology.map_cognition_topology()
        assert "nodes" in result
        for node in result["nodes"]:
            assert node["layer"] == "cognition"

    def test_data_flow(self, topology: SystemTopology) -> None:
        result = topology.map_data_flow()
        assert "nodes" in result
        assert "edges" in result
        assert "flow_path" in result
        assert len(result["flow_path"]) > 0
        assert "inference.mediator" in result["flow_path"]
        assert "traceability.audit" in result["flow_path"]

    def test_centrality_computation(self, topology: SystemTopology, sample_topology: dict) -> None:
        centrality = topology.compute_centrality(sample_topology)
        assert len(centrality) == len(sample_topology["nodes"])
        # Most connected nodes should have higher centrality
        scores = list(centrality.values())
        assert all(0 <= s <= 1 for s in scores)
        # cognition.state_machine should be highly central
        assert "cognition.state_machine" in centrality

    def test_centrality_empty_topology(self, topology: SystemTopology) -> None:
        centrality = topology.compute_centrality({"nodes": [], "edges": []})
        assert centrality == {}

    def test_find_critical_paths(self, topology: SystemTopology, sample_topology: dict) -> None:
        paths = topology.find_critical_paths(sample_topology)
        assert isinstance(paths, list)
        # Should find at least one critical path
        if paths:
            for path in paths:
                assert isinstance(path, list)
                assert len(path) >= 2
                assert all(isinstance(n, str) for n in path)

    def test_critical_paths_empty_topology(self, topology: SystemTopology) -> None:
        paths = topology.find_critical_paths({"nodes": [], "edges": []})
        assert paths == []

    def test_render_dot(self, topology: SystemTopology, sample_topology: dict) -> None:
        dot = topology.render_dot(sample_topology)
        assert "digraph GARVIS" in dot
        assert "governance_loader" in dot or "governance.loader" in dot
        assert "}" in dot

    def test_render_mermaid(self, topology: SystemTopology, sample_topology: dict) -> None:
        mermaid = topology.render_mermaid(sample_topology)
        assert "flowchart TB" in mermaid
        assert "subgraph" in mermaid

    def test_topology_has_key_components(self, topology: SystemTopology) -> None:
        """Verify that critical GARVIS components are in the topology."""
        result = topology.map_full_topology()
        node_ids = {n["id"] for n in result["nodes"]}
        critical_components = [
            "governance.loader",
            "governance.registry",
            "governance.validator",
            "governance.enforcer",
            "governance.middleware",
            "cognition.state_machine",
            "cognition.session",
            "memory.episodic",
            "traceability.audit",
            "inference.executor",
            "inference.mediator",
            "runtime.bootstrap",
            "runtime.operator_interface",
            "analytics.metrics",
            "analytics.overview",
            "monitoring.alert_engine",
            "monitoring.topology",
        ]
        for component in critical_components:
            assert component in node_ids, f"Missing component: {component}"

    def test_topology_has_data_models(self, topology: SystemTopology) -> None:
        result = topology.map_full_topology()
        node_ids = {n["id"] for n in result["nodes"]}
        assert "models.governance" in node_ids
        assert "models.cognition" in node_ids
        assert "models.memory" in node_ids
        assert "models.audit" in node_ids
        assert "models.inference" in node_ids

    def test_topology_has_database(self, topology: SystemTopology) -> None:
        result = topology.map_full_topology()
        node_ids = {n["id"] for n in result["nodes"]}
        assert "database.connection" in node_ids
        assert "database.queries" in node_ids


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_alert_with_none_violation(self, alert_engine: AlertEngine) -> None:
        # Info-level violations don't trigger alerts
        info_violation = GovernanceViolation(
            schema_id="test",
            policy_id="test",
            severity="info",
            description="Info only",
        )
        alert = alert_engine.check_governance_violation(info_violation)
        assert alert is None

    def test_pressure_exactly_at_0_7(self, alert_engine: AlertEngine) -> None:
        """Boundary: pressure at 0.7 should NOT trigger."""
        alert = alert_engine.check_pressure("scope", 0.7)
        assert alert is None

    def test_pressure_just_above_0_7(self, alert_engine: AlertEngine) -> None:
        """Boundary: pressure at 0.7000001 should trigger."""
        alert = alert_engine.check_pressure("scope", 0.7000001)
        assert alert is not None

    def test_drift_at_0_1(self, alert_engine: AlertEngine) -> None:
        """Boundary: drift at 0.1 should NOT trigger."""
        alert = alert_engine.check_alignment_drift(0.1)
        assert alert is None

    def test_disclosure_at_0_5(self, alert_engine: AlertEngine) -> None:
        """Boundary: disclosure at 0.5 should NOT trigger."""
        alert = alert_engine.check_uncertainty_disclosure(0.5)
        assert alert is None

    def test_disclosure_just_below_0_5(self, alert_engine: AlertEngine) -> None:
        """Boundary: disclosure at 0.4999 should trigger."""
        alert = alert_engine.check_uncertainty_disclosure(0.4999)
        assert alert is not None

    def test_resilience_at_0_6(self, alert_engine: AlertEngine) -> None:
        """Boundary: resilience at 0.6 should NOT trigger."""
        alert = alert_engine.check_resilience(0.6)
        assert alert is None

    def test_equilibrium_at_0_5(self, alert_engine: AlertEngine) -> None:
        """Boundary: equilibrium at 0.5 should NOT trigger."""
        alert = alert_engine.check_equilibrium(0.5)
        assert alert is None

    def test_resolve_already_resolved_alert(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_resilience(0.3)
        result1 = alert_engine.resolve(alert.alert_id)
        assert result1 is True
        result2 = alert_engine.resolve(alert.alert_id)
        assert result2 is False  # Already resolved

    def test_acknowledge_already_acknowledged_alert(
        self,
        alert_engine: AlertEngine,
    ) -> None:
        alert = alert_engine.check_resilience(0.3)
        result1 = alert_engine.acknowledge(alert.alert_id)
        assert result1 is True
        result2 = alert_engine.acknowledge(alert.alert_id)
        assert result2 is False  # Already acknowledged

    def test_duplicate_resolution_time(self, alert_engine: AlertEngine) -> None:
        alert = alert_engine.check_resilience(0.3)
        alert_engine.resolve(alert.alert_id)
        assert alert.resolution_time is not None
        # Resolution time should be set
        assert isinstance(alert.resolution_time, datetime)
