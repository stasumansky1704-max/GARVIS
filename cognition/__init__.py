"""Cognition Layer for GARVIS.

Manages the governed operational state machine, transitions,
forbidden state detection, and session management.
"""

from cognition.state_machine import CognitiveStateMachine
from cognition.transitions import (
    StateTransition as TransitionsModule,
    TransitionRule,
    TransitionValidator,
    standby_to_active,
    active_to_inference,
    inference_to_active,
    any_to_fail_closed,
    fail_closed_to_recovering,
)
from cognition.forbidden import (
    ForbiddenPatternDetector,
    ForbiddenStatePattern,
)
from cognition.session import CognitionSession, SessionManager
from models.cognition import OperationalState, StateTransition, ForbiddenStatePattern

__all__ = [
    # Main state machine
    "CognitiveStateMachine",
    # Models
    "StateTransition",
    "ForbiddenStatePattern",
    "OperationalState",
    # Transitions
    "TransitionRule",
    "TransitionValidator",
    "standby_to_active",
    "active_to_inference",
    "inference_to_active",
    "any_to_fail_closed",
    "fail_closed_to_recovering",
    # Forbidden
    "ForbiddenPatternDetector",
    # Session
    "CognitionSession",
    "SessionManager",
]
