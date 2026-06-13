"""Cognition router for the GARVIS Operator API.

Exposes operational state, transitions, forbidden patterns, and sessions.
State transitions require explicit POST with trigger reason.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import (
    get_state_machine,
    get_mock_transitions,
    get_mock_sessions,
)
from api.models import (
    StateResponse,
    StatesResponse,
    TransitionsListResponse,
    ValidTransitionsResponse,
    ForbiddenPatternsResponse,
    TransitionRequest,
    TransitionResult,
    SessionsListResponse,
    SessionInfo,
)
from models.cognition import OperationalState, ForbiddenStatePattern, StateTransition
from cognition.state_machine import CognitiveStateMachine

router = APIRouter()


# ── State ─────────────────────────────────────────────────────────────────


@router.get("/state", response_model=StateResponse)
async def get_current_state(
    machine: Any = Depends(get_state_machine),
) -> StateResponse:
    """Get the current operational state with metadata."""
    current = machine.get_current_state()
    history = machine.get_state_history()

    # Compute valid next states from the transition graph
    valid_next = CognitiveStateMachine.VALID_TRANSITIONS.get(current, [])
    valid_names = [s.value for s in valid_next]

    return StateResponse(
        current_state=current.value,
        state_label=current.value.replace("_", " ").title(),
        valid_next_states=valid_names,
        state_history_length=len(history),
        forbidden_patterns_detected=0,
    )


@router.get("/states", response_model=StatesResponse)
async def list_all_states() -> StatesResponse:
    """List all possible operational states."""
    states = [
        {"value": s.value, "label": s.value.replace("_", " ").title()}
        for s in OperationalState
    ]
    return StatesResponse(states=states)


# ── Transitions ───────────────────────────────────────────────────────────


@router.get("/transitions", response_model=TransitionsListResponse)
async def list_transitions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    machine: Any = Depends(get_state_machine),
) -> TransitionsListResponse:
    """List recent state transitions (paginated, newest first)."""
    all_transitions = machine.get_state_history()
    total = len(all_transitions)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = list(reversed(all_transitions[start:end]))

    return TransitionsListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


@router.get("/transitions/valid", response_model=ValidTransitionsResponse)
async def get_valid_transitions(
    machine: Any = Depends(get_state_machine),
) -> ValidTransitionsResponse:
    """Get all valid transitions from the current state."""
    current = machine.get_current_state()
    valid_next = CognitiveStateMachine.VALID_TRANSITIONS.get(current, [])

    transitions = []
    for target in valid_next:
        transitions.append({
            "from_state": current.value,
            "to_state": target.value,
            "to_state_label": target.value.replace("_", " ").title(),
            "description": f"{current.value} -> {target.value}",
        })

    return ValidTransitionsResponse(from_state=current.value, transitions=transitions)


@router.get("/forbidden-patterns", response_model=ForbiddenPatternsResponse)
async def get_forbidden_patterns() -> ForbiddenPatternsResponse:
    """Get all forbidden state patterns that trigger auto fail-closed."""
    patterns = [
        ForbiddenStatePattern(
            pattern_id="recursive_inference",
            description="Inference executing directly to inference executing (recursive)",
            state_sequence=[OperationalState.INFERENCE_EXECUTING, OperationalState.INFERENCE_EXECUTING],
            detection_logic="previous.to_state == inference_executing AND current.to_state == inference_executing",
            response_action="halt",
        ),
        ForbiddenStatePattern(
            pattern_id="illegal_recovery",
            description="Fail-closed directly to cognition-active without recovery",
            state_sequence=[OperationalState.FAIL_CLOSED, OperationalState.COGNITION_ACTIVE],
            detection_logic="previous.to_state == fail_closed AND current.to_state == cognition_active",
            response_action="halt",
        ),
        ForbiddenStatePattern(
            pattern_id="degraded_inference",
            description="Degraded state attempting inference execution",
            state_sequence=[OperationalState.DEGRADED, OperationalState.INFERENCE_EXECUTING],
            detection_logic="previous.to_state == degraded AND current.to_state == inference_executing",
            response_action="degrade",
        ),
        ForbiddenStatePattern(
            pattern_id="uninitialized_active",
            description="Uninitialized state transitioning directly to cognition-active",
            state_sequence=[OperationalState.UNINITIALIZED, OperationalState.COGNITION_ACTIVE],
            detection_logic="previous.to_state == uninitialized AND current.to_state == cognition_active",
            response_action="halt",
        ),
    ]
    return ForbiddenPatternsResponse(patterns=patterns)


@router.post("/transition", response_model=TransitionResult)
async def request_transition(
    body: TransitionRequest,
    machine: Any = Depends(get_state_machine),
) -> TransitionResult:
    """Request a state transition with explicit trigger reason.

    The transition is validated against the governance transition graph
    and governance checks. Returns success/failure.
    """
    try:
        target_state = OperationalState(body.to_state)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid state: '{body.to_state}'")

    success = await machine.transition(target_state, body.trigger)
    current = machine.get_current_state()

    return TransitionResult(
        success=success,
        from_state=current.value if success else body.to_state,
        to_state=target_state.value if success else body.to_state,
        trigger=body.trigger,
        transition_id=UUID(int=0x12345678) if success else None,
    )


# ── Sessions ──────────────────────────────────────────────────────────────


@router.get("/sessions", response_model=SessionsListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> SessionsListResponse:
    """List active and closed sessions (paginated)."""
    sessions = get_mock_sessions()
    total = len(sessions)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    page_items = sessions[start:end]

    items = [
        SessionInfo(
            session_id=s["session_id"],
            status=s["status"],
            trace_count=s["trace_count"],
            created_at=s["created_at"],
            last_activity=s.get("last_activity"),
        )
        for s in page_items
    ]

    return SessionsListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID,
) -> dict[str, Any]:
    """Get detailed information about a specific session."""
    sessions = get_mock_sessions()
    for s in sessions:
        if s["session_id"] == session_id:
            return dict(s)
    raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")


@router.get("/sessions/{session_id}/transitions", response_model=TransitionsListResponse)
async def get_session_transitions(
    session_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    machine: Any = Depends(get_state_machine),
) -> TransitionsListResponse:
    """Get state transitions for a specific session."""
    all_transitions = machine.get_state_history()
    total = len(all_transitions)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = list(reversed(all_transitions[start:end]))

    return TransitionsListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)
