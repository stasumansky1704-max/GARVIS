"""Runtime Monitor — runtime/monitor.py

Monitors GARVIS runtime health and resources.

Reports:
- Service status (API, Ollama, PostgreSQL)
- Container status
- Basic resource usage (CPU, RAM)
- Ollama model status
- Database status
- Dashboard status
- Governance schema status

Purely observational — reports only, never acts.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

from runtime.config import RuntimeConfig
from runtime.health import HealthMonitor

logger = logging.getLogger("garvis.runtime.monitor")


# ---------------------------------------------------------------------------
# RuntimeMonitor — observational runtime monitoring
# ---------------------------------------------------------------------------


class RuntimeMonitor:
    """Monitors GARVIS runtime health and resources.

    Reports:
    - Service status (API, Ollama, PostgreSQL)
    - Container status
    - Basic resource usage (CPU, RAM)
    - Ollama model status
    - Database status
    - Dashboard status
    - Governance schema status

    Purely observational — reports only, never acts.
    """

    # Service names and their expected endpoints/check methods
    SERVICES: dict[str, dict[str, Any]] = {
        "api": {
            "description": "GARVIS Operator API",
            "check_method": "_check_api",
        },
        "ollama": {
            "description": "Ollama LLM service",
            "check_method": "_check_ollama",
        },
        "postgres": {
            "description": "PostgreSQL database",
            "check_method": "_check_postgres",
        },
        "governance": {
            "description": "Governance subsystem",
            "check_method": "_check_governance",
        },
    }

    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig.from_env()
        self._monitoring_active = False
        self._monitoring_task: asyncio.Task | None = None
        self._last_report: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Service status
    # ------------------------------------------------------------------

    def get_service_status(self) -> dict[str, Any]:
        """Get status of all services.

        Returns:
            Dict with status for each service.
        """
        services: dict[str, Any] = {}

        for name, info in self.SERVICES.items():
            check_method = getattr(self, info["check_method"], None)
            if check_method:
                try:
                    status = check_method()
                except Exception as exc:
                    status = {
                        "status": "unknown",
                        "error": str(exc),
                    }
            else:
                status = {"status": "unknown", "reason": "No check method"}

            services[name] = {
                "name": name,
                "description": info["description"],
                **status,
            }

        # Overall status
        all_healthy = all(
            s.get("status") in ("healthy", "running", "active", "pass")
            for s in services.values()
        )

        return {
            "overall": "healthy" if all_healthy else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": services,
        }

    # ------------------------------------------------------------------
    # Container status
    # ------------------------------------------------------------------

    def get_container_status(self) -> list[dict[str, Any]]:
        """Get Docker container status.

        Returns:
            List of container status dicts.
        """
        containers: list[dict[str, Any]] = []

        # Check if docker is available
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json
                for line in result.stdout.strip().split("\n"):
                    try:
                        container = json.loads(line)
                        containers.append({
                            "id": container.get("ID", "unknown"),
                            "name": container.get("Names", "unknown"),
                            "image": container.get("Image", "unknown"),
                            "status": container.get("Status", "unknown"),
                            "state": container.get("State", "unknown"),
                            "ports": container.get("Ports", ""),
                        })
                    except json.JSONDecodeError:
                        continue
            elif result.returncode != 0:
                containers.append({
                    "name": "docker",
                    "status": "unavailable",
                    "error": result.stderr.strip(),
                })
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
            containers.append({
                "name": "docker",
                "status": "unavailable",
                "error": str(exc),
            })

        return containers

    # ------------------------------------------------------------------
    # Resource usage
    # ------------------------------------------------------------------

    def get_resource_usage(self) -> dict[str, Any]:
        """Get basic CPU/RAM usage.

        Returns:
            Resource usage dict.
        """
        resources: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # CPU usage
        try:
            # Read /proc/loadavg for load average
            if os.path.exists("/proc/loadavg"):
                with open("/proc/loadavg") as f:
                    loadavg = f.read().strip().split()
                    resources["cpu"] = {
                        "load_1min": float(loadavg[0]),
                        "load_5min": float(loadavg[1]),
                        "load_15min": float(loadavg[2]),
                    }
            else:
                resources["cpu"] = {"status": "unknown", "reason": "/proc/loadavg unavailable"}
        except OSError as exc:
            resources["cpu"] = {"status": "error", "error": str(exc)}

        # Memory usage
        try:
            if os.path.exists("/proc/meminfo"):
                meminfo: dict[str, int] = {}
                with open("/proc/meminfo") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip().split()[0]
                            meminfo[key] = int(value) * 1024  # Convert kB to bytes

                total = meminfo.get("MemTotal", 0)
                available = meminfo.get("MemAvailable", 0)
                used = total - available if total > 0 else 0
                percent = (used / total * 100) if total > 0 else 0

                resources["memory"] = {
                    "total_bytes": total,
                    "available_bytes": available,
                    "used_bytes": used,
                    "used_percent": round(percent, 2),
                    "total_gb": round(total / (1024 ** 3), 2),
                    "used_gb": round(used / (1024 ** 3), 2),
                }
            else:
                resources["memory"] = {
                    "status": "unknown",
                    "reason": "/proc/meminfo unavailable",
                }
        except OSError as exc:
            resources["memory"] = {"status": "error", "error": str(exc)}

        # Disk usage
        try:
            result = subprocess.run(
                ["df", "-h", "."],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 6:
                        resources["disk"] = {
                            "filesystem": parts[0],
                            "size": parts[1],
                            "used": parts[2],
                            "available": parts[3],
                            "use_percent": parts[4],
                            "mount": parts[5],
                        }
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
            resources["disk"] = {"status": "error", "error": str(exc)}

        return resources

    # ------------------------------------------------------------------
    # Ollama status
    # ------------------------------------------------------------------

    def get_ollama_status(self) -> dict[str, Any]:
        """Get Ollama status and available models.

        Returns:
            Ollama status dict.
        """
        return self._check_ollama()

    # ------------------------------------------------------------------
    # Database status
    # ------------------------------------------------------------------

    def get_database_status(self) -> dict[str, Any]:
        """Get PostgreSQL status.

        Returns:
            Database status dict.
        """
        return self._check_postgres()

    # ------------------------------------------------------------------
    # Full report
    # ------------------------------------------------------------------

    def get_full_report(self) -> dict[str, Any]:
        """Get complete monitoring report.

        Combines all monitoring checks into a single comprehensive report.

        Returns:
            Complete monitoring report dict.
        """
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": self.get_service_status(),
            "containers": self.get_container_status(),
            "resources": self.get_resource_usage(),
            "ollama": self.get_ollama_status(),
            "database": self.get_database_status(),
        }

        # Overall system health
        service_overall = report["services"].get("overall", "unknown")
        db_status = report["database"].get("status", "unknown")
        ollama_status = report["ollama"].get("status", "unknown")

        if service_overall == "healthy" and db_status in ("healthy", "running"):
            report["overall"] = "healthy"
        elif service_overall == "degraded" or db_status == "degraded":
            report["overall"] = "degraded"
        else:
            report["overall"] = "unknown"

        self._last_report = report
        return report

    # ------------------------------------------------------------------
    # Continuous monitoring
    # ------------------------------------------------------------------

    async def continuous_monitoring(self, interval: int = 60) -> None:
        """Continuous monitoring loop (operator-initiated only).

        Runs indefinitely until cancelled. Reports are logged but
        NEVER trigger autonomous actions.

        Args:
            interval: Seconds between monitoring cycles.
        """
        self._monitoring_active = True
        logger.info("Continuous monitoring started (interval=%ds)", interval)

        cycle = 0
        try:
            while self._monitoring_active:
                cycle += 1
                try:
                    report = self.get_full_report()
                    logger.info(
                        "Monitoring cycle #%d: overall=%s, services=%d",
                        cycle,
                        report.get("overall", "unknown"),
                        len(report.get("services", {}).get("services", {})),
                    )

                    # Log warnings for degraded services (never act)
                    services = report.get("services", {}).get("services", {})
                    for name, status in services.items():
                        if status.get("status") not in (
                            "healthy", "running", "active", "pass"
                        ):
                            logger.warning(
                                "Service '%s' status: %s",
                                name,
                                status.get("status"),
                            )

                except Exception as exc:
                    logger.error("Monitoring cycle failed: %s", exc)

                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Continuous monitoring cancelled")
        finally:
            self._monitoring_active = False

    def stop_monitoring(self) -> None:
        """Stop continuous monitoring."""
        self._monitoring_active = False
        logger.info("Continuous monitoring stopped")

    # ------------------------------------------------------------------
    # Individual check methods
    # ------------------------------------------------------------------

    def _check_api(self) -> dict[str, Any]:
        """Check GARVIS API status."""
        # In production, this would make a request to the API health endpoint
        return {
            "status": "unknown",
            "message": "API status check not configured",
        }

    def _check_ollama(self) -> dict[str, Any]:
        """Check Ollama service status."""
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 f"{self.config.ollama_host}/api/tags"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip() == "200":
                return {
                    "status": "healthy",
                    "host": self.config.ollama_host,
                    "default_model": self.config.default_model,
                }
            else:
                return {
                    "status": "unreachable",
                    "host": self.config.ollama_host,
                    "response_code": result.stdout.strip(),
                }
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
            return {
                "status": "unknown",
                "error": str(exc),
            }

    def _check_postgres(self) -> dict[str, Any]:
        """Check PostgreSQL status."""
        try:
            result = subprocess.run(
                [
                    "pg_isready",
                    "-h", self.config.postgres_host,
                    "-p", str(self.config.postgres_port),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return {
                    "status": "healthy",
                    "host": self.config.postgres_host,
                    "port": self.config.postgres_port,
                    "database": self.config.postgres_db,
                }
            else:
                return {
                    "status": "unreachable",
                    "host": self.config.postgres_host,
                    "port": self.config.postgres_port,
                    "error": result.stderr.strip(),
                }
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
            return {
                "status": "unknown",
                "error": str(exc),
            }

    def _check_governance(self) -> dict[str, Any]:
        """Check governance subsystem status."""
        return {
            "status": "unknown",
            "message": (
                "Governance status requires active runtime. "
                "Check via /api/v1/governance endpoint."
            ),
        }

    # ------------------------------------------------------------------
    # Dashboard status
    # ------------------------------------------------------------------

    def get_dashboard_status(self) -> dict[str, Any]:
        """Get status for the operator dashboard.

        Returns a condensed status suitable for dashboard display.
        """
        services = self.get_service_status()
        resources = self.get_resource_usage()

        return {
            "overall": services.get("overall", "unknown"),
            "services": {
                name: info.get("status", "unknown")
                for name, info in services.get("services", {}).items()
            },
            "memory_percent": resources.get("memory", {}).get("used_percent"),
            "load_average": resources.get("cpu", {}).get("load_1min"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
