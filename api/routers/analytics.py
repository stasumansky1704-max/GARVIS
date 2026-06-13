"""Analytics router for the GARVIS Operator API.

Provides aggregated metrics and trend data for the operator dashboard.
All endpoints serve mock analytics data that reflects realistic patterns.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter

from api.dependencies import (
    get_mock_schemas,
    get_mock_active_schema_ids,
    get_mock_traces,
    get_mock_memories,
    get_audit_events as get_mock_audit_events,
    get_mock_violations,
    get_mock_sessions,
    get_uptime_seconds,
)
from api.models import (
    AnalyticsOverview,
    GovernancePressureMetrics,
    AlignmentTrendsMetrics,
    UncertaintyDisclosureMetrics,
    ContinuityStabilityMetrics,
    DegradationTrendsMetrics,
    ResilienceMetrics,
    CognitionQualityMetrics,
    CognitionEcosystemData,
)

router = APIRouter()


# ── Helper: generate time series ──────────────────────────────────────────

def _generate_time_series(
    points: int = 24,
    base: float = 0.5,
    variance: float = 0.2,
    offset_minutes: int = 0,
) -> tuple[list[str], list[float]]:
    """Generate a mock time series with timestamps."""
    now = datetime.now(timezone.utc)
    timestamps = []
    values = []

    for i in range(points):
        ts = now - timedelta(minutes=offset_minutes + (points - i) * 5)
        timestamps.append(ts.isoformat())
        val = base + random.uniform(-variance, variance)
        values.append(max(0.0, min(1.0, val)))

    return timestamps, values


# ── Overview ──────────────────────────────────────────────────────────────


@router.get("/overview", response_model=AnalyticsOverview)
async def get_analytics_overview() -> AnalyticsOverview:
    """High-level analytics overview of the GARVIS runtime."""
    schemas = get_mock_schemas()
    active_ids = get_mock_active_schema_ids()
    traces = get_mock_traces()
    events = get_mock_audit_events()
    violations = get_mock_violations()
    sessions = get_mock_sessions()

    # Count inference events
    inference_events = [e for e in events if e.event_type == "inference"]
    passed = sum(1 for e in inference_events if e.details.get("passed_validation", True))

    return AnalyticsOverview(
        total_sessions=len(sessions),
        total_traces=len(traces),
        total_inferences=len(inference_events),
        total_violations=len(violations),
        active_schemas=len(active_ids),
        total_schemas=len(schemas),
        current_state="cognition_active",
        uptime_seconds=get_uptime_seconds(),
        avg_inference_time_ms=round(random.uniform(800, 2500), 1),
        pass_rate_percent=round((passed / len(inference_events) * 100) if inference_events else 100, 1),
        alignment_score=round(random.uniform(0.70, 0.95), 2),
    )


# ── Governance Pressure ───────────────────────────────────────────────────


@router.get("/governance-pressure", response_model=GovernancePressureMetrics)
async def get_governance_pressure() -> GovernancePressureMetrics:
    """Governance pressure metrics — how heavily governance is constraining inference."""
    timestamps, values = _generate_time_series(points=24, base=0.35, variance=0.15)

    return GovernancePressureMetrics(
        timestamps=timestamps,
        values=[round(v, 2) for v in values],
        avg_pressure=round(sum(values) / len(values), 2),
        peak_pressure=round(max(values), 2),
        current_pressure=round(values[-1], 2),
    )


# ── Alignment Trends ──────────────────────────────────────────────────────


@router.get("/alignment-trends", response_model=AlignmentTrendsMetrics)
async def get_alignment_trends() -> AlignmentTrendsMetrics:
    """Alignment persistence trends across sessions."""
    timestamps, values = _generate_time_series(points=24, base=0.82, variance=0.08)

    avg_val = sum(values) / len(values)
    trend = "improving" if values[-1] > avg_val + 0.05 else "stable" if values[-1] > avg_val - 0.05 else "declining"

    return AlignmentTrendsMetrics(
        timestamps=timestamps,
        alignment_scores=[round(v, 2) for v in values],
        avg_alignment=round(avg_val, 2),
        trend_direction=trend,
    )


# ── Uncertainty Disclosure ────────────────────────────────────────────────


@router.get("/uncertainty-disclosure", response_model=UncertaintyDisclosureMetrics)
async def get_uncertainty_disclosure() -> UncertaintyDisclosureMetrics:
    """Rate at which the system discloses uncertainty in responses."""
    timestamps, values = _generate_time_series(points=24, base=0.75, variance=0.12)

    return UncertaintyDisclosureMetrics(
        timestamps=timestamps,
        disclosure_rates=[round(v, 2) for v in values],
        avg_rate=round(sum(values) / len(values), 2),
        current_rate=round(values[-1], 2),
    )


# ── Continuity / Stability ────────────────────────────────────────────────


@router.get("/continuity-stability", response_model=ContinuityStabilityMetrics)
async def get_continuity_stability() -> ContinuityStabilityMetrics:
    """Session continuity and stability metrics."""
    timestamps, values = _generate_time_series(points=24, base=0.88, variance=0.06)

    return ContinuityStabilityMetrics(
        timestamps=timestamps,
        continuity_scores=[round(v, 2) for v in values],
        recovery_events=random.randint(0, 3),
        degradation_events=random.randint(0, 5),
        stability_score=round(values[-1], 2),
    )


# ── Degradation Trends ────────────────────────────────────────────────────


@router.get("/degradation-trends", response_model=DegradationTrendsMetrics)
async def get_degradation_trends() -> DegradationTrendsMetrics:
    """Degradation and recovery trend metrics."""
    timestamps_degrade, degradations = _generate_time_series(points=24, base=0.08, variance=0.06)
    _, recoveries = _generate_time_series(points=24, base=0.05, variance=0.04)

    return DegradationTrendsMetrics(
        timestamps=timestamps_degrade,
        degradation_counts=[round(d * 10) for d in degradations],
        recovery_counts=[round(r * 10) for r in recoveries],
        avg_recovery_time_seconds=round(random.uniform(15, 120), 1),
    )


# ── Resilience ────────────────────────────────────────────────────────────


@router.get("/resilience-metrics", response_model=ResilienceMetrics)
async def get_resilience_metrics() -> ResilienceMetrics:
    """Resilience analytics — ability to recover from failures."""
    timestamps, values = _generate_time_series(points=24, base=0.85, variance=0.10)

    avg_val = sum(values) / len(values)
    trend = "improving" if values[-1] > avg_val + 0.05 else "stable" if values[-1] > avg_val - 0.05 else "declining"

    return ResilienceMetrics(
        timestamps=timestamps,
        resilience_scores=[round(v, 2) for v in values],
        current_score=round(values[-1], 2),
        trend=trend,
        mtbf_seconds=round(random.uniform(1800, 7200), 1),
        mttr_seconds=round(random.uniform(10, 60), 1),
    )


# ── Cognition Quality ─────────────────────────────────────────────────────


@router.get("/cognition-quality", response_model=CognitionQualityMetrics)
async def get_cognition_quality() -> CognitionQualityMetrics:
    """Reasoning quality trend metrics."""
    timestamps, values = _generate_time_series(points=24, base=0.80, variance=0.10)

    return CognitionQualityMetrics(
        timestamps=timestamps,
        quality_scores=[round(v, 2) for v in values],
        avg_quality=round(sum(values) / len(values), 2),
        current_quality=round(values[-1], 2),
        reasoning_depth_avg=round(random.uniform(2.5, 5.0), 1),
    )


# ── Cognition Ecosystem ───────────────────────────────────────────────────


@router.get("/cognition-ecosystem", response_model=CognitionEcosystemData)
async def get_cognition_ecosystem() -> CognitionEcosystemData:
    """Full cognition ecosystem graph data.

    Returns nodes and edges representing the relationships between
    schemas, policies, constraints, memories, inferences, and audit events.
    """
    schemas = get_mock_schemas()
    active_ids = get_mock_active_schema_ids()
    memories = get_mock_memories()
    events = get_mock_audit_events()
    violations = get_mock_violations()

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    # Schema nodes
    for schema in schemas:
        node_id = f"schema:{schema.schema_id}"
        nodes.append({
            "id": node_id,
            "type": "schema",
            "label": schema.name,
            "category": schema.category,
            "active": schema.schema_id in active_ids,
            "policy_count": len(schema.policies),
            "constraint_count": len(schema.constraints),
        })

        # Policy nodes + edges
        for policy in schema.policies:
            policy_id = f"policy:{schema.schema_id}:{policy.policy_id}"
            nodes.append({
                "id": policy_id,
                "type": "policy",
                "label": policy.policy_id,
                "severity": policy.severity,
                "rule_type": policy.rule_type,
            })
            edges.append({"from": node_id, "to": policy_id, "type": "contains"})

        # Constraint nodes + edges
        for constraint in schema.constraints:
            constraint_id = f"constraint:{schema.schema_id}:{constraint.constraint_id}"
            nodes.append({
                "id": constraint_id,
                "type": "constraint",
                "label": constraint.constraint_id,
                "scope": constraint.scope,
                "enforcement": constraint.enforcement,
            })
            edges.append({"from": node_id, "to": constraint_id, "type": "enforces"})

    # Memory nodes
    for mem in memories[:6]:  # Limit to 6 for readability
        mem_id = f"memory:{mem.memory_id}"
        nodes.append({
            "id": mem_id,
            "type": "memory",
            "label": mem.episode_type,
            "confidence": mem.confidence,
            "retrieval_count": mem.retrieval_count,
        })

    # Violation nodes
    for v in violations:
        v_id = f"violation:{v.violation_id}"
        nodes.append({
            "id": v_id,
            "type": "violation",
            "label": v.severity,
            "schema": v.schema_id,
        })
        # Connect violation to its schema
        schema_node = f"schema:{v.schema_id}"
        edges.append({"from": schema_node, "to": v_id, "type": "violated_by"})

    # Audit event nodes (sample)
    for e in events[:5]:
        e_id = f"event:{e.event_id}"
        nodes.append({
            "id": e_id,
            "type": "audit_event",
            "label": e.event_type,
            "severity": e.severity,
        })

    return CognitionEcosystemData(
        nodes=nodes,
        edges=edges,
        node_count=len(nodes),
        edge_count=len(edges),
    )
