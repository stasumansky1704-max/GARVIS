"""Session management for the GARVIS cognition layer.

Sessions track which governance schemas are active for a given unit of work,
and bind together state transitions, audit events, and trace IDs.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from models.audit import AuditEvent
from models.cognition import OperationalState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CognitionSession
# ---------------------------------------------------------------------------


class CognitionSession:
    """A single cognition session.

    A session represents a bounded unit of governed cognition work.  It
    carries a unique identity, timestamps, the active governance schema set,
    the current operational state, and a trace ID for lineage tracking.
    """

    def __init__(
        self,
        session_id: UUID,
        active_schemas: list[str],
        trace_id: UUID | None = None,
    ) -> None:
        self.session_id: UUID = session_id
        self.created_at: datetime = datetime.now(timezone.utc)
        self.active_schemas: list[str] = active_schemas
        self.current_state: OperationalState = OperationalState.STANDBY
        self.trace_id: UUID = trace_id or uuid4()
        self._ended: bool = False
        self._ended_at: datetime | None = None

    # ------------------------------------------------------------------
    # Read-only helpers
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """``True`` until ``end()`` has been called."""
        return not self._ended

    @property
    def ended_at(self) -> datetime | None:
        return self._ended_at

    def update_state(self, new_state: OperationalState) -> None:
        """Update the tracked current state (called by the state machine)."""
        self.current_state = new_state
        logger.debug(
            "Session %s state updated: %s -> %s",
            self.session_id,
            self.current_state.value,
            new_state.value,
        )

    def end(self) -> None:
        """Mark the session as ended.  Idempotent."""
        if not self._ended:
            self._ended = True
            self._ended_at = datetime.now(timezone.utc)
            logger.info("Session %s ended at %s", self.session_id, self._ended_at)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the session to a plain dict."""
        return {
            "session_id": str(self.session_id),
            "created_at": self.created_at.isoformat(),
            "active_schemas": list(self.active_schemas),
            "current_state": self.current_state.value,
            "trace_id": str(self.trace_id),
            "is_active": self.is_active,
            "ended_at": self._ended_at.isoformat() if self._ended_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"CognitionSession({self.session_id!s}, "
            f"state={self.current_state.value}, "
            f"schemas={self.active_schemas})"
        )


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------


class SessionManager:
    """Manages the lifecycle of cognition sessions.

    Provides create / retrieve / terminate / list operations, and maintains
    an in-memory audit trail per session.  All operations are synchronous
    (the calling coroutine is responsible for any needed locking).
    """

    def __init__(self) -> None:
        self._sessions: dict[UUID, CognitionSession] = {}
        self._audit_trails: dict[UUID, list[AuditEvent]] = {}

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def create_session(self, active_schemas: list[str]) -> CognitionSession:
        """Create a new session with the given active governance schemas.

        Args:
            active_schemas: List of governance schema IDs active for this session.

        Returns:
            The newly created ``CognitionSession``.
        """
        session_id = uuid4()
        trace_id = uuid4()
        session = CognitionSession(
            session_id=session_id,
            active_schemas=list(active_schemas),
            trace_id=trace_id,
        )
        self._sessions[session_id] = session
        self._audit_trails[session_id] = []
        logger.info(
            "Created session %s with trace %s and schemas %s",
            session_id,
            trace_id,
            active_schemas,
        )
        return session

    def get_session(self, session_id: UUID) -> CognitionSession | None:
        """Retrieve a session by ID.

        Returns ``None`` if the session does not exist or has ended.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if not session.is_active:
            return None
        return session

    def end_session(self, session_id: UUID) -> None:
        """End a session.  No-op if the session does not exist or is already ended."""
        session = self._sessions.get(session_id)
        if session is None:
            logger.warning("end_session called for non-existent session %s", session_id)
            return
        session.end()
        logger.info("Session %s ended", session_id)

    def list_active_sessions(self) -> list[CognitionSession]:
        """Return all currently-active sessions."""
        return [s for s in self._sessions.values() if s.is_active]

    def get_session_audit_trail(self, session_id: UUID) -> list[AuditEvent]:
        """Return the in-memory audit trail for a session.

        Returns an empty list if the session does not exist.
        """
        return list(self._audit_trails.get(session_id, []))

    # ------------------------------------------------------------------
    # Audit trail helpers
    # ------------------------------------------------------------------

    def record_audit_event(self, session_id: UUID, event: AuditEvent) -> None:
        """Append an audit event to a session's trail.

        Creates the trail bucket lazily if it does not yet exist.
        """
        if session_id not in self._audit_trails:
            self._audit_trails[session_id] = []
        self._audit_trails[session_id].append(event)

    def update_session_state(
        self,
        session_id: UUID,
        new_state: OperationalState,
    ) -> None:
        """Update the current state of a session.

        Called by the state machine after a successful transition.
        """
        session = self._sessions.get(session_id)
        if session is not None:
            session.update_state(new_state)
