"""Shared pytest fixtures for the GARVIS comprehensive test suite.

All fixtures are async-compatible and use proper mocking for external
dependencies (PostgreSQL, Ollama HTTP, file system).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from models.governance import (
    GovernanceCheckResult,
    GovernanceConstraint,
    GovernancePolicy,
    GovernanceSchema,
    GovernanceViolation,
    ViolationResponse,
)
from models.cognition import OperationalState, StateTransition
from models.memory import EpisodicMemory, MemoryInfluence, ProvenanceRecord
from models.audit import AuditEvent
from models.inference import InferenceRequest, GovernedResponse, PromptMediationResult


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    """Provide a session-scoped asyncio event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Pydantic model fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_governance_schema() -> GovernanceSchema:
    """Return a fully populated GovernanceSchema for testing."""
    return GovernanceSchema(
        schema_id="uncertainty_management",
        name="Uncertainty Management",
        version="1.0.0",
        category="epistemic",
        description="Governs how the system acknowledges uncertainty.",
        policies=[
            GovernancePolicy(
                policy_id="uncertainty_quantification_required",
                description="All outputs must include uncertainty quantification",
                rule_type="requirement",
                condition="confidence_score present and between 0.0 and 1.0",
                evaluation_logic="validate_confidence_present",
                severity="critical",
                auto_remediation=False,
            ),
            GovernancePolicy(
                policy_id="uncertainty_honesty_threshold",
                description="System must not overstate confidence",
                rule_type="threshold",
                condition="stated_confidence <= supported_confidence",
                evaluation_logic="compare_stated_vs_supported",
                severity="warning",
                auto_remediation=True,
            ),
        ],
        constraints=[
            GovernanceConstraint(
                constraint_id="no_false_certainty",
                description="System must never present uncertain information as certain",
                scope="inference",
                enforcement="hard_stop",
            ),
        ],
        fail_closed=True,
        violation_response=ViolationResponse(
            action="halt",
            log_level="critical",
            notification_target="system",
        ),
    )


@pytest.fixture
def sample_inference_request() -> InferenceRequest:
    """Return a valid InferenceRequest for testing."""
    return InferenceRequest(
        request_id=uuid4(),
        session_id=uuid4(),
        prompt="What is the capital of France?",
        model="llama3.1",
        governance_context=["uncertainty_management", "truthfulness_governance"],
        memory_context=[],
        parameters={"temperature": 0.7, "max_tokens": 256},
    )


@pytest.fixture
def sample_governed_response(sample_inference_request: InferenceRequest) -> GovernedResponse:
    """Return a valid GovernedResponse for testing."""
    return GovernedResponse(
        response_id=uuid4(),
        request_id=sample_inference_request.request_id,
        raw_response="The capital of France is Paris. Confidence: 0.95",
        validated_response="The capital of France is Paris. Confidence: 0.95",
        passed_validation=True,
        validation_failures=[],
        memory_influences=[],
    )


@pytest.fixture
def sample_episodic_memory() -> EpisodicMemory:
    """Return a populated EpisodicMemory for testing."""
    return EpisodicMemory(
        memory_id=uuid4(),
        session_id=uuid4(),
        episode_type="inference",
        content="Paris is the capital of France.",
        provenance=ProvenanceRecord(
            source_schema="inference_schema",
            source_policy="knowledge_boundary_recognition",
            creator_component="GovernedInferenceExecutor",
        ),
        governance_influences=["uncertainty_management", "truthfulness_governance"],
        confidence=0.95,
    )


@pytest.fixture
def sample_state_transition() -> StateTransition:
    """Return a StateTransition for testing."""
    return StateTransition(
        transition_id=uuid4(),
        from_state=OperationalState.STANDBY,
        to_state=OperationalState.GOVERNANCE_CHECK,
        trigger="governance_validation_request",
        governance_check=True,
        timestamp=datetime.now(timezone.utc),
        trace_id=uuid4(),
    )


# ---------------------------------------------------------------------------
# Mock component fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db() -> MagicMock:
    """Return a mock DatabaseConnection with async methods."""
    db = MagicMock()
    db.execute = AsyncMock(return_value="INSERT 0 1")
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    db.fetchval = AsyncMock(return_value=1)
    db.executemany = AsyncMock(return_value=None)
    db.health_check = AsyncMock(return_value=True)
    db.is_initialized = True
    return db


