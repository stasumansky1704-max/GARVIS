"""Collaboration router for the GARVIS Operator API.

Exposes collaboration sessions, operator input processing,
governance negotiation views, and bounded strategic reasoning.

All endpoints carry full governance context in responses.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from cognition.collaboration import CollaborationSession, CollaborationInteraction
from cognition.negotiation import GovernanceNegotiation
from cognition.strategy import BoundedStrategyEngine
from api.dependencies import (
    get_mock_schemas,
    get_mock_active_schema_ids,
)

logger = logging.getLogger("garvis.api.collaboration")

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory session store (production uses persistent storage)
# ---------------------------------------------------------------------------

_collaboration_sessions: dict[str, CollaborationSession] = {}
_negotiation_engine = GovernanceNegotiation()
_strategy_engine: BoundedStrategyEngine | None = None


def _get_strategy_engine() -> BoundedStrategyEngine:
    """Get or create the strategy engine with current active schemas."""
    global _strategy_engine
    if _strategy_engine is None:
        active_ids = list(get_mock_active_schema_ids())
        _strategy_engine = BoundedStrategyEngine(active_schema_ids=active_ids)
    return _strategy_engine


# ---------------------------------------------------------------------------
# Collaboration Sessions
# ---------------------------------------------------------------------------


@router.post("/sessions")
async def start_collaboration_session(
    operator_id: str = Query(..., description="Operator identifier"),
    project_id: str = Query(..., description="Project identifier"),
) -> dict[str, Any]:
    """Start a new collaboration session.

    Creates a governed collaboration session between an operator and GARVIS.
    All subsequent interactions are mediated by governance and fully audited.
    """
    session_id = f"collab_{uuid4().hex[:12]}"

    # Create session with mock validator (no DB required)
    session = CollaborationSession(
        session_id=session_id,
        operator_id=operator_id,
        project_id=project_id,
        validator=None,  # Uses internal governance simulation
        audit=None,      # Uses internal audit logging
    )

    # Store in memory
    _collaboration_sessions[session_id] = session

    logger.info(
        "Collaboration session started via API: %s (operator=%s, project=%s)",
        session_id,
        operator_id,
        project_id,
    )

    return {
        "session_id": session_id,
        "operator_id": operator_id,
        "project_id": project_id,
        "status": "active",
        "message": (
            "Collaboration session started. This is a GOVERNED COGNITION "
            "COLLABORATION — not a chatbot. Every response will include "
            "governance checks, uncertainty disclosures, and reasoning traces."
        ),
        "governance_note": (
            "All interactions are mediated by active governance schemas. "
            "Blocks and modifications will be fully explained."
        ),
    }


@router.post("/sessions/{session_id}/input")
async def submit_input(
    session_id: str,
    input_type: str = Query(..., description="Input type: query, propose_action, request_analysis, governance_review, status_check, explain_decision"),
    content: str = Query(..., description="Operator input content"),
    context: str = Query("", description="Optional JSON context string"),
) -> dict[str, Any]:
    """Submit operator input to collaboration session.

    Processes the input through full governance validation and returns
    a governed response with complete reasoning visibility.
    """
    session = _collaboration_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    if not session.is_active:
        raise HTTPException(
            status_code=400, detail=f"Session '{session_id}' is not active (status: ended)"
        )

    # Parse optional context
    ctx: dict[str, Any] = {}
    if context:
        import json
        try:
            ctx = json.loads(context)
        except json.JSONDecodeError:
            ctx = {"raw_context": context}

    # Submit to session
    result = await session.submit_operator_input(
        input_type=input_type,
        content=content,
        context=ctx,
    )

    return result


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """Get collaboration session status and history.

    Returns full session state including interaction history
    with governance context for every interaction.
    """
    session = _collaboration_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return {
        "session_id": session.session_id,
        "operator_id": session.operator_id,
        "project_id": session.project_id,
        "status": "active" if session.is_active else "ended",
        "interaction_count": session.interaction_count,
        "duration_seconds": session.duration_seconds,
        "interactions": session.get_interaction_history_as_dicts(),
        "governance_summary": session.get_governance_summary(),
    }


@router.get("/sessions/{session_id}/governance")
async def get_session_governance(session_id: str) -> dict[str, Any]:
    """Get governance summary for session.

    Returns detailed governance check statistics, violation counts,
    and uncertainty disclosure rate for the session.
    """
    session = _collaboration_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return session.get_governance_summary()


@router.post("/sessions/{session_id}/end")
async def end_collaboration_session(session_id: str) -> dict[str, Any]:
    """End a collaboration session.

    Terminates the session and returns a full summary with audit trail.
    """
    session = _collaboration_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    summary = session.end_session()

    # Remove from active sessions
    if session_id in _collaboration_sessions:
        del _collaboration_sessions[session_id]

    return summary


# ---------------------------------------------------------------------------
# Governance Negotiation
# ---------------------------------------------------------------------------


@router.get("/negotiation/explain-block")
async def explain_block(
    violation_id: str = Query(..., description="Governance violation ID"),
    schema_id: str = Query(..., description="Schema that triggered the block"),
    policy_id: str = Query(..., description="Policy that triggered the block"),
    severity: str = Query("critical", description="Violation severity"),
    description: str = Query(..., description="Violation description"),
    blocked_action: str = Query("", description="Description of blocked action"),
) -> dict[str, Any]:
    """Explain why an action was blocked.

    Returns comprehensive explanation of the governance decision
    with escalation path and uncertainty disclosure.
    """
    from models.governance import GovernanceViolation
    from datetime import datetime

    violation = GovernanceViolation(
        schema_id=schema_id,
        policy_id=policy_id,
        severity=severity,
        description=description,
        context={"violation_id": violation_id},
    )

    explanation = _negotiation_engine.explain_block(
        violation=violation,
        blocked_action=blocked_action or "the requested action",
    )

    return explanation


@router.get("/negotiation/explain-modification")
async def explain_modification(
    original: str = Query(..., description="Original content"),
    mediated: str = Query(..., description="Mediated content"),
    schemas: str = Query(..., description="Comma-separated schema IDs"),
) -> dict[str, Any]:
    """Explain how governance modified content.

    Shows what changed and why, with full governance context.
    """
    schema_list = [s.strip() for s in schemas.split(",") if s.strip()]

    explanation = _negotiation_engine.explain_modification(
        original=original,
        mediated=mediated,
        schemas_applied=schema_list,
    )

    return explanation


@router.get("/negotiation/uncertainty")
async def explain_uncertainty(
    confidence: float = Query(..., ge=0.0, le=1.0, description="Confidence score"),
    topic: str = Query("the requested analysis", description="Topic being analyzed"),
) -> dict[str, Any]:
    """Explain uncertainty in a given context.

    Provides structured uncertainty disclosure with sources
    and confidence basis.
    """
    context = {
        "confidence_score": confidence,
        "topic": topic,
        "reasoning_steps": ["operator_requested_analysis"],
        "memory_sources": [],
        "governance_checks": [],
    }

    return _negotiation_engine.explain_uncertainty(context)


@router.get("/negotiation/view/{session_id}")
async def get_negotiation_view(session_id: str) -> dict[str, Any]:
    """Get full negotiation view for a session.

    Shows all governance decisions with explanations for a
    collaboration session.
    """
    session = _collaboration_sessions.get(session_id)
    interactions: list[dict[str, Any]] = []
    if session is not None:
        interactions = session.get_interaction_history_as_dicts()

    return _negotiation_engine.generate_negotiation_view(
        session_id=session_id,
        interactions=interactions,
    )


@router.get("/negotiation/approval-path")
async def get_approval_path(
    blocked_action: str = Query(..., description="Description of blocked action"),
) -> dict[str, Any]:
    """Get step-by-step approval path for a blocked action.

    Returns the governance requirements and steps needed
    to potentially approve a blocked action.
    """
    return _negotiation_engine.suggest_approval_path(blocked_action)


# ---------------------------------------------------------------------------
# Bounded Strategic Reasoning
# ---------------------------------------------------------------------------


@router.get("/strategy/trajectory/{project_id}")
async def get_project_trajectory(project_id: str) -> dict[str, Any]:
    """Get strategic trajectory analysis.

    Returns governance-safe recommendations for project direction
    with full reasoning visibility.
    """
    engine = _get_strategy_engine()
    return engine.analyze_project_trajectory(project_id)


@router.get("/strategy/forecast/{project_id}")
async def get_operational_forecast(
    project_id: str,
    horizon: str = Query("30d", description="Forecast horizon: 7d, 30d, 90d"),
) -> dict[str, Any]:
    """Get operational needs forecast.

    Returns bounded operational forecasting within governance constraints.
    """
    engine = _get_strategy_engine()
    return engine.forecast_operational_needs(project_id, time_horizon=horizon)


@router.get("/strategy/readiness/{project_id}")
async def get_operational_readiness(project_id: str) -> dict[str, Any]:
    """Get operational readiness assessment.

    Returns governance-bounded readiness evaluation with
    specific criteria and recommendations.
    """
    engine = _get_strategy_engine()
    return engine.assess_operational_readiness(project_id)


@router.get("/strategy/governance-recommendations/{project_id}")
async def get_governance_recommendations(project_id: str) -> dict[str, Any]:
    """Get governance adjustment recommendations.

    Returns recommendations that ALL require operator approval.
    The system NEVER auto-adjusts governance.
    """
    engine = _get_strategy_engine()
    return engine.recommend_governance_adjustments(project_id)


@router.get("/strategy/cognitive-strategy")
async def get_cognitive_strategy(
    objective: str = Query(..., description="Strategic objective"),
    constraints: str = Query("", description="Comma-separated constraints"),
) -> dict[str, Any]:
    """Generate a bounded cognitive strategy.

    Returns a governance-safe strategy with uncertainty disclosures
    and full reasoning trace.
    """
    engine = _get_strategy_engine()
    constraint_list = [c.strip() for c in constraints.split(",") if c.strip()]
    return engine.generate_cognitive_strategy(objective, constraint_list)
