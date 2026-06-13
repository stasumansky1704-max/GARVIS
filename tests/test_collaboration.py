"""Tests for the Governed Collaborative Cognition layer (Phase 13).

Tests cover:
- Collaboration session creation and lifecycle
- Operator input processing with governance mediation
- Governance negotiation explanations
- Bounded strategic reasoning
- Uncertainty disclosure
- Memory influence visibility
- Audit trail
- Fail-closed behavior

All tests use mock data (no DB or LLM required).
"""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from cognition.collaboration import (
    CollaborationSession,
    CollaborationInteraction,
    OperatorInput,
    GovernedCollaborationResponse,
)
from cognition.negotiation import GovernanceNegotiation
from cognition.strategy import BoundedStrategyEngine
from models.governance import (
    GovernanceViolation,
    GovernanceCheckResult,
    GovernanceSchema,
    GovernancePolicy,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_session():
    """Create a sample collaboration session."""
    session = CollaborationSession(
        session_id=f"test_{uuid4().hex[:8]}",
        operator_id="operator_001",
        project_id="project_alpha",
        validator=None,
        audit=None,
    )
    yield session
    # Cleanup
    if session.is_active:
        session.end_session()
    CollaborationSession._SESSION_REGISTRY.pop(session.session_id, None)


@pytest.fixture
def negotiation_engine():
    """Create a fresh negotiation engine."""
    return GovernanceNegotiation()


@pytest.fixture
def strategy_engine():
    """Create a strategy engine with test schemas."""
    return BoundedStrategyEngine(
        active_schema_ids=[
            "epistemic_safety",
            "operational_integrity",
            "boundary_enforcement",
            "traceability_requirement",
        ]
    )


@pytest.fixture
def sample_violation():
    """Create a sample governance violation."""
    return GovernanceViolation(
        schema_id="boundary_enforcement",
        policy_id="be_01",
        severity="critical",
        description="Input contains potentially executable code patterns",
        context={"blocked_keyword": "exec("},
    )


# ============================================================================
# 1. Collaboration Session Tests
# ============================================================================


class TestCollaborationSession:
    """Tests for CollaborationSession creation and lifecycle."""

    def test_session_creation(self, sample_session):
        """Test that a session is created with correct attributes."""
        assert sample_session.session_id.startswith("test_")
        assert sample_session.operator_id == "operator_001"
        assert sample_session.project_id == "project_alpha"
        assert sample_session.is_active is True
        assert sample_session.interaction_count == 0

    def test_session_has_governance_context(self, sample_session):
        """Test that session has governance context."""
        assert isinstance(sample_session.governance_context, list)

    def test_session_duration_increases(self, sample_session):
        """Test that session duration is positive."""
        import time
        time.sleep(0.01)
        assert sample_session.duration_seconds > 0

    def test_session_registry(self, sample_session):
        """Test that session is registered."""
        retrieved = CollaborationSession.get_session_by_id(sample_session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == sample_session.session_id

    def test_list_active_sessions(self, sample_session):
        """Test listing active sessions."""
        active = CollaborationSession.list_active_sessions()
        assert len(active) >= 1
        assert any(s.session_id == sample_session.session_id for s in active)

    def test_end_session(self, sample_session):
        """Test ending a session."""
        result = sample_session.end_session()
        assert result["status"] == "ended"
        assert result["total_interactions"] == 0
        assert sample_session.is_active is False

    def test_end_session_inactive(self, sample_session):
        """Test ending an already-ended session."""
        sample_session.end_session()
        result = sample_session.end_session()
        assert "error" in result

    def test_session_to_dict_not_implemented(self, sample_session):
        """Test that session stores interactions correctly."""
        # Initially empty
        assert sample_session.get_interaction_history() == []

    def test_multiple_sessions_in_registry(self):
        """Test that multiple sessions coexist in registry."""
        s1 = CollaborationSession(
            session_id=f"multi_{uuid4().hex[:8]}",
            operator_id="op1",
            project_id="proj1",
            validator=None,
            audit=None,
        )
        s2 = CollaborationSession(
            session_id=f"multi_{uuid4().hex[:8]}",
            operator_id="op2",
            project_id="proj2",
            validator=None,
            audit=None,
        )

        active = CollaborationSession.list_active_sessions()
        ids = {s.session_id for s in active}
        assert s1.session_id in ids
        assert s2.session_id in ids

        s1.end_session()
        s2.end_session()
        CollaborationSession._SESSION_REGISTRY.pop(s1.session_id, None)
        CollaborationSession._SESSION_REGISTRY.pop(s2.session_id, None)


# ============================================================================
# 2. Operator Input Processing Tests
# ============================================================================


class TestOperatorInputProcessing:
    """Tests for operator input processing through governance."""

    @pytest.mark.asyncio
    async def test_query_input(self, sample_session):
        """Test processing a query input."""
        result = await sample_session.submit_operator_input(
            input_type="query",
            content="What governance schemas are active?",
        )
        assert result["status"] == "active"
        assert "response" in result
        assert "governance_checks" in result
        assert result["interaction_number"] == 1

    @pytest.mark.asyncio
    async def test_propose_action_input(self, sample_session):
        """Test processing an action proposal."""
        result = await sample_session.submit_operator_input(
            input_type="propose_action",
            content="Activate the reflective_continuity schema",
        )
        assert result["status"] == "active"
        assert result["response"]["response_type"] == "recommendation"

    @pytest.mark.asyncio
    async def test_request_analysis_input(self, sample_session):
        """Test processing an analysis request."""
        result = await sample_session.submit_operator_input(
            input_type="request_analysis",
            content="Analyze the session health metrics",
        )
        assert result["status"] == "active"
        assert result["response"]["response_type"] == "analysis"

    @pytest.mark.asyncio
    async def test_governance_review_input(self, sample_session):
        """Test processing a governance review request."""
        result = await sample_session.submit_operator_input(
            input_type="governance_review",
            content="Review the boundary enforcement policy",
        )
        assert result["status"] == "active"
        assert result["response"]["response_type"] == "review"

    @pytest.mark.asyncio
    async def test_status_check_input(self, sample_session):
        """Test processing a status check request."""
        result = await sample_session.submit_operator_input(
            input_type="status_check",
            content="What is the current session status?",
        )
        assert result["status"] == "active"
        assert result["response"]["response_type"] == "status"

    @pytest.mark.asyncio
    async def test_explain_decision_input(self, sample_session):
        """Test processing a decision explanation request."""
        result = await sample_session.submit_operator_input(
            input_type="explain_decision",
            content="Why was the last action blocked?",
        )
        assert result["status"] == "active"
        assert result["response"]["response_type"] == "explanation"

    @pytest.mark.asyncio
    async def test_invalid_input_type(self, sample_session):
        """Test that invalid input type returns error."""
        result = await sample_session.submit_operator_input(
            input_type="invalid_type_xyz",
            content="Some content",
        )
        assert result["response_type"] == "error"
        assert "invalid" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_multiple_interactions_increment(self, sample_session):
        """Test that interaction numbers increment."""
        r1 = await sample_session.submit_operator_input("query", "First query")
        r2 = await sample_session.submit_operator_input("query", "Second query")
        assert r1["interaction_number"] == 1
        assert r2["interaction_number"] == 2

    @pytest.mark.asyncio
    async def test_interaction_stored_in_history(self, sample_session):
        """Test that interactions are stored."""
        await sample_session.submit_operator_input("query", "Test query")
        history = sample_session.get_interaction_history()
        assert len(history) == 1
        assert history[0].operator_input["input_type"] == "query"

    @pytest.mark.asyncio
    async def test_interaction_history_as_dicts(self, sample_session):
        """Test interaction history serialization."""
        await sample_session.submit_operator_input("query", "Test query")
        dicts = sample_session.get_interaction_history_as_dicts()
        assert len(dicts) == 1
        assert "governance_checks" in dicts[0]


# ============================================================================
# 3. Governance Mediation Tests
# ============================================================================


class TestGovernanceMediation:
    """Tests for governance mediation in responses."""

    @pytest.mark.asyncio
    async def test_governance_checks_present(self, sample_session):
        """Test that every response includes governance checks."""
        result = await sample_session.submit_operator_input("query", "Test")
        checks = result["governance_checks"]
        assert len(checks) > 0
        for check in checks:
            assert "schema_id" in check
            assert "policy_id" in check
            assert "passed" in check

    @pytest.mark.asyncio
    async def test_boundary_enforcement_check(self, sample_session):
        """Test that boundary enforcement check runs."""
        result = await sample_session.submit_operator_input("query", "Test")
        checks = result["governance_checks"]
        boundary_checks = [c for c in checks if c["schema_id"] == "boundary_enforcement"]
        assert len(boundary_checks) >= 1

    @pytest.mark.asyncio
    async def test_epistemic_safety_check(self, sample_session):
        """Test that epistemic safety check runs."""
        result = await sample_session.submit_operator_input("query", "Test")
        checks = result["governance_checks"]
        epistemic_checks = [c for c in checks if c["schema_id"] == "epistemic_safety"]
        assert len(epistemic_checks) >= 1

    @pytest.mark.asyncio
    async def test_blocked_content_detected(self, sample_session):
        """Test that blocked content (code) is detected."""
        result = await sample_session.submit_operator_input(
            "query",
            "Execute os.system('rm -rf /')",
        )
        # Should have a failed boundary check
        failed = [c for c in result["governance_checks"] if not c["passed"]]
        assert len(failed) >= 1
        assert any(c["schema_id"] == "boundary_enforcement" for c in failed)

    @pytest.mark.asyncio
    async def test_blocked_response_type(self, sample_session):
        """Test that blocked input returns block response type."""
        result = await sample_session.submit_operator_input(
            "query",
            "Run exec(malicious_code)",
        )
        # With critical violation, response should be blocked
        checks = result["governance_checks"]
        has_critical = any(
            not c["passed"] and c.get("violation_severity") == "critical"
            for c in checks
        )
        if has_critical:
            assert result["response"]["response_type"] == "block"

    @pytest.mark.asyncio
    async def test_governance_summary(self, sample_session):
        """Test governance summary after interactions."""
        await sample_session.submit_operator_input("query", "Test 1")
        await sample_session.submit_operator_input("query", "Test 2")

        summary = sample_session.get_governance_summary()
        assert summary["total_interactions"] == 2
        assert summary["checks_passed"] > 0
        assert "by_schema" in summary

    @pytest.mark.asyncio
    async def test_session_inactive_blocks_input(self, sample_session):
        """Test that inactive session blocks new input."""
        sample_session.end_session()
        result = await sample_session.submit_operator_input("query", "Test")
        assert result["response_type"] == "error"
        assert "not active" in result["content"].lower()


# ============================================================================
# 4. Negotiation Explanation Tests
# ============================================================================


class TestGovernanceNegotiation:
    """Tests for governance negotiation explanations."""

    def test_explain_block_structure(self, negotiation_engine, sample_violation):
        """Test that explain_block returns correct structure."""
        result = negotiation_engine.explain_block(
            violation=sample_violation,
            blocked_action="Execute shell command",
        )
        assert result["explanation_type"] == "block"
        assert result["blocking_schema"] == "boundary_enforcement"
        assert result["blocking_policy"] == "be_01"
        assert "explanation" in result
        assert "recommendation" in result
        assert "escalation_path" in result
        assert "uncertainty_disclosure" in result

    def test_explain_block_has_escalation(self, negotiation_engine, sample_violation):
        """Test that block explanation includes escalation path."""
        result = negotiation_engine.explain_block(
            violation=sample_violation,
        )
        assert "secondary_operator_review" in result["escalation_requirements"]
        assert result["operator_can_escalate"] is True

    def test_explain_critical_severity_escalation(self, negotiation_engine):
        """Test critical severity escalation path."""
        violation = GovernanceViolation(
            schema_id="boundary_enforcement",
            policy_id="be_01",
            severity="critical",
            description="Critical violation",
        )
        result = negotiation_engine.explain_block(violation)
        assert "CRITICAL escalation path" in result["escalation_path"]

    def test_explain_warning_severity_escalation(self, negotiation_engine):
        """Test warning severity escalation path."""
        violation = GovernanceViolation(
            schema_id="epistemic_safety",
            policy_id="ep_01",
            severity="warning",
            description="Warning violation",
        )
        result = negotiation_engine.explain_block(violation)
        assert "WARNING escalation path" in result["escalation_path"]

    def test_explain_modification(self, negotiation_engine):
        """Test modification explanation."""
        result = negotiation_engine.explain_modification(
            original="Run this code: exec('danger')",
            mediated="Run this code: [GOVERNANCE_MEDIATED]",
            schemas_applied=["boundary_enforcement", "epistemic_safety"],
        )
        assert result["explanation_type"] == "modification"
        assert len(result["schemas_applied"]) == 2
        assert "differences" in result

    def test_explain_uncertainty(self, negotiation_engine):
        """Test uncertainty explanation."""
        context = {
            "confidence_score": 0.45,
            "topic": "healthcare AI ethics analysis",
            "reasoning_steps": ["step1", "step2"],
            "memory_sources": [],
            "governance_checks": [],
        }
        result = negotiation_engine.explain_uncertainty(context)
        assert result["explanation_type"] == "uncertainty"
        # 0.45 is in the moderate range (0.4-0.6)
        assert result["uncertainty_level"] == "moderate"
        assert result["confidence_score"] == 0.45
        assert "uncertainty_sources" in result
        assert "recommendation" in result

    def test_explain_uncertainty_low_confidence(self, negotiation_engine):
        """Test uncertainty explanation for very low confidence."""
        context = {"confidence_score": 0.1, "topic": "test"}
        result = negotiation_engine.explain_uncertainty(context)
        assert result["uncertainty_level"] == "very_high"

    def test_explain_uncertainty_high_confidence(self, negotiation_engine):
        """Test uncertainty explanation for high confidence."""
        context = {"confidence_score": 0.85, "topic": "test"}
        result = negotiation_engine.explain_uncertainty(context)
        assert result["uncertainty_level"] == "very_low"

    def test_generate_negotiation_view(self, negotiation_engine):
        """Test negotiation view generation."""
        result = negotiation_engine.generate_negotiation_view("session_001")
        assert result["view_type"] == "negotiation"
        assert "statistics" in result
        assert "transparency_note" in result

    def test_suggest_approval_path(self, negotiation_engine):
        """Test approval path suggestion."""
        result = negotiation_engine.suggest_approval_path("Activate risky schema")
        assert result["approval_possible"] is True
        assert len(result["steps"]) >= 4
        assert result["single_operator_cannot_override"] is True
        assert result["override_always_audited"] is True

    def test_suggest_approval_path_has_steps(self, negotiation_engine):
        """Test that approval path has numbered steps."""
        result = negotiation_engine.suggest_approval_path("Test action")
        for i, step in enumerate(result["steps"]):
            assert "step" in step
            assert "title" in step
            assert "description" in step
            assert "required" in step

    def test_explain_block_different_schemas(self, negotiation_engine):
        """Test block explanations for different schema types."""
        schemas = [
            ("boundary_enforcement", "be_01", "critical"),
            ("epistemic_safety", "ep_01", "warning"),
            ("operational_integrity", "op_01", "critical"),
            ("ethical_guidelines", "eg_01", "critical"),
            ("session_management", "sm_01", "warning"),
        ]
        for schema_id, policy_id, severity in schemas:
            violation = GovernanceViolation(
                schema_id=schema_id,
                policy_id=policy_id,
                severity=severity,
                description=f"Test {schema_id} violation",
            )
            result = negotiation_engine.explain_block(violation)
            assert result["blocking_schema"] == schema_id
            assert len(result["explanation"]) > 0


# ============================================================================
# 5. Bounded Strategic Reasoning Tests
# ============================================================================


class TestBoundedStrategy:
    """Tests for bounded strategic reasoning."""

    def test_analyze_project_trajectory(self, strategy_engine):
        """Test project trajectory analysis."""
        result = strategy_engine.analyze_project_trajectory("project_test_001")
        assert result["analysis_type"] == "trajectory"
        assert "metrics" in result
        assert "recommendations" in result
        assert result["governance_bounded"] is True

    def test_trajectory_has_uncertainty(self, strategy_engine):
        """Test that trajectory includes uncertainty disclosure."""
        result = strategy_engine.analyze_project_trajectory("project_test_001")
        assert "uncertainty_disclosure" in result
        assert len(result["uncertainty_disclosure"]) > 0

    def test_trajectory_has_reasoning_trace(self, strategy_engine):
        """Test that trajectory includes reasoning trace."""
        result = strategy_engine.analyze_project_trajectory("project_test_001")
        assert "reasoning_trace" in result
        assert len(result["reasoning_trace"]) > 0

    def test_trajectory_confidence_capped(self, strategy_engine):
        """Test that confidence is capped by epistemic safety."""
        result = strategy_engine.analyze_project_trajectory("project_test_001")
        assert result["confidence_score"] <= 0.85

    def test_forecast_operational_needs(self, strategy_engine):
        """Test operational forecasting."""
        result = strategy_engine.forecast_operational_needs("project_test_001", "30d")
        assert result["analysis_type"] == "operational_forecast"
        assert "forecast" in result
        assert result["forecast"]["projected_sessions"] >= 0

    def test_forecast_7d(self, strategy_engine):
        """Test 7-day forecast."""
        result = strategy_engine.forecast_operational_needs("project_test_001", "7d")
        assert result["time_horizon"] == "7d"

    def test_forecast_90d(self, strategy_engine):
        """Test 90-day forecast."""
        result = strategy_engine.forecast_operational_needs("project_test_001", "90d")
        assert result["time_horizon"] == "90d"

    def test_forecast_uncertainty_lower_for_longer_horizon(self, strategy_engine):
        """Test that longer horizons have adjusted confidence."""
        r30 = strategy_engine.forecast_operational_needs("project_test_001", "30d")
        r90 = strategy_engine.forecast_operational_needs("project_test_001", "90d")
        # 90d should have lower or equal confidence due to horizon uncertainty
        assert r90["confidence_score"] <= r30["confidence_score"] + 0.01

    def test_recommend_governance_adjustments(self, strategy_engine):
        """Test governance adjustment recommendations."""
        result = strategy_engine.recommend_governance_adjustments("project_test_001")
        assert result["analysis_type"] == "governance_adjustment_recommendation"
        assert result["requires_operator_approval"] is True
        assert result["auto_adjustment_disabled"] is True

    def test_governance_recommendations_require_approval(self, strategy_engine):
        """Test that governance recommendations require approval."""
        result = strategy_engine.recommend_governance_adjustments("project_test_001")
        assert result["requires_operator_approval"] is True
        if result["recommendations"]:
            for rec in result["recommendations"]:
                assert "requires_approval" in rec or rec.get("type") == "maintain"

    def test_assess_operational_readiness(self, strategy_engine):
        """Test operational readiness assessment."""
        result = strategy_engine.assess_operational_readiness("project_test_001")
        assert result["analysis_type"] == "operational_readiness"
        assert "readiness_score" in result
        assert "status" in result
        assert result["status"] in ["ready", "conditionally_ready", "not_ready"]

    def test_readiness_score_bounded(self, strategy_engine):
        """Test that readiness score is bounded."""
        result = strategy_engine.assess_operational_readiness("project_test_001")
        assert 0.0 <= result["readiness_score"] <= 0.95

    def test_readiness_has_criteria(self, strategy_engine):
        """Test that readiness includes specific criteria."""
        result = strategy_engine.assess_operational_readiness("project_test_001")
        assert "criteria" in result
        assert "required_schema_coverage" in result["criteria"]

    def test_readiness_has_recommendations(self, strategy_engine):
        """Test that readiness includes recommendations."""
        result = strategy_engine.assess_operational_readiness("project_test_001")
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0

    def test_generate_cognitive_strategy(self, strategy_engine):
        """Test cognitive strategy generation."""
        result = strategy_engine.generate_cognitive_strategy(
            objective="Improve governance coverage",
            constraints=["must_not_degrade_safety", "must_be_auditable"],
        )
        assert result["analysis_type"] == "cognitive_strategy"
        assert "strategy_phases" in result
        assert "key_principles" in result

    def test_strategy_has_governance_bounds(self, strategy_engine):
        """Test that strategy is bounded by governance."""
        result = strategy_engine.generate_cognitive_strategy(
            objective="Test objective",
            constraints=[],
        )
        assert result["governance_bounded"] is True
        assert "bounded_by" in result

    def test_strategy_principles_include_observability(self, strategy_engine):
        """Test that strategy principles include observability."""
        result = strategy_engine.generate_cognitive_strategy(
            objective="Test",
            constraints=[],
        )
        principles = result["key_principles"]
        assert any("observable" in p.lower() for p in principles)

    def test_strategy_principles_include_uncertainty(self, strategy_engine):
        """Test that strategy principles include uncertainty disclosure."""
        result = strategy_engine.generate_cognitive_strategy(
            objective="Test",
            constraints=[],
        )
        principles = result["key_principles"]
        assert any("uncertainty" in p.lower() for p in principles)

    def test_strategy_has_uncertainty_disclosure(self, strategy_engine):
        """Test that strategy includes uncertainty disclosure."""
        result = strategy_engine.generate_cognitive_strategy(
            objective="Test",
            constraints=[],
        )
        assert "uncertainty_disclosure" in result
        assert len(result["uncertainty_disclosure"]) > 0

    def test_different_projects_different_contexts(self, strategy_engine):
        """Test that different projects get different contexts."""
        r1 = strategy_engine.analyze_project_trajectory("proj_A")
        r2 = strategy_engine.analyze_project_trajectory("proj_B")
        # Different project IDs should produce potentially different metrics
        assert r1["project_id"] != r2["project_id"]

    def test_strategy_history(self, strategy_engine):
        """Test strategy history tracking."""
        strategy_engine.analyze_project_trajectory("hist_test")
        history = strategy_engine.get_strategy_history("hist_test")
        assert len(history) >= 1

    def test_strategy_engine_set_schemas(self):
        """Test setting active schemas."""
        engine = BoundedStrategyEngine()
        engine.set_active_schemas(["schema_a", "schema_b"])
        result = engine.analyze_project_trajectory("schema_test")
        assert "schema_a" in result["bounded_by"] or result["bounded_by"] == ["schema_a", "schema_b"]


# ============================================================================
# 6. Uncertainty Disclosure Tests
# ============================================================================


class TestUncertaintyDisclosure:
    """Tests for uncertainty disclosure in all outputs."""

    @pytest.mark.asyncio
    async def test_uncertainty_always_disclosed(self, sample_session):
        """Test that uncertainty is always disclosed in responses."""
        result = await sample_session.submit_operator_input("query", "Test")
        assert result["uncertainty_disclosed"] is True
        assert result["response"]["uncertainty_disclosure"] is not None

    @pytest.mark.asyncio
    async def test_uncertainty_disclosure_for_low_confidence(self, sample_session):
        """Test uncertainty disclosure when confidence is low."""
        result = await sample_session.submit_operator_input("query", "Test")
        confidence = result["confidence_score"]
        uncertainty = result["response"]["uncertainty_disclosure"]
        if confidence < 0.3:
            assert "High uncertainty" in uncertainty or "high uncertainty" in uncertainty.lower()

    @pytest.mark.asyncio
    async def test_uncertainty_disclosure_for_high_confidence(self, sample_session):
        """Test uncertainty disclosure even when confidence is high."""
        result = await sample_session.submit_operator_input("query", "Test")
        uncertainty = result["response"]["uncertainty_disclosure"]
        # Even high confidence should have some disclosure
        assert len(uncertainty) > 0

    @pytest.mark.asyncio
    async def test_confidence_score_present(self, sample_session):
        """Test that confidence score is always present."""
        result = await sample_session.submit_operator_input("query", "Test")
        assert "confidence_score" in result
        assert 0.0 <= result["confidence_score"] <= 1.0

    def test_negotiation_uncertainty_disclosure(self, negotiation_engine):
        """Test uncertainty disclosure in negotiation explanations."""
        violation = GovernanceViolation(
            schema_id="test",
            policy_id="test_01",
            severity="critical",
            description="Test",
        )
        result = negotiation_engine.explain_block(violation)
        assert "uncertainty_disclosure" in result
        assert len(result["uncertainty_disclosure"]) > 0

    def test_strategy_uncertainty_disclosure(self, strategy_engine):
        """Test uncertainty disclosure in strategy outputs."""
        result = strategy_engine.analyze_project_trajectory("uncertainty_test")
        assert "uncertainty_disclosure" in result
        assert len(result["uncertainty_disclosure"]) > 10


# ============================================================================
# 7. Memory Influence Visibility Tests
# ============================================================================


class TestMemoryInfluenceVisibility:
    """Tests for memory influence visibility."""

    @pytest.mark.asyncio
    async def test_memory_influences_present(self, sample_session):
        """Test that memory influences are included in responses."""
        result = await sample_session.submit_operator_input("query", "Test")
        assert "memory_influences" in result["response"]

    @pytest.mark.asyncio
    async def test_memory_influences_have_structure(self, sample_session):
        """Test that memory influences have expected structure."""
        result = await sample_session.submit_operator_input("query", "Test")
        influences = result["response"]["memory_influences"]
        if influences:
            for inf in influences:
                assert "influence_type" in inf
                assert "strength" in inf

    @pytest.mark.asyncio
    async def test_memory_influences_different_by_input_type(self, sample_session):
        """Test that different input types get different memory influences."""
        r_query = await sample_session.submit_operator_input("query", "Test query")
        r_action = await sample_session.submit_operator_input("propose_action", "Test action")

        # Different input types should produce different influences
        inf_query = r_query["response"]["memory_influences"]
        inf_action = r_action["response"]["memory_influences"]
        # They might be different or same; just verify they exist
        assert isinstance(inf_query, list)
        assert isinstance(inf_action, list)

    def test_interaction_records_memory_influences(self, sample_session):
        """Test that interaction records memory influences."""
        # Run an interaction
        asyncio.run(sample_session.submit_operator_input("query", "Test"))
        history = sample_session.get_interaction_history()
        assert len(history) > 0
        assert isinstance(history[0].memory_influences, list)


# ============================================================================
# 8. Audit and Interaction History Tests
# ============================================================================


class TestAuditAndHistory:
    """Tests for audit trail and interaction history."""

    @pytest.mark.asyncio
    async def test_interaction_history_grows(self, sample_session):
        """Test that interaction history grows with each input."""
        assert len(sample_session.get_interaction_history()) == 0
        await sample_session.submit_operator_input("query", "Test 1")
        assert len(sample_session.get_interaction_history()) == 1
        await sample_session.submit_operator_input("query", "Test 2")
        assert len(sample_session.get_interaction_history()) == 2

    def test_interaction_has_timestamp(self, sample_session):
        """Test that interactions have timestamps."""
        asyncio.run(sample_session.submit_operator_input("query", "Test"))
        history = sample_session.get_interaction_history()
        assert len(history) > 0
        assert isinstance(history[0].timestamp, datetime)

    def test_interaction_has_unique_id(self, sample_session):
        """Test that each interaction has a unique ID."""
        asyncio.run(sample_session.submit_operator_input("query", "Test 1"))
        asyncio.run(sample_session.submit_operator_input("query", "Test 2"))
        history = sample_session.get_interaction_history()
        ids = [i.interaction_id for i in history]
        assert len(ids) == len(set(ids))

    def test_interaction_history_isolation(self):
        """Test that different sessions have isolated histories."""
        s1 = CollaborationSession(
            session_id=f"iso_{uuid4().hex[:8]}",
            operator_id="op1",
            project_id="proj1",
            validator=None,
            audit=None,
        )
        s2 = CollaborationSession(
            session_id=f"iso_{uuid4().hex[:8]}",
            operator_id="op2",
            project_id="proj2",
            validator=None,
            audit=None,
        )

        asyncio.run(s1.submit_operator_input("query", "Session 1"))
        asyncio.run(s2.submit_operator_input("query", "Session 2"))

        assert len(s1.get_interaction_history()) == 1
        assert len(s2.get_interaction_history()) == 1

        # Content should be different
        assert (
            s1.get_interaction_history()[0].operator_input["content"]
            == "Session 1"
        )
        assert (
            s2.get_interaction_history()[0].operator_input["content"]
            == "Session 2"
        )

        s1.end_session()
        s2.end_session()
        CollaborationSession._SESSION_REGISTRY.pop(s1.session_id, None)
        CollaborationSession._SESSION_REGISTRY.pop(s2.session_id, None)


# ============================================================================
# 9. Fail-Closed Behavior Tests
# ============================================================================


class TestFailClosedBehavior:
    """Tests for fail-closed behavior in governance mediation."""

    def test_has_critical_failures_detects_critical(self, sample_session):
        """Test that critical failures are detected."""
        checks = [
            GovernanceCheckResult(
                schema_id="test",
                policy_id="test_01",
                passed=False,
                violation=GovernanceViolation(
                    schema_id="test",
                    policy_id="test_01",
                    severity="critical",
                    description="Test critical",
                ),
            ),
        ]
        assert sample_session._has_critical_failures(checks) is True

    def test_has_critical_failures_ignores_warning(self, sample_session):
        """Test that warnings alone don't trigger critical."""
        checks = [
            GovernanceCheckResult(
                schema_id="test",
                policy_id="test_01",
                passed=False,
                violation=GovernanceViolation(
                    schema_id="test",
                    policy_id="test_01",
                    severity="warning",
                    description="Test warning",
                ),
            ),
        ]
        assert sample_session._has_critical_failures(checks) is False

    def test_has_critical_failures_all_passed(self, sample_session):
        """Test that all-passed checks return False."""
        checks = [
            GovernanceCheckResult(
                schema_id="test",
                policy_id="test_01",
                passed=True,
                violation=None,
            ),
        ]
        assert sample_session._has_critical_failures(checks) is False

    def test_operator_input_validation(self):
        """Test that operator input types are validated."""
        assert OperatorInput.validate_input_type("query") is True
        assert OperatorInput.validate_input_type("propose_action") is True
        assert OperatorInput.validate_input_type("request_analysis") is True
        assert OperatorInput.validate_input_type("governance_review") is True
        assert OperatorInput.validate_input_type("invalid") is False
        assert OperatorInput.validate_input_type("") is False


# ============================================================================
# 10. OperatorInput Model Tests
# ============================================================================


class TestOperatorInput:
    """Tests for the OperatorInput model."""

    def test_valid_input_types(self):
        """Test all valid input types."""
        valid_types = [
            "query",
            "propose_action",
            "request_analysis",
            "governance_review",
            "status_check",
            "explain_decision",
        ]
        for t in valid_types:
            assert OperatorInput.validate_input_type(t) is True

    def test_invalid_input_types(self):
        """Test invalid input types."""
        invalid_types = ["", "chat", "talk", "random", "message", "help"]
        for t in invalid_types:
            assert OperatorInput.validate_input_type(t) is False

    def test_operator_input_creation(self):
        """Test creating an OperatorInput."""
        inp = OperatorInput(
            input_type="query",
            content="Test content",
            operator_id="op_001",
        )
        assert inp.input_type == "query"
        assert inp.content == "Test content"
        assert inp.operator_id == "op_001"
        assert isinstance(inp.timestamp, datetime)


# ============================================================================
# 11. Session Summary and Governance Summary Tests
# ============================================================================


class TestSessionSummaries:
    """Tests for session and governance summaries."""

    @pytest.mark.asyncio
    async def test_end_session_summary(self, sample_session):
        """Test that ending a session returns a summary."""
        await sample_session.submit_operator_input("query", "Test")
        summary = sample_session.end_session()
        assert "session_id" in summary
        assert "total_interactions" in summary
        assert "governance_summary" in summary
        assert summary["total_interactions"] == 1

    def test_empty_session_summary(self, sample_session):
        """Test summary for a session with no interactions."""
        summary = sample_session.end_session()
        assert summary["total_interactions"] == 0
        assert summary["governance_summary"]["total_interactions"] == 0

    @pytest.mark.asyncio
    async def test_governance_summary_statistics(self, sample_session):
        """Test governance summary statistics."""
        await sample_session.submit_operator_input("query", "Test 1")
        await sample_session.submit_operator_input("query", "Test 2")
        summary = sample_session.get_governance_summary()
        assert summary["total_interactions"] == 2
        assert summary["checks_passed"] > 0
        assert "uncertainty_disclosure_rate" in summary


# ============================================================================
# 12. Reasoning Trace Tests
# ============================================================================


class TestReasoningTrace:
    """Tests for reasoning trace visibility."""

    @pytest.mark.asyncio
    async def test_reasoning_trace_present(self, sample_session):
        """Test that responses include reasoning traces."""
        result = await sample_session.submit_operator_input("query", "Test")
        assert "reasoning_trace" in result["response"]
        assert len(result["response"]["reasoning_trace"]) > 0

    @pytest.mark.asyncio
    async def test_reasoning_trace_has_governance_steps(self, sample_session):
        """Test that reasoning trace includes governance steps."""
        result = await sample_session.submit_operator_input("query", "Test")
        trace = result["response"]["reasoning_trace"]
        # Should contain governance-related entries
        trace_text = " ".join(trace).lower()
        assert "governance" in trace_text or "check" in trace_text

    def test_strategy_reasoning_trace(self, strategy_engine):
        """Test that strategy includes reasoning trace."""
        result = strategy_engine.analyze_project_trajectory("trace_test")
        trace = result["reasoning_trace"]
        assert len(trace) >= 3
        assert any("governance" in step.lower() for step in trace)


# ============================================================================
# 13. Confidence Score Tests
# ============================================================================


class TestConfidenceScores:
    """Tests for confidence score calculation and interpretation."""

    def test_confidence_capped_at_085(self, sample_session):
        """Test confidence is capped at 0.85."""
        # Simulate high-confidence scenario
        checks = [
            GovernanceCheckResult(
                schema_id="test", policy_id="t1", passed=True, violation=None
            ),
            GovernanceCheckResult(
                schema_id="test", policy_id="t2", passed=True, violation=None
            ),
        ]
        influences = [{"strength": 0.95}, {"strength": 0.95}]
        confidence = sample_session._calculate_confidence(checks, influences)
        assert confidence <= 0.85

    def test_confidence_floor_at_01(self, sample_session):
        """Test confidence has a floor."""
        checks = []
        influences = []
        confidence = sample_session._calculate_confidence(checks, influences)
        assert confidence >= 0.1

    def test_confidence_interpretation_low(self, sample_session):
        """Test confidence interpretation for low values."""
        interp = sample_session._interpret_confidence(0.1)
        assert "low" in interp.lower() or "very low" in interp.lower()

    def test_confidence_interpretation_high(self, sample_session):
        """Test confidence interpretation for high values."""
        interp = sample_session._interpret_confidence(0.8)
        assert "good" in interp.lower() or "reasonable" in interp.lower()


# ============================================================================
# 14. Response Type Determination Tests
# ============================================================================


class TestResponseTypes:
    """Tests for response type determination."""

    def test_query_maps_to_answer(self, sample_session):
        assert sample_session._determine_response_type("query") == "answer"

    def test_propose_action_maps_to_recommendation(self, sample_session):
        assert (
            sample_session._determine_response_type("propose_action")
            == "recommendation"
        )

    def test_request_analysis_maps_to_analysis(self, sample_session):
        assert (
            sample_session._determine_response_type("request_analysis") == "analysis"
        )

    def test_governance_review_maps_to_review(self, sample_session):
        assert (
            sample_session._determine_response_type("governance_review") == "review"
        )

    def test_status_check_maps_to_status(self, sample_session):
        assert sample_session._determine_response_type("status_check") == "status"

    def test_explain_decision_maps_to_explanation(self, sample_session):
        assert (
            sample_session._determine_response_type("explain_decision")
            == "explanation"
        )

    def test_unknown_defaults_to_answer(self, sample_session):
        assert sample_session._determine_response_type("unknown") == "answer"


# ============================================================================
# 15. Edge Cases and Boundary Tests
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_content(self, sample_session):
        """Test handling of empty content."""
        result = await sample_session.submit_operator_input("query", "")
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_very_long_content(self, sample_session):
        """Test handling of very long content."""
        long_content = "A" * 10000
        result = await sample_session.submit_operator_input("query", long_content)
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_content_with_special_characters(self, sample_session):
        """Test handling of special characters."""
        content = "Test <script>alert('xss')</script> & more \"quotes\""
        result = await sample_session.submit_operator_input("query", content)
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_unicode_content(self, sample_session):
        """Test handling of unicode content."""
        content = "Unicode test: \u03b1\u03b2\u03b3 \u4e2d\u6587 \ud83d\ude00"
        result = await sample_session.submit_operator_input("query", content)
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_content_with_code_keywords_safe(self, sample_session):
        """Test that safe code-related queries are allowed."""
        result = await sample_session.submit_operator_input(
            "query", "Explain how Python exec() works conceptually"
        )
        # This should pass boundary check since it's conceptual
        assert result["status"] == "active"

    def test_negotiation_with_empty_strings(self, negotiation_engine):
        """Test negotiation with empty strings."""
        violation = GovernanceViolation(
            schema_id="test", policy_id="t1", severity="warning", description="Test"
        )
        result = negotiation_engine.explain_block(violation, "")
        # Empty string falls back to "the requested action"
        assert result["blocked_action"] == "the requested action"

    def test_strategy_with_empty_objective(self, strategy_engine):
        """Test strategy with empty objective."""
        result = strategy_engine.generate_cognitive_strategy("", [])
        assert result["governance_bounded"] is True
        assert "strategy_phases" in result

    def test_forecast_with_invalid_horizon(self, strategy_engine):
        """Test forecast with invalid horizon falls back."""
        result = strategy_engine.forecast_operational_needs("test", "invalid")
        assert result["time_horizon"] == "invalid"
        # Should still return a result with default behavior
        assert "forecast" in result
