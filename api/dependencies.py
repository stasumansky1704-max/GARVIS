"""Shared dependencies for the GARVIS Operator API.

All dependencies are exposed as FastAPI dependency-callable functions.
For the operator-dashboard use-case the runtime is mocked so that the
API can start and serve realistic data without a live database or LLM
connection.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

# Lazy imports to avoid hard coupling at import time
from governance.loader import SchemaLoader
from governance.registry import GovernanceRegistry
from models.governance import (
    GovernanceSchema,
    GovernancePolicy,
    GovernanceConstraint,
    GovernanceViolation,
    GovernanceCheckResult,
    ViolationResponse,
)
from models.cognition import OperationalState, StateTransition, ForbiddenStatePattern
from models.memory import EpisodicMemory, MemoryInfluence, ProvenanceRecord
from models.audit import AuditEvent, CognitionTrace

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock data store — populated once at first access
# ---------------------------------------------------------------------------

_MOCK_START_TIME: float = time.monotonic()
_mock_data_initialized: bool = False

_mock_schemas: list[GovernanceSchema] = []
_mock_active_schemas: set[str] = set()
_mock_transitions: list[StateTransition] = []
_mock_memories: list[EpisodicMemory] = []
_mock_influences: list[MemoryInfluence] = []
_mock_audit_events: list[AuditEvent] = []
_mock_traces: list[dict[str, Any]] = []
_mock_sessions: list[dict[str, Any]] = []
_mock_violations: list[GovernanceViolation] = []
_mock_checks: list[GovernanceCheckResult] = []

# ---------------------------------------------------------------------------
# Singletons (lazy init)
# ---------------------------------------------------------------------------

_registry: GovernanceRegistry | None = None
_state_machine: Any = None  # We use a lightweight mock wrapper


# ---------------------------------------------------------------------------
# Mock data generators
# ---------------------------------------------------------------------------

def _init_mock_data() -> None:
    """Populate all mock data stores once."""
    global _mock_data_initialized, _mock_schemas, _mock_active_schemas
    global _mock_transitions, _mock_memories, _mock_influences
    global _mock_audit_events, _mock_traces, _mock_sessions
    global _mock_violations, _mock_checks

    if _mock_data_initialized:
        return

    # ── 1. Governance Schemas (8 schemas) ─────────────────────────
    _mock_schemas = [
        GovernanceSchema(
            schema_id="epistemic_safety",
            name="Epistemic Safety",
            version="1.0.0",
            category="epistemic",
            description="Ensures model outputs stay within epistemic boundaries and do not overclaim certainty.",
            policies=[
                GovernancePolicy(
                    policy_id="ep_01",
                    description="Maximum confidence for any factual claim is 0.85",
                    rule_type="threshold",
                    condition="confidence > 0.85",
                    evaluation_logic="confidence_capping",
                    severity="warning",
                ),
                GovernancePolicy(
                    policy_id="ep_02",
                    description="Uncertainty must be disclosed when confidence < 0.6",
                    rule_type="requirement",
                    condition="confidence < 0.6",
                    evaluation_logic="uncertainty_disclosure_check",
                    severity="critical",
                ),
            ],
            constraints=[
                GovernanceConstraint(
                    constraint_id="ep_c01",
                    description="Never claim certainty without evidence",
                    scope="inference",
                    enforcement="degrade",
                ),
            ],
            fail_closed=True,
            violation_response=ViolationResponse(
                action="degrade", log_level="warning", notification_target="operator"
            ),
        ),
        GovernanceSchema(
            schema_id="operational_integrity",
            name="Operational Integrity",
            version="2.1.0",
            category="operational",
            description="Maintains runtime operational constraints: timeouts, resource limits, error handling.",
            policies=[
                GovernancePolicy(
                    policy_id="op_01",
                    description="Inference timeout must not exceed 120s",
                    rule_type="threshold",
                    condition="inference_time > 120",
                    evaluation_logic="timeout_check",
                    severity="critical",
                ),
                GovernancePolicy(
                    policy_id="op_02",
                    description="Memory usage must stay below 80%",
                    rule_type="threshold",
                    condition="memory_percent > 80",
                    evaluation_logic="resource_limit_check",
                    severity="warning",
                ),
            ],
            constraints=[
                GovernanceConstraint(
                    constraint_id="op_c01",
                    description="Hard stop if inference exceeds timeout",
                    scope="inference",
                    enforcement="hard_stop",
                ),
                GovernanceConstraint(
                    constraint_id="op_c02",
                    description="Log all resource limit violations",
                    scope="global",
                    enforcement="log_only",
                ),
            ],
            fail_closed=True,
            violation_response=ViolationResponse(
                action="halt", log_level="critical", notification_target="admin"
            ),
        ),
        GovernanceSchema(
            schema_id="boundary_enforcement",
            name="Boundary Enforcement",
            version="1.3.0",
            category="boundary",
            description="Enforces hard boundaries on model behavior: no code execution, no external calls.",
            policies=[
                GovernancePolicy(
                    policy_id="be_01",
                    description="No subprocess or shell execution in prompts",
                    rule_type="prohibition",
                    condition="prompt_contains_shell",
                    evaluation_logic="code_injection_scan",
                    severity="critical",
                ),
                GovernancePolicy(
                    policy_id="be_02",
                    description="No network calls from inference context",
                    rule_type="prohibition",
                    condition="prompt_contains_url",
                    evaluation_logic="network_access_check",
                    severity="critical",
                ),
            ],
            constraints=[
                GovernanceConstraint(
                    constraint_id="be_c01",
                    description="Block any prompt containing executable code",
                    scope="inference",
                    enforcement="hard_stop",
                ),
            ],
            fail_closed=True,
            violation_response=ViolationResponse(
                action="halt", log_level="critical", notification_target="admin"
            ),
        ),
        GovernanceSchema(
            schema_id="reflective_continuity",
            name="Reflective Continuity",
            version="1.2.0",
            category="reflective",
            description="Maintains coherence across reasoning steps: alignment, persistence, degradation tracking.",
            policies=[
                GovernancePolicy(
                    policy_id="rc_01",
                    description="Alignment drift must not exceed 0.3 between turns",
                    rule_type="threshold",
                    condition="alignment_delta > 0.3",
                    evaluation_logic="alignment_persistence_check",
                    severity="warning",
                ),
                GovernancePolicy(
                    policy_id="rc_02",
                    description="Memory consistency must be validated before retrieval",
                    rule_type="requirement",
                    condition="memory_stale",
                    evaluation_logic="memory_freshness_check",
                    severity="info",
                ),
            ],
            constraints=[
                GovernanceConstraint(
                    constraint_id="rc_c01",
                    description="Degrade if alignment drift exceeds threshold",
                    scope="session",
                    enforcement="degrade",
                ),
            ],
            fail_closed=False,
            violation_response=ViolationResponse(
                action="log", log_level="info", notification_target="system"
            ),
        ),
        GovernanceSchema(
            schema_id="session_management",
            name="Session Management",
            version="1.0.0",
            category="session",
            description="Manages session lifecycle, isolation, and resource allocation per session.",
            policies=[
                GovernancePolicy(
                    policy_id="sm_01",
                    description="Max 10 active sessions per operator",
                    rule_type="threshold",
                    condition="active_sessions > 10",
                    evaluation_logic="session_limit_check",
                    severity="warning",
                ),
                GovernancePolicy(
                    policy_id="sm_02",
                    description="Sessions idle > 30min must be closed",
                    rule_type="requirement",
                    condition="session_idle > 1800",
                    evaluation_logic="session_timeout_check",
                    severity="info",
                ),
            ],
            constraints=[
                GovernanceConstraint(
                    constraint_id="sm_c01",
                    description="Reject new sessions if limit exceeded",
                    scope="session",
                    enforcement="hard_stop",
                ),
            ],
            fail_closed=True,
            violation_response=ViolationResponse(
                action="escalate", log_level="warning", notification_target="operator"
            ),
        ),
        GovernanceSchema(
            schema_id="ethical_guidelines",
            name="Ethical Guidelines",
            version="1.0.0",
            category="ethical",
            description="Guards against harmful outputs: toxicity, bias, privacy violations.",
            policies=[
                GovernancePolicy(
                    policy_id="eg_01",
                    description="Toxicity score must remain below 0.1",
                    rule_type="threshold",
                    condition="toxicity_score > 0.1",
                    evaluation_logic="toxicity_scan",
                    severity="critical",
                ),
                GovernancePolicy(
                    policy_id="eg_02",
                    description="No PII in model outputs",
                    rule_type="prohibition",
                    condition="output_contains_pii",
                    evaluation_logic="pii_detection",
                    severity="critical",
                ),
            ],
            constraints=[
                GovernanceConstraint(
                    constraint_id="eg_c01",
                    description="Halt and redact if PII detected",
                    scope="inference",
                    enforcement="hard_stop",
                ),
                GovernanceConstraint(
                    constraint_id="eg_c02",
                    description="Log all ethical guideline checks",
                    scope="global",
                    enforcement="log_only",
                ),
            ],
            fail_closed=True,
            violation_response=ViolationResponse(
                action="halt", log_level="critical", notification_target="admin"
            ),
        ),
        GovernanceSchema(
            schema_id="traceability_requirement",
            name="Traceability Requirement",
            version="1.0.0",
            category="operational",
            description="Ensures every inference has a complete trace and audit record.",
            policies=[
                GovernancePolicy(
                    policy_id="tr_01",
                    description="Every inference must produce a trace",
                    rule_type="requirement",
                    condition="trace_missing",
                    evaluation_logic="trace_completeness_check",
                    severity="critical",
                ),
                GovernancePolicy(
                    policy_id="tr_02",
                    description="Audit events must be flushed within 30s",
                    rule_type="threshold",
                    condition="audit_flush_age > 30",
                    evaluation_logic="audit_flush_check",
                    severity="warning",
                ),
            ],
            constraints=[
                GovernanceConstraint(
                    constraint_id="tr_c01",
                    description="Fail inference if trace cannot be created",
                    scope="inference",
                    enforcement="hard_stop",
                ),
            ],
            fail_closed=True,
            violation_response=ViolationResponse(
                action="halt", log_level="critical", notification_target="system"
            ),
        ),
        GovernanceSchema(
            schema_id="memory_integrity",
            name="Memory Integrity",
            version="1.1.0",
            category="reflective",
            description="Ensures memory consistency, provenance, and retrieval accuracy.",
            policies=[
                GovernancePolicy(
                    policy_id="mi_01",
                    description="Memory provenance must be recorded for all entries",
                    rule_type="requirement",
                    condition="provenance_missing",
                    evaluation_logic="provenance_check",
                    severity="warning",
                ),
                GovernancePolicy(
                    policy_id="mi_02",
                    description="Retrieval count must be accurate",
                    rule_type="threshold",
                    condition="retrieval_count_negative",
                    evaluation_logic="retrieval_sanity_check",
                    severity="info",
                ),
            ],
            constraints=[
                GovernanceConstraint(
                    constraint_id="mi_c01",
                    description="Reject memory entries without provenance",
                    scope="memory",
                    enforcement="log_only",
                ),
            ],
            fail_closed=False,
            violation_response=ViolationResponse(
                action="log", log_level="info", notification_target="system"
            ),
        ),
    ]

    _mock_active_schemas = {s.schema_id for s in _mock_schemas}

    # ── 2. State Transitions (10 transitions) ─────────────────────
    now = datetime.now(timezone.utc)
    _mock_transitions = [
        StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.UNINITIALIZED,
            to_state=OperationalState.INITIALIZING,
            trigger="runtime_start",
            governance_check=True,
            timestamp=now - timedelta(minutes=60),
            trace_id=uuid4(),
        ),
        StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.INITIALIZING,
            to_state=OperationalState.STANDBY,
            trigger="init_complete",
            governance_check=True,
            timestamp=now - timedelta(minutes=59),
            trace_id=uuid4(),
        ),
        StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.STANDBY,
            to_state=OperationalState.GOVERNANCE_CHECK,
            trigger="governance_validation",
            governance_check=True,
            timestamp=now - timedelta(minutes=58),
            trace_id=uuid4(),
        ),
        StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.GOVERNANCE_CHECK,
            to_state=OperationalState.COGNITION_ACTIVE,
            trigger="all_schemas_passed",
            governance_check=True,
            timestamp=now - timedelta(minutes=57),
            trace_id=uuid4(),
        ),
        StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.COGNITION_ACTIVE,
            to_state=OperationalState.INFERENCE_EXECUTING,
            trigger="inference_request_001",
            governance_check=True,
            timestamp=now - timedelta(minutes=55),
            trace_id=uuid4(),
        ),
        StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.INFERENCE_EXECUTING,
            to_state=OperationalState.AUDITING,
            trigger="inference_complete",
            governance_check=True,
            timestamp=now - timedelta(minutes=54),
            trace_id=uuid4(),
        ),
        StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.AUDITING,
            to_state=OperationalState.COGNITION_ACTIVE,
            trigger="audit_passed",
            governance_check=True,
            timestamp=now - timedelta(minutes=53),
            trace_id=uuid4(),
        ),
        StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.COGNITION_ACTIVE,
            to_state=OperationalState.MEMORY_RETRIEVING,
            trigger="memory_context_request",
            governance_check=True,
            timestamp=now - timedelta(minutes=45),
            trace_id=uuid4(),
        ),
        StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.MEMORY_RETRIEVING,
            to_state=OperationalState.COGNITION_ACTIVE,
            trigger="memory_retrieval_complete",
            governance_check=True,
            timestamp=now - timedelta(minutes=44),
            trace_id=uuid4(),
        ),
        StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.COGNITION_ACTIVE,
            to_state=OperationalState.TRACE_LOGGING,
            trigger="trace_record_request",
            governance_check=True,
            timestamp=now - timedelta(minutes=30),
            trace_id=uuid4(),
        ),
        StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.TRACE_LOGGING,
            to_state=OperationalState.COGNITION_ACTIVE,
            trigger="trace_logging_complete",
            governance_check=True,
            timestamp=now - timedelta(minutes=29),
            trace_id=uuid4(),
        ),
    ]

    # ── 3. Sessions (3 sessions) ─────────────────────────────────
    _mock_sessions = [
        {
            "session_id": UUID("a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"),
            "status": "active",
            "trace_count": 5,
            "created_at": now - timedelta(minutes=60),
            "last_activity": now - timedelta(minutes=5),
        },
        {
            "session_id": UUID("b1ffcd00-ad1c-5f09-cc7e-7cc0ce491b22"),
            "status": "closed",
            "trace_count": 3,
            "created_at": now - timedelta(hours=2),
            "last_activity": now - timedelta(hours=1, minutes=30),
        },
        {
            "session_id": UUID("c200de11-be2d-6f1a-dd8f-8dd1df5a2c33"),
            "status": "active",
            "trace_count": 2,
            "created_at": now - timedelta(minutes=30),
            "last_activity": now - timedelta(minutes=10),
        },
    ]

    # ── 4. Episodic Memories (8 memories) ────────────────────────
    _mock_memories = [
        EpisodicMemory(
            memory_id=uuid4(),
            session_id=_mock_sessions[0]["session_id"],
            episode_type="inference",
            content="User asked about the ethical implications of autonomous AI decision-making in healthcare contexts.",
            provenance=ProvenanceRecord(
                source_schema="epistemic_safety",
                source_policy="ep_01",
                inference_id=uuid4(),
                creator_component="GovernedInferenceExecutor",
            ),
            governance_influences=["epistemic_safety", "ethical_guidelines"],
            confidence=0.82,
            timestamp=now - timedelta(minutes=55),
            retrieval_count=3,
            last_accessed=now - timedelta(minutes=10),
        ),
        EpisodicMemory(
            memory_id=uuid4(),
            session_id=_mock_sessions[0]["session_id"],
            episode_type="reflection",
            content="Reflected on the epistemic limits of the previous response: the answer contained appropriate uncertainty disclaimers.",
            provenance=ProvenanceRecord(
                source_schema="reflective_continuity",
                source_policy="rc_01",
                inference_id=None,
                creator_component="ReflectionEngine",
            ),
            governance_influences=["reflective_continuity", "epistemic_safety"],
            confidence=0.91,
            timestamp=now - timedelta(minutes=53),
            retrieval_count=1,
            last_accessed=now - timedelta(minutes=20),
        ),
        EpisodicMemory(
            memory_id=uuid4(),
            session_id=_mock_sessions[0]["session_id"],
            episode_type="inference",
            content="User requested a summary of governance schema enforcement chains across all active scopes.",
            provenance=ProvenanceRecord(
                source_schema="operational_integrity",
                source_policy="op_01",
                inference_id=uuid4(),
                creator_component="GovernedInferenceExecutor",
            ),
            governance_influences=["operational_integrity", "traceability_requirement"],
            confidence=0.95,
            timestamp=now - timedelta(minutes=45),
            retrieval_count=5,
            last_accessed=now - timedelta(minutes=5),
        ),
        EpisodicMemory(
            memory_id=uuid4(),
            session_id=_mock_sessions[1]["session_id"],
            episode_type="audit",
            content="Governance check passed: alignment drift within threshold for session boundary_enforcement schema.",
            provenance=ProvenanceRecord(
                source_schema="boundary_enforcement",
                source_policy="be_01",
                inference_id=None,
                creator_component="GovernanceValidator",
            ),
            governance_influences=["boundary_enforcement"],
            confidence=0.88,
            timestamp=now - timedelta(hours=1, minutes=50),
            retrieval_count=0,
            last_accessed=None,
        ),
        EpisodicMemory(
            memory_id=uuid4(),
            session_id=_mock_sessions[1]["session_id"],
            episode_type="inference",
            content="User inquired about the session continuity guarantees provided by the reflective continuity schema.",
            provenance=ProvenanceRecord(
                source_schema="reflective_continuity",
                source_policy="rc_02",
                inference_id=uuid4(),
                creator_component="GovernedInferenceExecutor",
            ),
            governance_influences=["reflective_continuity", "memory_integrity"],
            confidence=0.76,
            timestamp=now - timedelta(hours=1, minutes=30),
            retrieval_count=2,
            last_accessed=now - timedelta(hours=1),
        ),
        EpisodicMemory(
            memory_id=uuid4(),
            session_id=_mock_sessions[2]["session_id"],
            episode_type="retrieval",
            content="Retrieved previous memory about healthcare AI ethics to provide context for current inference.",
            provenance=ProvenanceRecord(
                source_schema="memory_integrity",
                source_policy="mi_01",
                inference_id=None,
                creator_component="EpisodicMemoryStore",
            ),
            governance_influences=["memory_integrity"],
            confidence=0.85,
            timestamp=now - timedelta(minutes=25),
            retrieval_count=4,
            last_accessed=now - timedelta(minutes=5),
        ),
        EpisodicMemory(
            memory_id=uuid4(),
            session_id=_mock_sessions[2]["session_id"],
            episode_type="inference",
            content="User asked about the degradation behavior when a governance schema is deactivated during runtime.",
            provenance=ProvenanceRecord(
                source_schema="operational_integrity",
                source_policy="op_02",
                inference_id=uuid4(),
                creator_component="GovernedInferenceExecutor",
            ),
            governance_influences=["operational_integrity", "session_management"],
            confidence=0.79,
            timestamp=now - timedelta(minutes=20),
            retrieval_count=1,
            last_accessed=now - timedelta(minutes=15),
        ),
        EpisodicMemory(
            memory_id=uuid4(),
            session_id=_mock_sessions[2]["session_id"],
            episode_type="reflection",
            content="Reflected on the resilience properties of the fail-closed mechanism when two schemas conflict.",
            provenance=ProvenanceRecord(
                source_schema="reflective_continuity",
                source_policy="rc_01",
                inference_id=None,
                creator_component="ReflectionEngine",
            ),
            governance_influences=["reflective_continuity", "operational_integrity"],
            confidence=0.93,
            timestamp=now - timedelta(minutes=15),
            retrieval_count=0,
            last_accessed=None,
        ),
    ]

    # ── 5. Memory Influences (6 influences) ──────────────────────
    _mock_influences = [
        MemoryInfluence(
            influence_id=uuid4(),
            memory_id=_mock_memories[0].memory_id,
            target_inference_id=uuid4(),
            influence_type="context",
            strength=0.85,
            trace_visible=True,
            timestamp=now - timedelta(minutes=54),
        ),
        MemoryInfluence(
            influence_id=uuid4(),
            memory_id=_mock_memories[1].memory_id,
            target_inference_id=uuid4(),
            influence_type="retrieval",
            strength=0.72,
            trace_visible=True,
            timestamp=now - timedelta(minutes=52),
        ),
        MemoryInfluence(
            influence_id=uuid4(),
            memory_id=_mock_memories[2].memory_id,
            target_inference_id=uuid4(),
            influence_type="constraint",
            strength=0.91,
            trace_visible=True,
            timestamp=now - timedelta(minutes=44),
        ),
        MemoryInfluence(
            influence_id=uuid4(),
            memory_id=_mock_memories[3].memory_id,
            target_inference_id=uuid4(),
            influence_type="warning",
            strength=0.45,
            trace_visible=True,
            timestamp=now - timedelta(hours=1, minutes=45),
        ),
        MemoryInfluence(
            influence_id=uuid4(),
            memory_id=_mock_memories[5].memory_id,
            target_inference_id=uuid4(),
            influence_type="context",
            strength=0.78,
            trace_visible=True,
            timestamp=now - timedelta(minutes=24),
        ),
        MemoryInfluence(
            influence_id=uuid4(),
            memory_id=_mock_memories[6].memory_id,
            target_inference_id=uuid4(),
            influence_type="retrieval",
            strength=0.66,
            trace_visible=True,
            timestamp=now - timedelta(minutes=19),
        ),
    ]

    # ── 6. Audit Events (15 events) ──────────────────────────────
    _mock_audit_events = [
        AuditEvent(
            event_id=uuid4(),
            event_type="runtime_start",
            severity="info",
            component="runtime.bootstrap",
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=60),
            details={"version": "2.0.0", "mode": "operator"},
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="schema_load",
            severity="info",
            component="governance.loader",
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=59),
            details={"schemas_loaded": 8, "schemas_active": 8},
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="state_transition",
            severity="info",
            component="cognition.state_machine",
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=59),
            details={"from_state": "uninitialized", "to_state": "initializing", "trigger": "runtime_start"},
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="governance_check",
            severity="info",
            component="governance.validator",
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=58),
            details={"schema_id": "epistemic_safety", "policy_id": "ep_01", "passed": True},
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="governance_check",
            severity="info",
            component="governance.validator",
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=58),
            details={"schema_id": "boundary_enforcement", "policy_id": "be_01", "passed": True},
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="inference",
            severity="info",
            component="inference.executor",
            session_id=_mock_sessions[0]["session_id"],
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=55),
            details={"request_id": str(uuid4()), "model": "llama3.1", "passed_validation": True},
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="memory_store",
            severity="info",
            component="memory.store",
            session_id=_mock_sessions[0]["session_id"],
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=54),
            details={"memory_type": "inference", "size_chars": 120},
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="violation",
            severity="warning",
            component="governance.validator",
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=50),
            details={"schema_id": "session_management", "policy_id": "sm_02", "description": "Session idle approaching timeout threshold"},
            governance_context=["session_management"],
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="inference",
            severity="warning",
            component="inference.executor",
            session_id=_mock_sessions[0]["session_id"],
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=45),
            details={"request_id": str(uuid4()), "model": "llama3.1", "passed_validation": False, "failures": ["confidence_too_high"]},
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="memory_retrieval",
            severity="info",
            component="memory.store",
            session_id=_mock_sessions[1]["session_id"],
            trace_id=uuid4(),
            timestamp=now - timedelta(hours=1, minutes=45),
            details={"memories_retrieved": 2, "query_time_ms": 12},
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="state_transition",
            severity="info",
            component="cognition.state_machine",
            trace_id=uuid4(),
            timestamp=now - timedelta(hours=1, minutes=30),
            details={"from_state": "cognition_active", "to_state": "inference_executing", "trigger": "inference_request"},
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="governance_check",
            severity="critical",
            component="governance.validator",
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=40),
            details={"schema_id": "ethical_guidelines", "policy_id": "eg_01", "passed": False, "toxicity": 0.15},
            governance_context=["ethical_guidelines"],
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="violation",
            severity="critical",
            component="governance.validator",
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=40),
            details={"schema_id": "ethical_guidelines", "policy_id": "eg_01", "description": "Toxicity score 0.15 exceeded threshold 0.1", "action": "halt"},
            governance_context=["ethical_guidelines"],
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="degradation",
            severity="warning",
            component="runtime.degradation",
            trace_id=uuid4(),
            timestamp=now - timedelta(minutes=38),
            details={"reason": "ethical_guideline_violation", "recovery_action": "escalate_to_admin"},
        ),
        AuditEvent(
            event_id=uuid4(),
            event_type="session_close",
            severity="info",
            component="session.manager",
            session_id=_mock_sessions[1]["session_id"],
            trace_id=uuid4(),
            timestamp=now - timedelta(hours=1, minutes=20),
            details={"reason": "operator_request", "traces": 3},
        ),
    ]

    # ── 7. Traces (5 traces) ─────────────────────────────────────
    for i in range(5):
        trace_id = uuid4()
        session_idx = i % len(_mock_sessions)
        transitions_slice = _mock_transitions[i : i + 3] if i < len(_mock_transitions) - 2 else _mock_transitions[-3:]
        _mock_traces.append({
            "trace_id": trace_id,
            "session_id": _mock_sessions[session_idx]["session_id"],
            "start_time": now - timedelta(minutes=55 - i * 5),
            "end_time": now - timedelta(minutes=50 - i * 5) if i % 2 == 0 else None,
            "final_state": "cognition_active" if i % 2 == 0 else "inference_executing",
            "transition_count": len(transitions_slice),
            "event_count": 3,
            "check_count": 2,
            "influence_count": 1,
            "status": "success" if i < 3 else "warning" if i == 3 else "failed",
        })

    # ── 8. Governance Violations (4 violations) ──────────────────
    _mock_violations = [
        GovernanceViolation(
            violation_id=uuid4(),
            schema_id="session_management",
            policy_id="sm_02",
            severity="warning",
            description="Session idle approaching timeout threshold",
            context={"session_id": str(_mock_sessions[0]["session_id"]), "idle_seconds": 1500},
            timestamp=now - timedelta(minutes=50),
        ),
        GovernanceViolation(
            violation_id=uuid4(),
            schema_id="epistemic_safety",
            policy_id="ep_01",
            severity="warning",
            description="Confidence 0.92 for factual claim exceeded threshold 0.85",
            context={"confidence": 0.92, "claim": "Autonomous AI will reduce healthcare costs by 30%"},
            timestamp=now - timedelta(minutes=45),
        ),
        GovernanceViolation(
            violation_id=uuid4(),
            schema_id="ethical_guidelines",
            policy_id="eg_01",
            severity="critical",
            description="Toxicity score 0.15 exceeded threshold 0.1",
            context={"toxicity": 0.15, "model": "toxicity_v3", "text_sample": "..."},
            timestamp=now - timedelta(minutes=40),
        ),
        GovernanceViolation(
            violation_id=uuid4(),
            schema_id="operational_integrity",
            policy_id="op_02",
            severity="info",
            description="Memory usage at 82%, slightly above warning threshold of 80%",
            context={"memory_percent": 82, "threshold": 80},
            timestamp=now - timedelta(minutes=35),
        ),
    ]

    # ── 9. Governance Checks (8 checks) ──────────────────────────
    for i, (schema_id, policy_id, passed, severity) in enumerate([
        ("epistemic_safety", "ep_01", True, "info"),
        ("epistemic_safety", "ep_02", True, "info"),
        ("boundary_enforcement", "be_01", True, "info"),
        ("boundary_enforcement", "be_02", True, "info"),
        ("ethical_guidelines", "eg_01", False, "critical"),
        ("operational_integrity", "op_01", True, "info"),
        ("operational_integrity", "op_02", False, "warning"),
        ("reflective_continuity", "rc_01", True, "info"),
    ]):
        _mock_checks.append(
            GovernanceCheckResult(
                check_id=uuid4(),
                schema_id=schema_id,
                policy_id=policy_id,
                passed=passed,
                violation=_mock_violations[2] if not passed and schema_id == "ethical_guidelines" else
                         _mock_violations[1] if not passed and schema_id == "epistemic_safety" else
                         _mock_violations[3] if not passed and schema_id == "operational_integrity" else None,
                timestamp=now - timedelta(minutes=58 - i),
            )
        )

    _mock_data_initialized = True
    logger.info("Mock data initialized: %d schemas, %d transitions, %d memories, %d events, %d traces",
                len(_mock_schemas), len(_mock_transitions), len(_mock_memories),
                len(_mock_audit_events), len(_mock_traces))


# ---------------------------------------------------------------------------
# Dependency functions
# ---------------------------------------------------------------------------

def get_registry() -> GovernanceRegistry:
    """Return an initialized GovernanceRegistry.

    In production this loads schemas from disk.  For the operator API we
    also populate the mock data store so that the dashboard sees realistic
    content immediately.
    """
    global _registry
    _init_mock_data()
    if _registry is None:
        loader = SchemaLoader("governance/schemas")
        _registry = GovernanceRegistry(loader)
        try:
            _registry.initialize()
        except Exception as exc:
            logger.warning("Could not initialize registry from disk (%s); using mock schemas", exc)
            # Fall back to mock schemas — we inject them directly
            for schema in _mock_schemas:
                _registry._schemas[schema.schema_id] = schema
                _registry._active.add(schema.schema_id)
            _registry._initialized = True
    return _registry


def get_mock_schemas() -> list[GovernanceSchema]:
    """Return mock schemas (for use when registry cannot load from disk)."""
    _init_mock_data()
    return _mock_schemas


def get_mock_active_schema_ids() -> set[str]:
    """Return set of currently active schema IDs."""
    _init_mock_data()
    return set(_mock_active_schemas)


def get_state_machine() -> Any:
    """Return a lightweight state-machine-like object for read-only queries.

    The real CognitiveStateMachine requires a validator and enforcer.  We
    return a mock object that exposes the same read API.
    """
    _init_mock_data()

    class _MockStateMachine:
        def __init__(self) -> None:
            self._state = OperationalState.COGNITION_ACTIVE
            self._transitions = _mock_transitions

        def get_current_state(self) -> OperationalState:
            return self._state

        def get_state_history(self) -> list[StateTransition]:
            return list(self._transitions)

        def _can_transition(self, from_state: OperationalState, to_state: OperationalState) -> bool:
            from cognition.state_machine import CognitiveStateMachine
            return to_state in CognitiveStateMachine.VALID_TRANSITIONS.get(from_state, [])

        async def transition(self, to_state: OperationalState, trigger: str) -> bool:
            # Read-only: we do NOT actually transition, we just validate
            if not self._can_transition(self._state, to_state):
                return False
            self._state = to_state
            return True

    global _state_machine
    if _state_machine is None:
        _state_machine = _MockStateMachine()
    return _state_machine


def get_audit_events() -> list[AuditEvent]:
    """Return the mock audit event store."""
    _init_mock_data()
    return _mock_audit_events


def get_mock_memories() -> list[EpisodicMemory]:
    """Return the mock memory store."""
    _init_mock_data()
    return _mock_memories


def get_mock_influences() -> list[MemoryInfluence]:
    """Return the mock influence store."""
    _init_mock_data()
    return _mock_influences


def get_mock_traces() -> list[dict[str, Any]]:
    """Return the mock trace store."""
    _init_mock_data()
    return _mock_traces


def get_mock_transitions() -> list[StateTransition]:
    """Return the mock transition store."""
    _init_mock_data()
    return list(_mock_transitions)


def get_mock_sessions() -> list[dict[str, Any]]:
    """Return the mock session store."""
    _init_mock_data()
    return _mock_sessions


def get_mock_violations() -> list[GovernanceViolation]:
    """Return the mock violations store."""
    _init_mock_data()
    return _mock_violations


def get_mock_checks() -> list[GovernanceCheckResult]:
    """Return the mock checks store."""
    _init_mock_data()
    return _mock_checks


def get_uptime_seconds() -> float:
    """Return mock uptime in seconds."""
    return time.monotonic() - _MOCK_START_TIME


def set_mock_schema_active(schema_id: str, active: bool) -> None:
    """Update the active status of a mock schema."""
    global _mock_active_schemas
    _init_mock_data()
    if active:
        _mock_active_schemas.add(schema_id)
    else:
        _mock_active_schemas.discard(schema_id)
