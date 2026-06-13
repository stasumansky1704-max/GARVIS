"""Comprehensive tests for all GARVIS Pydantic models.

Tests cover creation, validation, serialization, and edge cases for
every model in the governance, cognition, memory, audit, and inference
domains.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from models.governance import (
    GovernanceCheckResult,
    GovernanceConstraint,
    GovernancePolicy,
    GovernanceSchema,
    GovernanceViolation,
    ViolationResponse,
)
from models.cognition import ForbiddenStatePattern, OperationalState, StateTransition
from models.memory import EpisodicMemory, MemoryInfluence, ProvenanceRecord
from models.audit import AuditEvent, CognitionTrace
from models.inference import InferenceRequest, GovernedResponse, PromptMediationResult


# ============================================================================
# Governance Models
# ============================================================================

class TestGovernanceSchema:
    """Tests for the GovernanceSchema model."""

    def test_creation(self) -> None:
        """GovernanceSchema can be created with all required fields."""
        schema = GovernanceSchema(
            schema_id="test_schema",
            name="Test Schema",
            version="1.0.0",
            category="epistemic",
            description="A test schema",
            policies=[],
            constraints=[],
        )
        assert schema.schema_id == "test_schema"
        assert schema.name == "Test Schema"
        assert schema.version == "1.0.0"
        assert schema.category == "epistemic"
        assert schema.fail_closed is True  # default

    def test_validation_missing_required_field(self) -> None:
        """GovernanceSchema rejects creation when required fields are missing."""
        with pytest.raises(ValidationError):
            GovernanceSchema(
                schema_id="test",
                name="Test",
                # version is required — missing
                category="epistemic",
                description="desc",
                policies=[],
                constraints=[],
            )

    def test_serialization_roundtrip(self, sample_governance_schema: GovernanceSchema) -> None:
        """GovernanceSchema serializes and deserializes correctly."""
        dumped = sample_governance_schema.model_dump()
        restored = GovernanceSchema(**dumped)
        assert restored.schema_id == sample_governance_schema.schema_id
        assert len(restored.policies) == len(sample_governance_schema.policies)
        assert len(restored.constraints) == len(sample_governance_schema.constraints)

    def test_get_policies_by_severity(self, sample_governance_schema: GovernanceSchema) -> None:
        """get_policies_by_severity returns only matching policies."""
        critical = sample_governance_schema.get_policies_by_severity("critical")
        assert len(critical) == 1
        assert critical[0].policy_id == "uncertainty_quantification_required"

        warning = sample_governance_schema.get_policies_by_severity("warning")
        assert len(warning) == 1
        assert warning[0].policy_id == "uncertainty_honesty_threshold"

        empty = sample_governance_schema.get_policies_by_severity("info")
        assert len(empty) == 0

    def test_get_constraints_by_scope(self, sample_governance_schema: GovernanceSchema) -> None:
        """get_constraints_by_scope returns only matching constraints."""
        inference = sample_governance_schema.get_constraints_by_scope("inference")
        assert len(inference) == 1
        assert inference[0].constraint_id == "no_false_certainty"

        empty = sample_governance_schema.get_constraints_by_scope("memory")
        assert len(empty) == 0


class TestGovernancePolicy:
    """Tests for the GovernancePolicy model."""

    def test_creation(self) -> None:
        """GovernancePolicy can be created with all required fields."""
        policy = GovernancePolicy(
            policy_id="test_policy",
            description="A test policy",
            rule_type="requirement",
            condition="always true",
            evaluation_logic="return True",
            severity="critical",
            auto_remediation=False,
        )
        assert policy.policy_id == "test_policy"
        assert policy.severity == "critical"
        assert policy.auto_remediation is False

    def test_severity_levels(self) -> None:
        """GovernancePolicy accepts all valid severity levels."""
        for severity in ("critical", "warning", "info"):
            policy = GovernancePolicy(
                policy_id=f"test_{severity}",
                description="desc",
                rule_type="requirement",
                condition="c",
                evaluation_logic="e",
                severity=severity,
            )
            assert policy.severity == severity


class TestGovernanceConstraint:
    """Tests for the GovernanceConstraint model."""

    def test_creation(self) -> None:
        """GovernanceConstraint can be created with all required fields."""
        constraint = GovernanceConstraint(
            constraint_id="test_constraint",
            description="A test constraint",
            scope="global",
            enforcement="hard_stop",
        )
        assert constraint.constraint_id == "test_constraint"
        assert constraint.scope == "global"
        assert constraint.enforcement == "hard_stop"

    def test_enforcement_types(self) -> None:
        """GovernanceConstraint accepts all valid enforcement types."""
        for enforcement in ("hard_stop", "log_only", "degrade"):
            constraint = GovernanceConstraint(
                constraint_id=f"test_{enforcement}",
                description="desc",
                scope="inference",
                enforcement=enforcement,
            )
            assert constraint.enforcement == enforcement


class TestGovernanceViolation:
    """Tests for the GovernanceViolation model."""

    def test_creation_with_uuid_generation(self) -> None:
        """GovernanceViolation auto-generates a UUID and timestamp."""
        violation = GovernanceViolation(
            schema_id="test_schema",
            policy_id="test_policy",
            severity="critical",
            description="Something went wrong",
        )
        assert isinstance(violation.violation_id, UUID)
        assert isinstance(violation.timestamp, datetime)
        assert violation.resolution is None

    def test_creation_with_explicit_values(self) -> None:
        """GovernanceViolation accepts explicit UUID and timestamp."""
        vid = uuid4()
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        violation = GovernanceViolation(
            violation_id=vid,
            schema_id="s",
            policy_id="p",
            severity="warning",
            description="desc",
            timestamp=ts,
            resolution="resolved",
        )
        assert violation.violation_id == vid
        assert violation.timestamp == ts
        assert violation.resolution == "resolved"

    def test_context_defaults_to_empty_dict(self) -> None:
        """GovernanceViolation context defaults to empty dict."""
        violation = GovernanceViolation(
            schema_id="s",
            policy_id="p",
            severity="info",
            description="desc",
        )
        assert violation.context == {}


class TestGovernanceCheckResult:
    """Tests for the GovernanceCheckResult model."""

    def test_passed_without_violation(self) -> None:
        """A passing check has no violation."""
        result = GovernanceCheckResult(
            schema_id="s",
            policy_id="p",
            passed=True,
        )
        assert result.passed is True
        assert result.violation is None

    def test_failed_with_violation(self) -> None:
        """A failing check may carry a violation."""
        violation = GovernanceViolation(
            schema_id="s",
            policy_id="p",
            severity="critical",
            description="failed",
        )
        result = GovernanceCheckResult(
            schema_id="s",
            policy_id="p",
            passed=False,
            violation=violation,
        )
        assert result.passed is False
        assert result.violation is not None


class TestViolationResponse:
    """Tests for the ViolationResponse model."""

    def test_creation(self) -> None:
        """ViolationResponse can be created with all required fields."""
        response = ViolationResponse(
            action="halt",
            log_level="critical",
            notification_target="admin",
        )
        assert response.action == "halt"
        assert response.log_level == "critical"
        assert response.notification_target == "admin"


# ============================================================================
# Cognition Models
# ============================================================================

class TestOperationalState:
    """Tests for the OperationalState enum."""

    def test_all_13_values_exist(self) -> None:
        """All 13 operational states are defined."""
        expected = {
            "uninitialized",
            "initializing",
            "standby",
            "governance_check",
            "cognition_active",
            "inference_executing",
            "memory_retrieving",
            "trace_logging",
            "auditing",
            "degraded",
            "fail_closed",
            "recovering",
            "shutdown",
        }
        actual = {member.value for member in OperationalState}
        assert actual == expected

    def test_member_count(self) -> None:
        """There are exactly 13 operational states."""
        assert len(OperationalState) == 13

    def test_comparison(self) -> None:
        """OperationalState members can be compared."""
        assert OperationalState.UNINITIALIZED != OperationalState.COGNITION_ACTIVE
        assert OperationalState.FAIL_CLOSED == OperationalState.FAIL_CLOSED


class TestStateTransition:
    """Tests for the StateTransition model."""

    def test_creation(self, sample_state_transition: StateTransition) -> None:
        """StateTransition can be created with all required fields."""
        assert isinstance(sample_state_transition.transition_id, UUID)
        assert sample_state_transition.from_state == OperationalState.STANDBY
        assert sample_state_transition.to_state == OperationalState.GOVERNANCE_CHECK
        assert sample_state_transition.governance_check is True
        assert isinstance(sample_state_transition.timestamp, datetime)

    def test_timestamp_required(self) -> None:
        """StateTransition requires a timestamp — not auto-generated."""
        with pytest.raises(ValidationError):
            StateTransition(
                transition_id=uuid4(),
                from_state=OperationalState.STANDBY,
                to_state=OperationalState.GOVERNANCE_CHECK,
                trigger="test",
                governance_check=True,
                # timestamp is required — missing
                trace_id=uuid4(),
            )


class TestForbiddenStatePattern:
    """Tests for the ForbiddenStatePattern model."""

    def test_creation(self) -> None:
        """ForbiddenStatePattern can be created with a state sequence."""
        pattern = ForbiddenStatePattern(
            pattern_id="recursive_inference",
            description="No recursive inference",
            state_sequence=[
                OperationalState.INFERENCE_EXECUTING,
                OperationalState.INFERENCE_EXECUTING,
            ],
            detection_logic="detect_recursive_inference",
            response_action="halt",
        )
        assert pattern.pattern_id == "recursive_inference"
        assert len(pattern.state_sequence) == 2
        assert pattern.response_action == "halt"


# ============================================================================
# Memory Models
# ============================================================================

class TestEpisodicMemory:
    """Tests for the EpisodicMemory model."""

    def test_creation(self, sample_episodic_memory: EpisodicMemory) -> None:
        """EpisodicMemory can be created with full provenance."""
        assert isinstance(sample_episodic_memory.memory_id, UUID)
        assert sample_episodic_memory.episode_type == "inference"
        assert sample_episodic_memory.confidence == 0.95
        assert isinstance(sample_episodic_memory.provenance, ProvenanceRecord)

    def test_memory_id_auto_generated(self) -> None:
        """EpisodicMemory auto-generates memory_id if not provided."""
        memory = EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="Test content",
            provenance=ProvenanceRecord(
                source_schema="test",
                creator_component="test",
            ),
            confidence=0.5,
        )
        assert isinstance(memory.memory_id, UUID)

    def test_confidence_bounds(self) -> None:
        """EpisodicMemory confidence must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            EpisodicMemory(
                session_id=uuid4(),
                episode_type="inference",
                content="Test",
                provenance=ProvenanceRecord(
                    source_schema="test",
                    creator_component="test",
                ),
                confidence=1.5,  # out of bounds
            )

    def test_retrieval_count_default(self) -> None:
        """EpisodicMemory retrieval_count defaults to 0."""
        memory = EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="Test",
            provenance=ProvenanceRecord(
                source_schema="test",
                creator_component="test",
            ),
            confidence=0.5,
        )
        assert memory.retrieval_count == 0

    def test_serialization(self, sample_episodic_memory: EpisodicMemory) -> None:
        """EpisodicMemory serializes to dict correctly."""
        dumped = sample_episodic_memory.model_dump()
        assert "memory_id" in dumped
        assert "session_id" in dumped
        assert "provenance" in dumped


