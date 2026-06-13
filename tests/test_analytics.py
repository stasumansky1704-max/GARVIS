"""Comprehensive tests for GARVIS analytics engine.

Tests all analytics modules with mock data:
- metrics: CognitionMetrics, GovernancePressureMetrics
- trends: TrendAnalyzer
- continuity: ContinuityAnalyzer
- ecosystem: EcosystemMapper
- overview: AnalyticsOverview

All tests use mock data built from actual Pydantic models.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from analytics.continuity import ContinuityAnalyzer
from analytics.ecosystem import EcosystemMapper
from analytics.metrics import CognitionMetrics, GovernancePressureMetrics
from analytics.overview import AnalyticsOverview
from analytics.trends import TrendAnalyzer
from models.cognition import OperationalState, StateTransition
from models.governance import (
    GovernanceCheckResult,
    GovernanceConstraint,
    GovernanceSchema,
    GovernanceViolation,
    GovernancePolicy,
    ViolationResponse,
)
from models.memory import EpisodicMemory, MemoryInfluence, ProvenanceRecord
from models.audit import AuditEvent, CognitionTrace
from models.inference import GovernedResponse, InferenceRequest


# =============================================================================
#  Fixtures
# =============================================================================

@pytest.fixture
def base_time() -> datetime:
    """Reference timestamp for all mock data."""
    return datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def mock_schemas(base_time: datetime) -> list[GovernanceSchema]:
    """Create mock governance schemas."""
    return [
        GovernanceSchema(
            schema_id="schema_safety",
            name="Safety",
            version="1.0",
            category="safety",
            description="Safety constraints",
            policies=[
                GovernancePolicy(
                    policy_id="p1",
                    description="No harmful content",
                    rule_type="prohibition",
                    condition="content.is_safe",
                    evaluation_logic="eval_safe",
                    severity="critical",
                )
            ],
            constraints=[
                GovernanceConstraint(
                    constraint_id="c1",
                    description="Hard stop on violation",
                    scope="global",
                    enforcement="hard_stop",
                )
            ],
        ),
        GovernanceSchema(
            schema_id="schema_truth",
            name="Truthfulness",
            version="1.0",
            category="alignment",
            description="Truth constraints",
            policies=[
                GovernancePolicy(
                    policy_id="p2",
                    description="Must be truthful",
                    rule_type="requirement",
                    condition="content.is_true",
                    evaluation_logic="eval_truth",
                    severity="critical",
                )
            ],
            constraints=[
                GovernanceConstraint(
                    constraint_id="c2",
                    description="Log on truth failure",
                    scope="inference",
                    enforcement="log_only",
                )
            ],
        ),
    ]


@pytest.fixture
def mock_checks(base_time: datetime) -> list[GovernanceCheckResult]:
    """Create mock governance check results — mix of pass and fail."""
    checks: list[GovernanceCheckResult] = []
    for i in range(20):
        # 15 pass, 5 fail
        passed = i < 15
        violation = None
        if not passed:
            violation = GovernanceViolation(
                schema_id="schema_safety" if i % 2 == 0 else "schema_truth",
                policy_id="p1" if i % 2 == 0 else "p2",
                severity="critical",
                description="Mock violation",
            )
        checks.append(GovernanceCheckResult(
            schema_id="schema_safety" if i % 2 == 0 else "schema_truth",
            policy_id="p1" if i % 2 == 0 else "p2",
            passed=passed,
            violation=violation,
            timestamp=base_time + timedelta(minutes=i * 5),
        ))
    return checks


@pytest.fixture
def mock_violations(mock_checks: list[GovernanceCheckResult]) -> list[GovernanceViolation]:
    """Extract violations from mock checks."""
    violations: list[GovernanceViolation] = []
    for c in mock_checks:
        if c.violation is not None:
            violations.append(c.violation)
    return violations


@pytest.fixture
def mock_constraints(mock_schemas: list[GovernanceSchema]) -> list[GovernanceConstraint]:
    """Extract constraints from mock schemas."""
    constraints: list[GovernanceConstraint] = []
    for s in mock_schemas:
        constraints.extend(s.constraints)
    return constraints


@pytest.fixture
def mock_responses(base_time: datetime) -> list[GovernedResponse]:
    """Create mock governed responses."""
    responses: list[GovernedResponse] = []
    texts = [
        "I am certain about this answer.",
        "I am not sure about this topic.",
        "The answer is clear.",
        "I have low confidence in this response.",
        "This is verified information.",
        "I cannot determine the correct answer.",
        "The data supports this conclusion.",
        "I am uncertain about the details.",
        "This is inconclusive.",
        "The information is insufficient.",
    ]
    for i, text in enumerate(texts):
        responses.append(GovernedResponse(
            request_id=uuid4(),
            raw_response=text,
            validated_response=text if i % 3 != 0 else None,
            passed_validation=i % 4 != 0,
            validation_failures=["failure"] if i % 4 == 0 else [],
            generated_at=base_time + timedelta(minutes=i * 10),
        ))
    return responses


@pytest.fixture
def mock_transitions(base_time: datetime) -> list[StateTransition]:
    """Create mock state transitions."""
    transitions: list[StateTransition] = []
    seq = [
        (OperationalState.UNINITIALIZED, OperationalState.INITIALIZING, "boot"),
        (OperationalState.INITIALIZING, OperationalState.STANDBY, "ready"),
        (OperationalState.STANDBY, OperationalState.COGNITION_ACTIVE, "start"),
        (OperationalState.COGNITION_ACTIVE, OperationalState.INFERENCE_EXECUTING, "infer"),
        (OperationalState.INFERENCE_EXECUTING, OperationalState.TRACE_LOGGING, "log"),
        (OperationalState.TRACE_LOGGING, OperationalState.AUDITING, "audit"),
        (OperationalState.AUDITING, OperationalState.STANDBY, "done"),
        (OperationalState.STANDBY, OperationalState.COGNITION_ACTIVE, "start2"),
        (OperationalState.COGNITION_ACTIVE, OperationalState.DEGRADED, "error"),
        (OperationalState.DEGRADED, OperationalState.RECOVERING, "recover"),
        (OperationalState.RECOVERING, OperationalState.STANDBY, "recovered"),
        (OperationalState.STANDBY, OperationalState.COGNITION_ACTIVE, "start3"),
    ]
    for i, (fr, to, trigger) in enumerate(seq):
        transitions.append(StateTransition(
            transition_id=uuid4(),
            from_state=fr,
            to_state=to,
            trigger=trigger,
            governance_check=True,
            timestamp=base_time + timedelta(minutes=i * 3),
            trace_id=uuid4(),
        ))
    return transitions


@pytest.fixture
def mock_memories(base_time: datetime) -> list[EpisodicMemory]:
    """Create mock episodic memories."""
    memories: list[EpisodicMemory] = []
    for i in range(8):
        parent_id = memories[i - 1].memory_id if i > 0 and i % 3 == 0 else None
        memories.append(EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference" if i % 2 == 0 else "reflection",
            content=f"Memory content {i}",
            provenance=ProvenanceRecord(
                source_schema="schema_safety" if i % 2 == 0 else "schema_truth",
                creator_component="EpisodicMemoryStore",
                parent_memory_id=parent_id,
            ),
            governance_influences=["schema_safety", "schema_truth"][: i % 2 + 1],
            confidence=0.8 + (i * 0.02),
            timestamp=base_time + timedelta(minutes=i * 15),
            retrieval_count=i * 2,  # 0, 2, 4, 6, 8, 10, 12, 14
        ))
    return memories


@pytest.fixture
def mock_influences(mock_memories: list[EpisodicMemory]) -> list[MemoryInfluence]:
    """Create mock memory influences."""
    influences: list[MemoryInfluence] = []
    for i, mem in enumerate(mock_memories[:5]):
        influences.append(MemoryInfluence(
            memory_id=mem.memory_id,
            target_inference_id=uuid4(),
            influence_type="retrieval" if i % 2 == 0 else "context",
            strength=0.5 + (i * 0.1),
            trace_visible=True,
        ))
    return influences


@pytest.fixture
def mock_traces(
    base_time: datetime,
    mock_transitions: list[StateTransition],
    mock_checks: list[GovernanceCheckResult],
) -> list[CognitionTrace]:
    """Create mock cognition traces."""
    traces: list[CognitionTrace] = []
    for i in range(4):
        start = base_time + timedelta(minutes=i * 30)
        end = start + timedelta(seconds=45)
        # Take a subset of transitions and checks per trace
        t_trans = mock_transitions[i * 3:(i + 1) * 3] if i * 3 < len(mock_transitions) else []
        t_checks = mock_checks[i * 5:(i + 1) * 5] if i * 5 < len(mock_checks) else []
        traces.append(CognitionTrace(
            trace_id=uuid4(),
            session_id=uuid4(),
            start_time=start,
            end_time=end,
            state_sequence=t_trans,
            governance_checks=t_checks,
            final_state=OperationalState.STANDBY,
        ))
    return traces


@pytest.fixture
def mock_sessions(mock_traces: list[CognitionTrace]) -> list[CognitionTrace]:
    """Use traces as session proxies."""
    return mock_traces


@pytest.fixture
def mock_audit_events(base_time: datetime) -> list[AuditEvent]:
    """Create mock audit events."""
    return [
        AuditEvent(
            event_type="governance_check",
            severity="info",
            component="GovernanceEnforcer",
            timestamp=base_time + timedelta(minutes=i * 7),
        )
        for i in range(6)
    ]


@pytest.fixture
def mock_data(
    mock_schemas, mock_checks, mock_violations, mock_constraints,
    mock_responses, mock_traces, mock_transitions, mock_memories,
    mock_influences, mock_sessions, mock_audit_events,
) -> dict:
    """Assemble full mock data dict for overview tests."""
    return {
        "schemas": mock_schemas,
        "checks": mock_checks,
        "violations": mock_violations,
        "constraints": mock_constraints,
        "responses": mock_responses,
        "traces": mock_traces,
        "transitions": mock_transitions,
        "memories": mock_memories,
        "influences": mock_influences,
        "sessions": mock_sessions,
        "current_state": "standby",
        "audit_events": mock_audit_events,
    }


# =============================================================================
#  CognitionMetrics Tests
# =============================================================================

class TestCognitionMetrics:
    """Tests for CognitionMetrics."""

    def test_compute_governance_coverage(self, mock_checks: list[GovernanceCheckResult]):
        """Governance coverage should be pass rate."""
        metrics = CognitionMetrics()
        coverage = metrics.compute_governance_coverage(mock_checks)
        assert 0.0 <= coverage <= 1.0
        assert coverage == 0.75  # 15/20 pass

    def test_compute_governance_coverage_empty(self):
        """Empty checks should return 0.0."""
        metrics = CognitionMetrics()
        assert metrics.compute_governance_coverage([]) == 0.0

    def test_compute_uncertainty_disclosure_rate(self, mock_responses: list[GovernedResponse]):
        """Should detect uncertainty in responses."""
        metrics = CognitionMetrics()
        rate = metrics.compute_uncertainty_disclosure_rate(mock_responses)
        assert 0.0 <= rate <= 1.0
        # Texts with uncertainty: indices 1, 3, 5, 7, 8, 9 = 6/10
        assert rate == 0.6

    def test_compute_uncertainty_disclosure_rate_empty(self):
        """Empty responses should return 0.0."""
        metrics = CognitionMetrics()
        assert metrics.compute_uncertainty_disclosure_rate([]) == 0.0

    def test_compute_truthfulness_score(self, mock_responses: list[GovernedResponse]):
        """Truthfulness should be validation pass rate."""
        metrics = CognitionMetrics()
        score = metrics.compute_truthfulness_score(mock_responses)
        assert 0.0 <= score <= 1.0
        # i % 4 != 0 means indices 1,2,3,5,6,7,9 = 7/10 fail validation
        assert score == 0.7

    def test_compute_truthfulness_score_empty(self):
        """Empty responses should return 0.0."""
        metrics = CognitionMetrics()
        assert metrics.compute_truthfulness_score([]) == 0.0

    def test_compute_boundary_compliance_rate(self, mock_checks: list[GovernanceCheckResult]):
        """Boundary compliance should count non-critical failures."""
        metrics = CognitionMetrics()
        rate = metrics.compute_boundary_compliance_rate(mock_checks)
        assert 0.0 <= rate <= 1.0
        # 15 passed + 5 failed (but violations are "critical", so not counted as compliant)
        # Actually: 15 passed = compliant, 5 failed with critical violation = not compliant
        # But wait - the violations have severity "critical", so they don't count as compliant
        # So boundary_compliance = 15/20 = 0.75
        # Hmm, let me re-check: compliant = passed OR (not passed AND violation.severity != "critical")
        # All failures have critical severity, so only passed ones are compliant
        assert rate == 0.75

    def test_compute_boundary_compliance_empty(self):
        """Empty checks should return 0.0."""
        metrics = CognitionMetrics()
        assert metrics.compute_boundary_compliance_rate([]) == 0.0

    def test_compute_session_success_rate(self, mock_sessions: list[CognitionTrace]):
        """Success rate should exclude fail_closed sessions."""
        metrics = CognitionMetrics()
        rate = metrics.compute_session_success_rate(mock_sessions)
        assert 0.0 <= rate <= 1.0
        # All mock traces have final_state=STANDBY, so all succeed
        assert rate == 1.0

    def test_compute_session_success_rate_empty(self):
        """Empty sessions should return 0.0."""
        metrics = CognitionMetrics()
        assert metrics.compute_session_success_rate([]) == 0.0

    def test_compute_average_response_time(self, mock_traces: list[CognitionTrace]):
        """Should compute average trace duration in ms."""
        metrics = CognitionMetrics()
        avg = metrics.compute_average_response_time(mock_traces)
        assert avg >= 0.0
        # Each trace is 45 seconds = 45000 ms
        assert avg == 45000.0

    def test_compute_average_response_time_empty(self):
        """Empty traces should return 0.0."""
        metrics = CognitionMetrics()
        assert metrics.compute_average_response_time([]) == 0.0

    def test_compute_average_response_time_no_end(self, base_time: datetime):
        """Traces without end_time should be skipped."""
        metrics = CognitionMetrics()
        trace = CognitionTrace(
            trace_id=uuid4(),
            session_id=uuid4(),
            start_time=base_time,
            end_time=None,
        )
        assert metrics.compute_average_response_time([trace]) == 0.0

    def test_compute_memory_retrieval_rate(self, mock_memories: list[EpisodicMemory]):
        """Should compute average retrievals per memory."""
        metrics = CognitionMetrics()
        rate = metrics.compute_memory_retrieval_rate(mock_memories)
        # retrieval_count: 0, 2, 4, 6, 8, 10, 12, 14 = sum=56, avg=7.0
        assert rate == 7.0

    def test_compute_memory_retrieval_rate_empty(self):
        """Empty memories should return 0.0."""
        metrics = CognitionMetrics()
        assert metrics.compute_memory_retrieval_rate([]) == 0.0


# =============================================================================
#  GovernancePressureMetrics Tests
# =============================================================================

class TestGovernancePressureMetrics:
    """Tests for GovernancePressureMetrics."""

    def test_compute_schema_pressure(self, mock_violations: list[GovernanceViolation], mock_checks: list[GovernanceCheckResult]):
        """Should compute per-schema pressure."""
        pressure = GovernancePressureMetrics()
        result = pressure.compute_schema_pressure(mock_violations, len(mock_checks))
        assert isinstance(result, dict)
        assert len(result) > 0
        for schema_id, metrics in result.items():
            assert "violation_rate" in metrics
            assert "check_density" in metrics
            assert 0.0 <= metrics["violation_rate"] <= 1.0

    def test_compute_schema_pressure_empty(self):
        """Empty input should return empty dict."""
        pressure = GovernancePressureMetrics()
        assert pressure.compute_schema_pressure([], 0) == {}
        assert pressure.compute_schema_pressure([], 10) == {}

    def test_compute_scope_pressure(self, mock_checks: list[GovernanceCheckResult]):
        """Should compute per-scope pressure."""
        pressure = GovernancePressureMetrics()
        by_scope = {
            "global": mock_checks[:10],
            "inference": mock_checks[10:],
        }
        result = pressure.compute_scope_pressure(by_scope)
        assert isinstance(result, dict)
        assert "global" in result
        assert "inference" in result
        for v in result.values():
            assert 0.0 <= v <= 1.0

    def test_compute_scope_pressure_empty(self):
        """Empty input should return empty dict."""
        pressure = GovernancePressureMetrics()
        assert pressure.compute_scope_pressure({}) == {}

    def test_compute_scope_pressure_empty_scope(self):
        """Scope with empty checks should return 0.0."""
        pressure = GovernancePressureMetrics()
        result = pressure.compute_scope_pressure({"global": []})
        assert result["global"] == 0.0

    def test_compute_enforcement_pressure(self, mock_constraints: list[GovernanceConstraint]):
        """Should compute enforcement pressure."""
        pressure = GovernancePressureMetrics()
        result = pressure.compute_enforcement_pressure(mock_constraints)
        assert 0.0 <= result <= 1.0
        # 1 hard_stop out of 2 constraints
        # base_pressure = 0.5, density_factor = min(2/20, 1) = 0.1
        # pressure = 0.7*0.5 + 0.3*0.1 = 0.35 + 0.03 = 0.38
        assert result == 0.38

    def test_compute_enforcement_pressure_empty(self):
        """Empty constraints should return 0.0."""
        pressure = GovernancePressureMetrics()
        assert pressure.compute_enforcement_pressure([]) == 0.0

    def test_compute_adaptation_pressure(self, mock_transitions: list[StateTransition]):
        """Should compute adaptation pressure from transitions."""
        pressure = GovernancePressureMetrics()
        result = pressure.compute_adaptation_pressure(mock_transitions)
        assert 0.0 <= result <= 1.0
        # One degraded transition at index 8, one recovering at index 9
        # stress_transitions = 2 (degraded) + 1 (recovering from degraded) + 0.5 (recovering)
        # Actually: to degraded (1), to recovering (1), from degraded to standby via recovering (0.5)
        # Total stress = 2 + 0.5 = 2.5 / 12 transitions
        # ratio * 5 = (2.5/12)*5 = 1.04, capped at 1.0

    def test_compute_adaptation_pressure_empty(self):
        """Empty transitions should return 0.0."""
        pressure = GovernancePressureMetrics()
        assert pressure.compute_adaptation_pressure([]) == 0.0

    def test_compute_adaptation_pressure_no_stress(self, base_time: datetime):
        """Transitions without stress states should return low pressure."""
        pressure = GovernancePressureMetrics()
        transitions = [
            StateTransition(
                transition_id=uuid4(),
                from_state=OperationalState.STANDBY,
                to_state=OperationalState.COGNITION_ACTIVE,
                trigger="start",
                governance_check=True,
                timestamp=base_time,
                trace_id=uuid4(),
            ),
            StateTransition(
                transition_id=uuid4(),
                from_state=OperationalState.COGNITION_ACTIVE,
                to_state=OperationalState.STANDBY,
                trigger="done",
                governance_check=True,
                timestamp=base_time + timedelta(minutes=1),
                trace_id=uuid4(),
            ),
        ]
        result = pressure.compute_adaptation_pressure(transitions)
        assert result == 0.0  # No stress transitions

    def test_compute_conflict_pressure(self, mock_violations: list[GovernanceViolation]):
        """Should compute conflict pressure."""
        pressure = GovernancePressureMetrics()
        result = pressure.compute_conflict_pressure(mock_violations)
        assert 0.0 <= result <= 1.0
        # 2 schemas with violations, 5 violations, all unresolved
        # schema_diversity = min(2/5, 1) = 0.4
        # unresolved_rate = 5/5 = 1.0
        # pressure = 0.6*0.4 + 0.4*1.0 = 0.24 + 0.4 = 0.64

    def test_compute_conflict_pressure_empty(self):
        """Empty violations should return 0.0."""
        pressure = GovernancePressureMetrics()
        assert pressure.compute_conflict_pressure([]) == 0.0


# =============================================================================
#  TrendAnalyzer Tests
# =============================================================================

class TestTrendAnalyzer:
    """Tests for TrendAnalyzer."""

    def test_analyze_governance_trend(self, mock_checks: list[GovernanceCheckResult]):
        """Should produce governance pass rate trend."""
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze_governance_trend(mock_checks, window_minutes=60)
        assert isinstance(trend, list)
        assert len(trend) > 0
        for point in trend:
            assert "window_start" in point
            assert "pass_rate" in point
            assert "total_checks" in point
            assert "passed_checks" in point
            assert 0.0 <= point["pass_rate"] <= 1.0

    def test_analyze_governance_trend_empty(self):
        """Empty checks should return empty list."""
        analyzer = TrendAnalyzer()
        assert analyzer.analyze_governance_trend([]) == []

    def test_analyze_state_stability(self, mock_transitions: list[StateTransition]):
        """Should produce state stability trend."""
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze_state_stability(mock_transitions, window_minutes=60)
        assert isinstance(trend, list)
        for point in trend:
            assert "window_start" in point
            assert "transition_count" in point
            assert "stability_score" in point
            assert "unique_states" in point
            assert 0.0 <= point["stability_score"] <= 1.0

    def test_analyze_state_stability_empty(self):
        """Empty transitions should return empty list."""
        analyzer = TrendAnalyzer()
        assert analyzer.analyze_state_stability([]) == []

    def test_analyze_uncertainty_trend(self, mock_responses: list[GovernedResponse]):
        """Should produce uncertainty disclosure trend."""
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze_uncertainty_trend(mock_responses, window_minutes=60)
        assert isinstance(trend, list)
        for point in trend:
            assert "window_start" in point
            assert "disclosure_rate" in point
            assert "total_responses" in point
            assert 0.0 <= point["disclosure_rate"] <= 1.0

    def test_analyze_degradation_trend(self, mock_transitions: list[StateTransition]):
        """Should produce degradation trend."""
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze_degradation_trend(mock_transitions, window_minutes=60)
        assert isinstance(trend, list)
        for point in trend:
            assert "window_start" in point
            assert "degradation_events" in point
            assert "recovery_events" in point
            assert "degradation_rate" in point

    def test_analyze_memory_usage_trend(self, mock_memories: list[EpisodicMemory]):
        """Should produce memory usage trend."""
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze_memory_usage_trend(mock_memories, window_minutes=60)
        assert isinstance(trend, list)
        for point in trend:
            assert "window_start" in point
            assert "memories_created" in point
            assert "avg_retrievals" in point
            assert "total_retrievals" in point

    def test_analyze_quality_trend(self, mock_traces: list[CognitionTrace]):
        """Should produce quality trend."""
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze_quality_trend(mock_traces, window_minutes=60)
        assert isinstance(trend, list)
        for point in trend:
            assert "window_start" in point
            assert "quality_score" in point
            assert "traces_in_window" in point

    def test_compute_moving_average(self):
        """Should compute simple moving average."""
        analyzer = TrendAnalyzer()
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        ma = analyzer.compute_moving_average(values, window=3)
        assert len(ma) == 5
        # [1/1, (1+2)/2, (1+2+3)/3, (2+3+4)/3, (3+4+5)/3]
        assert ma[0] == 1.0
        assert ma[1] == 1.5
        assert ma[2] == 2.0
        assert ma[4] == 4.0

    def test_compute_moving_average_empty(self):
        """Empty list should return empty list."""
        analyzer = TrendAnalyzer()
        assert analyzer.compute_moving_average([]) == []

    def test_compute_rate_of_change(self):
        """Should compute rate of change."""
        analyzer = TrendAnalyzer()
        values = [10.0, 15.0, 12.0]
        roc = analyzer.compute_rate_of_change(values)
        assert len(roc) == 2
        # (15-10)/10 = 0.5, (12-15)/15 = -0.2
        assert roc[0] == 0.5
        assert abs(roc[1] - (-0.2)) < 0.001

    def test_compute_rate_of_change_empty(self):
        """Empty or single-element list should return empty list."""
        analyzer = TrendAnalyzer()
        assert analyzer.compute_rate_of_change([]) == []
        assert analyzer.compute_rate_of_change([1.0]) == []

    def test_compute_rate_of_change_zero_division(self):
        """Should handle zero division gracefully."""
        analyzer = TrendAnalyzer()
        roc = analyzer.compute_rate_of_change([0.0, 5.0])
        assert roc[0] == 1.0  # Positive from zero


# =============================================================================
#  ContinuityAnalyzer Tests
# =============================================================================

class TestContinuityAnalyzer:
    """Tests for ContinuityAnalyzer."""

    def test_compute_session_continuity_score(self, mock_sessions: list[CognitionTrace]):
        """Should compute session continuity score."""
        analyzer = ContinuityAnalyzer()
        score = analyzer.compute_session_continuity_score(mock_sessions)
        assert 0.0 <= score <= 1.0
        # All sessions completed (STANDBY), all same duration
        assert score > 0.8

    def test_compute_session_continuity_score_empty(self):
        """Empty sessions should return 0.0."""
        analyzer = ContinuityAnalyzer()
        assert analyzer.compute_session_continuity_score([]) == 0.0

    def test_compute_governance_persistence(self):
        """Should compute governance schema persistence."""
        analyzer = ContinuityAnalyzer()
        schemas_active = [
            ["s1", "s2", "s3"],
            ["s1", "s2", "s3"],  # identical
            ["s1", "s2"],         # s3 removed
            ["s1", "s2", "s4"],  # s4 added
        ]
        score = analyzer.compute_governance_persistence(schemas_active)
        assert 0.0 <= score <= 1.0
        # Jaccard similarities: [1.0, 0.8, 0.6] -> avg ~0.8

    def test_compute_governance_persistence_empty(self):
        """Empty input should return 0.0."""
        analyzer = ContinuityAnalyzer()
        assert analyzer.compute_governance_persistence([]) == 0.0

    def test_compute_governance_persistence_single(self):
        """Single observation should return 1.0."""
        analyzer = ContinuityAnalyzer()
        assert analyzer.compute_governance_persistence([["s1"]]) == 1.0

    def test_compute_governance_persistence_identical(self):
        """Identical schema sets should return 1.0."""
        analyzer = ContinuityAnalyzer()
        score = analyzer.compute_governance_persistence([
            ["s1", "s2"],
            ["s1", "s2"],
            ["s1", "s2"],
        ])
        assert score == 1.0

    def test_compute_alignment_drift(self, mock_checks: list[GovernanceCheckResult]):
        """Should detect alignment drift."""
        analyzer = ContinuityAnalyzer()
        result = analyzer.compute_alignment_drift(mock_checks)
        assert "drift_score" in result
        assert "trend_direction" in result
        assert "per_period_rates" in result
        assert 0.0 <= result["drift_score"] <= 1.0
        assert result["trend_direction"] in ("improving", "degrading", "stable")

    def test_compute_alignment_drift_empty(self):
        """Empty input should return neutral result."""
        analyzer = ContinuityAnalyzer()
        result = analyzer.compute_alignment_drift([])
        assert result["drift_score"] == 0.0
        assert result["trend_direction"] == "stable"

    def test_compute_memory_continuity(self, mock_memories: list[EpisodicMemory]):
        """Should compute memory continuity score."""
        analyzer = ContinuityAnalyzer()
        score = analyzer.compute_memory_continuity(mock_memories)
        assert 0.0 <= score <= 1.0
        # Multiple memories with retrievals, shared schemas, parent-child

    def test_compute_memory_continuity_empty(self):
        """Empty memories should return 0.0."""
        analyzer = ContinuityAnalyzer()
        assert analyzer.compute_memory_continuity([]) == 0.0

    def test_compute_reasoning_continuity(self, mock_traces: list[CognitionTrace]):
        """Should compute reasoning continuity."""
        analyzer = ContinuityAnalyzer()
        score = analyzer.compute_reasoning_continuity(mock_traces)
        assert 0.0 <= score <= 1.0

    def test_compute_reasoning_continuity_empty(self):
        """Empty traces should return 0.0."""
        analyzer = ContinuityAnalyzer()
        assert analyzer.compute_reasoning_continuity([]) == 0.0

    def test_generate_continuity_map(self, mock_sessions, mock_memories, mock_traces):
        """Should generate full continuity map."""
        analyzer = ContinuityAnalyzer()
        cmap = analyzer.generate_continuity_map(mock_sessions, mock_memories, mock_traces)
        assert "session_continuity" in cmap
        assert "memory_continuity" in cmap
        assert "reasoning_continuity" in cmap
        assert "governance_persistence" in cmap
        assert "overall_score" in cmap
        assert "dimensions" in cmap
        assert 0.0 <= cmap["overall_score"] <= 1.0

    def test_compute_resilience_score(self, mock_transitions: list[StateTransition]):
        """Should compute resilience from degradation-recovery."""
        analyzer = ContinuityAnalyzer()
        score = analyzer.compute_resilience_score(mock_transitions)
        assert 0.0 <= score <= 1.0
        # One degradation followed by recovery after 2 steps

    def test_compute_resilience_score_empty(self):
        """Empty transitions should return 0.0."""
        analyzer = ContinuityAnalyzer()
        assert analyzer.compute_resilience_score([]) == 0.0

    def test_compute_resilience_score_no_degradation(self, base_time: datetime):
        """No degradation at all should return 1.0."""
        analyzer = ContinuityAnalyzer()
        transitions = [
            StateTransition(
                transition_id=uuid4(),
                from_state=OperationalState.STANDBY,
                to_state=OperationalState.COGNITION_ACTIVE,
                trigger="start",
                governance_check=True,
                timestamp=base_time,
                trace_id=uuid4(),
            ),
        ]
        assert analyzer.compute_resilience_score(transitions) == 1.0

    def test_compute_equilibrium_stability(self):
        """Should compute equilibrium stability from state durations."""
        analyzer = ContinuityAnalyzer()
        state_durations = {
            "cognition_active": 100.0,
            "standby": 50.0,
            "degraded": 10.0,
            "recovering": 5.0,
        }
        score = analyzer.compute_equilibrium_stability(state_durations)
        assert 0.0 <= score <= 1.0
        # Productive: 150/165 = 0.909, non-productive penalty: 15/165 = 0.09
        # stability = 0.909 - 0.3*0.09 = 0.882

    def test_compute_equilibrium_stability_empty(self):
        """Empty durations should return 0.0."""
        analyzer = ContinuityAnalyzer()
        assert analyzer.compute_equilibrium_stability({}) == 0.0


# =============================================================================
#  EcosystemMapper Tests
# =============================================================================

class TestEcosystemMapper:
    """Tests for EcosystemMapper."""

    def test_map_governance_influence_ecosystem(
        self, mock_checks: list[GovernanceCheckResult], mock_violations: list[GovernanceViolation]
    ):
        """Should map governance influence ecosystem."""
        mapper = EcosystemMapper()
        eco = mapper.map_governance_influence_ecosystem(mock_checks, mock_violations)
        assert "nodes" in eco
        assert "edges" in eco
        assert "centrality" in eco
        assert len(eco["nodes"]) > 0

    def test_map_governance_influence_ecosystem_empty(self):
        """Empty input should return empty structure."""
        mapper = EcosystemMapper()
        eco = mapper.map_governance_influence_ecosystem([], [])
        assert eco["nodes"] == []
        assert eco["edges"] == []
        assert eco["centrality"] == {}

    def test_map_memory_relationship_ecosystem(
        self, mock_memories: list[EpisodicMemory], mock_influences: list[MemoryInfluence]
    ):
        """Should map memory relationship ecosystem."""
        mapper = EcosystemMapper()
        eco = mapper.map_memory_relationship_ecosystem(mock_memories, mock_influences)
        assert "nodes" in eco
        assert "edges" in eco
        assert "clusters" in eco
        assert len(eco["nodes"]) == len(mock_memories)

    def test_map_memory_relationship_ecosystem_empty(self):
        """Empty memories should return empty structure."""
        mapper = EcosystemMapper()
        eco = mapper.map_memory_relationship_ecosystem([], [])
        assert eco["nodes"] == []
        assert eco["edges"] == []
        assert eco["clusters"] == {}

    def test_map_reasoning_influence_ecosystem(self, mock_traces: list[CognitionTrace]):
        """Should map reasoning influence ecosystem."""
        mapper = EcosystemMapper()
        eco = mapper.map_reasoning_influence_ecosystem(mock_traces)
        assert "nodes" in eco
        assert "edges" in eco
        assert "flow_summary" in eco
        assert eco["flow_summary"]["total_traces_analyzed"] == len(mock_traces)

    def test_map_reasoning_influence_ecosystem_empty(self):
        """Empty traces should return empty structure."""
        mapper = EcosystemMapper()
        eco = mapper.map_reasoning_influence_ecosystem([])
        assert eco["nodes"] == []
        assert eco["edges"] == []

    def test_compute_cognition_ecosystem_graph(
        self, mock_data: dict,
    ):
        """Should compute full cognition ecosystem graph."""
        mapper = EcosystemMapper()
        graph = mapper.compute_cognition_ecosystem_graph({
            "checks": mock_data["checks"],
            "violations": mock_data["violations"],
            "memories": mock_data["memories"],
            "influences": mock_data["influences"],
            "traces": mock_data["traces"],
        })
        assert "nodes" in graph
        assert "edges" in graph
        assert "stats" in graph
        stats = graph["stats"]
        assert "total_nodes" in stats
        assert "total_edges" in stats
        assert "governance_nodes" in stats
        assert "memory_nodes" in stats
        assert "reasoning_nodes" in stats

    def test_compute_cognition_ecosystem_graph_empty(self):
        """Empty data should return empty graph with zero stats."""
        mapper = EcosystemMapper()
        graph = mapper.compute_cognition_ecosystem_graph({
            "checks": [],
            "violations": [],
            "memories": [],
            "influences": [],
            "traces": [],
        })
        assert graph["stats"]["total_nodes"] == 0
        assert graph["stats"]["total_edges"] == 0

    def test_compute_alignment_ecology(
        self, mock_sessions: list[CognitionTrace], mock_checks: list[GovernanceCheckResult]
    ):
        """Should compute alignment ecology."""
        mapper = EcosystemMapper()
        eco = mapper.compute_alignment_ecology(mock_sessions, mock_checks)
        assert "drift_rate" in eco
        assert "durability_score" in eco
        assert "stability_score" in eco
        assert "alignment_health" in eco
        assert eco["alignment_health"] in ("healthy", "stable", "degrading", "critical", "unknown")

    def test_compute_alignment_ecology_empty(self):
        """Empty checks should return zero scores."""
        mapper = EcosystemMapper()
        eco = mapper.compute_alignment_ecology([], [])
        assert eco["drift_rate"] == 0.0
        assert eco["durability_score"] == 0.0
        assert eco["stability_score"] == 0.0
        assert eco["alignment_health"] == "unknown"

    def test_compute_governance_durability(
        self, mock_schemas: list[GovernanceSchema], mock_checks: list[GovernanceCheckResult]
    ):
        """Should compute governance durability."""
        mapper = EcosystemMapper()
        score = mapper.compute_governance_durability(mock_schemas, mock_checks)
        assert 0.0 <= score <= 1.0

    def test_compute_governance_durability_empty(self):
        """Empty input should return 0.0."""
        mapper = EcosystemMapper()
        assert mapper.compute_governance_durability([], []) == 0.0


# =============================================================================
#  AnalyticsOverview Tests
# =============================================================================

class TestAnalyticsOverview:
    """Tests for AnalyticsOverview."""

    def test_generate_overview_structure(self, mock_data: dict):
        """Should generate overview with all required sections."""
        overview = AnalyticsOverview()
        result = overview.generate(mock_data)

        # All top-level sections
        assert "governance" in result
        assert "cognition" in result
        assert "memory" in result
        assert "traceability" in result
        assert "continuity" in result
        assert "pressure" in result
        assert "trends" in result
        assert "ecosystem" in result

    def test_generate_governance_section(self, mock_data: dict):
        """Governance section should have all fields."""
        overview = AnalyticsOverview()
        result = overview.generate(mock_data)["governance"]
        assert "active_schemas" in result
        assert "total_constraints" in result
        assert "hard_stop_rate" in result
        assert "coverage_score" in result
        assert "pressure" in result
        assert result["active_schemas"] == len(mock_data["schemas"])

    def test_generate_cognition_section(self, mock_data: dict):
        """Cognition section should have all fields."""
        overview = AnalyticsOverview()
        result = overview.generate(mock_data)["cognition"]
        assert "current_state" in result
        assert "session_count" in result
        assert "success_rate" in result
        assert "avg_response_time_ms" in result
        assert "quality_score" in result
        assert 0.0 <= result["quality_score"] <= 1.0

    def test_generate_memory_section(self, mock_data: dict):
        """Memory section should have all fields."""
        overview = AnalyticsOverview()
        result = overview.generate(mock_data)["memory"]
        assert "total_memories" in result
        assert "avg_retrievals" in result
        assert "influences_tracked" in result
        assert "trace_visible_rate" in result

    def test_generate_traceability_section(self, mock_data: dict):
        """Traceability section should have all fields."""
        overview = AnalyticsOverview()
        result = overview.generate(mock_data)["traceability"]
        assert "total_traces" in result
        assert "avg_governance_checks" in result
        assert "violation_count" in result
        assert "audit_event_count" in result

    def test_generate_continuity_section(self, mock_data: dict):
        """Continuity section should have all fields."""
        overview = AnalyticsOverview()
        result = overview.generate(mock_data)["continuity"]
        assert "continuity_score" in result
        assert "alignment_drift" in result
        assert "resilience_score" in result
        assert "equilibrium_stability" in result
        for v in result.values():
            assert isinstance(v, float)
            assert 0.0 <= v <= 1.0

    def test_generate_pressure_section(self, mock_data: dict):
        """Pressure section should have all fields."""
        overview = AnalyticsOverview()
        result = overview.generate(mock_data)["pressure"]
        assert "adaptation_pressure" in result
        assert "enforcement_pressure" in result
        assert "conflict_pressure" in result
        assert "overall_pressure" in result
        for v in result.values():
            assert isinstance(v, float)
            assert 0.0 <= v <= 1.0

    def test_generate_trends_section(self, mock_data: dict):
        """Trends section should have all trend lists."""
        overview = AnalyticsOverview()
        result = overview.generate(mock_data)["trends"]
        assert "governance_trend" in result
        assert "state_stability_trend" in result
        assert "quality_trend" in result
        assert "degradation_trend" in result
        for trend_list in result.values():
            assert isinstance(trend_list, list)

    def test_generate_ecosystem_section(self, mock_data: dict):
        """Ecosystem section should have all fields."""
        overview = AnalyticsOverview()
        result = overview.generate(mock_data)["ecosystem"]
        assert "governance_nodes" in result
        assert "memory_nodes" in result
        assert "reasoning_nodes" in result
        assert "total_edges" in result
        assert "alignment_ecology" in result

    def test_generate_empty_data(self):
        """Empty data should still produce valid structure with zero values."""
        overview = AnalyticsOverview()
        empty_data = {
            "schemas": [],
            "checks": [],
            "violations": [],
            "constraints": [],
            "responses": [],
            "traces": [],
            "transitions": [],
            "memories": [],
            "influences": [],
            "sessions": [],
            "current_state": "unknown",
            "audit_events": [],
        }
        result = overview.generate(empty_data)
        assert "governance" in result
        assert "cognition" in result
        assert result["governance"]["active_schemas"] == 0
        assert result["cognition"]["session_count"] == 0
        assert result["memory"]["total_memories"] == 0


# =============================================================================
#  Edge Cases & Integration
# =============================================================================

class TestEdgeCases:
    """Edge case tests across all modules."""

    def test_all_metrics_normalized(self, mock_data: dict):
        """All scalar metrics should be in [0.0, 1.0]."""
        overview = AnalyticsOverview()
        result = overview.generate(mock_data)

        sections_to_check = [
            ("governance", ["hard_stop_rate", "coverage_score", "pressure"]),
            ("cognition", ["success_rate", "quality_score"]),
            ("memory", ["trace_visible_rate"]),
            ("continuity", ["continuity_score", "alignment_drift", "resilience_score", "equilibrium_stability"]),
            ("pressure", ["adaptation_pressure", "enforcement_pressure", "conflict_pressure", "overall_pressure"]),
        ]

        for section, keys in sections_to_check:
            for key in keys:
                value = result[section][key]
                assert 0.0 <= value <= 1.0, \
                    f"{section}.{key} = {value}, expected [0.0, 1.0]"

    def test_graceful_empty_handling(self):
        """All modules should handle empty input gracefully."""
        metrics = CognitionMetrics()
        pressure = GovernancePressureMetrics()
        trends = TrendAnalyzer()
        continuity = ContinuityAnalyzer()
        ecosystem = EcosystemMapper()

        # None should crash
        assert metrics.compute_governance_coverage([]) == 0.0
        assert metrics.compute_uncertainty_disclosure_rate([]) == 0.0
        assert metrics.compute_truthfulness_score([]) == 0.0
        assert metrics.compute_boundary_compliance_rate([]) == 0.0
        assert metrics.compute_session_success_rate([]) == 0.0
        assert metrics.compute_average_response_time([]) == 0.0
        assert metrics.compute_memory_retrieval_rate([]) == 0.0

        assert pressure.compute_enforcement_pressure([]) == 0.0
        assert pressure.compute_adaptation_pressure([]) == 0.0
        assert pressure.compute_conflict_pressure([]) == 0.0
        assert pressure.compute_schema_pressure([], 0) == {}
        assert pressure.compute_scope_pressure({}) == {}

        assert trends.analyze_governance_trend([]) == []
        assert trends.analyze_state_stability([]) == []
        assert trends.analyze_uncertainty_trend([]) == []
        assert trends.analyze_degradation_trend([]) == []
        assert trends.analyze_memory_usage_trend([]) == []
        assert trends.analyze_quality_trend([]) == []
        assert trends.compute_moving_average([]) == []
        assert trends.compute_rate_of_change([]) == []

        assert continuity.compute_session_continuity_score([]) == 0.0
        assert continuity.compute_governance_persistence([]) == 0.0
        assert continuity.compute_memory_continuity([]) == 0.0
        assert continuity.compute_reasoning_continuity([]) == 0.0
        assert continuity.compute_resilience_score([]) == 0.0
        assert continuity.compute_equilibrium_stability({}) == 0.0
        drift = continuity.compute_alignment_drift([])
        assert drift["drift_score"] == 0.0

        eco = ecosystem.map_governance_influence_ecosystem([], [])
        assert eco["nodes"] == []
        eco = ecosystem.map_memory_relationship_ecosystem([], [])
        assert eco["nodes"] == []
        eco = ecosystem.map_reasoning_influence_ecosystem([])
        assert eco["nodes"] == []

    def test_purity_same_input_same_output(self, mock_checks: list[GovernanceCheckResult]):
        """Pure functions should return identical results for identical input."""
        metrics1 = CognitionMetrics()
        metrics2 = CognitionMetrics()

        r1 = metrics1.compute_governance_coverage(mock_checks)
        r2 = metrics2.compute_governance_coverage(mock_checks)
        assert r1 == r2

        pressure1 = GovernancePressureMetrics()
        pressure2 = GovernancePressureMetrics()
        p1 = pressure1.compute_enforcement_pressure([])
        p2 = pressure2.compute_enforcement_pressure([])
        assert p1 == p2 == 0.0
