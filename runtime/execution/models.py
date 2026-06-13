from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field
from typing_extensions import Literal


class RuntimeCommand(BaseModel):
    command_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str = "default"
    source: Literal["text", "voice", "system", "api"] = "text"
    text: str
    project_id: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RuntimeEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    command_id: str | None = None
    session_id: str | None = None
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RuntimeResult(BaseModel):
    command_id: str
    status: Literal["accepted", "running", "completed", "blocked", "failed"]
    response_text: str = ""
    governance_decision: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    audit_event_id: str | None = None
    cognition_state_before: str | None = None
    cognition_state_after: str | None = None
    errors: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
