"""Audit Pydantic models for GARVIS."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from models.cognition import OperationalState, StateTransition
from models.governance import GovernanceCheckResult
from models.memory import MemoryInfluence


class AuditEvent(BaseModel):
    """A single auditable event in the runtime."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    severity: str  # "info", "warning", "critical"
    component: str
    session_id: UUID | None = None
    trace_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: dict[str, Any] = Field(default_factory=dict)
    governance_context: list[str] = Field(default_factory=list)


class CognitionTrace(BaseModel):
    """A complete trace of a cognition session."""

    trace_id: UUID
    session_id: UUID
    start_time: datetime
    end_time: datetime | None = None
    state_sequence: list[StateTransition] = Field(default_factory=list)
    events: list[AuditEvent] = Field(default_factory=list)
    memory_influences: list[MemoryInfluence] = Field(default_factory=list)
    governance_checks: list[GovernanceCheckResult] = Field(default_factory=list)
    final_state: OperationalState = OperationalState.UNINITIALIZED
