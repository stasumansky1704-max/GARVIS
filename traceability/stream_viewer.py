"""
Real-time Audit Stream Viewer

Connects to the audit pipeline and displays events as they occur,
with optional filtering by severity, event type, or component.

The operator sees EVERYTHING — every governance check, every state
transition, every audit event — streamed in real-time with
color-coded formatting.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ANSI codes
# ---------------------------------------------------------------------------

_C: dict[str, str] = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
    "bright_white": "\033[97m",
    "bg_bright_red": "\033[101m",
    "bg_yellow": "\033[43m",
    "bg_blue": "\033[44m",
}


def _c(text: str, *codes: str) -> str:
    if not AuditStreamViewer._color_enabled:
        return text
    prefix = "".join(_C.get(c, "") for c in codes)
    return f"{prefix}{text}{_C['reset']}"


def _bold(text: str) -> str:
    return _c(text, "bold")


def _dim(text: str) -> str:
    return _c(text, "dim")


def _green(text: str) -> str:
    return _c(text, "bright_green")


def _red(text: str) -> str:
    return _c(text, "bright_red")


def _yellow(text: str) -> str:
    return _c(text, "bright_yellow")


def _blue(text: str) -> str:
    return _c(text, "bright_blue")


def _magenta(text: str) -> str:
    return _c(text, "bright_magenta")


def _cyan(text: str) -> str:
    return _c(text, "bright_cyan")


def _critical(text: str) -> str:
    return _c(text, "bg_bright_red", "bold")


def _warning(text: str) -> str:
    return _c(text, "bg_yellow", "bold")


# ---------------------------------------------------------------------------
# AuditStreamViewer
# ---------------------------------------------------------------------------


class AuditStreamViewer:
    """Real-time streaming display of audit events.

    Connects to the audit pipeline and displays events as they occur,
    with optional filtering by severity, event type, or component.
    """

    _color_enabled: bool = True

    def __init__(self, audit_pipeline: Any | None = None) -> None:
        self.audit = audit_pipeline
        self.filters: dict[str, str | None] = {}
        self._running = False
        self._seen_event_ids: set[str] = set()
        self._poll_interval: float = 1.0

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def start_streaming(self, interval: float = 1.0) -> None:
        """Start displaying audit events in real-time.

        Polls the audit pipeline at *interval* seconds and displays
        new events since last poll.  Press Ctrl+C to stop.

        Parameters
        ----------
        interval:
            Polling interval in seconds (default 1.0).
        """
        self._running = True
        self._poll_interval = interval
        self._seen_event_ids.clear()

        # Banner
        print()
        print("  " + "=" * 60)
        print("  " + _bold("  GARVIS AUDIT STREAM"))
        print("  " + _dim(f"  Polling every {interval}s | Filters: {self._fmt_filters() or 'none'}"))
        print("  " + "=" * 60)
        print()

        try:
            while self._running:
                await self._poll_once()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            print()
            print("  " + _dim("Audit stream stopped by operator."))
            print()
        finally:
            self._running = False

    async def _poll_once(self) -> None:
        """Single poll cycle: fetch new events and display them."""
        if self.audit is None:
            return

        try:
            events = await self.audit.get_events(
                event_type=self.filters.get("event_type"),
                severity=self.filters.get("severity"),
                limit=100,
            )
        except Exception as exc:
            logger.warning("Failed to poll audit events: %s", exc)
            return

        new_events = [e for e in events if str(e.event_id) not in self._seen_event_ids]
        # Keep seen set bounded
        for e in new_events:
            self._seen_event_ids.add(str(e.event_id))
        if len(self._seen_event_ids) > 10000:
            self._seen_event_ids = set(list(self._seen_event_ids)[-5000:])

        # Filter by component if specified
        component_filter = self.filters.get("component")
        if component_filter:
            new_events = [e for e in new_events if e.component == component_filter]

        for event in new_events:
            self.display_event(event)

    # ------------------------------------------------------------------
    # Event display
    # ------------------------------------------------------------------

    def display_event(self, event: Any) -> None:
        """Display a single audit event with color-coded formatting.

        Parameters
        ----------
        event:
            An AuditEvent or dict with at least event_type, severity,
            component, timestamp, and details attributes/keys.
        """
        # Normalise dict vs model
        if isinstance(event, dict):
            evt = event
            event_type = evt.get("event_type", "?")
            severity = evt.get("severity", "info")
            component = evt.get("component", "?")
            timestamp = evt.get("timestamp", datetime.now(timezone.utc))
            session_id = evt.get("session_id")
            trace_id = evt.get("trace_id")
            details = evt.get("details", {})
            governance_context = evt.get("governance_context", [])
        else:
            event_type = getattr(event, "event_type", "?")
            severity = getattr(event, "severity", "info")
            component = getattr(event, "component", "?")
            timestamp = getattr(event, "timestamp", datetime.now(timezone.utc))
            session_id = getattr(event, "session_id", None)
            trace_id = getattr(event, "trace_id", None)
            details = getattr(event, "details", {})
            governance_context = getattr(event, "governance_context", [])

        # Format timestamp
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except Exception:
                timestamp = datetime.now(timezone.utc)
        ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Severity badge
        sev_badge = self._severity_badge(severity)

        # Session / trace IDs
        session_str = self._fmt_id(session_id)[:8] if session_id else "?"
        trace_str = self._fmt_id(trace_id)[:8] if trace_id else "?"

        # Build output
        lines: list[str] = []
        lines.append(f"[{ts_str}] {sev_badge} {_cyan(component)}::{_bold(event_type)}")
        lines.append(f"  Session: {session_str} | Trace: {trace_str} | Component: {component}")

        # Details
        detail_lines = self._format_details(details, governance_context, event_type)
        lines.extend(detail_lines)

        # Print with severity-based color coding for the whole block
        block = "\n".join(lines)
        if severity == "critical":
            block = _red(block)
        elif severity == "warning":
            block = _yellow(block)
        elif severity == "debug":
            block = _dim(block)

        print(block)
        print()  # blank line between events

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def set_filter(
        self,
        event_type: str | None = None,
        severity: str | None = None,
        component: str | None = None,
    ) -> None:
        """Set filters for the event stream.

        Parameters
        ----------
        event_type:
            Only show events of this type (e.g. "inference", "state_transition").
        severity:
            Only show events with this severity ("critical", "warning", "info", "debug").
        component:
            Only show events from this component.
        """
        if event_type is not None:
            self.filters["event_type"] = event_type
        if severity is not None:
            self.filters["severity"] = severity
        if component is not None:
            self.filters["component"] = component

        logger.info(
            "Audit stream filters updated: %s",
            self._fmt_filters() or "none",
        )

    def clear_filters(self) -> None:
        """Remove all filters."""
        self.filters.clear()
        self._seen_event_ids.clear()

    def stop_streaming(self) -> None:
        """Stop the event stream."""
        self._running = False
        logger.info("Audit stream stopped")

    # ------------------------------------------------------------------
    # Colour toggle
    # ------------------------------------------------------------------

    @classmethod
    def enable_color(cls) -> None:
        cls._color_enabled = True

    @classmethod
    def disable_color(cls) -> None:
        cls._color_enabled = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_id(val: Any) -> str:
        if val is None:
            return "?"
        if isinstance(val, UUID):
            return str(val)
        return str(val)

    def _severity_badge(self, severity: str) -> str:
        badges = {
            "critical": _critical(" CRITICAL "),
            "warning": _warning(" WARNING  "),
            "info": _blue("  INFO    "),
            "debug": _dim("  DEBUG   "),
        }
        return badges.get(severity, severity.upper().rjust(10))

    def _format_details(
        self,
        details: dict[str, Any],
        governance_context: list[str],
        event_type: str,
    ) -> list[str]:
        """Format event details into indented lines."""
        lines: list[str] = []

        # Type-specific formatting
        if event_type == "inference":
            model = details.get("model", "?")
            prompt_len = details.get("prompt_length", 0)
            resp_len = details.get("response_length", 0)
            passed = details.get("passed_validation", True)
            checks_count = details.get("governance_checks_count", 0)
            mem_count = details.get("memory_influences_count", 0)
            duration = details.get("duration_ms", 0)
            if duration:
                lines.append(f"  Model: {model} | Tokens: {prompt_len + resp_len} | "
                            f"Duration: {duration}ms")
            else:
                lines.append(f"  Model: {model} | Prompt: {prompt_len} chars | "
                            f"Response: {resp_len} chars")
            if passed:
                lines.append(f"  Validation: {_green('PASSED')} | Governance: {checks_count} checks | "
                            f"Memory: {mem_count} influences")
            else:
                failures = details.get("validation_failures", [])
                lines.append(f"  Validation: {_red('FAILED')} | Failures: {failures}")

        elif event_type == "state_transition":
            from_s = details.get("from_state", "?")
            to_s = details.get("to_state", "?")
            trigger = details.get("trigger", "")
            gov = details.get("governance_check", False)
            from_col = from_s
            to_col = _red(to_s) if to_s in ("fail_closed", "degraded") else _green(to_s)
            lines.append(f"  {from_col} -> {to_col}  (trigger: {trigger})")
            if gov:
                lines.append(f"  [{_cyan('governance check passed')}]")

        elif event_type == "governance_check":
            schema_id = details.get("schema_id", "?")
            policy_id = details.get("policy_id", "?")
            passed = details.get("passed", False)
            if passed:
                lines.append(f"  [{_green('PASS')}] {schema_id}::{policy_id}")
            else:
                violation = details.get("violation")
                lines.append(f"  [{_red('FAIL')}] {schema_id}::{policy_id}")
                if violation:
                    if isinstance(violation, dict):
                        sev = violation.get("severity", "critical")
                        desc = violation.get("description", "")
                        sev_str = _red(sev.upper()) if sev == "critical" else _yellow(sev.upper())
                        lines.append(f"  SEVERITY: {sev_str} | {_dim(desc)}")

        elif event_type == "violation":
            schema_id = details.get("schema_id", "?")
            policy_id = details.get("policy_id", "?")
            desc = details.get("description", "")
            sev = details.get("severity", "critical")
            lines.append(f"  Schema: {schema_id} | Policy: {policy_id}")
            lines.append(f"  {_red(desc)}")
            if sev == "critical":
                lines.append(f"  {_critical(' IMMEDIATE ACTION REQUIRED ')}")

        elif event_type == "retrieval":
            mem_id = details.get("memory_id", "?")
            inf_type = details.get("influence_type", "?")
            strength = details.get("strength", 0.0)
            lines.append(f"  Memory: {mem_id} | Type: {inf_type} | Strength: {strength}")

        elif event_type == "lifecycle":
            action = details.get("action", "?")
            lines.append(f"  Action: {action}")

        else:
            # Generic details rendering
            for k, v in details.items():
                if k in ("context", "violation") and isinstance(v, dict):
                    continue
                v_str = str(v)[:120]
                lines.append(f"  {k}: {v_str}")

        # Governance context
        if governance_context:
            ctx_str = ", ".join(governance_context)
            lines.append(f"  {_dim('Governance context:')}{_magenta(ctx_str)}")

        return lines

    def _fmt_filters(self) -> str:
        parts = []
        for k, v in self.filters.items():
            if v:
                parts.append(f"{k}={v}")
        return ", ".join(parts)


# ---------------------------------------------------------------------------
# Standalone async helper for quick event display without pipeline
# ---------------------------------------------------------------------------


async def display_events(
    events: list[Any],
    severity: str | None = None,
    event_type: str | None = None,
    component: str | None = None,
) -> None:
    """Display a list of events with optional filtering (no pipeline needed).

    Parameters
    ----------
    events:
        List of AuditEvent or dict events.
    severity, event_type, component:
        Optional filters applied before display.
    """
    viewer = AuditStreamViewer()
    viewer.set_filter(event_type=event_type, severity=severity, component=component)

    for event in events:
        # Apply filters manually
        evt_sev = event.get("severity", "info") if isinstance(event, dict) else getattr(event, "severity", "info")
        evt_type = event.get("event_type", "?") if isinstance(event, dict) else getattr(event, "event_type", "?")
        evt_comp = event.get("component", "?") if isinstance(event, dict) else getattr(event, "component", "?")

        if severity and evt_sev != severity:
            continue
        if event_type and evt_type != event_type:
            continue
        if component and evt_comp != component:
            continue

        viewer.display_event(event)


__all__ = ["AuditStreamViewer", "display_events"]
