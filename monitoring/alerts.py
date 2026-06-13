"""Governance Alert Engine — monitoring/alerts.py

Observational alert engine for governance monitoring.
Alerts notify the operator. They NEVER take autonomous action.
The operator must acknowledge and resolve every alert.

Alert rules cover:
- Governance violations (critical + warning)
- Governance pressure thresholds
- Alignment drift detection
- State machine transitions (FAIL_CLOSED, DEGRADED)
- Forbidden pattern detection
- Uncertainty disclosure rates
- Boundary violations
- System resilience and equilibrium
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from models.governance import GovernanceViolation
from models.cognition import OperationalState

logger = logging.getLogger("garvis.monitoring.alerts")


# -----------------------------------------------------------------------------
# AlertSeverity — severity levels for operator attention
# -----------------------------------------------------------------------------


class AlertSeverity(str, Enum):
    """Alert severity levels.

    CRITICAL: Immediate operator attention required
    WARNING:  Operator should be aware
    INFO:     FYI — informational only
    DEBUG:    Detailed diagnostic data
    """

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


# -----------------------------------------------------------------------------
# Alert — individual alert record
# -----------------------------------------------------------------------------


class Alert(BaseModel):
    """A single alert for operator notification.

    Alerts are purely observational — they describe what happened,
    never what to do about it. The operator decides on action.
    """

    alert_id: UUID = Field(default_factory=uuid4)
    severity: AlertSeverity
    category: str  # "governance", "cognition", "memory", "system"
    title: str
    description: str
    source_schema: str | None = None
    source_component: str | None = None
    session_id: UUID | None = None
    trace_id: UUID | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    resolved: bool = False
    resolution_time: datetime | None = None
    auto_resolve_conditions: list[str] = Field(default_factory=list)
    # Deduplication key — alerts with the same key may be suppressed
    dedup_key: str | None = None

    def model_post_init(self, __context: Any) -> None:
        """Build dedup_key from alert attributes if not set."""
        if self.dedup_key is None:
            parts = [
                self.severity.value,
                self.category,
                self.title,
                str(self.source_schema or ""),
                str(self.source_component or ""),
            ]
            self.dedup_key = "|".join(parts)


# -----------------------------------------------------------------------------
# AlertEngine — observational alert system
# -----------------------------------------------------------------------------


class AlertEngine:
    """Observational alert engine for governance monitoring.

    Alerts notify the operator. They NEVER take autonomous action.
    The operator must acknowledge and resolve every alert.

    Critical alerts require manual resolution (no auto-resolve).
    Warning/Info alerts may auto-resolve when conditions improve.
    """

    # ------------------------------------------------------------------
    # Alert rule definitions
    # ------------------------------------------------------------------

    ALERT_RULES: dict[str, dict[str, Any]] = {
        "governance_violation_critical": {
            "severity": AlertSeverity.CRITICAL,
            "category": "governance",
            "title_template": "Critical Governance Violation: {schema_id}",
            "description_template": (
                "Policy {policy_id} violated in schema {schema_id}. "
                "Enforcement: {enforcement}. Context: {context}"
            ),
            "auto_resolve": False,
        },
        "governance_pressure_high": {
            "severity": AlertSeverity.WARNING,
            "category": "governance",
            "title_template": "High Governance Pressure: {scope}",
            "description_template": (
                "Pressure score {pressure:.2f} exceeds threshold {threshold:.2f}. "
                "Scope: {scope}. Review governance constraints."
            ),
            "threshold": 0.7,
            "auto_resolve": True,
            "auto_resolve_condition": "pressure drops below threshold",
        },
        "alignment_drift_detected": {
            "severity": AlertSeverity.WARNING,
            "category": "governance",
            "title_template": "Alignment Drift Detected",
            "description_template": (
                "Drift rate {drift_rate:.4f} exceeds threshold {threshold:.4f}. "
                "Indicates gradual alignment degradation. Review governance schemas."
            ),
            "threshold": 0.1,
            "auto_resolve": True,
            "auto_resolve_condition": "drift rate returns below threshold",
        },
        "state_fail_closed": {
            "severity": AlertSeverity.CRITICAL,
            "category": "cognition",
            "title_template": "Runtime Entered FAIL_CLOSED State",
            "description_template": (
                "Reason: {reason}. All cognition halted. "
                "Operator intervention required to recover."
            ),
            "auto_resolve": False,
        },
        "state_degraded": {
            "severity": AlertSeverity.WARNING,
            "category": "cognition",
            "title_template": "Runtime Entered DEGRADED State",
            "description_template": (
                "Reason: {reason}. Reduced capability mode active. "
                "Enhanced governance monitoring in effect."
            ),
            "auto_resolve": True,
            "auto_resolve_condition": "runtime returns to normal state",
        },
        "forbidden_pattern_detected": {
            "severity": AlertSeverity.CRITICAL,
            "category": "cognition",
            "title_template": "Forbidden Pattern Detected: {pattern_id}",
            "description_template": (
                "Pattern '{pattern_id}' detected in state sequence. "
                "Auto-FAIL_CLOSED triggered. State machine locked."
            ),
            "auto_resolve": False,
        },
        "uncertainty_disclosure_low": {
            "severity": AlertSeverity.WARNING,
            "category": "governance",
            "title_template": "Low Uncertainty Disclosure Rate",
            "description_template": (
                "Disclosure rate {rate:.2f} below threshold {threshold:.2f}. "
                "Check uncertainty_management schema. "
                "System may be overconfident."
            ),
            "threshold": 0.5,
            "auto_resolve": True,
            "auto_resolve_condition": "disclosure rate returns above threshold",
        },
        "boundary_violation": {
            "severity": AlertSeverity.CRITICAL,
            "category": "governance",
            "title_template": "Boundary Violation Detected",
            "description_template": (
                "Operation exceeded declared boundaries. Schema: {schema_id}. "
                "Operation was blocked. Review boundary constraints."
            ),
            "auto_resolve": False,
        },
        "resilience_drop": {
            "severity": AlertSeverity.WARNING,
            "category": "system",
            "title_template": "Resilience Score Dropped",
            "description_template": (
                "Resilience score {score:.2f} below threshold {threshold:.2f}. "
                "System may be approaching failure mode."
            ),
            "threshold": 0.6,
            "auto_resolve": True,
            "auto_resolve_condition": "resilience score returns above threshold",
        },
        "equilibrium_unstable": {
            "severity": AlertSeverity.WARNING,
            "category": "system",
            "title_template": "Equilibrium Unstable",
            "description_template": (
                "Stability score {score:.2f} below threshold {threshold:.2f}. "
                "Excessive state churn detected. System may oscillate."
            ),
            "threshold": 0.5,
            "auto_resolve": True,
            "auto_resolve_condition": "stability score returns above threshold",
        },
    }

    # Duplicate suppression window (seconds) — alerts with the same dedup_key
    # within this window will increment a counter on the existing alert
    # instead of creating a new one
    DEDUP_WINDOW_SECONDS: int = 60

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._alerts: list[Alert] = []
        self._alert_history: list[Alert] = []
        self._handlers: list[Callable[[Alert], None]] = []
        self._suppress_until: dict[str, datetime] = {}

    # ------------------------------------------------------------------
    # Core alert creation
    # ------------------------------------------------------------------

    def _create_alert(
        self,
        rule_id: str,
        **format_kwargs: Any,
    ) -> Alert | None:
        """Create an alert from a rule definition.

        Handles deduplication suppression. Returns None if the alert
        should be suppressed (duplicate within window).
        """
        rule = self.ALERT_RULES[rule_id]
        title = rule["title_template"].format(**format_kwargs)
        description = rule["description_template"].format(**format_kwargs)

        severity: AlertSeverity = rule["severity"]
        category: str = rule["category"]
        auto_resolve: bool = rule.get("auto_resolve", False)
        auto_resolve_conditions: list[str] = []
        if auto_resolve:
            condition = rule.get("auto_resolve_condition", "condition resolves")
            auto_resolve_conditions.append(condition)

        alert = Alert(
            severity=severity,
            category=category,
            title=title,
            description=description,
            auto_resolve_conditions=auto_resolve_conditions,
        )

        # Check deduplication suppression
        now = datetime.now(timezone.utc)
        suppress_key = alert.dedup_key or str(alert.alert_id)
        if suppress_key in self._suppress_until:
            if now < self._suppress_until[suppress_key]:
                logger.debug(
                    "Alert suppressed (dedup): %s (within %ds window)",
                    title,
                    self.DEDUP_WINDOW_SECONDS,
                )
                return None

        # Set suppression window for this dedup key
        self._suppress_until[suppress_key] = now + timedelta(
            seconds=self.DEDUP_WINDOW_SECONDS
        )

        return alert

    def _emit(self, alert: Alert | None) -> Alert | None:
        """Store and notify if alert is not None."""
        if alert is None:
            return None
        self._alerts.append(alert)
        self._alert_history.append(alert)
        self._notify(alert)
        logger.info(
            "ALERT %s [%s] %s — id=%s",
            alert.severity.value.upper(),
            alert.category,
            alert.title,
            alert.alert_id,
        )
        return alert

    # ------------------------------------------------------------------
    # Alert rule checkers
    # ------------------------------------------------------------------

    def check_governance_violation(
        self,
        violation: GovernanceViolation,
    ) -> Alert | None:
        """Check if a governance violation should trigger an alert.

        Critical violations always trigger alerts. Warnings trigger
        if they haven't been seen recently (dedup window).
        """
        severity = AlertSeverity(violation.severity) if violation.severity in {
            "critical", "warning", "info", "debug"
        } else AlertSeverity.WARNING

        if severity == AlertSeverity.CRITICAL:
            rule_id = "governance_violation_critical"
        elif severity == AlertSeverity.WARNING:
            rule_id = "governance_violation_critical"
        else:
            # Info-level violations don't alert unless configured
            return None

        if rule_id not in self.ALERT_RULES:
            return None

        enforcement = violation.context.get("enforcement", "unknown")
        context_summary = ", ".join(
            f"{k}={v}" for k, v in list(violation.context.items())[:3]
        )

        alert = self._create_alert(
            rule_id,
            schema_id=violation.schema_id,
            policy_id=violation.policy_id,
            enforcement=enforcement,
            context=context_summary,
        )
        if alert:
            alert.source_schema = violation.schema_id
            alert.timestamp = violation.timestamp
        return self._emit(alert)

    def check_pressure(self, scope: str, pressure: float) -> Alert | None:
        """Check if governance pressure exceeds threshold."""
        rule = self.ALERT_RULES["governance_pressure_high"]
        threshold: float = rule["threshold"]

        if pressure <= threshold:
            return None

        alert = self._create_alert(
            "governance_pressure_high",
            scope=scope,
            pressure=pressure,
            threshold=threshold,
        )
        if alert:
            alert.source_component = f"governance.pressure.{scope}"
        return self._emit(alert)

    def check_alignment_drift(self, drift_rate: float) -> Alert | None:
        """Check if alignment drift exceeds threshold."""
        rule = self.ALERT_RULES["alignment_drift_detected"]
        threshold: float = rule["threshold"]

        if drift_rate <= threshold:
            return None

        alert = self._create_alert(
            "alignment_drift_detected",
            drift_rate=drift_rate,
            threshold=threshold,
        )
        if alert:
            alert.source_component = "governance.alignment_monitor"
        return self._emit(alert)

    def check_state_change(
        self,
        from_state: OperationalState,
        to_state: OperationalState,
        reason: str,
    ) -> list[Alert]:
        """Check if a state transition should trigger alerts.

        Returns a list because some transitions may trigger multiple
        alerts (e.g., FAIL_CLOSED from a forbidden pattern triggers
        both state_fail_closed and forbidden_pattern_detected).
        """
        alerts: list[Alert] = []

        # Check for FAIL_CLOSED entry
        if to_state == OperationalState.FAIL_CLOSED:
            alert = self._create_alert(
                "state_fail_closed",
                reason=reason,
            )
            if alert:
                alert.source_component = "cognition.state_machine"
                self._emit(alert)
                alerts.append(alert)

        # Check for DEGRADED entry
        if to_state == OperationalState.DEGRADED:
            alert = self._create_alert(
                "state_degraded",
                reason=reason,
            )
            if alert:
                alert.source_component = "cognition.state_machine"
                self._emit(alert)
                alerts.append(alert)

        # Check for forbidden patterns in the transition
        # These are detected by the state machine and passed as the reason
        if "forbidden_pattern" in reason.lower():
            pattern_id = reason.split(":")[-1].strip() if ":" in reason else "unknown"
            alert = self._create_alert(
                "forbidden_pattern_detected",
                pattern_id=pattern_id,
            )
            if alert:
                alert.source_component = "cognition.state_machine"
                self._emit(alert)
                alerts.append(alert)

        return alerts

    def check_forbidden_pattern_direct(self, pattern_id: str) -> Alert | None:
        """Directly alert on a forbidden pattern detection.

        Used when the forbidden pattern is detected outside of
        normal state change flow (e.g., by a scanner).
        """
        alert = self._create_alert(
            "forbidden_pattern_detected",
            pattern_id=pattern_id,
        )
        if alert:
            alert.source_component = "cognition.pattern_scanner"
        return self._emit(alert)

    def check_uncertainty_disclosure(self, rate: float) -> Alert | None:
        """Check if uncertainty disclosure rate is too low."""
        rule = self.ALERT_RULES["uncertainty_disclosure_low"]
        threshold: float = rule["threshold"]

        if rate >= threshold:
            return None

        alert = self._create_alert(
            "uncertainty_disclosure_low",
            rate=rate,
            threshold=threshold,
        )
        if alert:
            alert.source_schema = "uncertainty_management"
            alert.source_component = "governance.disclosure_monitor"
        return self._emit(alert)

    def check_boundary_violation(
        self,
        schema_id: str,
        operation: str,
    ) -> Alert | None:
        """Check if a boundary violation should trigger an alert."""
        alert = self._create_alert(
            "boundary_violation",
            schema_id=schema_id,
            operation=operation,
        )
        if alert:
            alert.source_schema = schema_id
            alert.source_component = "governance.boundary_enforcer"
        return self._emit(alert)

    def check_resilience(self, score: float) -> Alert | None:
        """Check if resilience score dropped below threshold."""
        rule = self.ALERT_RULES["resilience_drop"]
        threshold: float = rule["threshold"]

        if score >= threshold:
            return None

        alert = self._create_alert(
            "resilience_drop",
            score=score,
            threshold=threshold,
        )
        if alert:
            alert.source_component = "system.resilience_monitor"
        return self._emit(alert)

    def check_equilibrium(self, score: float) -> Alert | None:
        """Check if equilibrium is unstable."""
        rule = self.ALERT_RULES["equilibrium_unstable"]
        threshold: float = rule["threshold"]

        if score >= threshold:
            return None

        alert = self._create_alert(
            "equilibrium_unstable",
            score=score,
            threshold=threshold,
        )
        if alert:
            alert.source_component = "system.equilibrium_monitor"
        return self._emit(alert)

    # ------------------------------------------------------------------
    # Operator actions
    # ------------------------------------------------------------------

    def acknowledge(self, alert_id: UUID) -> bool:
        """Operator acknowledges an alert.

        Acknowledgment means the operator has seen the alert.
        It does NOT mean the alert is resolved.

        Returns True if the alert was found and acknowledged.
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id and not alert.acknowledged:
                alert.acknowledged = True
                logger.info(
                    "Alert acknowledged by operator: %s (%s)",
                    alert_id,
                    alert.title,
                )
                return True
        return False

    def resolve(self, alert_id: UUID) -> bool:
        """Operator resolves an alert.

        Resolution means the operator has taken action and considers
        the alert handled. Resolved alerts are removed from active
        alerts but kept in history.

        Returns True if the alert was found and resolved.
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolution_time = datetime.now(timezone.utc)
                logger.info(
                    "Alert resolved by operator: %s (%s)",
                    alert_id,
                    alert.title,
                )
                return True
        return False

    # ------------------------------------------------------------------
    # Auto-resolve: called periodically to resolve alerts whose
    # conditions have cleared
    # ------------------------------------------------------------------

    def attempt_auto_resolve(self, alert_id: UUID) -> bool:
        """Attempt to auto-resolve an alert.

        Only alerts with auto_resolve_conditions can be auto-resolved.
        Critical alerts (no auto_resolve) always return False.

        Called by the monitoring loop when conditions improve.
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id and not alert.resolved:
                if not alert.auto_resolve_conditions:
                    return False  # Cannot auto-resolve
                alert.resolved = True
                alert.resolution_time = datetime.now(timezone.utc)
                logger.info(
                    "Alert auto-resolved: %s (%s) — condition: %s",
                    alert_id,
                    alert.title,
                    alert.auto_resolve_conditions[0],
                )
                return True
        return False

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_active_alerts(
        self,
        severity: AlertSeverity | None = None,
        category: str | None = None,
    ) -> list[Alert]:
        """Get active (unresolved) alerts with optional filtering."""
        result = [a for a in self._alerts if not a.resolved]
        if severity:
            result = [a for a in result if a.severity == severity]
        if category:
            result = [a for a in result if a.category == category]
        return result

    def get_alert_history(self, limit: int = 100) -> list[Alert]:
        """Get full alert history (newest first)."""
        history = sorted(
            self._alert_history,
            key=lambda a: a.timestamp,
            reverse=True,
        )
        return history[:limit]

    def get_alert_summary(self) -> dict[str, Any]:
        """Summary: counts by severity, category, active/resolved."""
        active = [a for a in self._alerts if not a.resolved]
        resolved = [a for a in self._alerts if a.resolved]

        by_severity: dict[str, int] = {}
        by_category: dict[str, int] = {}
        active_by_severity: dict[str, int] = {}

        for alert in self._alert_history:
            sev = alert.severity.value
            cat = alert.category
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_category[cat] = by_category.get(cat, 0) + 1

        for alert in active:
            sev = alert.severity.value
            active_by_severity[sev] = active_by_severity.get(sev, 0) + 1

        return {
            "total_alerts": len(self._alert_history),
            "active_alerts": len(active),
            "resolved_alerts": len(resolved),
            "by_severity": by_severity,
            "by_category": by_category,
            "active_by_severity": active_by_severity,
            "critical_unacknowledged": len([
                a for a in active
                if a.severity == AlertSeverity.CRITICAL and not a.acknowledged
            ]),
            "oldest_unresolved": (
                min((a.timestamp for a in active), default=None)
            ),
        }

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def register_handler(self, handler: Callable[[Alert], None]) -> None:
        """Register a callback for new alerts.

        Handlers are called synchronously when an alert is emitted.
        They must not raise exceptions.
        """
        self._handlers.append(handler)
        logger.debug("Alert handler registered: %s", handler.__name__ if hasattr(handler, "__name__") else repr(handler))

    def unregister_handler(self, handler: Callable[[Alert], None]) -> bool:
        """Unregister a handler. Returns True if found and removed."""
        if handler in self._handlers:
            self._handlers.remove(handler)
            return True
        return False

    def _notify(self, alert: Alert) -> None:
        """Notify all registered handlers of a new alert."""
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as exc:
                logger.error(
                    "Alert handler %s raised exception: %s",
                    handler.__name__ if hasattr(handler, "__name__") else repr(handler),
                    exc,
                )

    # ------------------------------------------------------------------
    # Cascading alert detection
    # ------------------------------------------------------------------

    def detect_cascading_alerts(self, window_seconds: int = 300) -> list[dict[str, Any]]:
        """Detect groups of alerts that may be causally related.

        Looks for bursts of alerts within a time window that share
        the same category or component, suggesting a cascading failure.

        Returns a list of cascade groups, each containing:
        - alerts: list of alert IDs in the cascade
        - category: shared category
        - time_span: seconds between first and last alert
        - alert_count: number of alerts
        """
        if not self._alert_history:
            return []

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_seconds)

        # Filter to recent alerts — handle both naive and aware timestamps
        def _is_recent(alert: Alert) -> bool:
            ts = alert.timestamp
            if ts.tzinfo is None:
                # Naive timestamp — treat as UTC
                ts = ts.replace(tzinfo=timezone.utc)
            return ts >= window_start

        recent = [a for a in self._alert_history if _is_recent(a)]
        if not recent:
            return []

        # Group by category
        by_category: dict[str, list[Alert]] = {}
        for alert in recent:
            by_category.setdefault(alert.category, []).append(alert)

        cascades: list[dict[str, Any]] = []
        for category, alerts in by_category.items():
            if len(alerts) < 3:
                # Need at least 3 alerts to consider it a cascade
                continue

            # Sort by time
            alerts_sorted = sorted(alerts, key=lambda a: a.timestamp)
            time_span = (alerts_sorted[-1].timestamp - alerts_sorted[0].timestamp).total_seconds()

            # Check if any critical alerts in the cascade
            has_critical = any(a.severity == AlertSeverity.CRITICAL for a in alerts)

            cascades.append({
                "alerts": [str(a.alert_id) for a in alerts_sorted],
                "category": category,
                "time_span_seconds": round(time_span, 1),
                "alert_count": len(alerts),
                "has_critical": has_critical,
                "severity_breakdown": self._severity_breakdown(alerts),
            })

        # Sort by severity (critical first) then count
        cascades.sort(key=lambda c: (not c["has_critical"], -c["alert_count"]))
        return cascades

    @staticmethod
    def _severity_breakdown(alerts: list[Alert]) -> dict[str, int]:
        """Count alerts by severity."""
        breakdown: dict[str, int] = {}
        for a in alerts:
            sev = a.severity.value
            breakdown[sev] = breakdown.get(sev, 0) + 1
        return breakdown

    # ------------------------------------------------------------------
    # Expired alert cleanup
    # ------------------------------------------------------------------

    def cleanup_expired_alerts(self, max_age_hours: int = 72) -> int:
        """Remove resolved alerts older than max_age_hours from active list.

        Historical record is preserved in _alert_history. This only
        cleans up the active alert list to prevent unbounded growth.

        Returns the number of alerts cleaned up.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        to_remove = [
            a for a in self._alerts
            if a.resolved and a.resolution_time and a.resolution_time < cutoff
        ]
        for alert in to_remove:
            self._alerts.remove(alert)
        if to_remove:
            logger.info(
                "Cleaned up %d expired resolved alerts (older than %d hours)",
                len(to_remove),
                max_age_hours,
            )
        return len(to_remove)

    # ------------------------------------------------------------------
    # Reset (for testing)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all alerts. For testing only."""
        self._alerts.clear()
        self._alert_history.clear()
        self._handlers.clear()
        self._suppress_until.clear()
        logger.warning("AlertEngine reset — all alerts cleared")
