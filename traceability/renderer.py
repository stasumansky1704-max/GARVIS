"""
Cognition Trace Renderer

Renders cognition traces in multiple human-readable formats.
The operator's window into the cognition process.

Supports: text (ANSI-colored), DOT (Graphviz), Mermaid, JSON

Every governance check, memory influence, state transition, and audit event
is rendered in clear, structured, human-readable formats.
"""

from __future__ import annotations

import json
import logging
import shutil
import textwrap
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

_CODES: dict[str, str] = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "italic": "\033[3m",
    "underline": "\033[4m",
    # Foreground
    "black": "\033[30m",
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
    # Background
    "bg_red": "\033[41m",
    "bg_green": "\033[42m",
    "bg_yellow": "\033[43m",
    "bg_blue": "\033[44m",
    "bg_magenta": "\033[45m",
    "bg_white": "\033[47m",
    "bg_bright_red": "\033[101m",
}


def _c(text: str, *codes: str) -> str:
    """Wrap *text* in ANSI colour codes (nop when TTY absent)."""
    if not TraceRenderer._color_enabled:
        return text
    prefix = "".join(_CODES.get(c, "") for c in codes)
    return f"{prefix}{text}{_CODES['reset']}"


# Convenience wrappers
def _green(text: str) -> str:
    return _c(text, "green")


def _red(text: str) -> str:
    return _c(text, "red")


def _bright_red(text: str) -> str:
    return _c(text, "bright_red")


def _yellow(text: str) -> str:
    return _c(text, "yellow")


def _blue(text: str) -> str:
    return _c(text, "blue")


def _cyan(text: str) -> str:
    return _c(text, "cyan")


def _magenta(text: str) -> str:
    return _c(text, "magenta")


def _dim(text: str) -> str:
    return _c(text, "dim")


def _bold(text: str) -> str:
    return _c(text, "bold")


def _bg_red(text: str) -> str:
    return _c(text, "bg_bright_red", "white")


def _bg_yellow(text: str) -> str:
    return _c(text, "bg_yellow", "black")


_C = _CODES

# ---------------------------------------------------------------------------
# TraceRenderer
# ---------------------------------------------------------------------------


