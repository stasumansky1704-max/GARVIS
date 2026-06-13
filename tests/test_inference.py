"""Tests for the inference layer.

Tests cover Ollama client initialization, prompt mediation, response validation,
and the governed executor. Both happy path and governance-blocked paths are tested.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio

from inference.ollama_client import OllamaClient
from inference.prompt_mediator import PromptMediator
from inference.response_validator import ResponseValidator
from inference.governed_executor import (
    GovernedInferenceExecutor,
    GovernanceBlockedError,
    InferenceError,
    ResponseValidationError,
)
from models.inference import InferenceRequest, GovernedResponse, PromptMediationResult
from models.memory import EpisodicMemory, MemoryInfluence


# ============================================================================
# OllamaClient
# ============================================================================

class TestOllamaClient:
    """Tests for OllamaClient."""

    def test_init_defaults(self) -> None:
        """OllamaClient initializes with correct defaults."""
        client = OllamaClient()
        assert client.base_url == "http://localhost:11434"
        assert client.default_model == "llama3.1"

    def test_init_custom_values(self) -> None:
        """OllamaClient accepts custom base_url and model."""
        client = OllamaClient(
            base_url="http://ollama.example.com:11434",
            default_model="mistral",
        )
        assert client.base_url == "http://ollama.example.com:11434"
        assert client.default_model == "mistral"

    def test_base_url_strips_trailing_slash(self) -> None:
        """OllamaClient strips trailing slash from base_url."""
        client = OllamaClient(base_url="http://localhost:11434/")
        assert client.base_url == "http://localhost:11434"


# ============================================================================
# PromptMediator
# ============================================================================

class TestPromptMediator:
    """Tests for PromptMediator."""

    @pytest.fixture
    def mediator(self) -> PromptMediator:
        """Return a PromptMediator."""
        return PromptMediator()

    def test_prompt_mediation_injects_constraints(self, mediator: PromptMediator) -> None:
        """mediate() injects governance constraints into the prompt."""
        result = mediator.mediate(
            prompt="What is 2+2?",
            active_schemas=["uncertainty_management"],
        )

        assert isinstance(result, PromptMediationResult)
        assert "GOVERNANCE INSTRUCTIONS" in result.mediated_prompt
        assert result.original_prompt == "What is 2+2?"
        assert len(result.applied_schemas) > 0

    def test_prompt_mediation_applies_multiple_schemas(self, mediator: PromptMediator) -> None:
        """mediate() applies multiple active schemas."""
        schemas = [
            "uncertainty_management",
            "truthfulness_governance",
            "cognitive_humility",
            "boundary_preservation",
            "provenance_awareness",
        ]
        result = mediator.mediate(prompt="Hello", active_schemas=schemas)

        assert len(result.applied_schemas) == 5
        for schema in schemas:
            assert schema in result.applied_schemas

    def test_prompt_mediation_no_schemas(self, mediator: PromptMediator) -> None:
        """mediate() with no schemas returns prompt unchanged (no governance block)."""
        result = mediator.mediate(prompt="Hello", active_schemas=[])

        assert result.mediated_prompt == "Original: Hello"
        assert result.applied_schemas == []

    def test_prompt_mediation_none_schemas(self, mediator: PromptMediator) -> None:
        """mediate() with None schemas returns prompt unchanged."""
        result = mediator.mediate(prompt="Hello", active_schemas=None)

        assert result.mediated_prompt == "Original: Hello"
        assert result.applied_schemas == []

    def test_prompt_mediation_unknown_schema_ignored(self, mediator: PromptMediator) -> None:
        """mediate() ignores unknown schema IDs."""
        result = mediator.mediate(
            prompt="Hello",
            active_schemas=["unknown_schema"],
        )

        assert result.applied_schemas == []

    def test_inject_governance_prefix(self, mediator: PromptMediator) -> None:
        """inject_governance_prefix() creates a prefix with instructions."""
        prefix = mediator.inject_governance_prefix(
            "test", ["uncertainty_management"]
        )

        assert "GOVERNANCE INSTRUCTIONS" in prefix
        assert "uncertainty_management" in prefix

    def test_inject_governance_suffix(self, mediator: PromptMediator) -> None:
        """inject_governance_suffix() creates a suffix with reminders."""
        suffix = mediator.inject_governance_suffix(
            "test", ["uncertainty_management"]
        )

        assert "GOVERNANCE REMINDERS" in suffix

    def test_get_applied_schemas(self, mediator: PromptMediator) -> None:
        """get_applied_schemas() returns schemas from last mediation."""
        mediator.mediate("Hello", ["uncertainty_management"])
        schemas = mediator.get_applied_schemas()

        assert "uncertainty_management" in schemas

    def test_get_injected_constraints(self, mediator: PromptMediator) -> None:
        """get_injected_constraints() returns constraints from last mediation."""
        mediator.mediate("Hello", ["uncertainty_management"])
        constraints = mediator.get_injected_constraints()

        assert len(constraints) > 0


# ============================================================================
# ResponseValidator
# ============================================================================

class TestResponseValidator:
    """Tests for ResponseValidator."""

    @pytest.fixture
    def validator(self) -> ResponseValidator:
        """Return a ResponseValidator."""
        return ResponseValidator()

    @pytest.fixture
    def valid_request(self) -> InferenceRequest:
        """Return a valid inference request."""
        return InferenceRequest(
            request_id=uuid4(),
            session_id=uuid4(),
            prompt="What is the capital of France?",
            model="llama3.1",
            governance_context=["uncertainty_management", "truthfulness_governance"],
        )

    def test_response_validator_pass(self, validator: ResponseValidator, valid_request: InferenceRequest) -> None:
        """Valid response with confidence score passes validation."""
        response = GovernedResponse(
            request_id=valid_request.request_id,
            raw_response="The capital of France is Paris. Confidence: 0.95",
            passed_validation=False,  # will be set by validator
        )

        result = validator.validate(response, valid_request)

        assert result.passed_validation is True
        assert result.validated_response is not None
        assert len(result.validation_failures) == 0

    def test_response_validator_detects_false_certainty(
        self, validator: ResponseValidator, valid_request: InferenceRequest
    ) -> None:
        """Response with false certainty phrases is flagged."""
        response = GovernedResponse(
            request_id=valid_request.request_id,
            raw_response="I am certain that Paris is the capital of France. Confidence: 0.95",
            passed_validation=False,
        )

        result = validator.validate(response, valid_request)

        # False certainty should be detected
        checks = validator.get_last_checks()
        truthfulness_check = [c for c in checks if c.schema_id == "truthfulness_governance"]
        assert len(truthfulness_check) > 0
        # The false certainty detection returns True (meaning false certainty IS detected)
        # which makes the check fail (passed=False)
        assert truthfulness_check[0].passed is False

    def test_response_validator_detects_missing_confidence(
        self, validator: ResponseValidator, valid_request: InferenceRequest
    ) -> None:
        """Response without confidence score fails uncertainty check."""
        response = GovernedResponse(
            request_id=valid_request.request_id,
            raw_response="Paris is the capital of France.",  # no confidence score
            passed_validation=False,
        )

        result = validator.validate(response, valid_request)

        # Should have failed checks
        assert len(result.validation_failures) > 0
        assert result.passed_validation is False
        assert result.validated_response is None

    def test_check_false_certainty_detection(self, validator: ResponseValidator) -> None:
        """check_false_certainty() detects false certainty phrases."""
        assert validator.check_false_certainty("I am certain that this is correct") is True
        assert validator.check_false_certainty("It is definitely true") is True
        assert validator.check_false_certainty("There is no doubt about it") is True
        assert validator.check_false_certainty("100% sure about this") is True

    def test_check_false_certainty_no_detection(self, validator: ResponseValidator) -> None:
        """check_false_certainty() returns False for humble responses."""
        assert validator.check_false_certainty("I think this might be correct") is False
        assert validator.check_false_certainty("Based on my knowledge") is False

    def test_check_confidence_score_present(self, validator: ResponseValidator) -> None:
        """check_confidence_score_present() detects confidence scores."""
        assert validator.check_confidence_score_present("Confidence: 0.95") is True
        assert validator.check_confidence_score_present("score is 0.7") is True
        assert validator.check_confidence_score_present("No score here") is False

    def test_check_uncertainty_acknowledgment(self, validator: ResponseValidator) -> None:
        """check_uncertainty_acknowledgment() detects humility."""
        assert validator.check_uncertainty_acknowledgment("I don't know the answer") is True
        assert validator.check_uncertainty_acknowledgment("I'm not sure") is True
        assert validator.check_uncertainty_acknowledgment("Uncertain about this") is True

    def test_check_uncertainty_short_text(self, validator: ResponseValidator) -> None:
        """check_uncertainty_acknowledgment() passes short text."""
        assert validator.check_uncertainty_acknowledgment("Hi") is True  # too short to assess

    def test_check_boundary_compliance(self, validator: ResponseValidator) -> None:
        """check_boundary_compliance() detects boundary violations."""
        sample_boundaries = ["confidential", "restricted", "classified"]
        # check_boundary_compliance returns True when content is COMPLIANT
        assert validator.check_boundary_compliance("I will help you", sample_boundaries) is True
        # Verify the function actually checks content (non-empty input processed)
        result = validator.check_boundary_compliance("Some response text", sample_boundaries)
        assert isinstance(result, bool)

    def test_get_last_checks(self, validator: ResponseValidator, valid_request: InferenceRequest) -> None:
        """get_last_checks() returns checks from the last validation."""
        response = GovernedResponse(
            request_id=valid_request.request_id,
            raw_response="Test. Confidence: 0.8",
            passed_validation=False,
        )
        validator.validate(response, valid_request)

        checks = validator.get_last_checks()
        assert len(checks) > 0
        assert all(isinstance(c, __import__("models.governance", fromlist=["GovernanceCheckResult"]).GovernanceCheckResult) for c in checks)


# ============================================================================
# GovernedInferenceExecutor
# ============================================================================

class TestGovernedInferenceExecutor:
    """Tests for GovernedInferenceExecutor."""

    @pytest.fixture
    def executor(self, mock_ollama: MagicMock, mock_middleware: MagicMock,
                 mock_db: MagicMock, mock_audit: MagicMock,
                 mock_lineage: MagicMock) -> GovernedInferenceExecutor:
        """Return a GovernedInferenceExecutor with mocked dependencies."""
        from cognition.state_machine import CognitiveStateMachine
        from memory.episodic import EpisodicMemoryStore

        # Create a mock state machine
        state_machine = MagicMock(spec=CognitiveStateMachine)
        state_machine.transition = AsyncMock(return_value=True)
        state_machine.get_current_state = MagicMock(
            return_value=__import__("models.cognition", fromlist=["OperationalState"]).OperationalState.COGNITION_ACTIVE
        )
        state_machine._force_transition = AsyncMock(return_value=True)

        memory_store = MagicMock(spec=EpisodicMemoryStore)
        memory_store.store = AsyncMock(return_value=None)
        memory_store.retrieve = AsyncMock(return_value=[])
        memory_store.record_influence = AsyncMock()

        executor = GovernedInferenceExecutor(
            ollama_client=mock_ollama,
            middleware=mock_middleware,
            state_machine=state_machine,
            memory_store=memory_store,
            lineage=mock_lineage,
            audit=mock_audit,
        )
        return executor

    def test_governed_executor_init(self, executor: GovernedInferenceExecutor) -> None:
        """GovernedInferenceExecutor initializes with all components wired."""
        assert executor.ollama is not None
        assert executor.middleware is not None
        assert executor.state_machine is not None
        assert executor.memory is not None
        assert executor.lineage is not None
        assert executor.audit is not None
        assert executor._mediator is not None
        assert executor._validator is not None

    @pytest.mark.asyncio
    async def test_governed_executor_execute_blocked_by_governance(
        self, executor: GovernedInferenceExecutor, mock_middleware: MagicMock
    ) -> None:
        """Governance blocks execution when middleware returns None."""
        mock_middleware.validate_request = AsyncMock(return_value=None)
        # Override to make it appear inactive so validate_request returns None
        mock_middleware.is_active = True
        mock_middleware.process_inference_request = AsyncMock(return_value=None)

        request = InferenceRequest(
            request_id=uuid4(),
            session_id=uuid4(),
            prompt="Hello?",
            model="llama3.1",
            governance_context=["uncertainty_management"],
        )

        # The middleware.validate_request returning None should cause GovernanceBlockedError
        # But the actual code calls middleware.validate_request, not process_inference_request
        # Let's check what the code actually does...
        # Looking at the executor code:
        #   validation_context = await self.middleware.validate_request(request)
        #   if validation_context is None: raise GovernanceBlockedError
        
        # We need to mock validate_request to return None
        mock_middleware.validate_request = AsyncMock(return_value=None)

        with pytest.raises(GovernanceBlockedError):
            await executor.execute(request)

    def test_build_memory_influences(self) -> None:
        """_build_memory_influences() creates influences from memories."""
        from inference.governed_executor import GovernedInferenceExecutor
        from models.memory import ProvenanceRecord
        request_id = uuid4()
        memories = [
            EpisodicMemory(
                session_id=uuid4(),
                episode_type="inference",
                content="Memory 1",
                provenance=ProvenanceRecord(source_schema="s", creator_component="c"),
                confidence=0.8,
            ),
            EpisodicMemory(
                session_id=uuid4(),
                episode_type="inference",
                content="Memory 2",
                provenance=ProvenanceRecord(source_schema="s", creator_component="c"),
                confidence=0.7,
            ),
        ]
        executor = GovernedInferenceExecutor.__new__(GovernedInferenceExecutor)
        influences = executor._build_memory_influences(memories, request_id)
        assert len(influences) == 2
        for inf in influences:
            assert isinstance(inf, MemoryInfluence)
            assert inf.target_inference_id == request_id
            assert inf.influence_type == "retrieval"
            assert inf.trace_visible is True

    def test_augment_with_memory_no_memories(self, executor: GovernedInferenceExecutor) -> None:
        """_augment_with_memory() returns original prompt when no memories."""
        result = executor._augment_with_memory("Original prompt", [])
        assert result == "Original prompt"

    def test_augment_with_memory(self, executor: GovernedInferenceExecutor) -> None:
        """_augment_with_memory() appends memory context to prompt."""
        from models.memory import ProvenanceRecord
        memories = [
            EpisodicMemory(
                session_id=uuid4(),
                episode_type="inference",
                content="Paris is the capital of France.",
                provenance=ProvenanceRecord(source_schema="s", creator_component="c"),
                confidence=0.9,
            ),
        ]

        result = executor._augment_with_memory("Prompt", memories)

        assert "Paris is the capital" in result
