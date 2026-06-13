"""Forbidden state pattern detection for the GARVIS cognition layer.

Implements detection logic for all forbidden state sequences that
violate governance constraints. Each forbidden pattern has a unique
detector method and an associated response action.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from models.cognition import (
    ForbiddenStatePattern,
    OperationalState,
    StateTransition,
)

if TYPE_CHECKING:
    from cognition.state_machine import CognitiveStateMachine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in forbidden pattern definitions
# ---------------------------------------------------------------------------

PATTERN_DEFINITIONS: list[ForbiddenStatePattern] = [
    ForbiddenStatePattern(
        pattern_id="recursive_inference",
        description="Two consecutive INFERENCE_EXECUTING states are forbidden. "
                    "No recursive inference without returning to COGNITION_ACTIVE first.",
        state_sequence=[
            OperationalState.INFERENCE_EXECUTING,
            OperationalState.INFERENCE_EXECUTING,
        ],
        detection_logic="detect_recursive_inference",
        response_action="halt",
    ),
    ForbiddenStatePattern(
        pattern_id="illegal_recovery",
        description="FAIL_CLOSED directly to COGNITION_ACTIVE is forbidden. "
                    "Must recover through RECOVERING -> STANDBY -> GOVERNANCE_CHECK path.",
        state_sequence=[
            OperationalState.FAIL_CLOSED,
            OperationalState.COGNITION_ACTIVE,
        ],
        detection_logic="detect_illegal_recovery",
        response_action="halt",
    ),
    ForbiddenStatePattern(
        pattern_id="degraded_inference",
        description="DEGRADED directly to INFERENCE_EXECUTING is forbidden. "
                    "Degraded mode cannot execute inference.",
        state_sequence=[
            OperationalState.DEGRADED,
            OperationalState.INFERENCE_EXECUTING,
        ],
        detection_logic="detect_degraded_inference",
        response_action="halt",
    ),
    ForbiddenStatePattern(
        pattern_id="uninitialized_active",
        description="UNINITIALIZED directly to COGNITION_ACTIVE is forbidden. "
                    "Must go through proper initialization and governance check.",
        state_sequence=[
            OperationalState.UNINITIALIZED,
            OperationalState.COGNITION_ACTIVE,
        ],
        detection_logic="detect_uninitialized_active",
        response_action="halt",
    ),
]


# ---------------------------------------------------------------------------
# ForbiddenPatternDetector
# ---------------------------------------------------------------------------


class ForbiddenPatternDetector:
    """Detects forbidden state patterns in transition history.

    Each method inspects the tail of the transition history and returns
    ``True`` when the corresponding forbidden sequence is found.
    """

    def __init__(self, definitions: list[ForbiddenStatePattern] | None = None) -> None:
        self.definitions = definitions or PATTERN_DEFINITIONS
        self._pattern_map: dict[str, ForbiddenStatePattern] = {
            d.pattern_id: d for d in self.definitions
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_all(self, history: list[StateTransition]) -> list[str]:
        """Run every detector and return IDs of all matched patterns."""
        matched: list[str] = []
        if len(history) < 2:
            return matched
        for definition in self.definitions:
            detector_name = definition.detection_logic
            detector = getattr(self, detector_name, None)
            if detector is None:
                logger.warning("No detector for pattern %s", definition.pattern_id)
                continue
            if detector(history):
                matched.append(definition.pattern_id)
                logger.critical(
                    "Forbidden pattern detected: %s — %s",
                    definition.pattern_id,
                    definition.description,
                )
        return matched

    def get_pattern(self, pattern_id: str) -> ForbiddenStatePattern | None:
        """Retrieve the definition for a given pattern ID."""
        return self._pattern_map.get(pattern_id)

    def get_response_action(self, pattern_id: str) -> str:
        """Get the configured response action for a detected pattern."""
        definition = self._pattern_map.get(pattern_id)
        if definition is None:
            return "halt"
        return definition.response_action

    # ------------------------------------------------------------------
    # Individual detectors
    # ------------------------------------------------------------------

    @staticmethod
    def detect_recursive_inference(history: list[StateTransition]) -> bool:
        """Detect two consecutive INFERENCE_EXECUTING states.

        Recursive inference (inference triggering another inference without
        returning to COGNITION_ACTIVE) is a governance violation.
        """
        if len(history) < 2:
            return False
        tail = history[-2:]
        return all(
            t.to_state == OperationalState.INFERENCE_EXECUTING for t in tail
        )

    @staticmethod
    def detect_illegal_recovery(history: list[StateTransition]) -> bool:
        """Detect FAIL_CLOSED -> COGNITION_ACTIVE direct transition.

        Recovery from FAIL_CLOSED must go through RECOVERING first.
        """
        if len(history) < 2:
            return False
        last = history[-1]
        previous = history[-2]
        return (
            previous.to_state == OperationalState.FAIL_CLOSED
            and last.to_state == OperationalState.COGNITION_ACTIVE
        )

    @staticmethod
    def detect_degraded_inference(history: list[StateTransition]) -> bool:
        """Detect DEGRADED -> INFERENCE_EXECUTING direct transition.

        Degraded mode cannot execute inference; must recover first.
        """
        if len(history) < 2:
            return False
        last = history[-1]
        previous = history[-2]
        return (
            previous.to_state == OperationalState.DEGRADED
            and last.to_state == OperationalState.INFERENCE_EXECUTING
        )

    @staticmethod
    def detect_uninitialized_active(history: list[StateTransition]) -> bool:
        """Detect UNINITIALIZED -> COGNITION_ACTIVE direct transition.

        Must go through proper initialization and governance check.
        """
        if len(history) < 2:
            return False
        last = history[-1]
        previous = history[-2]
        return (
            previous.to_state == OperationalState.UNINITIALIZED
            and last.to_state == OperationalState.COGNITION_ACTIVE
        )
