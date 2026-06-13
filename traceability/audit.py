"""
Audit Pipeline

Comprehensive audit logging for all runtime events.
Immutable append-only log with buffered writes for performance.

Per SPEC section 5.9:
- log_event(event) -> void (buffers event)
- log_state_transition(transition) -> void (convenience)
- log_governance_violation(violation) -> void (convenience)
- log_inference(request, response) -> void (convenience)
- get_events(session_id, event_type, severity, since, limit) -> list[AuditEvent]
- flush() -> void (force flush buffer to PostgreSQL)
- get_violation_summary(since) -> dict with counts by severity/schema

Buffer management:
- Events buffered in memory (list)
- Auto-flush when buffer reaches _buffer_size (100)
- Periodic flush every _flush_interval seconds (5)
- Buffer cleared after successful flush
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from database.connection import DatabaseConnection
from database.queries import Queries
from models.audit import AuditEvent
from models.cognition import OperationalState, StateTransition
from models.governance import GovernanceViolation
from models.inference import GovernedResponse, InferenceRequest

logger = logging.getLogger(__name__)


class AuditPipeline:
    """Comprehensive audit logging for all runtime events.

    Immutable append-only log with buffered writes for performance.
    Events are buffered in memory and flushed to PostgreSQL:
    - When buffer reaches _buffer_size (100 events)
    - On explicit flush() call
    - Periodic flush every _flush_interval seconds (5)
    """

    DEFAULT_BUFFER_SIZE: int = 100
    DEFAULT_FLUSH_INTERVAL: float = 5.0

    def __init__(
        self,
        db: DatabaseConnection,
        buffer_size: int | None = None,
        flush_interval: float | None = None,
    ) -> None:
        self.db = db
        self._buffer: list[AuditEvent] = []
        self._buffer_size = buffer_size or self.DEFAULT_BUFFER_SIZE
        self._flush_interval = flush_interval or self.DEFAULT_FLUSH_INTERVAL
        self._flush_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._shutting_down = False

        logger.info(
            "AuditPipeline initialized: buffer_size=%d, flush_interval=%.1fs",
            self._buffer_size,
            self._flush_interval,
        )

    async def start(self) -> None:
        """Start the periodic flush background task."""
        if self._flush_task is None or self._flush_task.done():
            self._shutting_down = False
            self._flush_task = asyncio.create_task(
                self._periodic_flush(), name="audit_periodic_flush"
            )
            logger.debug("AuditPipeline periodic flush started")

    async def stop(self) -> None:
        """Stop the periodic flush and force a final flush."""
        self._shutting_down = True

        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush of remaining events
        await self.flush()
        logger.info("AuditPipeline stopped")

    async def log_event(self, event: AuditEvent) -> None:
        """Log an audit event.

        The event is added to the buffer. If the buffer is full,
        it is flushed to PostgreSQL immediately.

        Args:
            event: The audit event to log.
        """
        async with self._lock:
            self._buffer.append(event)
            current_size = len(self._buffer)

        logger.debug(
            "Audit event buffered: type=%s, severity=%s, component=%s (buffer: %d/%d)",
            event.event_type,
            event.severity,
            event.component,
            current_size,
            self._buffer_size,
        )

        # Auto-flush if buffer is full
        if current_size >= self._buffer_size:
            logger.info(
                "Audit buffer full (%d/%d), triggering auto-flush",
                current_size,
                self._buffer_size,
            )
            await self.flush()

    async def log_state_transition(self, transition: StateTransition) -> None:
        """Convenience method for logging state transitions.

        Args:
            transition: The state transition to log.
        """
        event = AuditEvent(
            event_id=uuid4(),
            event_type="state_transition",
            severity="info",
            component="state_machine",
            session_id=None,  # Resolved from trace if needed
            trace_id=transition.trace_id,
            details={
                "transition_id": str(transition.transition_id),
                "from_state": transition.from_state.value,
                "to_state": transition.to_state.value,
                "trigger": transition.trigger,
                "governance_check": transition.governance_check,
            },
        )
        await self.log_event(event)

        # Also persist the transition itself
        try:
            await self.db.execute(
                Queries.TRANSITION_INSERT,
                str(transition.transition_id),
                transition.from_state.value,
                transition.to_state.value,
                transition.trigger,
                transition.governance_check,
                str(transition.trace_id),
                transition.timestamp,
            )
        except Exception as exc:
            logger.error("Failed to persist state transition: %s", exc)
            raise

    async def log_governance_violation(
        self,
        violation: GovernanceViolation,
        trace_id: UUID | None = None,
    ) -> None:
        """Convenience method for logging governance violations.

        Args:
            violation: The governance violation to log.
            trace_id: Optional trace ID to associate.
        """
        severity = (
            "critical"
            if violation.severity == "critical"
            else "warning" if violation.severity == "warning" else "info"
        )

        event = AuditEvent(
            event_id=uuid4(),
            event_type="violation",
            severity=severity,
            component="governance_validator",
            session_id=None,
            trace_id=trace_id or uuid4(),
            details={
                "violation_id": str(violation.violation_id),
                "schema_id": violation.schema_id,
                "policy_id": violation.policy_id,
                "description": violation.description,
                "severity": violation.severity,
                "context": violation.context,
            },
        )
        await self.log_event(event)

        # Also persist the violation itself
        try:
            await self.db.execute(
                Queries.VIOLATION_INSERT,
                str(violation.violation_id),
                violation.schema_id,
                violation.policy_id,
                violation.severity,
                violation.description,
                violation.context,
                violation.resolution,
                violation.timestamp,
            )
        except Exception as exc:
            logger.error("Failed to persist governance violation: %s", exc)
            raise

    async def log_inference(
        self,
        request: InferenceRequest,
        response: GovernedResponse,
        trace_id: UUID | None = None,
    ) -> None:
        """Convenience method for logging inference operations.

        Args:
            request: The inference request.
            response: The governed response.
            trace_id: Optional trace ID to associate.
        """
        severity = "info" if response.passed_validation else "warning"

        event = AuditEvent(
            event_id=uuid4(),
            event_type="inference",
            severity=severity,
            component="inference_executor",
            session_id=request.session_id,
            trace_id=trace_id or uuid4(),
            details={
                "request_id": str(request.request_id),
                "response_id": str(response.response_id),
                "model": request.model,
                "prompt_length": len(request.prompt),
                "response_length": len(response.raw_response),
                "passed_validation": response.passed_validation,
                "validation_failures": response.validation_failures,
                "governance_checks_count": len(response.governance_checks),
                "memory_influences_count": len(response.memory_influences),
            },
        )
        await self.log_event(event)

    async def get_events(
        self,
        session_id: UUID | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events with filters.

        Args:
            session_id: Filter by session (None = all sessions).
            event_type: Filter by event type (None = all types).
            severity: Filter by severity (None = all severities).
            since: Only events after this time (None = all time).
            limit: Maximum number of events to return.

        Returns:
            List of AuditEvent, ordered by time (newest first).
        """
        logger.debug(
            "Querying audit events: session=%s, type=%s, severity=%s, since=%s, limit=%d",
            session_id,
            event_type,
            severity,
            since.isoformat() if since else None,
            limit,
        )

        try:
            rows = await self.db.fetch(
                Queries.AUDIT_GET_FILTERED,
                str(session_id) if session_id else None,
                event_type,
                severity,
                since,
                limit,
            )
        except Exception as exc:
            logger.error("Failed to query audit events: %s", exc)
            raise

        events = [AuditEvent.from_db_row(dict(row)) for row in rows]

        logger.debug("Retrieved %d audit events", len(events))
        return events

    async def flush(self) -> None:
        """Force-flush buffered events to persistent storage.

        Inserts all buffered events into the audit_events table,
        then clears the buffer.
        """
        async with self._lock:
            if not self._buffer:
                return

            events_to_flush = self._buffer
            self._buffer = []

        logger.info(
            "Flushing %d audit events to PostgreSQL",
            len(events_to_flush),
        )

        try:
            # Build parameters for executemany
            params = []
            for event in events_to_flush:
                params.append(
                    (
                        str(event.event_id),
                        event.event_type,
                        event.severity,
                        event.component,
                        str(event.session_id) if event.session_id else None,
                        str(event.trace_id),
                        event.timestamp,
                        event.details,
                        event.governance_context,
                    )
                )

            await self.db.executemany(Queries.AUDIT_INSERT_MANY, params)

            logger.info(
                "Successfully flushed %d audit events",
                len(events_to_flush),
            )
        except Exception as exc:
            logger.critical(
                "Failed to flush %d audit events: %s",
                len(events_to_flush),
                exc,
            )
            # Re-add failed events back to buffer for retry
            async with self._lock:
                self._buffer = events_to_flush + self._buffer
                # Trim if buffer grew too large
                if len(self._buffer) > self._buffer_size * 2:
                    logger.critical(
                        "Audit buffer overflow: dropping %d oldest events",
                        len(self._buffer) - self._buffer_size * 2,
                    )
                    self._buffer = self._buffer[: self._buffer_size * 2]
            raise

    async def get_violation_summary(
        self,
        since: datetime | None = None,
    ) -> dict:
        """Get summary of violations for reporting.

        Args:
            since: Only violations after this time (None = all time).

        Returns:
            Dict with:
                - by_severity: dict of severity -> count
                - by_schema: dict of schema_id -> count
                - total: total count
                - period_start: since parameter
        """
        logger.debug(
            "Generating violation summary since %s",
            since.isoformat() if since else "(all time)",
        )

        try:
            rows = await self.db.fetch(
                Queries.VIOLATION_SUMMARY, since
            )
        except Exception as exc:
            logger.error("Failed to get violation summary: %s", exc)
            raise

        by_severity: dict[str, int] = {}
        by_schema: dict[str, int] = {}
        total = 0

        for row in rows:
            row_dict = dict(row)
            sev = row_dict["severity"]
            schema = row_dict["schema_id"]
            count = row_dict["count"]

            by_severity[sev] = by_severity.get(sev, 0) + count
            by_schema[schema] = by_schema.get(schema, 0) + count
            total += count

        summary = {
            "by_severity": by_severity,
            "by_schema": by_schema,
            "total": total,
            "period_start": since.isoformat() if since else None,
        }

        logger.debug(
            "Violation summary: %d total (%s)",
            total,
            ", ".join(f"{k}={v}" for k, v in by_severity.items()),
        )
        return summary

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _periodic_flush(self) -> None:
        """Background task that flushes the buffer periodically."""
        while not self._shutting_down:
            try:
                await asyncio.sleep(self._flush_interval)
                if self._buffer:
                    await self.flush()
            except asyncio.CancelledError:
                logger.debug("Periodic flush task cancelled")
                break
            except Exception as exc:
                logger.error("Periodic flush error: %s", exc)
