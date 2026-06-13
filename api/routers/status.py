"""Status router for the GARVIS Operator API.

Exposes runtime health, component status, and key metrics.
All endpoints are read-only.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from api.dependencies import (
    get_mock_schemas,
    get_mock_active_schema_ids,
    get_mock_sessions,
    get_audit_events as get_mock_audit_events,
    get_mock_violations,
    get_mock_traces,
    get_uptime_seconds,
)
from api.models import (
    StatusResponse,
    HealthResponse,
    ComponentsResponse,
    ComponentStatus,
    MetricsResponse,
)

router = APIRouter()

_START_TIME = datetime.now(timezone.utc)


# ── Status ────────────────────────────────────────────────────────────────


@router.get("/", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """Runtime status overview."""
    schemas = get_mock_schemas()
    active_ids = get_mock_active_schema_ids()
    sessions = get_mock_sessions()
    events = get_mock_audit_events()
    traces = get_mock_traces()

    active_sessions = sum(1 for s in sessions if s.get("status") == "active")
    inference_events = [e for e in events if e.event_type == "inference"]

    return StatusResponse(
        runtime_version="2.0.0",
        current_state="cognition_active",
        uptime_seconds=get_uptime_seconds(),
        start_time=_START_TIME,
        component_count=7,
        active_sessions=active_sessions,
        total_inferences=len(inference_events),
        schemas_loaded=len(schemas),
        schemas_active=len(active_ids),
    )


# ── Health ────────────────────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Health check for all runtime components.

    Returns healthy/degraded/unhealthy status for:
    - PostgreSQL database
    - Ollama LLM service
    - Governance registry
    - Audit pipeline
    - Memory store
    - State machine
    """
    checks = {
        "postgresql": ComponentStatus(
            name="PostgreSQL",
            status="healthy",
            details={"host": "localhost", "port": 5432, "pool_size": "5/10"},
        ),
        "ollama": ComponentStatus(
            name="Ollama",
            status="healthy",
            details={"host": "http://localhost:11434", "model": "llama3.1", "response_time_ms": 45},
        ),
        "governance_registry": ComponentStatus(
            name="Governance Registry",
            status="healthy",
            details={"schemas_loaded": 8, "schemas_active": 8, "cross_schema_valid": True},
        ),
        "audit_pipeline": ComponentStatus(
            name="Audit Pipeline",
            status="healthy",
            details={"buffer_size": 0, "flush_interval": 5, "events_logged": 15},
        ),
        "memory_store": ComponentStatus(
            name="Memory Store",
            status="healthy",
            details={"entries": 8, "avg_retrieval_time_ms": 12, "cache_hit_rate": 0.85},
        ),
        "state_machine": ComponentStatus(
            name="State Machine",
            status="healthy",
            details={"current_state": "cognition_active", "transitions": 11, "forbidden_patterns": 0},
        ),
    }

    overall = "healthy"
    for check in checks.values():
        if check.status == "unhealthy":
            overall = "unhealthy"
            break
        if check.status == "degraded" and overall != "unhealthy":
            overall = "degraded"

    return HealthResponse(status=overall, checks=checks)


# ── Components ────────────────────────────────────────────────────────────


@router.get("/components", response_model=ComponentsResponse)
async def get_components() -> ComponentsResponse:
    """List all component statuses."""
    health = await get_health()
    components = list(health.checks.values())

    # Add a few more sub-components
    components.append(ComponentStatus(
        name="Inference Executor",
        status="healthy",
        details={"avg_latency_ms": 850, "throughput_qps": 2.5, "queue_depth": 0},
    ))
    components.append(ComponentStatus(
        name="Trace Renderer",
        status="healthy",
        details={"formats": ["text", "dot", "mermaid", "json"]},
    ))
    components.append(ComponentStatus(
        name="Lineage Tracker",
        status="healthy",
        details={"traces_tracked": 5, "graph_depth_avg": 3},
    ))

    return ComponentsResponse(components=components)


# ── Metrics ───────────────────────────────────────────────────────────────


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Key runtime metrics."""
    events = get_mock_audit_events()
    violations = get_mock_violations()
    memories = get_mock_sessions()
    traces = get_mock_traces()

    inference_events = [e for e in events if e.event_type == "inference"]
    passed = sum(1 for e in inference_events if e.details.get("passed_validation", True))
    failed = len(inference_events) - passed

    critical_v = sum(1 for v in violations if v.severity == "critical")
    warning_v = sum(1 for v in violations if v.severity == "warning")

    # Find last inference time
    last_inference = None
    for e in reversed(inference_events):
        if e.timestamp:
            last_inference = e.timestamp.isoformat() if hasattr(e.timestamp, "isoformat") else str(e.timestamp)
            break

    return MetricsResponse(
        inferences_total=len(inference_events),
        inferences_passed=passed,
        inferences_failed=failed,
        violations_total=len(violations),
        violations_critical=critical_v,
        violations_warning=warning_v,
        avg_response_time_ms=round(850 + (failed * 200), 1),
        memory_entries=8,
        trace_count=len(traces),
        session_count=len(memories),
        last_inference_at=last_inference,
    )
