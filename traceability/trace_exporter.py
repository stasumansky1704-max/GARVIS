"""
Trace Exporter

Exports cognition traces to various file formats.

Supports: JSON, Markdown (with Mermaid), DOT, plain text

Every export includes the full trace data: state transitions, governance
checks, memory influences, and audit events.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from traceability.renderer import TraceRenderer

logger = logging.getLogger(__name__)


class TraceExporter:
    """Exports cognition traces to various file formats.

    Supports: JSON, Markdown (with Mermaid), DOT, plain text
    """

    def __init__(self) -> None:
        self._renderer = TraceRenderer()

    # ------------------------------------------------------------------
    # Individual format exports
    # ------------------------------------------------------------------

    def export_json(self, trace_data: dict, filepath: str) -> None:
        """Export trace as a JSON file.

        Parameters
        ----------
        trace_data:
            Dict representation of a cognition trace.
        filepath:
            Destination path (should end in ``.json``).
        """
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        rendered = self._renderer.render_json(trace_data)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(rendered)
        logger.info("Exported trace to JSON: %s", filepath)

    def export_markdown(self, trace_data: dict, filepath: str) -> None:
        """Export trace as Markdown with embedded Mermaid diagram.

        Parameters
        ----------
        trace_data:
            Dict representation of a cognition trace.
        filepath:
            Destination path (should end in ``.md``).
        """
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

        trace_id = self._fmt_id(trace_data.get("trace_id"))
        session_id = self._fmt_id(trace_data.get("session_id"))
        status = trace_data.get("status", self._derive_status(trace_data))
        duration = self._calc_duration_ms(trace_data)

        md_lines: list[str] = []
        _a = md_lines.append

        _a("# GARVIS Cognition Trace\n")

        # Metadata
        _a(f"**Trace ID:** `{trace_id}`  ")
        _a(f"**Session:** `{session_id}`  ")
        _a(f"**Status:** {self._md_status_badge(status)}  ")
        _a(f"**Duration:** {duration}ms  ")
        if trace_data.get("start_time"):
            ts = self._fmt_ts(trace_data["start_time"])
            _a(f"**Started:** {ts}  ")
        _a("")

        # State Transitions
        _a("## State Transitions\n")
        transitions = trace_data.get("state_sequence", [])
        if transitions:
            _a("| # | From | To | Trigger | Governance |")
            _a("|---|------|-----|---------|------------|")
            for i, tr in enumerate(transitions, 1):
                from_s = tr.get("from_state", "?")
                to_s = tr.get("to_state", "?")
                trigger = tr.get("trigger", "")
                gov = "Yes" if tr.get("governance_check", False) else "No"
                # Highlight critical state transitions
                to_fmt = f"**{to_s}**" if to_s in ("fail_closed", "degraded") else to_s
                _a(f"| {i} | {from_s} | {to_fmt} | {trigger} | {gov} |")
        else:
            _a("*(No state transitions recorded)*")
        _a("")

        # Governance Checks
        _a("## Governance Checks\n")
        checks = trace_data.get("governance_checks", [])
        if checks:
            _a("| Result | Schema | Policy | Severity | Description |")
            _a("|--------|--------|--------|----------|-------------|")
            for check in checks:
                schema = check.get("schema_id", "?")
                policy = check.get("policy_id", "?")
                passed = check.get("passed", False)
                result = "PASS" if passed else "FAIL"
                violation = check.get("violation")
                sev = "-"
                desc = "-"
                if violation:
                    sev = violation.get("severity", "critical")
                    desc = violation.get("description", "")
                _a(f"| {result} | {schema} | {policy} | {sev} | {desc} |")
        else:
            _a("*(No governance checks recorded)*")
        _a("")

        # Memory Influences
        _a("## Memory Influences\n")
        influences = trace_data.get("memory_influences", [])
        if influences:
            _a("| Memory ID | Type | Strength | Details |")
            _a("|-----------|------|----------|---------|")
            for inf in influences:
                mem_id = self._fmt_id(inf.get("memory_id"))[:8]
                inf_type = inf.get("influence_type", "?")
                strength = inf.get("strength", 0.0)
                content = inf.get("content", "")
                if content:
                    content = content[:60] + "..." if len(content) > 60 else content
                else:
                    content = "-"
                _a(f"| {mem_id} | {inf_type} | {strength:.2f} | {content} |")
        else:
            _a("*(No memory influences recorded)*")
        _a("")

        # Audit Events
        _a("## Audit Events\n")
        events = trace_data.get("events", [])
        if events:
            _a("| Time | Severity | Type | Component | Details |")
            _a("|------|----------|------|-----------|---------|")
            for event in events:
                ts = self._fmt_ts(event.get("timestamp"))
                sev = event.get("severity", "info")
                evt_type = event.get("event_type", "?")
                comp = event.get("component", "?")
                details = event.get("details", {})
                detail_str = ""
                if isinstance(details, dict):
                    parts = []
                    for k in ("model", "prompt_length", "response_length", "passed_validation",
                              "from_state", "to_state", "schema_id", "policy_id"):
                        if k in details:
                            v = details[k]
                            if isinstance(v, bool):
                                v = "yes" if v else "no"
                            parts.append(f"{k}={v}")
                    detail_str = ", ".join(parts)
                if not detail_str:
                    detail_str = "-"
                _a(f"| {ts} | {sev} | {evt_type} | {comp} | {detail_str} |")
        else:
            _a("*(No audit events recorded)*")
        _a("")

        # Cognition Graph (Mermaid)
        _a("## Cognition Graph\n")
        mermaid = self._renderer.render_mermaid(trace_data)
        _a("```mermaid")
        _a(mermaid)
        _a("```\n")

        # Summary
        _a("## Summary\n")
        total_checks = len(checks)
        failed_checks = sum(1 for c in checks if not c.get("passed", True))
        critical_events = sum(1 for e in events if e.get("severity") == "critical")
        warning_events = sum(1 for e in events if e.get("severity") == "warning")

        _a(f"- **State transitions:** {len(transitions)}")
        _a(f"- **Governance checks:** {total_checks} total, {total_checks - failed_checks} passed, {failed_checks} failed")
        _a(f"- **Memory influences:** {len(influences)}")
        _a(f"- **Audit events:** {len(events)} total, {critical_events} critical, {warning_events} warnings")
        if trace_data.get("final_state"):
            _a(f"- **Final state:** {trace_data['final_state']}")
        _a("")

        # Footer
        _a("---\n")
        _a(f"*Generated by GARVIS TraceExporter at {datetime.now(timezone.utc).isoformat()}Z*\n")

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write("\n".join(md_lines))
        logger.info("Exported trace to Markdown: %s", filepath)

    def export_dot(self, trace_data: dict, filepath: str) -> None:
        """Export trace as a DOT file for Graphviz rendering.

        Parameters
        ----------
        trace_data:
            Dict representation of a cognition trace.
        filepath:
            Destination path (should end in ``.dot``).
        """
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        rendered = self._renderer.render_dot(trace_data)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(rendered)
        logger.info("Exported trace to DOT: %s", filepath)

    def export_text(self, trace_data: dict, filepath: str) -> None:
        """Export trace as a formatted text file.

        Writes the ANSI-coloured text representation.  View with ``less -R``
        or any terminal that supports ANSI codes.

        Parameters
        ----------
        trace_data:
            Dict representation of a cognition trace.
        filepath:
            Destination path (should end in ``.txt``).
        """
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        rendered = self._renderer.render_text(trace_data)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(rendered)
        logger.info("Exported trace to text: %s", filepath)

    # ------------------------------------------------------------------
    # Bulk export
    # ------------------------------------------------------------------

    def export_all(
        self,
        trace_data: dict,
        basename: str,
        output_dir: str,
    ) -> list[str]:
        """Export trace in all formats.

        Parameters
        ----------
        trace_data:
            Dict representation of a cognition trace.
        basename:
            Base filename without extension.
        output_dir:
            Directory to write files into.

        Returns
        -------
        list[str]
            Paths of all files written.
        """
        os.makedirs(output_dir, exist_ok=True)

        paths: list[str] = []

        formats = {
            "json": self.export_json,
            "md": self.export_markdown,
            "dot": self.export_dot,
            "txt": self.export_text,
        }

        for ext, method in formats.items():
            filepath = os.path.join(output_dir, f"{basename}.{ext}")
            try:
                method(trace_data, filepath)
                paths.append(filepath)
            except Exception as exc:
                logger.error("Failed to export %s: %s", ext, exc)

        logger.info(
            "Bulk export complete: %d/%d formats succeeded -> %s",
            len(paths),
            len(formats),
            output_dir,
        )
        return paths

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_id(val: Any) -> str:
        if val is None:
            return "N/A"
        if isinstance(val, UUID):
            return str(val)
        return str(val)

    @staticmethod
    def _fmt_ts(val: Any) -> str:
        if val is None:
            return "N/A"
        if isinstance(val, datetime):
            return val.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(val, str):
            try:
                dt = datetime.fromisoformat(val)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        return str(val)[:19]

    @staticmethod
    def _calc_duration_ms(trace_data: dict) -> int:
        start = trace_data.get("start_time")
        end = trace_data.get("end_time")
        if start and end:
            if isinstance(start, str):
                try:
                    start = datetime.fromisoformat(start)
                except Exception:
                    return 0
            if isinstance(end, str):
                try:
                    end = datetime.fromisoformat(end)
                except Exception:
                    return 0
            try:
                return int((end - start).total_seconds() * 1000)
            except Exception:
                return 0
        return trace_data.get("duration_ms", 0)

    @staticmethod
    def _derive_status(trace_data: dict) -> str:
        checks = trace_data.get("governance_checks", [])
        if any(not c.get("passed", True) for c in checks):
            worst = "warning"
            for c in checks:
                if not c.get("passed", True):
                    v = c.get("violation")
                    if v and v.get("severity") == "critical":
                        worst = "failed"
                        break
            if worst == "failed":
                return "failed"
            return "warning"

        events = trace_data.get("events", [])
        if any(e.get("severity") == "critical" for e in events):
            return "failed"
        if any(e.get("severity") == "warning" for e in events):
            return "warning"

        final = trace_data.get("final_state", "")
        if final in ("fail_closed", "degraded"):
            return "failed" if final == "fail_closed" else "warning"

        return trace_data.get("status", "success")

    @staticmethod
    def _md_status_badge(status: str) -> str:
        badges = {
            "success": "PASSING",
            "failed": "**FAILED**",
            "warning": "*WARNING*",
            "blocked": "**BLOCKED**",
            "active": "ACTIVE",
        }
        return badges.get(status, status.upper())


__all__ = ["TraceExporter"]
