"""Pydantic models for the GARVIS Operator API.

Request/response schemas that wrap the core domain models for API
serialization.  All models are JSON-serialisable and carry governance
context headers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from models.governance import GovernanceSchema, GovernanceConstraint, GovernancePolicy, GovernanceViolation, GovernanceCheckResult
from models.cognition import OperationalState, StateTransition, ForbiddenStatePattern
from models.memory import EpisodicMemory, MemoryInfluence
from models.audit import AuditEvent, CognitionTrace


# ---------------------------------------------------------------------------
# Pagination / list helpers
# ---------------------------------------------------------------------------


class PaginatedResponse(BaseModel):
    """Mixin for paginated list responses."""

    total: int = Field(description="Total number of items available")
    page: int = Field(description="Current page number (1-based)")
    per_page: int = Field(description="Items per page")
    pages: int = Field(description="Total number of pages")


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------


class SchemaSummary(BaseModel):
    """Lightweight schema info for list views."""

    schema_id: str
    name: str
    version: str
    category: str
    description: str
    active: bool
    policy_count: int
    constraint_count: int
    fail_closed: bool


class SchemaListResponse(PaginatedResponse):
    """Paginated list of schema summaries."""

    items: list[SchemaSummary]


class SchemaCategoriesResponse(BaseModel):
    """Schema categories with counts."""

    categories: dict[str, int] = Field(description="Category name -> count")


class ConstraintsByScopeResponse(BaseModel):
    """Constraints grouped by scope."""

    scope: str
    constraints: list[GovernanceConstraint]


class ViolationListResponse(PaginatedResponse):
    """Paginated list of violations."""

    items: list[GovernanceViolation]


class EnforcementChainResponse(BaseModel):
    """Enforcement chain for a scope."""

    scope: str
    constraints: list[GovernanceConstraint]


# ---------------------------------------------------------------------------
# Cognition
# ---------------------------------------------------------------------------


class StateResponse(BaseModel):
    """Current operational state with metadata."""

    current_state: str
    state_label: str = Field(description="Human-readable state name")
    valid_next_states: list[str]
    state_history_length: int
    forbidden_patterns_detected: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StatesResponse(BaseModel):
    """All possible operational states."""

    states: list[dict[str, str]] = Field(description="List of {value, label}")


class TransitionRequest(BaseModel):
    """Request body for POST /transition."""

    to_state: str = Field(description="Target OperationalState value")
    trigger: str = Field(description="Human-readable reason for the transition")


class TransitionResult(BaseModel):
    """Result of a requested state transition."""

    success: bool
    from_state: str
    to_state: str
    trigger: str
    transition_id: UUID | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TransitionsListResponse(PaginatedResponse):
    """Paginated list of state transitions."""

    items: list[StateTransition]


class ValidTransitionsResponse(BaseModel):
    """Valid transitions from the current state."""

    from_state: str
    transitions: list[dict[str, Any]]


class ForbiddenPatternsResponse(BaseModel):
    """All forbidden state patterns."""

    patterns: list[ForbiddenStatePattern]


class SessionInfo(BaseModel):
    """Lightweight session information."""

    session_id: UUID
    status: str
    trace_count: int
    created_at: datetime
    last_activity: datetime | None = None


class SessionsListResponse(PaginatedResponse):
    """Paginated list of sessions."""

    items: list[SessionInfo]


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class MemoryListResponse(PaginatedResponse):
    """Paginated list of episodic memories."""

    items: list[EpisodicMemory]


class MemorySearchRequest(BaseModel):
    """Search parameters for memory search."""

    query: str | None = None
    episode_type: str | None = None
    session_id: UUID | None = None
    since: datetime | None = None
    confidence_min: float = 0.0
    confidence_max: float = 1.0


class MemorySearchResponse(PaginatedResponse):
    """Paginated search results for memories."""

    items: list[EpisodicMemory]
    query: str | None = None


class InfluenceListResponse(PaginatedResponse):
    """Paginated list of memory influences."""

    items: list[MemoryInfluence]


# ---------------------------------------------------------------------------
# Traceability
# ---------------------------------------------------------------------------


class TraceListResponse(PaginatedResponse):
    """Paginated list of cognition traces."""

    items: list[dict[str, Any]] = Field(description="Lightweight trace summaries")


class TraceDetailResponse(BaseModel):
    """Full trace with all details."""

    trace: CognitionTrace


class TraceGraphResponse(BaseModel):
    """Trace lineage graph."""

    trace_id: UUID
    graph: dict[str, Any]


class TraceRenderResponse(BaseModel):
    """Rendered trace in requested format."""

    trace_id: UUID
    format: str
    content: str


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class AuditEventListResponse(PaginatedResponse):
    """Paginated list of audit events."""

    items: list[AuditEvent]


class AuditEventSummaryResponse(BaseModel):
    """Summary of audit events by type and severity."""

    by_type: dict[str, int]
    by_severity: dict[str, int]
    by_component: dict[str, int]
    total: int
    period_start: str | None = None


class ViolationsSummaryResponse(BaseModel):
    """Summary of governance violations."""

    by_severity: dict[str, int]
    by_schema: dict[str, int]
    total: int
    period_start: str | None = None


class ChecksListResponse(PaginatedResponse):
    """Paginated list of governance check results."""

    items: list[GovernanceCheckResult]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class AnalyticsOverview(BaseModel):
    """High-level analytics overview."""

    total_sessions: int
    total_traces: int
    total_inferences: int
    total_violations: int
    active_schemas: int
    total_schemas: int
    current_state: str
    uptime_seconds: float
    avg_inference_time_ms: float
    pass_rate_percent: float
    alignment_score: float


class GovernancePressureMetrics(BaseModel):
    """Governance pressure metrics over time."""

    timestamps: list[str]
    values: list[float]
    avg_pressure: float
    peak_pressure: float
    current_pressure: float


class AlignmentTrendsMetrics(BaseModel):
    """Alignment persistence trends."""

    timestamps: list[str]
    alignment_scores: list[float]
    avg_alignment: float
    trend_direction: str  # "improving", "stable", "declining"


class UncertaintyDisclosureMetrics(BaseModel):
    """Uncertainty disclosure rate metrics."""

    timestamps: list[str]
    disclosure_rates: list[float]
    avg_rate: float
    current_rate: float


class ContinuityStabilityMetrics(BaseModel):
    """Session continuity and stability metrics."""

    timestamps: list[str]
    continuity_scores: list[float]
    recovery_events: int
    degradation_events: int
    stability_score: float


class DegradationTrendsMetrics(BaseModel):
    """Degradation and recovery trend metrics."""

    timestamps: list[str]
    degradation_counts: list[int]
    recovery_counts: list[int]
    avg_recovery_time_seconds: float


class ResilienceMetrics(BaseModel):
    """Resilience analytics."""

    timestamps: list[str]
    resilience_scores: list[float]
    current_score: float
    trend: str
    mtbf_seconds: float  # mean time between failures
    mttr_seconds: float  # mean time to recovery


class CognitionQualityMetrics(BaseModel):
    """Reasoning quality trend metrics."""

    timestamps: list[str]
    quality_scores: list[float]
    avg_quality: float
    current_quality: float
    reasoning_depth_avg: float


class CognitionEcosystemData(BaseModel):
    """Full cognition ecosystem graph data."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    node_count: int
    edge_count: int


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


class ComponentStatus(BaseModel):
    """Status of a single component."""

    name: str
    status: str  # "healthy", "degraded", "unavailable", "unknown"
    details: dict[str, Any] = Field(default_factory=dict)
    last_check: datetime = Field(default_factory=datetime.utcnow)


class StatusResponse(BaseModel):
    """Runtime status overview."""

    runtime_version: str
    current_state: str
    uptime_seconds: float
    start_time: datetime
    component_count: int
    active_sessions: int
    total_inferences: int
    schemas_loaded: int
    schemas_active: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str  # "healthy", "degraded", "unhealthy"
    checks: dict[str, ComponentStatus]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ComponentsResponse(BaseModel):
    """List of all component statuses."""

    components: list[ComponentStatus]


class MetricsResponse(BaseModel):
    """Key runtime metrics."""

    inferences_total: int
    inferences_passed: int
    inferences_failed: int
    violations_total: int
    violations_critical: int
    violations_warning: int
    avg_response_time_ms: float
    memory_entries: int
    trace_count: int
    session_count: int
    last_inference_at: str | None = None
