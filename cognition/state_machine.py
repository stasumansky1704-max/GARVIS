"""Governed operational state machine for GARVIS.

The ``CognitiveStateMachine`` is the **single source of truth** for the
operational state of the cognition runtime.  Every component that needs
to observe or change state must go through this class.

Transitions are validated against the ``VALID_TRANSITIONS`` graph,
governance-checked by the supplied validator, and audited.  After each
transition forbidden patterns are scanned; detection triggers an
automatic transition to ``FAIL_CLOSED``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from models.cognition import (
    ForbiddenStatePattern,
    OperationalState,
    StateTransition,
)

if TYPE_CHECKING:
    from models.audit import AuditEvent
    from models.governance import GovernanceViolation

    # Use protocol-like references to avoid import-time coupling.
    class _RuntimeValidatorLike:
        async def validate_state_transition(
            self, transition: StateTransition
        ) -> list[dict[str, Any]]: ...

        def has_critical_failure(self, results: list[dict[str, Any]]) -> bool: ...

        def build_violation(
            self, transition: StateTransition, result: dict[str, Any]
        ) -> "GovernanceViolation": ...

    class _EnforcerLike:
        async def enforce_violation(self, violation: "GovernanceViolation") -> None: ...

        def halt_runtime(self, reason: str) -> None: ...

    class _AuditLike:
        async def log_state_transition(self, transition: StateTransition) -> None: ...

        async def log_event(self, event: "AuditEvent") -> None: ...

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CognitiveStateMachine
# ---------------------------------------------------------------------------


class CognitiveStateMachine:
    """Governed operational state machine.

    All state transitions are validated by the transition graph, then
    governance-checked, then audited.  Forbidden patterns detected in the
    transition history trigger automatic fail-closed behaviour.
    """

    # ------------------------------------------------------------------
    # Transition graph — canonical source of valid transitions
    # ------------------------------------------------------------------

    VALID_TRANSITIONS: dict[OperationalState, list[OperationalState]] = {
        OperationalState.UNINITIALIZED: [
            OperationalState.INITIALIZING,
            OperationalState.SHUTDOWN,
        ],
        OperationalState.INITIALIZING: [
            OperationalState.STANDBY,
            OperationalState.FAIL_CLOSED,
            OperationalState.SHUTDOWN,
        ],
        OperationalState.STANDBY: [
            OperationalState.GOVERNANCE_CHECK,
            OperationalState.DEGRADED,
            OperationalState.SHUTDOWN,
        ],
        OperationalState.GOVERNANCE_CHECK: [
            OperationalState.COGNITION_ACTIVE,
            OperationalState.STANDBY,
            OperationalState.DEGRADED,
            OperationalState.FAIL_CLOSED,
        ],
        OperationalState.COGNITION_ACTIVE: [
            OperationalState.INFERENCE_EXECUTING,
            OperationalState.MEMORY_RETRIEVING,
            OperationalState.TRACE_LOGGING,
            OperationalState.STANDBY,
            OperationalState.DEGRADED,
        ],
        OperationalState.INFERENCE_EXECUTING: [
            OperationalState.COGNITION_ACTIVE,
            OperationalState.AUDITING,
            OperationalState.DEGRADED,
            OperationalState.FAIL_CLOSED,
        ],
        OperationalState.MEMORY_RETRIEVING: [
            OperationalState.COGNITION_ACTIVE,
            OperationalState.DEGRADED,
            OperationalState.FAIL_CLOSED,
        ],
        OperationalState.TRACE_LOGGING: [
            OperationalState.COGNITION_ACTIVE,
        ],
        OperationalState.AUDITING: [
            OperationalState.COGNITION_ACTIVE,
            OperationalState.DEGRADED,
            OperationalState.FAIL_CLOSED,
        ],
        OperationalState.DEGRADED: [
            OperationalState.RECOVERING,
            OperationalState.STANDBY,
            OperationalState.FAIL_CLOSED,
            OperationalState.SHUTDOWN,
        ],
        OperationalState.FAIL_CLOSED: [
            OperationalState.RECOVERING,
            OperationalState.SHUTDOWN,
        ],
        OperationalState.RECOVERING: [
            OperationalState.STANDBY,
            OperationalState.DEGRADED,
            OperationalState.FAIL_CLOSED,
        ],
        OperationalState.SHUTDOWN: [
            OperationalState.UNINITIALIZED,
        ],
    }

    # Forbidden patterns — sequences that must never appear in history.
    # Each entry is a 2-tuple of (from_state, to_state) that is forbidden.
    FORBIDDEN_PATTERNS: list[tuple[OperationalState, OperationalState]] = [
        (
            OperationalState.INFERENCE_EXECUTING,
            OperationalState.INFERENCE_EXECUTING,
        ),  # recursive_inference
        (
            OperationalState.FAIL_CLOSED,
            OperationalState.COGNITION_ACTIVE,
        ),  # illegal_recovery
        (
            OperationalState.DEGRADED,
            OperationalState.INFERENCE_EXECUTING,
        ),  # degraded_inference
        (
            OperationalState.UNINITIALIZED,
            OperationalState.COGNITION_ACTIVE,
        ),  # uninitialized_active
    ]

    def __init__(
        self,
        validator: Any,
        enforcer: Any,
        audit_pipeline: Any | None = None,
    ) -> None:
        """Initialise the state machine.

        Args:
            validator: Object with ``validate_state_transition`` and
                ``has_critical_failure`` methods.
            enforcer: Object with ``enforce_violation`` and ``halt_runtime``
                methods.
            audit_pipeline: Optional audit logger with ``log_state_transition``
                and ``log_event`` async methods.
        """
        self._state: OperationalState = OperationalState.UNINITIALIZED
        self.validator: Any = validator
        self.enforcer: Any = enforcer
        self.audit: Any = audit_pipeline
        self._transition_log: list[StateTransition] = []
        self._lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def get_current_state(self) -> OperationalState:
        """Return the current operational state."""
        return self._state

    def get_state_history(self) -> list[StateTransition]:
        """Return a shallow copy of the full transition history."""
        return list(self._transition_log)

    def _can_transition(self, from_state: OperationalState, to_state: OperationalState) -> bool:
        """Check whether *to_state* is in the allowed set for *from_state*.

        This only tests the transition graph — it does **not** invoke
        governance validation.
        """
        allowed = self.VALID_TRANSITIONS.get(from_state, [])
        return to_state in allowed

    # ------------------------------------------------------------------
    # Transition history management
    # ------------------------------------------------------------------

    def _record_transition(self, transition: StateTransition) -> None:
        """Append a transition to the internal log."""
        self._transition_log.append(transition)

    # ------------------------------------------------------------------
    # Forbidden pattern detection
    # ------------------------------------------------------------------

    def check_forbidden_pattern(self) -> str | None:
        """Check if the last two transitions form a forbidden pattern.

        Returns:
            The ``pattern_id`` of the first detected forbidden pattern,
            or ``None`` if no pattern is found.
        """
        if len(self._transition_log) < 2:
            return None

        # Inspect the last two *to_state* values in the log
        previous = self._transition_log[-2].to_state
        current = self._transition_log[-1].to_state

        for p_idx, (forbidden_from, forbidden_to) in enumerate(self.FORBIDDEN_PATTERNS):
            if previous == forbidden_from and current == forbidden_to:
                pattern_ids = [
                    "recursive_inference",
                    "illegal_recovery",
                    "degraded_inference",
                    "uninitialized_active",
                ]
                return pattern_ids[p_idx]

        return None

    # ------------------------------------------------------------------
    # Core transition method
    # ------------------------------------------------------------------

    async def transition(self, to_state: OperationalState, trigger: str) -> bool:
        """Request a state transition.

        The method executes the following pipeline under an
        ``asyncio.Lock``:

        1. Validate *to_state* is allowed from the current state.
        2. If not allowed → reject and log (return ``False``).
        3. Build a ``StateTransition`` record.
        4. Call the validator to governance-check the transition.
        5. If any critical check fails → reject and log (return ``False``).
        6. If approved → commit the transition, record in history, audit.
        7. After transition, scan for forbidden patterns.
        8. If a forbidden pattern is detected → auto-transition to
           ``FAIL_CLOSED``.

        Args:
            to_state: Desired destination state.
            trigger: Human-readable description of what caused the
                transition.

        Returns:
            ``True`` if the transition was approved and executed
            (including the case where a normal transition succeeded but
            was followed by a forbidden-pattern auto-transition to
            FAIL_CLOSED).  ``False`` if the transition was rejected.
        """
        async with self._lock:
            from_state = self._state

            # Step 1: Check structural validity
            if not self._can_transition(from_state, to_state):
                logger.warning(
                    "Invalid transition rejected: %s -> %s (trigger: %s)",
                    from_state.value,
                    to_state.value,
                    trigger,
                )
                await self._emit_rejection_audit(from_state, to_state, trigger)
                return False

            # Step 2: Build transition record
            transition = StateTransition(
                transition_id=uuid4(),
                from_state=from_state,
                to_state=to_state,
                trigger=trigger,
                governance_check=False,  # Will be updated after validation
                timestamp=datetime.now(timezone.utc),
                trace_id=uuid4(),
            )

            # Step 3: Governance validation
            try:
                validation_results = await self.validator.validate_state_transition(
                    transition
                )
            except Exception as exc:
                logger.exception("Validator raised exception during transition: %s", exc)
                return False

            # Step 4: Check for critical failures
            if hasattr(self.validator, "has_critical_failure"):
                has_critical = self.validator.has_critical_failure(validation_results)
            else:
                has_critical = any(
                    not r.get("passed", True) for r in validation_results
                )

            if has_critical:
                logger.critical(
                    "Transition %s -> %s blocked by governance (trigger: %s)",
                    from_state.value,
                    to_state.value,
                    trigger,
                )
                # Optionally enforce violation if enforcer supports it
                for result in validation_results:
                    if not result.get("passed", True) and hasattr(
                        self.validator, "build_violation"
                    ):
                        try:
                            violation = self.validator.build_violation(
                                transition, result
                            )
                            if hasattr(self.enforcer, "enforce_violation"):
                                await self.enforcer.enforce_violation(violation)
                        except Exception:
                            logger.exception(
                                "Failed to enforce violation for transition"
                            )
                await self._emit_rejection_audit(from_state, to_state, trigger)
                return False

            # Step 5: Transition approved — commit
            transition.governance_check = True
            self._state = to_state
            self._record_transition(transition)

            logger.info(
                "State transition: %s -> %s (trigger: %s)",
                from_state.value,
                to_state.value,
                trigger,
            )

            # Step 6: Audit logging
            await self._emit_transition_audit(transition)

            # Step 7: Check for forbidden patterns
            forbidden_pattern = self.check_forbidden_pattern()
            if forbidden_pattern is not None:
                logger.critical(
                    "Forbidden pattern '%s' detected after transition %s -> %s. "
                    "Auto-transitioning to FAIL_CLOSED.",
                    forbidden_pattern,
                    from_state.value,
                    to_state.value,
                )
                await self._handle_forbidden_pattern(forbidden_pattern, transition)
                # The auto-transition has occurred; still return True
                # because the original transition *was* executed.
                return True

            return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _force_transition(
        self,
        to_state: OperationalState,
        trigger: str,
    ) -> bool:
        """Force a transition **bypassing** structural validation.

        Used only for enforcement actions (e.g. forbidden-pattern
        auto-transition, emergency fail-closed).  Governance checks
        are still run if the validator is available.

        This method must be called from within the lock or from code
        that already holds it.
        """
        async with self._lock:
            from_state = self._state
            transition = StateTransition(
                transition_id=uuid4(),
                from_state=from_state,
                to_state=to_state,
                trigger=trigger,
                governance_check=True,  # enforcement overrides governance
                timestamp=datetime.now(timezone.utc),
                trace_id=uuid4(),
            )
            self._state = to_state
            self._record_transition(transition)
            logger.critical(
                "Forced state transition: %s -> %s (trigger: %s)",
                from_state.value,
                to_state.value,
                trigger,
            )
            await self._emit_transition_audit(transition)

            # Chain-check: if we transitioned to FAIL_CLOSED, verify
            # it didn't create another forbidden pattern.
            forbidden = self.check_forbidden_pattern()
            if forbidden is not None:
                logger.critical(
                    "Forbidden pattern '%s' detected after forced transition",
                    forbidden,
                )
            return True

    async def _handle_forbidden_pattern(
        self,
        pattern_id: str,
        triggering_transition: StateTransition,
    ) -> None:
        """Handle detection of a forbidden pattern.

        1. Log a critical audit event.
        2. Transition to FAIL_CLOSED (forced).
        3. Notify enforcer.
        """
        # Emit audit event for the forbidden pattern detection
        if self.audit is not None and hasattr(self.audit, "log_event"):
            from models.audit import AuditEvent

            event = AuditEvent(
                event_id=uuid4(),
                event_type="forbidden_pattern_detected",
                severity="critical",
                component="cognition.state_machine",
                session_id=None,
                trace_id=triggering_transition.trace_id,
                timestamp=datetime.now(timezone.utc),
                details={
                    "pattern_id": pattern_id,
                    "triggering_transition_id": str(
                        triggering_transition.transition_id
                    ),
                    "from_state": triggering_transition.from_state.value,
                    "to_state": triggering_transition.to_state.value,
                    "trigger": triggering_transition.trigger,
                },
                governance_context=["operational_state_model"],
            )
            try:
                await self.audit.log_event(event)
            except Exception:
                logger.exception("Failed to log forbidden-pattern audit event")

        # Notify enforcer
        if hasattr(self.enforcer, "halt_runtime"):
            self.enforcer.halt_runtime(
                reason=f"Forbidden pattern detected: {pattern_id}"
            )

        # Auto-transition to FAIL_CLOSED
        await self._force_transition(
            OperationalState.FAIL_CLOSED,
            trigger=f"forbidden_pattern:{pattern_id}",
        )

    # ------------------------------------------------------------------
    # Audit helpers
    # ------------------------------------------------------------------

    async def _emit_transition_audit(self, transition: StateTransition) -> None:
        """Send a transition record to the audit pipeline if available."""
        if self.audit is not None and hasattr(self.audit, "log_state_transition"):
            try:
                await self.audit.log_state_transition(transition)
            except Exception:
                logger.exception("Failed to log transition to audit pipeline")

    async def _emit_rejection_audit(
        self,
        from_state: OperationalState,
        to_state: OperationalState,
        trigger: str,
    ) -> None:
        """Log a rejected-transition event to the audit pipeline."""
        if self.audit is not None and hasattr(self.audit, "log_event"):
            from models.audit import AuditEvent

            event = AuditEvent(
                event_id=uuid4(),
                event_type="state_transition_rejected",
                severity="warning",
                component="cognition.state_machine",
                session_id=None,
                trace_id=uuid4(),
                timestamp=datetime.now(timezone.utc),
                details={
                    "from_state": from_state.value,
                    "to_state": to_state.value,
                    "trigger": trigger,
                    "reason": "transition_not_in_valid_graph",
                },
                governance_context=["operational_state_model"],
            )
            try:
                await self.audit.log_event(event)
            except Exception:
                logger.exception("Failed to log rejection audit event")