class TestMemoryInfluence:
    """Tests for the MemoryInfluence model."""

    def test_creation(self) -> None:
        """MemoryInfluence can be created with all required fields."""
        influence = MemoryInfluence(
            memory_id=uuid4(),
            target_inference_id=uuid4(),
            influence_type="retrieval",
            strength=0.8,
        )
        assert isinstance(influence.influence_id, UUID)
        assert influence.influence_type == "retrieval"
        assert influence.strength == 0.8

    def test_trace_visible_defaults_to_true(self) -> None:
        """MemoryInfluence trace_visible defaults to True."""
        influence = MemoryInfluence(
            memory_id=uuid4(),
            target_inference_id=uuid4(),
            influence_type="retrieval",
            strength=0.5,
        )
        assert influence.trace_visible is True

    def test_strength_bounds(self) -> None:
        """MemoryInfluence strength must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            MemoryInfluence(
                memory_id=uuid4(),
                target_inference_id=uuid4(),
                influence_type="retrieval",
                strength=-0.1,
            )

    def test_serialization(self) -> None:
        """MemoryInfluence serializes to dict correctly."""
        influence = MemoryInfluence(
            memory_id=uuid4(),
            target_inference_id=uuid4(),
            influence_type="context",
            strength=0.7,
        )
        dumped = influence.model_dump()
        assert dumped["trace_visible"] is True
        assert dumped["strength"] == 0.7


class TestProvenanceRecord:
    """Tests for the ProvenanceRecord model."""

    def test_creation(self) -> None:
        """ProvenanceRecord can be created with all required fields."""
        record = ProvenanceRecord(
            source_schema="test_schema",
            source_policy="test_policy",
            creator_component="TestComponent",
            inference_id=uuid4(),
        )
        assert record.source_schema == "test_schema"
        assert record.creator_component == "TestComponent"

    def test_source_policy_optional(self) -> None:
        """ProvenanceRecord source_policy defaults to None."""
        record = ProvenanceRecord(
            source_schema="test",
            creator_component="TestComponent",
        )
        assert record.source_policy is None


# ============================================================================
# Audit Models
# ============================================================================

class TestAuditEvent:
    """Tests for the AuditEvent model."""

    def test_creation(self) -> None:
        """AuditEvent can be created with all required fields."""
        event = AuditEvent(
            event_type="state_transition",
            severity="info",
            component="state_machine",
        )
        assert isinstance(event.event_id, UUID)
        assert event.event_type == "state_transition"
        assert event.severity == "info"
        assert event.component == "state_machine"
        assert isinstance(event.timestamp, datetime)

    def test_severity_validation(self) -> None:
        """AuditEvent accepts valid severity values."""
        for severity in ("info", "warning", "critical"):
            event = AuditEvent(
                event_type="test",
                severity=severity,
                component="test",
            )
            assert event.severity == severity

    def test_details_default(self) -> None:
        """AuditEvent details defaults to empty dict."""
        event = AuditEvent(
            event_type="test",
            severity="info",
            component="test",
        )
        assert event.details == {}

    def test_governance_context_default(self) -> None:
        """AuditEvent governance_context defaults to empty list."""
        event = AuditEvent(
            event_type="test",
            severity="info",
            component="test",
        )
        assert event.governance_context == []

    def test_session_id_optional(self) -> None:
        """AuditEvent session_id defaults to None."""
        event = AuditEvent(
            event_type="test",
            severity="info",
            component="test",
        )
        assert event.session_id is None


class TestCognitionTrace:
    """Tests for the CognitionTrace model."""

    def test_creation(self) -> None:
        """CognitionTrace can be created with all required fields."""
        trace = CognitionTrace(
            trace_id=uuid4(),
            session_id=uuid4(),
            start_time=datetime.now(timezone.utc),
        )
        assert trace.end_time is None
        assert trace.state_sequence == []
        assert trace.events == []
        assert trace.memory_influences == []
        assert trace.governance_checks == []
        assert trace.final_state == OperationalState.UNINITIALIZED


# ============================================================================
# Inference Models
# ============================================================================

class TestInferenceRequest:
    """Tests for the InferenceRequest model."""

    def test_creation_with_all_fields(self, sample_inference_request: InferenceRequest) -> None:
        """InferenceRequest can be created with all fields."""
        assert isinstance(sample_inference_request.request_id, UUID)
        assert isinstance(sample_inference_request.session_id, UUID)
        assert sample_inference_request.prompt == "What is the capital of France?"
        assert sample_inference_request.model == "llama3.1"
        assert "uncertainty_management" in sample_inference_request.governance_context
        assert sample_inference_request.parameters["temperature"] == 0.7

    def test_request_id_auto_generated(self) -> None:
        """InferenceRequest auto-generates request_id."""
        req = InferenceRequest(
            session_id=uuid4(),
            prompt="Test",
            model="llama3.1",
            governance_context=["uncertainty_management"],
        )
        assert isinstance(req.request_id, UUID)

    def test_memory_context_default(self) -> None:
        """InferenceRequest memory_context defaults to empty list."""
        req = InferenceRequest(
            session_id=uuid4(),
            prompt="Test",
            model="llama3.1",
            governance_context=["g1"],
        )
        assert req.memory_context == []

    def test_parameters_default(self) -> None:
        """InferenceRequest parameters defaults to empty dict."""
        req = InferenceRequest(
            session_id=uuid4(),
            prompt="Test",
            model="llama3.1",
            governance_context=["g1"],
        )
        assert req.parameters == {}

    def test_missing_required_field(self) -> None:
        """InferenceRequest rejects missing required fields."""
        with pytest.raises(ValidationError):
            InferenceRequest(
                session_id=uuid4(),
                # prompt is required — missing
                model="llama3.1",
                governance_context=["g1"],
            )


class TestGovernedResponse:
    """Tests for the GovernedResponse model."""

    def test_creation(self, sample_governed_response: GovernedResponse) -> None:
        """GovernedResponse can be created with all required fields."""
        assert isinstance(sample_governed_response.response_id, UUID)
        assert sample_governed_response.passed_validation is True
        assert sample_governed_response.validation_failures == []

    def test_validated_response_none_when_failed(self, sample_inference_request: InferenceRequest) -> None:
        """GovernedResponse validated_response is None when validation fails."""
        response = GovernedResponse(
            request_id=sample_inference_request.request_id,
            raw_response="Some response",
            validated_response=None,
            passed_validation=False,
            validation_failures=["uncertainty_management: Confidence score not present"],
        )
        assert response.validated_response is None
        assert response.passed_validation is False

    def test_response_id_auto_generated(self, sample_inference_request: InferenceRequest) -> None:
        """GovernedResponse auto-generates response_id."""
        response = GovernedResponse(
            request_id=sample_inference_request.request_id,
            raw_response="Test",
            passed_validation=True,
        )
        assert isinstance(response.response_id, UUID)

    def test_released_at_default(self, sample_inference_request: InferenceRequest) -> None:
        """GovernedResponse released_at defaults to None."""
        response = GovernedResponse(
            request_id=sample_inference_request.request_id,
            raw_response="Test",
            passed_validation=True,
        )
        assert response.released_at is None


class TestPromptMediationResult:
    """Tests for the PromptMediationResult model."""

    def test_creation(self) -> None:
        """PromptMediationResult can be created with all required fields."""
        result = PromptMediationResult(
            original_prompt="Hello",
            mediated_prompt="[GOVERNANCE]\nHello\n[REMINDERS]",
            applied_schemas=["uncertainty_management"],
            injected_constraints=["prefix:uncertainty_management"],
        )
        assert result.original_prompt == "Hello"
        assert "uncertainty_management" in result.applied_schemas
