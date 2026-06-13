"""Audit router for the GARVIS Operator API.

Exposes audit events, violations, governance check results,
and a Server-Sent Events (SSE) stream for real-time event feed.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from api.dependencies import (
    get_audit_events as get_mock_audit_events,
    get_mock_violations,
    get_mock_checks,
)
from api.models import (
    AuditEventListResponse,
    AuditEventSummaryResponse,
    ViolationsSummaryResponse,
    ChecksListResponse,
)

router = APIRouter()


# ── Events ────────────────────────────────────────────────────────────────


@router.get("/events", response_model=AuditEventListResponse)
async def list_events(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    event_type: str | None = Query(None),
    severity: str | None = Query(None),
    component: str | None = Query(None),
    session_id: UUID | None = Query(None),
) -> AuditEventListResponse:
    """List audit events (paginated, filterable).

    Filter by event_type, severity, component, or session_id.
    """
    events = get_mock_audit_events()

    if event_type:
        events = [e for e in events if e.event_type == event_type]
    if severity:
        events = [e for e in events if e.severity == severity]
    if component:
        events = [e for e in events if e.component == component]
    if session_id:
        events = [e for e in events if e.session_id == session_id]

    total = len(events)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = list(reversed(events[start:end]))  # Newest first

    return AuditEventListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


@router.get("/events/summary", response_model=AuditEventSummaryResponse)
async def get_event_summary(
    since: datetime | None = Query(None),
) -> AuditEventSummaryResponse:
    """Get a summary of audit events grouped by type and severity."""
    events = get_mock_audit_events()

    if since:
        events = [e for e in events if e.timestamp >= since]

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_component: dict[str, int] = {}

    for e in events:
        by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
        by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
        by_component[e.component] = by_component.get(e.component, 0) + 1

    return AuditEventSummaryResponse(
        by_type=by_type,
        by_severity=by_severity,
        by_component=by_component,
        total=len(events),
        period_start=since.isoformat() if since else None,
    )


@router.get("/events/stream")
async def event_stream(request: Request) -> StreamingResponse:
    """Server-Sent Events (SSE) stream of audit events.

    Streams real-time audit events as they occur.  In mock mode,
    generates synthetic events at regular intervals.
    """
    async def _generate():
        event_id = 0
        event_types = ["heartbeat", "inference", "governance_check", "memory_retrieval", "state_transition"]
        severities = ["info", "info", "info", "warning", "info"]
        components = ["runtime.core", "inference.executor", "governance.validator",
                      "memory.store", "cognition.state_machine"]

        while True:
            if await request.is_disconnected():
                break

            idx = event_id % len(event_types)
            event = {
                "event_id": str(UUID(int=event_id)),
                "event_type": event_types[idx],
                "severity": severities[idx],
                "component": components[idx],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {"seq": event_id, "mock": True},
            }

            yield f"event: audit_event\n"
            yield f"id: {event_id}\n"
            yield f"data: {json.dumps(event)}\n\n"

            event_id += 1
            await asyncio.sleep(5)  # Send an event every 5 seconds

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Violations ────────────────────────────────────────────────────────────


@router.get("/violations/list", response_model=AuditEventListResponse)
async def list_violations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    severity: str | None = Query(None),
    schema_id: str | None = Query(None),
) -> AuditEventListResponse:
    """List governance violation records (paginated, filterable)."""
    events = get_mock_audit_events()
    violations = [e for e in events if e.event_type == "violation"]

    if severity:
        violations = [v for v in violations if v.severity == severity]
    if schema_id:
        violations = [v for v in violations if v.details.get("schema_id") == schema_id]

    total = len(violations)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = list(reversed(violations[start:end]))

    return AuditEventListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


@router.get("/violations/summary", response_model=ViolationsSummaryResponse)
async def get_violation_summary(
    since: datetime | None = Query(None),
) -> ViolationsSummaryResponse:
    """Get a summary of violations grouped by severity and schema."""
    violations = get_mock_violations()

    if since:
        violations = [v for v in violations if v.timestamp >= since]

    by_severity: dict[str, int] = {}
    by_schema: dict[str, int] = {}

    for v in violations:
        by_severity[v.severity] = by_severity.get(v.severity, 0) + 1
        by_schema[v.schema_id] = by_schema.get(v.schema_id, 0) + 1

    return ViolationsSummaryResponse(
        by_severity=by_severity,
        by_schema=by_schema,
        total=len(violations),
        period_start=since.isoformat() if since else None,
    )


# ── Checks ────────────────────────────────────────────────────────────────


@router.get("/checks", response_model=ChecksListResponse)
async def list_checks(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    schema_id: str | None = Query(None),
    passed: bool | None = Query(None),
) -> ChecksListResponse:
    """List governance check results (paginated, filterable)."""
    checks = get_mock_checks()

    if schema_id:
        checks = [c for c in checks if c.schema_id == schema_id]
    if passed is not None:
        checks = [c for c in checks if c.passed == passed]

    total = len(checks)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = checks[start:end]

    return ChecksListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


@router.get("/checks/{trace_id}")
async def get_trace_checks(
    trace_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ChecksListResponse:
    """Get governance check results for a specific trace."""
    checks = get_mock_checks()

    # In mock mode, all checks are associated with all traces
    total = len(checks)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = checks[start:end]

    return ChecksListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)