@pytest.fixture
def mock_ollama() -> MagicMock:
    """Return a mock OllamaClient with async methods."""
    client = MagicMock()
    client.base_url = "http://localhost:11434"
    client.default_model = "llama3.1"
    client.generate = AsyncMock(return_value="This is a test response. Confidence: 0.85")
    client.list_models = AsyncMock(return_value=["llama3.1", "mistral"])
    client.health_check = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_validator() -> MagicMock:
    """Return a mock RuntimeValidator with async validate_state_transition."""
    validator = MagicMock()
    validator.validate_state_transition = AsyncMock(return_value=[])
    validator.validate_inference_request = MagicMock(return_value=[])
    validator.validate_response = MagicMock(return_value=[])
    validator.validate_memory_operation = MagicMock(return_value=[])
    validator.has_critical_failure = MagicMock(return_value=False)
    validator.get_validation_history = MagicMock(return_value=[])
    validator.clear_history = MagicMock()
    return validator


@pytest.fixture
def mock_enforcer() -> MagicMock:
    """Return a mock EnforcementEngine."""
    enforcer = MagicMock()
    enforcer.enforce_violation = AsyncMock()
    enforcer.halt_runtime = MagicMock()
    enforcer.degrade_runtime = MagicMock()
    enforcer.escalate_violation = MagicMock()
    enforcer.is_halted = False
    enforcer.is_degraded = False
    enforcer.halt_reason = None
    enforcer.degrade_reason = None
    enforcer.get_violation_counts = MagicMock(return_value={"critical": 0, "warning": 0, "info": 0})
    enforcer.reset = MagicMock()
    return enforcer


@pytest.fixture
def mock_audit() -> MagicMock:
    """Return a mock AuditPipeline with async methods."""
    audit = MagicMock()
    audit.log_event = AsyncMock()
    audit.log_state_transition = AsyncMock()
    audit.log_governance_violation = AsyncMock()
    audit.log_inference = AsyncMock()
    audit.get_events = AsyncMock(return_value=[])
    audit.flush = AsyncMock()
    audit.get_violation_summary = AsyncMock(return_value={
        "by_severity": {},
        "by_schema": {},
        "total": 0,
        "period_start": None,
    })
    audit.start = AsyncMock()
    audit.stop = AsyncMock()
    return audit


@pytest.fixture
def mock_lineage() -> MagicMock:
    """Return a mock LineageTracker with async methods."""
    lineage = MagicMock()
    lineage.start_trace = AsyncMock(return_value=uuid4())
    lineage.record_inference = AsyncMock()
    lineage.record_governance_influence = AsyncMock()
    lineage.record_memory_influence = AsyncMock()
    lineage.get_trace = AsyncMock(return_value=None)
    lineage.get_lineage_graph = AsyncMock(return_value={
        "nodes": {},
        "edges": [],
        "trace_id": str(uuid4()),
    })
    return lineage


@pytest.fixture
def mock_memory_store() -> MagicMock:
    """Return a mock EpisodicMemoryStore with async methods."""
    store = MagicMock()
    store.store = AsyncMock(return_value=None)
    store.retrieve = AsyncMock(return_value=[])
    store.get_by_id = AsyncMock(return_value=None)
    store.get_session_memories = AsyncMock(return_value=[])
    store.record_influence = AsyncMock()
    store.middleware = None
    return store


@pytest.fixture
def mock_middleware() -> MagicMock:
    """Return a mock GovernanceMiddleware with async methods."""
    middleware = MagicMock()
    middleware.is_active = True
    middleware.activate = MagicMock()
    middleware.deactivate = MagicMock()
    middleware.process_inference_request = AsyncMock(return_value=None)  # Returns None = blocked
    middleware.process_inference_response = AsyncMock(return_value=None)
    middleware.process_memory_store = AsyncMock(return_value=None)
    middleware.process_memory_retrieval = AsyncMock(return_value=None)
    middleware.process_state_transition = AsyncMock(return_value=None)
    middleware.validate_request = AsyncMock(return_value=None)
    return middleware


@pytest.fixture
def mock_registry() -> MagicMock:
    """Return a mock GovernanceRegistry."""
    registry = MagicMock()
    registry.initialize = MagicMock()
    registry.activate = MagicMock()
    registry.deactivate = MagicMock()
    registry.is_active = MagicMock(return_value=True)
    registry.get_active_schemas = MagicMock(return_value=[])
    registry.get_all_schemas = MagicMock(return_value=[])
    registry.get_schema = MagicMock(return_value=None)
    registry.validate_cross_schema_consistency = MagicMock(return_value=[])
    registry.get_enforcement_chain = MagicMock(return_value=[])
    registry.get_policies_for_scope = MagicMock(return_value=[])
    registry.get_active_schema_ids = MagicMock(return_value=[])
    registry.__len__ = MagicMock(return_value=0)
    return registry
