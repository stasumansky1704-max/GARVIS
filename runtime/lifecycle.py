"""Runtime lifecycle management for GARVIS.

Manages the full lifecycle of the runtime:
start -> pause -> resume -> stop -> emergency_stop

All state transitions are audited and governed.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from models.cognition import OperationalState
from runtime.bootstrap import RuntimeBootstrap
from runtime.health import HealthMonitor

logger = logging.getLogger(__name__)


class RuntimeLifecycle:
    """Manages the GARVIS runtime lifecycle.

    Lifecycle states and transitions:
        start()       : UNINITIALIZED -> INITIALIZING -> STANDBY
        pause()       : STANDBY -> DEGRADED (governance still active)
        resume()      : DEGRADED -> STANDBY
        stop()        : Any -> SHUTDOWN (graceful)
        emergency_stop(): Any -> FAIL_CLOSED (immediate halt)

    All transitions produce audit events and are subject to governance.
    """

    def __init__(self) -> None:
        self._bootstrap: RuntimeBootstrap | None = None
        self._health_monitor: HealthMonitor | None = None
        self._start_time: float | None = None
        self._paused_at: float | None = None
        self._total_paused_time: float = 0.0
        self._status_history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Lifecycle operations
    # ------------------------------------------------------------------

    async def start(self) -> dict[str, Any]:
        """Start the runtime with full bootstrap sequence.

        Returns:
            Dictionary of initialized components.

        Raises:
            RuntimeError: If bootstrap fails.
        """
        logger.info("=" * 60)
        logger.info("GARVIS Runtime Lifecycle: START")
        logger.info("=" * 60)

        self._start_time = time.time()
        self._bootstrap = RuntimeBootstrap()
        self._health_monitor = HealthMonitor(self._bootstrap)

        try:
            components = await self._bootstrap.bootstrap()
            logger.info("Runtime started successfully")
            self._record_status("started")
            return components

        except Exception as exc:
            logger.critical("Runtime start failed: %s", exc, exc_info=True)
            self._record_status("start_failed", {"error": str(exc)})
            raise RuntimeError(f"Runtime start failed: {exc}") from exc

    async def pause(self) -> bool:
        """Pause the runtime -- transition to DEGRADED.

        Governance remains active. Inference is blocked but
        audit and memory are still operational.

        Returns:
            True if transition succeeded.
        """
        if self._bootstrap is None or self._bootstrap.state_machine is None:
            logger.error("Cannot pause: runtime not started")
            return False

        logger.info("Pausing runtime -- transitioning to DEGRADED...")
        state_machine = self._bootstrap.state_machine

        current = state_machine.get_current_state()
        if current == OperationalState.DEGRADED:
            logger.warning("Runtime already in DEGRADED state")
            return True

        if current not in (OperationalState.STANDBY, OperationalState.COGNITION_ACTIVE):
            logger.error("Cannot pause from state: %s", current.value)
            return False

        success = await state_machine.transition(
            OperationalState.DEGRADED, "operator_pause"
        )

        if success:
            self._paused_at = time.time()
            self._record_status("paused")
            logger.info("Runtime paused -- now in DEGRADED state")
        else:
            logger.error("Failed to transition to DEGRADED")

        return success

    async def resume(self) -> bool:
        """Resume the runtime -- transition back to STANDBY.

        Returns:
            True if transition succeeded.
        """
        if self._bootstrap is None or self._bootstrap.state_machine is None:
            logger.error("Cannot resume: runtime not started")
            return False

        logger.info("Resuming runtime -- transitioning to STANDBY...")
        state_machine = self._bootstrap.state_machine

        current = state_machine.get_current_state()
        if current == OperationalState.STANDBY:
            logger.warning("Runtime already in STANDBY state")
            return True

        if current != OperationalState.DEGRADED:
            logger.error("Cannot resume from state: %s (expected DEGRADED)", current.value)
            return False

        success = await state_machine.transition(
            OperationalState.STANDBY, "operator_resume"
        )

        if success:
            if self._paused_at is not None:
                self._total_paused_time += time.time() - self._paused_at
                self._paused_at = None
            self._record_status("resumed")
            logger.info("Runtime resumed -- now in STANDBY state")
        else:
            logger.error("Failed to transition to STANDBY")

        return success

    async def stop(self) -> None:
        """Graceful shutdown of the runtime.

        Sequence:
            1. Flush all pending audit events
            2. Persist memory data
            3. Transition to SHUTDOWN
            4. Close all connections
        """
        logger.info("=" * 60)
        logger.info("GARVIS Runtime Lifecycle: STOP (graceful)")
        logger.info("=" * 60)

        if self._health_monitor is not None:
            await self._health_monitor.stop_monitoring()

        if self._bootstrap is not None:
            await self._bootstrap.shutdown()
            self._record_status("stopped")
            logger.info("Runtime stopped gracefully")
        else:
            logger.warning("No bootstrap instance -- nothing to stop")

    async def emergency_stop(self, reason: str = "emergency_halt") -> None:
        """Immediate emergency halt -- transition to FAIL_CLOSED.

        This is the nuclear option. All inference stops immediately.
        Active sessions are terminated. No new sessions can be created.
        Memory is preserved (read-only). Audit continues.

        Args:
            reason: Why the emergency stop was triggered.
        """
        logger.critical("=" * 60)
        logger.critical("GARVIS Runtime Lifecycle: EMERGENCY STOP")
        logger.critical("Reason: %s", reason)
        logger.critical("=" * 60)

        if self._health_monitor is not None:
            await self._health_monitor.stop_monitoring()

        if self._bootstrap is not None and self._bootstrap.state_machine is not None:
            state_machine = self._bootstrap.state_machine
            try:
                await state_machine.transition(OperationalState.FAIL_CLOSED, reason)
                logger.critical("State machine: FAIL_CLOSED")
            except Exception as exc:
                logger.critical(
                    "Even FAIL_CLOSED transition failed: %s", exc, exc_info=True
                )

            # Still try to flush audit and close connections
            try:
                audit = self._bootstrap.components.get("audit_pipeline")
                if audit is not None:
                    await audit.flush()
                    logger.info("Audit flushed during emergency stop")
            except Exception as exc:
                logger.error("Audit flush during emergency stop failed: %s", exc)

            try:
                db = self._bootstrap.components.get("database")
                if db is not None:
                    await db.close()
                    logger.info("Database closed during emergency stop")
            except Exception as exc:
                logger.error("Database close during emergency stop failed: %s", exc)

        self._record_status("emergency_stopped", {"reason": reason})
        logger.critical("Emergency stop complete -- operator intervention required")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Get current runtime status.

        Returns:
            Dictionary with current state, uptime, component health,
            and lifecycle history.
        """
        status: dict[str, Any] = {
            "initialized": self._bootstrap is not None and self._bootstrap.is_initialized,
            "uptime_seconds": self.get_uptime(),
            "total_paused_seconds": round(self._total_paused_time, 2),
            "history": self._status_history[-10:],  # Last 10 events
        }

        if self._bootstrap is not None and self._bootstrap.state_machine is not None:
            sm = self._bootstrap.state_machine
            status["current_state"] = sm.get_current_state().value
            status["transitions_count"] = len(sm.get_state_history())

            # Component availability
            status["components"] = {
                "database": "database" in self._bootstrap.components,
                "governance_registry": "governance_registry" in self._bootstrap.components,
                "governance_middleware": "governance_middleware" in self._bootstrap.components,
                "state_machine": "state_machine" in self._bootstrap.components,
                "audit_pipeline": "audit_pipeline" in self._bootstrap.components,
                "lineage_tracker": "lineage_tracker" in self._bootstrap.components,
                "memory_store": "memory_store" in self._bootstrap.components,
                "ollama_client": "ollama_client" in self._bootstrap.components,
                "inference_executor": "inference_executor" in self._bootstrap.components,
            }

        return status

    def get_uptime(self) -> float:
        """Get seconds since runtime start.

        Returns:
            Uptime in seconds (excluding paused time). 0 if not started.
        """
        if self._start_time is None:
            return 0.0
        uptime = time.time() - self._start_time - self._total_paused_time
        # Subtract current pause if active
        if self._paused_at is not None:
            uptime -= (time.time() - self._paused_at)
        return max(0.0, uptime)

    def _record_status(self, event: str, details: dict[str, Any] | None = None) -> None:
        """Record a lifecycle event in the history."""
        entry = {
            "event": event,
            "timestamp": time.time(),
            "details": details or {},
        }
        self._status_history.append(entry)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def bootstrap(self) -> RuntimeBootstrap | None:
        """Access the bootstrap instance."""
        return self._bootstrap

    @property
    def health_monitor(self) -> HealthMonitor | None:
        """Access the health monitor."""
        return self._health_monitor
