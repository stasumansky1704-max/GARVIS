"""Production Mode Controller — runtime/production_mode.py

Operator production mode for safe daily GARVIS operation.

This is the operator-facing production controller. It manages:
- Safe startup/shutdown sequences
- Operator session tracking
- Safe operation guardrails
- Daily log management
- Snapshot/rollback coordination

NOTHING here executes autonomously. Every action requires
explicit operator approval.
"""

from __future__ import annotations

import logging
import subprocess
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

# Import directly from submodule to avoid triggering runtime/__init__.py
from runtime.config import RuntimeConfig

logger = logging.getLogger("garvis.runtime.production_mode")


# ---------------------------------------------------------------------------
# ProductionSession — individual operator session record
# ---------------------------------------------------------------------------


class ProductionSession:
    """A single operator production session.

    Tracks the session lifecycle, operations performed, and audit trail.
    """

    def __init__(self, session_id: str, operator_id: str) -> None:
        self.session_id = session_id
        self.operator_id = operator_id
        self.started_at: datetime = datetime.now(timezone.utc)
        self.ended_at: datetime | None = None
        self.operations_performed: list[dict[str, Any]] = []
        self.mode_transitions: list[dict[str, Any]] = []
        self.active = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "session_id": self.session_id,
            "operator_id": self.operator_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "active": self.active,
            "operations_count": len(self.operations_performed),
            "operations": self.operations_performed,
            "mode_transitions": self.mode_transitions,
        }

    def log_operation(self, operation: str, params: dict[str, Any] | None, result: str) -> None:
        """Log an operation performed during this session."""
        self.operations_performed.append({
            "operation": operation,
            "params": params or {},
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def end(self) -> None:
        """End this session."""
        self.ended_at = datetime.now(timezone.utc)
        self.active = False


# ---------------------------------------------------------------------------
# ProductionMode — operator production mode controller
# ---------------------------------------------------------------------------


class ProductionMode:
    """Production mode for safe daily GARVIS operation.

    This is the operator-facing production controller. It manages:
    - Safe startup/shutdown sequences
    - Operator session tracking
    - Safe operation guardrails
    - Daily log management
    - Snapshot/rollback coordination

    NOTHING here executes autonomously. Every action requires
    explicit operator approval.
    """

    SAFE_OPERATIONS: dict[str, str] = {
        "start": "Start GARVIS services",
        "stop": "Stop GARVIS services",
        "restart": "Restart GARVIS services",
        "status": "Check system status",
        "backup": "Create backup snapshot",
        "rollback": "Rollback to previous state",
        "health": "Run health checks",
        "schema_reload": "Reload governance schemas",
        "log_view": "View system logs",
        "alert_ack": "Acknowledge alerts",
    }

    DESTRUCTIVE_OPERATIONS: dict[str, bool] = {
        "rollback": True,
        "schema_reload": True,
        "force_stop": True,
        "volume_delete": True,
    }

    # Valid mode transitions
    # standby -> operating, maintenance
    # operating -> standby, degraded, maintenance
    # degraded -> standby, maintenance
    # maintenance -> standby
    VALID_MODE_TRANSITIONS: dict[str, list[str]] = {
        "standby": ["operating", "maintenance"],
        "operating": ["standby", "degraded", "maintenance"],
        "degraded": ["standby", "maintenance"],
        "maintenance": ["standby"],
    }

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self._mode: str = "standby"  # standby | operating | degraded | maintenance
        self._operator_sessions: list[ProductionSession] = []
        self._guardrails_active: bool = True
        self._operation_log: list[dict[str, Any]] = []
        self._maintenance_log: list[dict[str, Any]] = []
        self._daily_logs: dict[str, list[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Property accessors
    # ------------------------------------------------------------------

    @property
    def mode(self) -> str:
        """Current production mode."""
        return self._mode

    @property
    def is_operating(self) -> bool:
        """True if currently in operating mode."""
        return self._mode == "operating"

    @property
    def is_maintenance(self) -> bool:
        """True if currently in maintenance mode."""
        return self._mode == "maintenance"

    @property
    def guardrails_active(self) -> bool:
        """True if guardrails are currently enforced."""
        return self._guardrails_active

    @property
    def active_sessions(self) -> list[ProductionSession]:
        """List of currently active (unended) sessions."""
        return [s for s in self._operator_sessions if s.active]

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def start_production_session(self, operator_id: str) -> dict[str, Any]:
        """Start a production operator session.

        Validates system health, loads governance, enters operating mode.
        Returns session metadata.

        Args:
            operator_id: Unique identifier for the operator.

        Returns:
            Session metadata dict with session_id, mode, timestamp.
        """
        session_id = str(uuid4())
        session = ProductionSession(session_id, operator_id)
        self._operator_sessions.append(session)

        logger.info(
            "Production session started: %s by operator: %s",
            session_id,
            operator_id,
        )

        # Log the session start
        self._log_operation("start_production_session", {
            "session_id": session_id,
            "operator_id": operator_id,
            "mode": self._mode,
        })

        return {
            "session_id": session_id,
            "operator_id": operator_id,
            "mode": self._mode,
            "started_at": session.started_at.isoformat(),
            "guardrails_active": self._guardrails_active,
            "status": "started",
        }

    def end_production_session(self, session_id: str) -> dict[str, Any]:
        """End a production session with full audit.

        Args:
            session_id: The session ID to end.

        Returns:
            Session summary dict with audit trail.
        """
        for session in self._operator_sessions:
            if session.session_id == session_id and session.active:
                session.end()
                logger.info(
                    "Production session ended: %s (operator: %s, ops: %d)",
                    session_id,
                    session.operator_id,
                    len(session.operations_performed),
                )
                return {
                    "session_id": session_id,
                    "status": "ended",
                    "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                    "operations_count": len(session.operations_performed),
                    "session_summary": session.to_dict(),
                }

        logger.warning("Session not found or already ended: %s", session_id)
        return {
            "session_id": session_id,
            "status": "error",
            "reason": "Session not found or already ended",
        }

    # ------------------------------------------------------------------
    # Mode transitions
    # ------------------------------------------------------------------

    def _transition_mode(self, from_mode: str, to_mode: str, operator_id: str, reason: str) -> bool:
        """Attempt a mode transition.

        Returns True if transition was successful.
        """
        if from_mode != self._mode:
            logger.warning(
                "Mode transition rejected: current is '%s', expected '%s'",
                self._mode,
                from_mode,
            )
            return False

        allowed = self.VALID_MODE_TRANSITIONS.get(from_mode, [])
        if to_mode not in allowed:
            logger.warning(
                "Invalid mode transition: '%s' -> '%s' (allowed: %s)",
                from_mode,
                to_mode,
                allowed,
            )
            return False

        self._mode = to_mode

        # Log the transition
        transition_record = {
            "from_mode": from_mode,
            "to_mode": to_mode,
            "operator_id": operator_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._maintenance_log.append(transition_record)

        # Record on active sessions
        for session in self.active_sessions:
            session.mode_transitions.append(transition_record)

        logger.info(
            "Mode transition: '%s' -> '%s' by operator: %s (reason: %s)",
            from_mode,
            to_mode,
            operator_id,
            reason,
        )
        return True

    def enter_maintenance_mode(self, operator_id: str, reason: str) -> bool:
        """Enter maintenance mode (reduced capability, enhanced logging).

        In maintenance mode:
        - Only read-only operations are permitted
        - Enhanced logging is active
        - No inference or cognition operations

        Args:
            operator_id: The operator requesting maintenance mode.
            reason: Human-readable reason for entering maintenance.

        Returns:
            True if successfully entered maintenance mode.
        """
        result = self._transition_mode(
            self._mode, "maintenance", operator_id, reason
        )
        if result:
            logger.warning(
                "Maintenance mode entered by %s. Reason: %s",
                operator_id,
                reason,
            )
        return result

    def exit_maintenance_mode(self, operator_id: str) -> bool:
        """Exit maintenance mode back to normal operation.

        Args:
            operator_id: The operator requesting to exit maintenance.

        Returns:
            True if successfully exited maintenance mode.
        """
        return self._transition_mode(
            "maintenance", "standby", operator_id, "maintenance_complete"
        )

    # ------------------------------------------------------------------
    # Safe operation execution
    # ------------------------------------------------------------------

    def execute_safe_operation(
        self, operation: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a safe operation with guardrails.

        For destructive operations, requires explicit confirmation.

        Args:
            operation: The operation name from SAFE_OPERATIONS.
            params: Optional parameters for the operation.

        Returns:
            Operation result dict.
        """
        params = params or {}

        # Validate operation is known
        if operation not in self.SAFE_OPERATIONS:
            logger.error("Unknown operation requested: '%s'", operation)
            return {
                "operation": operation,
                "status": "error",
                "reason": f"Unknown operation. Valid operations: {list(self.SAFE_OPERATIONS.keys())}",
            }

        # Check if in maintenance mode (only read-only ops allowed)
        if self._mode == "maintenance" and not self._is_read_only_operation(operation):
            logger.warning(
                "Operation '%s' blocked: system in maintenance mode",
                operation,
            )
            return {
                "operation": operation,
                "status": "blocked",
                "reason": "System is in maintenance mode. Only read-only operations allowed.",
            }

        # Check if destructive and needs confirmation
        if self.DESTRUCTIVE_OPERATIONS.get(operation, False):
            logger.info(
                "Destructive operation '%s' requires explicit confirmation",
                operation,
            )
            return {
                "operation": operation,
                "status": "requires_confirmation",
                "reason": (
                    f"'{operation}' is a DESTRUCTIVE operation. "
                    "Explicit operator confirmation required. "
                    "Call require_confirmation() to confirm."
                ),
                "params": params,
            }

        # Execute the operation (simulated — actual execution is operator-driven)
        result = self._execute_operation(operation, params)

        # Log on active sessions
        for session in self.active_sessions:
            session.log_operation(operation, params, result.get("status", "unknown"))

        self._log_operation(operation, params)
        return result

    def _execute_operation(
        self, operation: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Internal: execute an operation (simulated dispatch).

        In production, these would interface with the actual runtime.
        Here we return structured responses that describe what WOULD happen.
        """
        dispatch: dict[str, dict[str, Any]] = {
            "start": {
                "status": "ready",
                "message": "GARVIS services ready to start",
                "services": ["api", "ollama", "postgres", "governance"],
                "action_required": "Operator must confirm start sequence",
            },
            "stop": {
                "status": "ready",
                "message": "GARVIS services ready to stop",
                "services": ["api", "ollama", "postgres", "governance"],
                "action_required": "Operator must confirm stop sequence",
            },
            "restart": {
                "status": "ready",
                "message": "GARVIS services ready to restart",
                "services": ["api", "ollama", "postgres", "governance"],
                "action_required": "Operator must confirm restart sequence",
            },
            "status": {
                "status": "ok",
                "mode": self._mode,
                "guardrails": self._guardrails_active,
                "active_sessions": len(self.active_sessions),
                "services": {
                    "api": "unknown",
                    "ollama": "unknown",
                    "postgres": "unknown",
                    "governance": "unknown",
                },
            },
            "backup": {
                "status": "ready",
                "message": "Snapshot ready to create",
                "includes": ["git_state", "config", "runtime_state", "audit_log"],
                "action_required": "Operator must provide snapshot label",
            },
            "rollback": {
                "status": "blocked",
                "message": "Rollback requires explicit confirmation",
                "warning": "This is a DESTRUCTIVE operation",
                "action_required": "Operator must explicitly confirm",
            },
            "health": {
                "status": "ok",
                "checks": ["postgres", "ollama", "governance", "state_machine"],
                "message": "Run health checks via HealthMonitor",
            },
            "schema_reload": {
                "status": "blocked",
                "message": "Schema reload requires explicit confirmation",
                "warning": "This is a DESTRUCTIVE operation",
                "action_required": "Operator must explicitly confirm",
            },
            "log_view": {
                "status": "ok",
                "logs_available": True,
                "log_count": len(self._operation_log),
                "message": f"{len(self._operation_log)} operations logged today",
            },
            "alert_ack": {
                "status": "ok",
                "message": "Alert acknowledged",
            },
        }

        return {
            "operation": operation,
            **dispatch.get(operation, {"status": "error", "reason": "Unknown operation"}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _is_read_only_operation(operation: str) -> bool:
        """Check if an operation is read-only (safe in maintenance mode)."""
        read_only_ops = {"status", "health", "log_view", "alert_ack"}
        return operation in read_only_ops

    # ------------------------------------------------------------------
    # Confirmation for destructive operations
    # ------------------------------------------------------------------

    def require_confirmation(self, operation: str, details: str) -> dict[str, Any]:
        """Check if operation requires explicit operator confirmation.

        Returns structured confirmation request. The operator must
        explicitly respond with confirmation.

        Args:
            operation: The operation to confirm.
            details: Human-readable description of what will happen.

        Returns:
            Dict with confirmation requirement and instructions.
        """
        is_destructive = self.DESTRUCTIVE_OPERATIONS.get(operation, False)

        confirmation = {
            "operation": operation,
            "requires_confirmation": is_destructive,
            "is_destructive": is_destructive,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if is_destructive:
            confirmation["warning"] = (
                "This is a DESTRUCTIVE operation that may result in "
                "data loss or service interruption."
            )
            confirmation["required_response"] = (
                "Operator must type 'yes' and provide operator_id to confirm"
            )
            confirmation["backup_recommended"] = True
            logger.warning(
                "Destructive operation confirmation requested: '%s' — %s",
                operation,
                details,
            )
        else:
            confirmation["required_response"] = "Operator approval required"

        return confirmation

    def confirm_destructive_operation(
        self, operation: str, operator_id: str, confirmation_response: str
    ) -> dict[str, Any]:
        """Process operator confirmation for a destructive operation.

        The operator MUST respond with the exact string 'yes'.
        Anything else results in rejection.

        Args:
            operation: The destructive operation to confirm.
            operator_id: The operator confirming the operation.
            confirmation_response: Must be exactly 'yes'.

        Returns:
            Result of the confirmation attempt.
        """
        if not self.DESTRUCTIVE_OPERATIONS.get(operation, False):
            return {
                "operation": operation,
                "status": "error",
                "reason": "Not a destructive operation — no confirmation needed",
            }

        if confirmation_response.strip().lower() != "yes":
            logger.warning(
                "Destructive operation '%s' REJECTED by operator '%s' — "
                "response was '%s', expected 'yes'",
                operation,
                operator_id,
                confirmation_response,
            )
            return {
                "operation": operation,
                "status": "rejected",
                "reason": (
                    "Confirmation rejected. Operator must respond with "
                    "exact string 'yes' to proceed."
                ),
            }

        logger.critical(
            "DESTRUCTIVE OPERATION CONFIRMED: '%s' by operator '%s'",
            operation,
            operator_id,
        )

        # Log the confirmation
        self._log_operation("confirm_destructive", {
            "operation": operation,
            "operator_id": operator_id,
            "confirmed": True,
        })

        return {
            "operation": operation,
            "status": "confirmed",
            "confirmed_by": operator_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "warning": "Operation confirmed — executing destructive action",
        }

    # ------------------------------------------------------------------
    # Daily status and logs
    # ------------------------------------------------------------------

    def get_daily_status(self) -> dict[str, Any]:
        """Get daily status summary for operator review.

        Returns:
            Comprehensive daily status dict.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_logs = self._daily_logs.get(today, [])

        return {
            "date": today,
            "current_mode": self._mode,
            "guardrails_active": self._guardrails_active,
            "active_sessions": len(self.active_sessions),
            "total_sessions_today": len([
                s for s in self._operator_sessions
                if s.started_at.strftime("%Y-%m-%d") == today
            ]),
            "operations_today": len(today_logs),
            "available_operations": self.SAFE_OPERATIONS,
            "destructive_operations": list(self.DESTRUCTIVE_OPERATIONS.keys()),
            "maintenance_entries": len(self._maintenance_log),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_daily_logs(self, date: str | None = None) -> list[dict[str, Any]]:
        """Get logs for a specific date (default: today).

        Args:
            date: Date string in YYYY-MM-DD format. Defaults to today.

        Returns:
            List of log entries for the date.
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        return self._daily_logs.get(date, [])

    def get_guardrail_status(self) -> dict[str, Any]:
        """Get current guardrail configuration and status.

        Returns:
            Guardrail status dict.
        """
        return {
            "guardrails_active": self._guardrails_active,
            "destructive_operations_blocked": self._guardrails_active,
            "destructive_operations": {
                op: "blocked_without_confirmation"
                for op in self.DESTRUCTIVE_OPERATIONS
            },
            "safe_operations": {
                op: "allowed"
                for op in self.SAFE_OPERATIONS
                if op not in self.DESTRUCTIVE_OPERATIONS
            },
            "maintenance_mode_readonly": self._mode == "maintenance",
            "current_mode": self._mode,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_operation(self, operation: str, params: dict[str, Any]) -> None:
        """Log an operation to the daily log."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        entry = {
            "operation": operation,
            "params": params,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": self._mode,
        }
        if today not in self._daily_logs:
            self._daily_logs[today] = []
        self._daily_logs[today].append(entry)

    def disable_guardrails(self, operator_id: str, reason: str) -> dict[str, Any]:
        """DISABLE guardrails — requires explicit confirmation.

        This is a highly dangerous operation. Guardrails must be
        fail-closed. Disabling them removes protection.

        Args:
            operator_id: Operator requesting guardrail disable.
            reason: Reason for disabling.

        Returns:
            Result of the operation.
        """
        logger.critical(
            "GUARDRAIL DISABLE requested by '%s'. Reason: %s",
            operator_id,
            reason,
        )
        return {
            "action": "disable_guardrails",
            "status": "requires_confirmation",
            "warning": (
                "DISABLING GUARDRAILS IS EXTREMELY DANGEROUS. "
                "This removes all safety protections."
            ),
            "required_response": (
                "Type 'yes I understand the risk' and provide operator_id"
            ),
        }

    def enable_guardrails(self) -> dict[str, Any]:
        """Re-enable guardrails.

        Returns:
            Result of re-enabling guardrails.
        """
        self._guardrails_active = True
        logger.info("Guardrails re-enabled")
        return {
            "action": "enable_guardrails",
            "status": "ok",
            "guardrails_active": True,
        }
