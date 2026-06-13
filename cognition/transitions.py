"""State transition rules and helpers for the GARVIS cognition layer.

Defines the ``TransitionRule`` dataclass for declarative transition constraints,
the ``TransitionValidator`` that gates every transition through governance,
and convenience coroutines for the most common operational transitions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from models.cognition import OperationalState, StateTransition
from models.governance import GovernanceViolation

if TYPE_CHECKING:
    from cognition.state_machine import CognitiveStateMachine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TransitionRule
# ---------------------------------------------------------------------------


@dataclass
class TransitionRule:
    """Declarative rule governing a set of allowed transitions.

    Attributes:
        from_state: The source operational state.
        to_states: All destination states permitted from *from_state*.
        required_governance_schemas: Schema IDs that must be active for
            transitions under this rule to proceed.
    """

    from_state: OperationalState
    to_states: list[OperationalState] = field(default_factory=list)
    required_governance_schemas: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# TransitionValidator
# ---------------------------------------------------------------------------


class TransitionValidator:
    """Validates state transitions against governance rules.

    The validator is called by ``CognitiveStateMachine.transition()`` *before*
    a requested transition is committed.  It returns a list of governance
    check results; any critical failure in the list means the transition is
    rejected (fail-closed).
    """

    def __init__(self, rules: list[TransitionRule] | None = None) -> None:
        self._rules: dict[OperationalState, TransitionRule] = {}
        if rules:
            for rule in rules:
                self._rules[rule.from_state] = rule

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def register_rule(self, rule: TransitionRule) -> None:
        """Register (or overwrite) a transition rule."""
        self._rules[rule.from_state] = rule
        logger.debug("Registered transition rule: %s", rule.from_state.value)

    def get_rule(self, from_state: OperationalState) -> TransitionRule | None:
        """Retrieve the rule for a given source state."""
        return self._rules.get(from_state)

    def remove_rule(self, from_state: OperationalState) -> None:
        """Remove a rule for a given source state."""
        self._rules.pop(from_state, None)

    # ------------------------------------------------------------------
    # Validation entry-point
    # ------------------------------------------------------------------

    async def validate(
        self,
        transition: StateTransition,
        active_schemas: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Validate a proposed transition.

        Returns a list of check-result dicts.  A result with
        ``passed == False`` and ``severity == "critical"`` blocks the
        transition.

        Args:
            transition: The proposed transition.
            active_schemas: Currently active governance schema IDs.
        """
        results: list[dict[str, Any]] = []
        active_schemas = active_schemas or []

        # 1. Check structural validity (is the transition allowed by rules?)
        rule = self._rules.get(transition.from_state)
        if rule is not None and transition.to_state not in rule.to_states:
            results.append(
                {
                    "check_id": uuid4(),
                    "schema_id": "operational_state_model",
                    "policy_id": "valid_transition_only",
                    "passed": False,
                    "severity": "critical",
                    "reason": (
                        f"Transition from {transition.from_state.value} "
                        f"to {transition.to_state.value} is not allowed "
                        f"by rule {rule.from_state.value}"
                    ),
                    "timestamp": datetime.now(timezone.utc),
                }
            )
            return results

        # 2. Check required governance schemas are active
        if rule is not None and rule.required_governance_schemas:
            missing = [
                s for s in rule.required_governance_schemas if s not in active_schemas
            ]
            if missing:
                results.append(
                    {
                        "check_id": uuid4(),
                        "schema_id": "operational_state_model",
                        "policy_id": "required_schemas_active",
                        "passed": False,
                        "severity": "critical",
                        "reason": (
                            f"Missing required governance schemas for transition: "
                            f"{', '.join(missing)}"
                        ),
                        "timestamp": datetime.now(timezone.utc),
                    }
                )
                return results

        # 3. Transition is structurally and governance-wise valid
        results.append(
            {
                "check_id": uuid4(),
                "schema_id": "operational_state_model",
                "policy_id": "valid_transition_only",
                "passed": True,
                "severity": "info",
                "reason": (
                    f"Transition from {transition.from_state.value} "
                    f"to {transition.to_state.value} is valid"
                ),
                "timestamp": datetime.now(timezone.utc),
            }
        )
        return results

    def has_critical_failure(self, results: list[dict[str, Any]]) -> bool:
        """Return ``True`` if any result in the list is a critical failure."""
        return any(
            not r.get("passed", True) and r.get("severity") == "critical"
            for r in results
        )

    def build_violation(
        self,
        transition: StateTransition,
        result: dict[str, Any],
    ) -> GovernanceViolation:
        """Build a ``GovernanceViolation`` from a failed check result."""
        return GovernanceViolation(
            violation_id=uuid4(),
            schema_id=result.get("schema_id", "unknown"),
            policy_id=result.get("policy_id", "unknown"),
            severity=result.get("severity", "critical"),
            description=result.get("reason", "Transition validation failed"),
            context={
                "transition_id": str(transition.transition_id),
                "from_state": transition.from_state.value,
                "to_state": transition.to_state.value,
                "trigger": transition.trigger,
                "trace_id": str(transition.trace_id),
            },
            timestamp=datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Convenience transition helpers
# ---------------------------------------------------------------------------


async def standby_to_active(state_machine: "CognitiveStateMachine") -> bool:
    """Transition STANDBY -> GOVERNANCE_CHECK -> COGNITION_ACTIVE.

    Returns ``True`` if both transitions succeeded.
    """
    ok1 = await state_machine.transition(
        OperationalState.GOVERNANCE_CHECK,
        trigger="standby_to_active:governance_check",
    )
    if not ok1:
        logger.error("Failed to transition STANDBY -> GOVERNANCE_CHECK")
        return False
    ok2 = await state_machine.transition(
        OperationalState.COGNITION_ACTIVE,
        trigger="standby_to_active:cognition_active",
    )
    if not ok2:
        logger.error("Failed to transition GOVERNANCE_CHECK -> COGNITION_ACTIVE")
        return False
    return True


async def active_to_inference(state_machine: "CognitiveStateMachine") -> bool:
    """Transition COGNITION_ACTIVE -> INFERENCE_EXECUTING.

    Returns ``True`` on success.
    """
    return await state_machine.transition(
        OperationalState.INFERENCE_EXECUTING,
        trigger="active_to_inference",
    )


async def inference_to_active(state_machine: "CognitiveStateMachine") -> bool:
    """Transition INFERENCE_EXECUTING -> COGNITION_ACTIVE.

    Returns ``True`` on success.
    """
    return await state_machine.transition(
        OperationalState.COGNITION_ACTIVE,
        trigger="inference_to_active",
    )


async def any_to_fail_closed(
    state_machine: "CognitiveStateMachine",
    reason: str,
) -> bool:
    """Emergency transition to FAIL_CLOSED from any state.

    This bypasses the normal transition graph validation because it is an
    enforcement action triggered by governance violations or forbidden
    pattern detection.

    Args:
        state_machine: The state machine to transition.
        reason: Human-readable reason for the fail-closed action.

    Returns ``True`` on success.
    """
    logger.critical("FAIL_CLOSED enforced: %s", reason)
    # Use the internal _force_transition helper on the state machine
    return await state_machine._force_transition(
        OperationalState.FAIL_CLOSED,
        trigger=f"enforcement:fail_closed:{reason}",
    )


async def fail_closed_to_recovering(
    state_machine: "CognitiveStateMachine",
) -> bool:
    """Transition FAIL_CLOSED -> RECOVERING.

    Returns ``True`` on success.
    """
    return await state_machine.transition(
        OperationalState.RECOVERING,
        trigger="fail_closed_to_recovering",
    )
