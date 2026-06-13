"""Cognition Pydantic models for GARVIS."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class OperationalState(str, Enum):
    """Governed operational states of the cognition runtime."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    STANDBY = "standby"
    GOVERNANCE_CHECK = "governance_check"
    COGNITION_ACTIVE = "cognition_active"
    INFERENCE_EXECUTING = "inference_executing"
    MEMORY_RETRIEVING = "memory_retrieving"
    TRACE_LOGGING = "trace_logging"
    AUDITING = "auditing"
    DEGRADED = "degraded"
    FAIL_CLOSED = "fail_closed"
    RECOVERING = "recovering"
    SHUTDOWN = "shutdown"


class StateTransition(BaseModel):
    """A validated state transition record."""

    transition_id: UUID
    from_state: OperationalState
    to_state: OperationalState
    trigger: str
    governance_check: bool
    timestamp: datetime
    trace_id: UUID


class ForbiddenStatePattern(BaseModel):
    """A pattern of states that must never occur."""

    pattern_id: str
    description: str
    state_sequence: list[OperationalState]
    detection_logic: str
    response_action: str  # e.g., "halt", "degrade", "escalate"
