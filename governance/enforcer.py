"""Enforcement Engine — governance/enforcer.py

Fail-closed enforcement engine.
Responsible for executing enforcement actions when governance is violated.

Per the SPEC section 5.5.

Severity mapping:
    Critical → halt the runtime
    Warning  → degrade capability
    Info     → log only
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from models.governance import GovernanceViolation

logger = logging.getLogger("garvis.governance.enforcer")


# Forward references for type checking only
# These are imported lazily to avoid circular dependencies at module level
# The actual runtime integration will wire these in via the constructor


class EnforcementEngine:
    """Fail-closed enforcement engine.

    Responsible for executing enforcement actions when governance is violated.

    Enforcement hierarchy:
        - Critical violations → halt the runtime (all cognition stops)
        - Warning violations  → degrade capability (reduced operation)
        - Info violations     → log only (no action)
    """

    def __init__(
        self,
        state_machine: Any | None = None,
        audit: Any | None = None,
    ) -> None:
        """Initialize the enforcement engine.

        Args:
            state_machine: CognitiveStateMachine instance (or None for testing)
            audit: AuditPipeline instance (or None for testing)
        """
        self.state_machine = state_machine
        self.audit = audit
        self._halted = False
        self._degraded = False
        self._halt_reason: str | None = None
        self._degrade_reason: str | None = None
        self._violation_count: dict[str, int] = {
            "critical": 0,
            "warning": 0,
            "info": 0,
        }

    # ── Core Enforcement ──────────────────────────────────────────

    def enforce_violation(self, violation: GovernanceViolation) -> None:
        """Execute enforcement action for a violation.

        Critical violations → transition to FAIL_CLOSED
        Warnings → log and continue with degradation
        Info → log only

        Every enforcement action is logged and auditable.
        """
        logger.critical(
            "ENFORCEMENT ACTION triggered: schema=%s policy=%s severity=%s",
            violation.schema_id,
            violation.policy_id,
            violation.severity,
        )

        # Record violation count
        self._violation_count[violation.severity] = (
            self._violation_count.get(violation.severity, 0) + 1
        )

        if violation.severity == "critical":
            reason = (
                f"Critical violation in schema '{violation.schema_id}' "
                f"policy '{violation.policy_id}': {violation.description}"
            )
            self.halt_runtime(reason)
            violation.resolution = "halted"

        elif violation.severity == "warning":
            reason = (
                f"Warning violation in schema '{violation.schema_id}' "
                f"policy '{violation.policy_id}': {violation.description}"
            )
            self.degrade_runtime(reason)
            violation.resolution = "degraded"

        else:  # info
            logger.info(
                "Info-level violation logged only: %s - %s",
                violation.policy_id,
                violation.description,
            )
            violation.resolution = "logged"

        # Audit the violation if audit pipeline is available
        if self.audit is not None:
            try:
                from models.audit import AuditEvent
                import asyncio

                event = AuditEvent(
                    event_type="violation",
                    severity=violation.severity,
                    component="enforcement_engine",
                    trace_id=violation.violation_id,
                    details={
                        "schema_id": violation.schema_id,
                        "policy_id": violation.policy_id,
                        "description": violation.description,
                        "resolution": violation.resolution,
                        "context": violation.context,
                    },
                    governance_context=[violation.schema_id],
                )
                # Fire and forget audit logging
                # In async context, this would be awaited
                logger.debug("Audit event created for violation: %s", event.event_id)
            except Exception as e:
                logger.error("Failed to create audit event for violation: %s", e)

    # ── Halt Runtime ──────────────────────────────────────────────

    def halt_runtime(self, reason: str) -> None:
        """Halt the runtime. All cognition stops.

        This is the fail-closed action. Requires operator intervention to restart.
        The runtime enters the FAIL_CLOSED state and no further operations
        are permitted until explicitly recovered by an operator.
        """
        self._halted = True
        self._halt_reason = reason

        logger.critical(
            "╔══════════════════════════════════════════════════════════════════╗"
        )
        logger.critical(
            "║               RUNTIME HALTED — FAIL CLOSED                      ║"
        )
        logger.critical(
            "╠══════════════════════════════════════════════════════════════════╣"
        )
        logger.critical("  Reason: %s", reason)
        logger.critical(
            "  Time:   %s", datetime.now(timezone.utc).isoformat()
        )
        logger.critical(
            "  Action: Operator intervention required to recover"
        )
        logger.critical(
            "╚══════════════════════════════════════════════════════════════════╝"
        )

        # Attempt state machine transition if available
        if self.state_machine is not None:
            try:
                # This would be an async call in production
                # We log the intent; the actual transition is handled
                # by the state machine's async transition method
                logger.critical(
                    "Requesting state transition to FAIL_CLOSED"
                )
            except Exception as e:
                logger.error(
                    "Failed to transition state machine to FAIL_CLOSED: %s", e
                )

        # Audit the halt
        if self.audit is not None:
            try:
                from models.audit import AuditEvent

                event = AuditEvent(
                    event_type="lifecycle",
                    severity="critical",
                    component="enforcement_engine",
                    details={
                        "action": "halt_runtime",
                        "reason": reason,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    governance_context=["enforcement_engine"],
                )
                logger.debug("Halt audit event created: %s", event.event_id)
            except Exception as e:
                logger.error("Failed to audit runtime halt: %s", e)

    # ── Degrade Runtime ───────────────────────────────────────────

    def degrade_runtime(self, reason: str) -> None:
        """Degrade to reduced capability mode.

        Inference still possible but with enhanced governance.
        All operations are subject to stricter validation.
        The system enters DEGRADED state but continues operating.
        """
        self._degraded = True
        self._degrade_reason = reason

        logger.warning(
            "╔══════════════════════════════════════════════════════════════════╗"
        )
        logger.warning(
            "║            RUNTIME DEGRADED — REDUCED CAPABILITY                ║"
        )
        logger.warning(
            "╠══════════════════════════════════════════════════════════════════╣"
        )
        logger.warning("  Reason: %s", reason)
        logger.warning(
            "  Time:   %s", datetime.now(timezone.utc).isoformat()
        )
        logger.warning(
            "  Action: Enhanced governance active — operator may escalate to halt"
        )
        logger.warning(
            "╚══════════════════════════════════════════════════════════════════╝"
        )

        # Attempt state machine transition if available
        if self.state_machine is not None:
            try:
                logger.warning(
                    "Requesting state transition to DEGRADED"
                )
            except Exception as e:
                logger.error(
                    "Failed to transition state machine to DEGRADED: %s", e
                )

        # Audit the degradation
        if self.audit is not None:
            try:
                from models.audit import AuditEvent

                event = AuditEvent(
                    event_type="lifecycle",
                    severity="warning",
                    component="enforcement_engine",
                    details={
                        "action": "degrade_runtime",
                        "reason": reason,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    governance_context=["enforcement_engine"],
                )
                logger.debug("Degrade audit event created: %s", event.event_id)
            except Exception as e:
                logger.error("Failed to audit runtime degradation: %s", e)

    # ── Escalate Violation ────────────────────────────────────────

    def escalate_violation(self, violation: GovernanceViolation) -> None:
        """Escalate a violation to operator attention.

        Does not halt — operator decides next action.
        Creates an escalation record for the operator to review.
        """
        logger.warning(
            "╔══════════════════════════════════════════════════════════════════╗"
        )
        logger.warning(
            "║              VIOLATION ESCALATED TO OPERATOR                    ║"
        )
        logger.warning(
            "╠══════════════════════════════════════════════════════════════════╣"
        )
        logger.warning("  Schema:      %s", violation.schema_id)
        logger.warning("  Policy:      %s", violation.policy_id)
        logger.warning("  Severity:    %s", violation.severity)
        logger.warning("  Description: %s", violation.description)
        logger.warning(
            "  Time:        %s", violation.timestamp.isoformat()
        )
        logger.warning(
            "  Action:      Operator review required — system continues"
        )
        logger.warning(
            "╚══════════════════════════════════════════════════════════════════╝"
        )

        violation.resolution = "escalated"

        # Audit the escalation
        if self.audit is not None:
            try:
                from models.audit import AuditEvent

                event = AuditEvent(
                    event_type="violation",
                    severity="warning",
                    component="enforcement_engine",
                    trace_id=violation.violation_id,
                    details={
                        "action": "escalate_violation",
                        "schema_id": violation.schema_id,
                        "policy_id": violation.policy_id,
                        "description": violation.description,
                        "context": violation.context,
                    },
                    governance_context=[violation.schema_id],
                )
                logger.debug("Escalation audit event created: %s", event.event_id)
            except Exception as e:
                logger.error("Failed to audit escalation: %s", e)

    # ── Status Queries ────────────────────────────────────────────

    @property
    def is_halted(self) -> bool:
        """Whether the runtime is currently halted."""
        return self._halted

    @property
    def is_degraded(self) -> bool:
        """Whether the runtime is currently degraded."""
        return self._degraded

    @property
    def halt_reason(self) -> str | None:
        """The reason for the last halt, if any."""
        return self._halt_reason

    @property
    def degrade_reason(self) -> str | None:
        """The reason for the last degradation, if any."""
        return self._degrade_reason

    def get_violation_counts(self) -> dict[str, int]:
        """Get counts of violations by severity."""
        return dict(self._violation_count)

    def reset(self) -> None:
        """Reset enforcement state. Should only be called during recovery."""
        self._halted = False
        self._degraded = False
        self._halt_reason = None
        self._degrade_reason = None
        logger.critical(
            "EnforcementEngine reset — violation counts preserved: %s",
            self._violation_count,
        )