class TraceRenderer:
    """Renders cognition traces in human-readable formats.

    Supports: text, DOT (Graphviz), Mermaid, JSON
    """

    _color_enabled: bool = True  # class-level toggle

    # ------------------------------------------------------------------
    # Text rendering
    # ------------------------------------------------------------------

    def render_text(self, trace_data: dict) -> str:
        """Render a cognition trace as structured, ANSI-colored text.

        Parameters
        ----------
        trace_data:
            Dict representation of a cognition trace.  Expected keys:
            trace_id, session_id, start_time, end_time, final_state,
            state_sequence, governance_checks, memory_influences, events.

        Returns
        -------
        str
            Box-drawing formatted, ANSI-coloured trace report.
        """
        lines: list[str] = []
        _a = lines.append

        # Determine terminal width
        term_w = self._terminal_width()
        box_w = min(term_w, 80)

        trace_id = self._fmt_id(trace_data.get("trace_id"))
        session_id = self._fmt_id(trace_data.get("session_id"))
        status = trace_data.get("status", self._derive_status(trace_data))
        duration = self._calc_duration_ms(trace_data)

        # ════ HEADER ════
        _a(self._hbar("double", box_w))
        _a(self._hcenter(f"GARVIS COGNITION TRACE: {trace_id}", box_w))
        _a(self._hbar("double", box_w))
        _a("")

        # Session info
        _a(f"  {_bold('SESSION:')}    {session_id}")
        _a(f"  {_bold('STATUS:')}     {self._status_color(status, status.upper())}")
        _a(f"  {_bold('DURATION:')}   {duration}ms")
        if trace_data.get("start_time"):
            ts = self._fmt_ts(trace_data["start_time"])
            _a(f"  {_bold('STARTED:')}    {ts}")
        _a("")

        # ─── STATE TRANSITIONS ───
        _a(self._section_header("STATE TRANSITIONS", box_w))
        transitions = trace_data.get("state_sequence", [])
        if transitions:
            for i, tr in enumerate(transitions, 1):
                line = self._render_transition(i, tr)
                _a(line)
        else:
            _a(f"  {_dim('(no state transitions recorded)')}")
        _a("")

        # ─── GOVERNANCE CHECKS ───
        _a(self._section_header("GOVERNANCE CHECKS", box_w))
        checks = trace_data.get("governance_checks", [])
        if checks:
            for check in checks:
                line = self._render_governance_check(check)
                _a(line)
        else:
            _a(f"  {_dim('(no governance checks recorded)')}")
        _a("")

        # ─── MEMORY INFLUENCES ───
        _a(self._section_header("MEMORY INFLUENCES", box_w))
        influences = trace_data.get("memory_influences", [])
        if influences:
            for inf in influences:
                lines.extend(self._render_memory_influence(inf))
        else:
            _a(f"  {_dim('(no memory influences recorded)')}")
        _a("")

        # ─── AUDIT EVENTS ───
        _a(self._section_header("AUDIT EVENTS", box_w))
        events = trace_data.get("events", [])
        if events:
            for event in events:
                _a(self._render_audit_event(event))
        else:
            _a(f"  {_dim('(no audit events recorded)')}")
        _a("")

        # ─── PROMPT MEDIATION ───
        if trace_data.get("original_prompt") or trace_data.get("mediated_prompt"):
            _a(self._section_header("PROMPT MEDIATION", box_w))
            if trace_data.get("original_prompt"):
                orig = trace_data["original_prompt"]
                _a(f"  {_bold('Original:')} {orig!r}")
            if trace_data.get("mediated_prompt"):
                mediated = trace_data["mediated_prompt"]
                schemas = trace_data.get("mediation_schemas", [])
                schema_str = ", ".join(schemas) if schemas else "none"
                _a(f"  {_bold('Mediated:')} {_cyan(mediated)}")
                _a(f"  {_bold('Schemas:')}  {_magenta(schema_str)}")
            _a("")

        # ─── RESPONSE ───
        if trace_data.get("response") or trace_data.get("response_status"):
            _a(self._section_header("RESPONSE", box_w))
            resp_status = trace_data.get("response_status", "unknown")
            if resp_status == "blocked":
                _a(f"  {_bold('Status:')} {_bg_red(' BLOCKED ')}")
            elif resp_status == "success":
                _a(f"  {_bold('Status:')} {_green('SUCCESS')}")
            else:
                _a(f"  {_bold('Status:')} {resp_status}")

            if trace_data.get("response"):
                resp = trace_data["response"]
                wrapped = textwrap.fill(str(resp), width=box_w - 4, initial_indent="  ", subsequent_indent="  ")
                _a(wrapped)
            if trace_data.get("blocking_violation"):
                bv = trace_data["blocking_violation"]
                _a(f"  {_bold('Violation:')} {_red(bv)}")
            _a("")

        # ─── SUMMARY ───
        _a(self._section_header("SUMMARY", box_w))
        total_checks = len(checks)
        failed_checks = sum(1 for c in checks if not c.get("passed", True))
        critical_events = sum(1 for e in events if e.get("severity") == "critical")
        warning_events = sum(1 for e in events if e.get("severity") == "warning")

        _a(f"  State transitions: {len(transitions)}")
        _a(f"  Governance checks: {total_checks} total, "
           f"{_green(str(total_checks - failed_checks) + ' passed')}, "
           f"{_red(str(failed_checks) + ' failed')}" if failed_checks else
           f"{_green(str(total_checks) + ' passed')}, 0 failed")
        _a(f"  Memory influences: {len(influences)}")
        _a(f"  Audit events:      {len(events)} total, "
           f"{_red(str(critical_events) + ' critical')}, "
           f"{_yellow(str(warning_events) + ' warnings')}")
        if trace_data.get("final_state"):
            fs = trace_data["final_state"]
            _a(f"  Final state:       {fs}")
        _a("")
        _a(self._hbar("double", box_w))

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # DOT rendering
    # ------------------------------------------------------------------

    def render_dot(self, trace_data: dict) -> str:
        """Render as Graphviz DOT format for visualization.

        Nodes are colour-coded: green=pass, red=fail, blue=memory,
        yellow=state, orange=audit, purple=inference, pink=influence.
        """
        trace_id = self._fmt_id(trace_data.get("trace_id"))
        session_id = self._fmt_id(trace_data.get("session_id"))

        lines: list[str] = []
        _a = lines.append

        _a(f'// GARVIS Cognition Trace: {trace_id}')
        _a(f'// Session: {session_id}')
        _a(f'// Generated: {datetime.now(timezone.utc).isoformat().replace("+00:00", "")}Z')
        _a('')
        _a('digraph garvis_trace {')
        _a('    rankdir=TB;')
        _a('    node [fontname="Helvetica", fontsize=10, shape=box, style="rounded,filled"];')
        _a('    edge [fontname="Helvetica", fontsize=9];')
        _a('')

        # Root trace node
        status = trace_data.get("status", self._derive_status(trace_data))
        root_color = "#ff6b6b" if status == "failed" else "#69db7c" if status == "success" else "#74c0fc"
        _a(f'    "trace_root" [label="Trace {trace_id[:8]}...", fillcolor="{root_color}", '
           f'fontcolor=black, shape=ellipse, style="filled", penwidth=2];')
        _a('')

        # State transitions
        transitions = trace_data.get("state_sequence", [])
        for i, tr in enumerate(transitions):
            node_id = f'trans_{i}'
            from_s = tr.get("from_state", "?")
            to_s = tr.get("to_state", "?")
            trigger = tr.get("trigger", "")
            label = f"{from_s}\\n-> {to_s}"
            fillcolor = "#ffd43b"  # yellow for state
            if to_s in ("fail_closed", "degraded"):
                fillcolor = "#ff6b6b"
            _a(f'    "{node_id}" [label="{label}", fillcolor="{fillcolor}", '
               f'tooltip="trigger: {trigger}"];')
            _a(f'    "trace_root" -> "{node_id}" [label="contains", color="#868e96", penwidth=1];')
            if i > 0:
                _a(f'    "trans_{i - 1}" -> "{node_id}" [style=dashed, color="#adb5bd", '
                   f'label="seq", constraint=false];')
        if transitions:
            _a('')

        # Governance checks
        checks = trace_data.get("governance_checks", [])
        for i, check in enumerate(checks):
            node_id = f'check_{i}'
            schema = check.get("schema_id", "?")
            policy = check.get("policy_id", "?")
            passed = check.get("passed", False)
            label = f"{schema}\\n:: {policy}"
            fillcolor = "#69db7c" if passed else "#ff6b6b"  # green/red
            fontcolor = "black"
            _a(f'    "{node_id}" [label="{label}", fillcolor="{fillcolor}", '
               f'fontcolor="{fontcolor}", shape=diamond, penwidth={1 if passed else 2}];')
            _a(f'    "trace_root" -> "{node_id}" [label="governs", color="#cc5de8", '
               f'penwidth={1 if passed else 2}];')
        if checks:
            _a('')

        # Memory influences
        influences = trace_data.get("memory_influences", [])
        seen_memories: set[str] = set()
        seen_inferences: set[str] = set()
        for i, inf in enumerate(influences):
            mem_id = self._fmt_id(inf.get("memory_id"))
            inf_id = self._fmt_id(inf.get("influence_id"))
            tgt_id = self._fmt_id(inf.get("target_inference_id"))
            inf_type = inf.get("influence_type", "?")
            strength = inf.get("strength", 0.0)

            mem_node = f'mem_{mem_id[:8]}'
            inf_node = f'inf_{inf_id[:8]}'
            tgt_node = f'inference_{tgt_id[:8]}'

            if mem_node not in seen_memories:
                seen_memories.add(mem_node)
                _a(f'    "{mem_node}" [label="Memory {mem_id[:8]}...", fillcolor="#4dabf7", '
                   f'shape=cylinder, fontcolor=white];')
                _a(f'    "trace_root" -> "{mem_node}" [color="#868e96", style=dotted];')

            if inf_node not in influences:
                pass

            if tgt_node not in seen_inferences:
                seen_inferences.add(tgt_node)
                _a(f'    "{tgt_node}" [label="Inference {tgt_id[:8]}...", fillcolor="#9775fa", '
                   f'shape=box, fontcolor=white];')
                _a(f'    "trace_root" -> "{tgt_node}" [color="#868e96", style=dotted];')

            # Influence node
            _a(f'    "{inf_node}" [label="{inf_type}\\n({strength:.2f})", fillcolor="#f783ac", '
               f'shape=ellipse, fontcolor=black, fontsize=9];')
            _a(f'    "{mem_node}" -> "{inf_node}" [label="exerts ({strength:.2f})", '
               f'color="#339af0", penwidth={max(0.5, strength * 3)}];')
            _a(f'    "{inf_node}" -> "{tgt_node}" [label="affects", color="#da77f2", '
               f'penwidth={max(0.5, strength * 3)}];')
        if influences:
            _a('')

        # Audit events
        events = trace_data.get("events", [])
        for i, event in enumerate(events):
            node_id = f'event_{i}'
            evt_type = event.get("event_type", "?")
            severity = event.get("severity", "info")
            component = event.get("component", "?")
            label = f"{evt_type}\\n({severity})"
            fillcolor = self._event_color(severity)
            fontcolor = "black" if severity in ("warning", "info") else "white"
            shape = "note" if severity == "critical" else "box"
            _a(f'    "{node_id}" [label="{label}", fillcolor="{fillcolor}", '
               f'fontcolor="{fontcolor}", shape={shape}, tooltip="{component}"];')
            _a(f'    "trace_root" -> "{node_id}" [label="logs", color="#868e96", style=dashed];')

        _a('')
        _a('    // Subgraph for legend')
        _a('    subgraph cluster_legend {')
        _a('        label="Legend"; fontsize=10; color=gray; style=dashed;')
        _a('        rank=sink;')
        _a('        "legend_pass" [label="PASS", fillcolor="#69db7c", shape=diamond, fontsize=9];')
        _a('        "legend_fail" [label="FAIL", fillcolor="#ff6b6b", shape=diamond, fontsize=9];')
        _a('        "legend_memory" [label="Memory", fillcolor="#4dabf7", shape=cylinder, fontsize=9, fontcolor=white];')
        _a('        "legend_inference" [label="Inference", fillcolor="#9775fa", shape=box, fontsize=9, fontcolor=white];')
        _a('        "legend_state" [label="State", fillcolor="#ffd43b", shape=box, fontsize=9];')
        _a('    }')
        _a('}')

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Mermaid rendering
    # ------------------------------------------------------------------

    def render_mermaid(self, trace_data: dict) -> str:
        """Render as Mermaid flowchart for Markdown embedding.

        Uses subgraphs for governance, memory, inference, and audit.
        """
        lines: list[str] = []
        _a = lines.append

        trace_id = self._fmt_id(trace_data.get("trace_id"))
        status = trace_data.get("status", self._derive_status(trace_data))

        _a(f'%% GARVIS Cognition Trace: {trace_id}')
        _a('%% Generated at runtime')
        _a('flowchart TD')
        _a('')

        # Root node
        root_style = "fill:#69db7c" if status == "success" else "fill:#ff6b6b" if status == "failed" else "fill:#74c0fc"
        _a(f'    root(["Trace {trace_id[:8]}..."]):::traceRoot')
        _a(f'    style root {root_style},stroke:#333,stroke-width:2px')
        _a('')

        # Governance subgraph
        checks = trace_data.get("governance_checks", [])
        if checks:
            _a('    subgraph GOV["Governance Checks"]')
            for i, check in enumerate(checks):
                node_id = f'GC{i}'
                schema = check.get("schema_id", "?")
                policy = check.get("policy_id", "?")
                passed = check.get("passed", False)
                label = f"{schema}:: {policy}"
                status_str = "PASS" if passed else "FAIL"
                _a(f'        {node_id}{{"{label}"}}')
                _a(f'        style {node_id} fill:{"#69db7c" if passed else "#ff6b6b"},stroke:#333')
                _a(f'        root -.->|governs| {node_id}')
            _a('    end')
            _a('')

        # State transitions subgraph
        transitions = trace_data.get("state_sequence", [])
        if transitions:
            _a('    subgraph STM["State Machine"]')
            for i, tr in enumerate(transitions):
                node_id = f'ST{i}'
                from_s = tr.get("from_state", "?")
                to_s = tr.get("to_state", "?")
                _a(f'        {node_id}["{from_s} -> {to_s}"]')
                fill = "#ff6b6b" if to_s in ("fail_closed", "degraded") else "#ffd43b"
                _a(f'        style {node_id} fill:{fill},stroke:#333')
                _a(f'        root -.->|contains| {node_id}')
                if i > 0:
                    _a(f'        ST{i - 1} --> ST{i}')
            _a('    end')
            _a('')

        # Memory & Inference subgraph
        influences = trace_data.get("memory_influences", [])
        if influences:
            _a('    subgraph MEM["Memory Layer"]')
            seen_mem: set[str] = set()
            for i, inf in enumerate(influences):
                mem_id = self._fmt_id(inf.get("memory_id"))[:8]
                mem_node = f'MEM_{mem_id}'
                if mem_node not in seen_mem:
                    seen_mem.add(mem_node)
                    _a(f'        {mem_node}[("Memory {mem_id}...")]')
                    _a(f'        style {mem_node} fill:#4dabf7,stroke:#333,color:#fff')
                    _a(f'        root -.->|ref| {mem_node}')
            _a('    end')
            _a('')

            _a('    subgraph INF["Inference"]')
            seen_inf: set[str] = set()
            for i, inf in enumerate(influences):
                inf_id = self._fmt_id(inf.get("influence_id"))[:8]
                tgt_id = self._fmt_id(inf.get("target_inference_id"))[:8]
                inf_type = inf.get("influence_type", "?")
                strength = inf.get("strength", 0.0)
                inf_node = f'INFL_{inf_id}'
                tgt_node = f'INFR_{tgt_id}'
                if inf_node not in seen_inf:
                    seen_inf.add(inf_node)
                    _a(f'        {inf_node}[/"{inf_type} ({strength:.2f})"/]')
                    _a(f'        style {inf_node} fill:#f783ac,stroke:#333')
                if tgt_node not in seen_inf:
                    seen_inf.add(tgt_node)
                    _a(f'        {tgt_node}["Inference {tgt_id}..."]')
                    _a(f'        style {tgt_node} fill:#9775fa,stroke:#333,color:#fff')
                    _a(f'        root -.->|uses| {tgt_node}')
                _a(f'        {inf_node} -->|"influences ({strength:.2f})"| {tgt_node}')
            _a('    end')
            _a('')

            # Cross-subgraph edges: memory -> influence -> inference
            seen_links: set[str] = set()
            for i, inf in enumerate(influences):
                mem_id = self._fmt_id(inf.get("memory_id"))[:8]
                inf_id = self._fmt_id(inf.get("influence_id"))[:8]
                link_key = f'{mem_id}_{inf_id}'
                if link_key not in seen_links:
                    seen_links.add(link_key)
                    _a(f'    MEM_{mem_id} --> INFL_{inf_id}')

        # Audit events subgraph
        events = trace_data.get("events", [])
        if events:
            _a('    subgraph AUD["Audit Events"]')
            for i, event in enumerate(events):
                node_id = f'AE{i}'
                evt_type = event.get("event_type", "?")
                severity = event.get("severity", "info")
                _a(f'        {node_id}["{evt_type}"]')
                fill = self._mermaid_event_color(severity)
                _a(f'        style {node_id} fill:{fill},stroke:#333')
                _a(f'        root -.->|logs| {node_id}')
            _a('    end')
            _a('')

        # Class definitions
        _a('    classDef traceRoot fill:#74c0fc,stroke:#333,stroke-width:3px')
        _a('    classDef pass fill:#69db7c,stroke:#333')
        _a('    classDef fail fill:#ff6b6b,stroke:#333')
        _a('    classDef memory fill:#4dabf7,stroke:#333,color:#fff')
        _a('    classDef inference fill:#9775fa,stroke:#333,color:#fff')

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # JSON rendering
    # ------------------------------------------------------------------

    def render_json(self, trace_data: dict) -> str:
        """Render as pretty-printed JSON.

        Normalises UUID / datetime objects and produces a complete,
        human-readable JSON representation of the trace.
        """
        serialisable = self._to_json_safe(trace_data)
        return json.dumps(serialisable, indent=2, default=str, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Internal helpers – section rendering
    # ------------------------------------------------------------------

    def _render_transition(self, idx: int, tr: dict) -> str:
        """Render a single state transition line."""
        from_s = tr.get("from_state", "?")
        to_s = tr.get("to_state", "?")
        trigger = tr.get("trigger", "")
        gov = tr.get("governance_check", False)

        from_c = _dim(from_s) if from_s in ("uninitialized", "standby") else from_s
        to_c = _red(to_s) if to_s in ("fail_closed", "degraded") else _green(to_s) if to_s == "cognition_active" else to_s
        trigger_str = f" (trigger: {trigger})" if trigger else ""
        gov_str = f" [{_cyan('governance: ' + ('PASSED' if gov else 'SKIPPED'))}]" if gov else ""

        return f"  [{idx}] {from_c} -> {to_c}{trigger_str}{gov_str}"

    def _render_governance_check(self, check: dict) -> str:
        """Render a governance check as a single line."""
        schema = check.get("schema_id", "?")
        policy = check.get("policy_id", "?")
        passed = check.get("passed", False)
        violation = check.get("violation")

        if passed:
            status = _green("[PASS]")
        else:
            status = _red("[FAIL]")

        line = f"  {status} {schema}::{policy}"

        if violation:
            sev = violation.get("severity", "critical")
            desc = violation.get("description", "")
            sev_colored = _red(sev.upper()) if sev == "critical" else _yellow(sev.upper())
            line += f"  (SEVERITY: {sev_colored})"
            if desc:
                line += f"\n    {_dim('Reason: ' + desc)}"

        return line

    def _render_memory_influence(self, inf: dict) -> list[str]:
        """Render a memory influence as multiple lines."""
        mem_id = self._fmt_id(inf.get("memory_id"))
        inf_type = inf.get("influence_type", "?")
        strength = inf.get("strength", 0.0)

        lines: list[str] = []
        lines.append(f"  [Mem: {_cyan(mem_id[:8])}] influence: {inf_type}, strength: {_yellow(str(strength))}")

        # Additional details if present in trace_data
        if inf.get("content"):
            content = inf["content"]
            if len(content) > 70:
                content = content[:67] + "..."
            lines.append(f"    Content: \"{content}\"")
        if inf.get("provenance"):
            prov = inf["provenance"]
            if isinstance(prov, dict):
                schema = prov.get("source_schema", "unknown")
                lines.append(f"    Provenance: {schema}")
        if inf.get("trace_visible") is False:
            lines.append(f"    {_dim('[Hidden from trace]')}")

        return lines

    def _render_audit_event(self, event: dict) -> str:
        """Render an audit event as a structured line."""
        evt_type = event.get("event_type", "?")
        severity = event.get("severity", "info")
        component = event.get("component", "")

        sev_map = {
            "critical": _bg_red("CRITICAL"),
            "warning": _bg_yellow("WARNING "),
            "info": _blue("INFO"),
            "debug": _dim("DEBUG"),
        }
        sev_str = sev_map.get(severity, severity.upper())

        line = f"  [{sev_str}] {component}::{evt_type}"

        details = event.get("details", {})
        if isinstance(details, dict) and details:
            # Show a few key details inline
            detail_parts = []
            for k in ("from_state", "to_state", "schema_id", "policy_id", "passed"):
                if k in details:
                    v = details[k]
                    if k == "passed":
                        detail_parts.append(f"{k}={_green('yes') if v else _red('no')}")
                    else:
                        detail_parts.append(f"{k}={v}")
            if detail_parts:
                line += f"  ({', '.join(detail_parts)})"

        return line

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hbar(style: str = "single", width: int = 60) -> str:
        char = "═" if style == "double" else "─"
        return char * width

    def _hcenter(self, text: str, width: int = 60) -> str:
        pad = max(0, width - len(text))
        left = pad // 2
        right = pad - left
        return " " * left + text + " " * right

    def _section_header(self, title: str, width: int = 60) -> str:
        return f"─── {_bold(title)} {self._hbar('single', max(0, width - len(title) - 6))}"

    # ------------------------------------------------------------------
    # Colour / status helpers
    # ------------------------------------------------------------------

    def _status_color(self, status: str, text: str | None = None) -> str:
        text = text or status
        if status in ("success", "passed", "active"):
            return _green(text)
        if status in ("failed", "blocked", "error"):
            return _red(text)
        if status in ("warning", "degraded"):
            return _yellow(text)
        return text

    def _event_color(self, severity: str) -> str:
        """DOT fill colour for an audit-event severity."""
        return {
            "critical": "#ff6b6b",
            "warning": "#ffd43b",
            "info": "#74c0fc",
            "debug": "#dee2e6",
        }.get(severity, "#74c0fc")

    def _mermaid_event_color(self, severity: str) -> str:
        """Mermaid fill colour for an audit-event severity."""
        return self._event_color(severity)

    # ------------------------------------------------------------------
    # Value helpers
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
            return val.isoformat()
        return str(val)

    @staticmethod
    def _terminal_width() -> int:
        try:
            return shutil.get_terminal_size().columns
        except Exception:
            return 80

    def _calc_duration_ms(self, trace_data: dict) -> int:
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

    def _derive_status(self, trace_data: dict) -> str:
        """Derive overall trace status from data."""
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

    def _to_json_safe(self, obj: Any) -> Any:
        """Recursively convert objects to JSON-safe primitives."""
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: self._to_json_safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._to_json_safe(v) for v in obj]
        return obj

    # ------------------------------------------------------------------
    # Class-level colour toggle
    # ------------------------------------------------------------------

    @classmethod
    def enable_color(cls) -> None:
        cls._color_enabled = True

    @classmethod
    def disable_color(cls) -> None:
        cls._color_enabled = False

    @classmethod
    def set_color(cls, enabled: bool) -> None:
        cls._color_enabled = enabled


# Re-export colour helpers for downstream use
__all__ = ["TraceRenderer"]
