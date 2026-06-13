"""Health monitoring for GARVIS runtime.

Provides periodic health checks for all critical dependencies:
PostgreSQL, Ollama, governance subsystem, and state machine.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    name: str
    status: str  # "pass", "fail", "warn"
    response_time_ms: float
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class HealthMonitor:
    """Monitors the health of all GARVIS runtime dependencies.

    Performs checks on:
        - PostgreSQL connectivity
        - Ollama availability
        - Governance subsystem (schemas loaded, no inconsistencies)
        - State machine (current state, uptime)

    Can run checks on-demand or periodically via start_monitoring().
    """

    CRITICAL_CHECKS = {"postgres", "ollama", "governance"}

    def __init__(self, bootstrap: Any | None = None) -> None:
        self._bootstrap = bootstrap
        self._check_results: dict[str, HealthCheckResult] = {}
        self._monitoring_task: asyncio.Task | None = None
        self._monitoring_interval: int = 30
        self._stop_event: asyncio.Event | None = None
        self._start_time: float = time.time()
        self._check_count: int = 0

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    async def check_postgres(self) -> bool:
        """Check PostgreSQL connectivity.

        Returns:
            True if PostgreSQL is reachable and responsive.
        """
        start = time.time()
        try:
            db = self._get_component("database")
            if db is None:
                self._store_result(
                    "postgres",
                    "fail",
                    time.time() - start,
                    {"error": "database component not available"},
                )
                return False

            # Attempt a simple query
            result = await db.fetchrow("SELECT 1 AS health_check")
            elapsed_ms = (time.time() - start) * 1000

            if result is not None:
                self._store_result(
                    "postgres",
                    "pass",
                    elapsed_ms,
                    {"response_ms": round(elapsed_ms, 2)},
                )
                logger.debug("PostgreSQL health check: PASS (%.2f ms)", elapsed_ms)
                return True
            else:
                self._store_result(
                    "postgres",
                    "fail",
                    elapsed_ms,
                    {"error": "empty response from health check query"},
                )
                return False

        except Exception as exc:
            elapsed_ms = (time.time() - start) * 1000
            self._store_result(
                "postgres",
                "fail",
                elapsed_ms,
                {"error": str(exc)},
            )
            logger.warning("PostgreSQL health check failed: %s", exc)
            return False

    async def check_ollama(self) -> bool:
        """Check Ollama availability.

        Returns:
            True if Ollama is reachable and responsive.
        """
        start = time.time()
        try:
            client = self._get_component("ollama_client")
            if client is None:
                self._store_result(
                    "ollama",
                    "fail",
                    time.time() - start,
                    {"error": "ollama_client component not available"},
                )
                return False

            healthy = await client.health_check()
            elapsed_ms = (time.time() - start) * 1000

            if healthy:
                self._store_result(
                    "ollama",
                    "pass",
                    elapsed_ms,
                    {"response_ms": round(elapsed_ms, 2)},
                )
                logger.debug("Ollama health check: PASS (%.2f ms)", elapsed_ms)
            else:
                self._store_result(
                    "ollama",
                    "fail",
                    elapsed_ms,
                    {"error": "Ollama returned unhealthy status"},
                )
                logger.warning("Ollama health check: FAIL")

            return healthy

        except Exception as exc:
            elapsed_ms = (time.time() - start) * 1000
            self._store_result(
                "ollama",
                "fail",
                elapsed_ms,
                {"error": str(exc)},
            )
            logger.warning("Ollama health check failed: %s", exc)
            return False

    async def check_governance(self) -> bool:
        """Check governance subsystem health.

        Verifies that schemas are loaded and there are no
        cross-schema inconsistencies.

        Returns:
            True if governance subsystem is healthy.
        """
        start = time.time()
        try:
            registry = self._get_component("governance_registry")
            middleware = self._get_component("governance_middleware")

            if registry is None:
                self._store_result(
                    "governance",
                    "fail",
                    time.time() - start,
                    {"error": "governance_registry component not available"},
                )
                return False

            if middleware is None:
                self._store_result(
                    "governance",
                    "fail",
                    time.time() - start,
                    {"error": "governance_middleware component not available"},
                )
                return False

            # Check schemas are loaded
            active_schemas = registry.get_active_schemas()

            # Check middleware is active (governance must be enforced)
            is_active = getattr(middleware, "is_active", lambda: False)()

            inconsistencies = registry.validate_cross_schema_consistency()
            elapsed_ms = (time.time() - start) * 1000

            details = {
                "active_schemas_count": len(active_schemas),
                "middleware_active": is_active,
                "inconsistencies": inconsistencies,
                "response_ms": round(elapsed_ms, 2),
            }

            if inconsistencies:
                self._store_result(
                    "governance",
                    "fail",
                    elapsed_ms,
                    details,
                )
                logger.critical(
                    "Governance health check: FAIL -- %d inconsistencies found",
                    len(inconsistencies),
                )
                return False

            if not is_active:
                self._store_result(
                    "governance",
                    "warn",
                    elapsed_ms,
                    details,
                )
                logger.warning(
                    "Governance health check: WARN -- middleware inactive"
                )
                return True  # Warning, not failure

            self._store_result(
                "governance",
                "pass",
                elapsed_ms,
                details,
            )
            logger.debug("Governance health check: PASS (%.2f ms)", elapsed_ms)
            return True

        except Exception as exc:
            elapsed_ms = (time.time() - start) * 1000
            self._store_result(
                "governance",
                "fail",
                elapsed_ms,
                {"error": str(exc)},
            )
            logger.critical("Governance health check failed: %s", exc)
            return False

    def check_state_machine(self) -> dict[str, Any]:
        """Check state machine status.

        Returns:
            Dictionary with current state, uptime, and transition count.
        """
        start = time.time()
        try:
            state_machine = self._get_component("state_machine")
            if state_machine is None:
                result = {
                    "status": "unknown",
                    "current_state": None,
                    "uptime_seconds": round(time.time() - self._start_time, 2),
                    "transitions_count": 0,
                    "error": "state_machine component not available",
                }
                self._store_result("state_machine", "fail", time.time() - start, result)
                return result

            uptime = time.time() - self._start_time
            history = state_machine.get_state_history()
            current_state = state_machine.get_current_state()

            result = {
                "status": "pass",
                "current_state": current_state.value if current_state else None,
                "uptime_seconds": round(uptime, 2),
                "transitions_count": len(history),
            }

            elapsed_ms = (time.time() - start) * 1000
            self._store_result("state_machine", "pass", elapsed_ms, result)
            return result

        except Exception as exc:
            result = {
                "status": "fail",
                "error": str(exc),
                "uptime_seconds": round(time.time() - self._start_time, 2),
            }
            self._store_result("state_machine", "fail", time.time() - start, result)
            return result

    # ------------------------------------------------------------------
    # Aggregate checks
    # ------------------------------------------------------------------

    async def get_health_report(self) -> dict[str, Any]:
        """Run all health checks and return a comprehensive report.

        Returns:
            Dictionary with all check results and overall status.
        """
        logger.debug("Running full health check suite...")
        self._check_count += 1

        await self.check_postgres()
        await self.check_ollama()
        await self.check_governance()
        self.check_state_machine()

        critical_results = {
            name: self._check_results.get(name)
            for name in self.CRITICAL_CHECKS
        }

        all_critical_pass = all(
            r is not None and r.status == "pass"
            for r in critical_results.values()
        )

        report = {
            "overall_status": "healthy" if all_critical_pass else "unhealthy",
            "timestamp": time.time(),
            "checks": {
                name: {
                    "status": r.status if r else "unknown",
                    "response_ms": round(r.response_time_ms, 2) if r else None,
                    "details": r.details if r else {},
                }
                for name, r in self._check_results.items()
            },
            "summary": {
                "total_checks": len(self._check_results),
                "pass": sum(1 for r in self._check_results.values() if r.status == "pass"),
                "warn": sum(1 for r in self._check_results.values() if r.status == "warn"),
                "fail": sum(1 for r in self._check_results.values() if r.status == "fail"),
                "checks_performed": self._check_count,
            },
        }

        logger.debug(
            "Health report: %s (pass=%d, warn=%d, fail=%d)",
            report["overall_status"],
            report["summary"]["pass"],
            report["summary"]["warn"],
            report["summary"]["fail"],
        )

        return report

    def is_healthy(self) -> bool:
        """Quick check: are all critical components healthy?

        Returns:
            True if all critical checks (postgres, ollama, governance) pass.
        """
        for name in self.CRITICAL_CHECKS:
            result = self._check_results.get(name)
            if result is None or result.status != "pass":
                return False
        return True

    # ------------------------------------------------------------------
    # Periodic monitoring
    # ------------------------------------------------------------------

    async def start_monitoring(self, interval: int = 30) -> None:
        """Start periodic health checks in the background.

        Args:
            interval: Seconds between health checks (default: 30).
        """
        if self._monitoring_task is not None and not self._monitoring_task.done():
            logger.warning("Health monitoring already running")
            return

        self._monitoring_interval = interval
        self._stop_event = asyncio.Event()
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(), name="health_monitor"
        )
        logger.info("Health monitoring started (interval=%ds)", interval)

    async def stop_monitoring(self) -> None:
        """Stop periodic health checks."""
        if self._monitoring_task is None:
            return

        if self._stop_event is not None:
            self._stop_event.set()

        try:
            await asyncio.wait_for(self._monitoring_task, timeout=5)
        except asyncio.TimeoutError:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        self._monitoring_task = None
        logger.info("Health monitoring stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _monitoring_loop(self) -> None:
        """Background loop that runs periodic health checks."""
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                report = await self.get_health_report()
                if report["overall_status"] != "healthy":
                    logger.warning(
                        "Health check detected unhealthy state: %s",
                        report["overall_status"],
                    )
            except Exception as exc:
                logger.error("Health monitoring check failed: %s", exc)

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._monitoring_interval,
                )
            except asyncio.TimeoutError:
                pass  # Normal -- interval elapsed, run next check

    def _store_result(
        self,
        name: str,
        status: str,
        elapsed_s: float,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Store a health check result."""
        self._check_results[name] = HealthCheckResult(
            name=name,
            status=status,
            response_time_ms=elapsed_s * 1000,
            details=details or {},
        )

    def _get_component(self, name: str) -> Any | None:
        """Safely get a component from the bootstrap instance."""
        if self._bootstrap is None:
            return None
        try:
            return self._bootstrap.get_component(name)
        except KeyError:
            return None
