"""Operator-facing text formatting utilities for the GARVIS CLI.

Provides ANSI-coloured output with clear visual hierarchy for governance
infrastructure observation.  This is NOT a chatbot UI — it is an industrial
control interface for observing governed cognition.

Colour scheme:
    GREEN   = pass / success / healthy
    RED     = fail / critical / error
    YELLOW  = warning / degraded
    BLUE    = info / processing / state
    MAGENTA = governance / enforcement
    CYAN    = memory / trace
    BOLD    = section headers
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

# ---------------------------------------------------------------------------
# ANSI colour codes
# ---------------------------------------------------------------------------

_C = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "italic": "\033[3m",
    "green": "\033[32m",
    "red": "\033[31m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bright_green": "\033[92m",
    "bright_red": "\033[91m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
}

# Detect terminal width
TERM_WIDTH: int = shutil.get_terminal_size(fallback=(100, 24)).columns


def _use_color() -> bool:
    """Check if terminal supports colour output."""
    return sys.stdout.isatty()


def _c(name: str) -> str:
    """Get ANSI code by name, or empty string if no colour support."""
    if not _use_color():
        return ""
    return _C.get(name, "")


def _fmt(text: str, *codes: str) -> str:
    """Format text with ANSI codes."""
    if not _use_color():
        return text
    prefix = "".join(_C.get(c, "") for c in codes)
    return f"{prefix}{text}{_C['reset']}"


# ---------------------------------------------------------------------------
# Section formatting
# ---------------------------------------------------------------------------

def print_header(title: str, width: int | None = None) -> None:
    """Print a visually distinct section header.

    Args:
        title: The section title text.
        width: Override the terminal width for the separator line.
    """
    w = width or min(TERM_WIDTH, 80)
    sep = "=" * w
    print(f"\n{_c('bold')}{_c('bright_blue')}{sep}{_c('reset')}")
    print(f"{_c('bold')}{_c('bright_blue')}  {title.upper()}{_c('reset')}")
    print(f"{_c('bold')}{_c('bright_blue')}{sep}{_c('reset')}")


def print_subheader(title: str) -> None:
    """Print a subsection header."""
    print(f"\n{_c('bold')}{_c('blue')}--- {title} ---{_c('reset')}")


def print_separator(width: int | None = None) -> None:
    """Print a horizontal rule."""
    w = width or min(TERM_WIDTH, 80)
    print(f"{_c('dim')}{'-' * w}{_c('reset')}")


def print_label_value(label: str, value: str, label_color: str = "blue") -> None:
    """Print a label-value pair aligned."""
    label_fmt = _fmt(f"{label:<24}", label_color, "bold")
    print(f"  {label_fmt} {_c('white')}{value}{_c('reset')}")


# ---------------------------------------------------------------------------
# Status indicators
# ---------------------------------------------------------------------------

def status_pass(text: str = "PASS") -> str:
    """Green PASS indicator."""
    return _fmt(f"[{text}]", "bright_green", "bold")


def status_fail(text: str = "FAIL") -> str:
    """Red FAIL indicator."""
    return _fmt(f"[{text}]", "bright_red", "bold")


def status_warn(text: str = "WARN") -> str:
    """Yellow WARN indicator."""
    return _fmt(f"[{text}]", "bright_yellow", "bold")


def status_info(text: str = "INFO") -> str:
    """Blue INFO indicator."""
    return _fmt(f"[{text}]", "bright_blue", "bold")


def status_governance(text: str) -> str:
    """Magenta governance indicator."""
    return _fmt(f"[{text}]", "bright_magenta", "bold")


def status_blocked() -> str:
    """Red BLOCKED indicator."""
    return _fmt("[BLOCKED]", "bright_red", "bold")


def status_degraded() -> str:
    """Yellow DEGRADED indicator."""
    return _fmt("[DEGRADED]", "bright_yellow", "bold")


def status_completed() -> str:
    """Green COMPLETED indicator."""
    return _fmt("[COMPLETED]", "bright_green", "bold")


def status_fail_closed() -> str:
    """Red FAIL-CLOSED indicator."""
    return _fmt("[FAIL-CLOSED]", "bright_red", "bold")


# ---------------------------------------------------------------------------
# Governance check formatting
# ---------------------------------------------------------------------------

def format_governance_check(check: Any) -> str:
    """Format a GovernanceCheckResult as a readable line.

    Args:
        check: A GovernanceCheckResult instance (duck-typed).

    Returns:
        Formatted string with pass/fail status, schema, and policy.
    """
    passed = getattr(check, "passed", False)
    schema_id = getattr(check, "schema_id", "unknown")
    policy_id = getattr(check, "policy_id", "unknown")
    violation = getattr(check, "violation", None)

    indicator = status_pass("PASS") if passed else status_fail("FAIL")
    schema_fmt = _fmt(schema_id, "magenta")
    policy_fmt = _fmt(policy_id, "cyan")

    lines = [f"  {indicator}  {schema_fmt} / {policy_fmt}"]

    if violation is not None:
        sev = getattr(violation, "severity", "unknown")
        desc = getattr(violation, "description", "No description")
        sev_color = "red" if sev == "critical" else "yellow"
        sev_fmt = _fmt(sev.upper(), sev_color, "bold")
        lines.append(f"       {_c('red')}Violation:{_c('reset')} {sev_fmt} — {desc}")

    return "\n".join(lines)


def format_governance_checks(checks: list[Any]) -> str:
    """Format a list of governance checks.

    Returns:
        Multi-line formatted string with summary.
    """
    if not checks:
        return f"  {_c('dim')}(no governance checks performed){_c('reset')}"

    lines: list[str] = []
    passed_count = sum(1 for c in checks if getattr(c, "passed", False))
    failed_count = len(checks) - passed_count

    lines.append(
        f"  {_c('bold')}Checks:{_c('reset')} {len(checks)} total, "
        f"{_c('green')}{passed_count} passed{_c('reset')}, "
        f"{_c('red') if failed_count else _c('green')}{failed_count} failed{_c('reset')}"
    )
    lines.append("")

    for check in checks:
        lines.append(format_governance_check(check))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# State transition formatting
# ---------------------------------------------------------------------------

def format_state_transition(transition: Any) -> str:
    """Format a StateTransition as a readable line.

    Args:
        transition: A StateTransition instance (duck-typed).

    Returns:
        Formatted string showing from → to states with trigger.
    """
    from_state = getattr(transition, "from_state", None)
    to_state = getattr(transition, "to_state", None)
    trigger = getattr(transition, "trigger", "unknown")
    ts = getattr(transition, "timestamp", None)
    governance_check = getattr(transition, "governance_check", False)

    # Handle both enum and string states
    from_val = from_state.value if hasattr(from_state, "value") else str(from_state)
    to_val = to_state.value if hasattr(to_state, "value") else str(to_state)

    from_fmt = _fmt(from_val, "blue")
    arrow = _fmt("→", "dim")
    to_color = "green" if to_val in ("standby", "cognition_active") else "red" if to_val == "fail_closed" else "yellow" if to_val == "degraded" else "blue"
    to_fmt = _fmt(to_val, to_color, "bold")
    trigger_fmt = _fmt(trigger, "dim")

    gov_indicator = status_pass("GOV") if governance_check else status_warn("NOGOV")

    ts_str = ""
    if ts is not None:
        if isinstance(ts, datetime):
            ts_str = f" {_c('dim')}at {ts.isoformat()}{_c('reset')}"

    return f"  {gov_indicator} {from_fmt} {arrow} {to_fmt}  ({trigger_fmt}){ts_str}"


def format_state_transitions(transitions: list[Any]) -> str:
    """Format a list of state transitions.

    Returns:
        Multi-line formatted string.
    """
    if not transitions:
        return f"  {_c('dim')}(no state transitions recorded){_c('reset')}"

    lines: list[str] = []
    lines.append(f"  {_c('bold')}{len(transitions)} transition(s) recorded:{_c('reset')}\n")

    for t in transitions:
        lines.append(format_state_transition(t))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Memory influence formatting
# ---------------------------------------------------------------------------

def format_memory_influence(influence: Any) -> str:
    """Format a MemoryInfluence as a readable line.

    Args:
        influence: A MemoryInfluence instance (duck-typed).

    Returns:
        Formatted string showing memory → inference influence.
    """
    memory_id = getattr(influence, "memory_id", None)
    target_id = getattr(influence, "target_inference_id", None)
    inf_type = getattr(influence, "influence_type", "unknown")
    strength = getattr(influence, "strength", 0.0)
    trace_visible = getattr(influence, "trace_visible", True)

    mem_short = str(memory_id)[:8] if memory_id else "????????"
    tgt_short = str(target_id)[:8] if target_id else "????????"

    mem_fmt = _fmt(f"mem:{mem_short}", "cyan")
    tgt_fmt = _fmt(f"inf:{tgt_short}", "blue")
    type_fmt = _fmt(inf_type, "magenta")

    # Strength bar
    bar_len = int(strength * 10)
    bar = "█" * bar_len + "░" * (10 - bar_len)
    strength_fmt = _fmt(f"{bar} {strength:.2f}", "yellow")

    vis_indicator = status_pass("VIS") if trace_visible else status_fail("HID")

    return f"  {vis_indicator} {mem_fmt} → {tgt_fmt}  {type_fmt}  strength: {strength_fmt}"


def format_memory_influences(influences: list[Any]) -> str:
    """Format a list of memory influences.

    Returns:
        Multi-line formatted string.
    """
    if not influences:
        return f"  {_c('dim')}(no memory influences recorded){_c('reset')}"

    lines: list[str] = []
    lines.append(
        f"  {_c('bold')}{len(influences)} memory influence(s) recorded:{_c('reset')}\n"
    )

    for inf in influences:
        lines.append(format_memory_influence(inf))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Trace summary formatting
# ---------------------------------------------------------------------------

def format_trace_summary(trace_data: dict[str, Any]) -> str:
    """Format a cognition trace summary as a multi-line string.

    Args:
        trace_data: Dict with trace information from SessionController.submit().

    Returns:
        Formatted multi-line trace summary.
    """
    lines: list[str] = []

    # Header
    trace_id = trace_data.get("trace_id", "unknown")
    session_id = trace_data.get("session_id", "unknown")
    status = trace_data.get("status", "unknown")

    lines.append(f"{_c('bold')}Trace:{_c('reset')}     {_c('cyan')}{trace_id}{_c('reset')}")
    lines.append(f"{_c('bold')}Session:{_c('reset')}   {_c('cyan')}{session_id}{_c('reset')}")

    # Status
    if status == "completed":
        lines.append(f"{_c('bold')}Status:{_c('reset')}    {status_completed()}")
    elif status == "blocked":
        lines.append(f"{_c('bold')}Status:{_c('reset')}    {status_blocked()}")
    elif status == "degraded":
        lines.append(f"{_c('bold')}Status:{_c('reset')}    {status_degraded()}")
    elif status == "fail_closed":
        lines.append(f"{_c('bold')}Status:{_c('reset')}    {status_fail_closed()}")
    else:
        lines.append(f"{_c('bold')}Status:{_c('reset')}    {_c('yellow')}{status}{_c('reset')}")

    lines.append("")

    # State transitions
    transitions = trace_data.get("state_transitions", [])
    lines.append(f"{_c('bold')}State Transitions:{_c('reset')} {len(transitions)}")
    for t in transitions:
        lines.append(format_state_transition(t))

    lines.append("")

    # Governance checks
    checks = trace_data.get("governance_checks", [])
    lines.append(f"{_c('bold')}Governance Checks:{_c('reset')} {len(checks)}")
    lines.append(format_governance_checks(checks))

    lines.append("")

    # Response info
    response = trace_data.get("response")
    if response is not None:
        lines.append(f"{_c('bold')}Response:{_c('reset')}  {_c('green')}Present{_c('reset')}")
        validated = getattr(response, "validated_response", None)
        if validated:
            # Show first 200 chars
            preview = validated[:200].replace("\n", " ")
            if len(validated) > 200:
                preview += "..."
            lines.append(f"  {_c('dim')}Preview:{_c('reset')} {preview}")
    else:
        lines.append(f"{_c('bold')}Response:{_c('reset')}  {_c('red')}None (governance blocked){_c('reset')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Schema table formatting
# ---------------------------------------------------------------------------

def format_schema_table(schemas: list[Any]) -> str:
    """Format a list of governance schemas as a text table.

    Args:
        schemas: List of GovernanceSchema instances.

    Returns:
        Formatted table string.
    """
    if not schemas:
        return f"  {_c('dim')}(no schemas loaded){_c('reset')}"

    # Column widths
    id_w = max(max(len(str(getattr(s, "schema_id", ""))) for s in schemas), 20)
    name_w = max(max(len(str(getattr(s, "name", ""))) for s in schemas), 18)
    ver_w = max(max(len(str(getattr(s, "version", ""))) for s in schemas), 7)
    cat_w = max(max(len(str(getattr(s, "category", ""))) for s in schemas), 12)
    pol_w = 8
    con_w = 12

    header = (
        f"  {_c('bold')}{'Schema ID':<{id_w}}  {'Name':<{name_w}}  {'Version':<{ver_w}}  "
        f"{'Category':<{cat_w}}  {'Policies':>{pol_w}}  {'Constraints':>{con_w}}{_c('reset')}"
    )
    sep = (
        f"  {'-' * id_w}  {'-' * name_w}  {'-' * ver_w}  "
        f"{'-' * cat_w}  {'-' * pol_w}  {'-' * con_w}"
    )

    lines = [header, sep]

    for s in schemas:
        sid = str(getattr(s, "schema_id", "?"))
        name = str(getattr(s, "name", "?"))
        ver = str(getattr(s, "version", "?"))
        cat = str(getattr(s, "category", "?"))
        policies = getattr(s, "policies", [])
        constraints = getattr(s, "constraints", [])

        sid_fmt = _fmt(sid, "magenta")
        cat_color = "blue" if cat == "epistemic" else "green" if cat == "operational" else "yellow"
        cat_fmt = _fmt(cat, cat_color)

        line = (
            f"  {sid_fmt:<{id_w + 9}}  "  # +9 for ANSI escape codes
            f"{_c('white')}{name:<{name_w}}{_c('reset')}  "
            f"{_c('dim')}{ver:<{ver_w}}{_c('reset')}  "
            f"{cat_fmt:<{cat_w + 9}}  "  # +9 for ANSI
            f"{_c('white')}{len(policies):>{pol_w}}{_c('reset')}  "
            f"{_c('white')}{len(constraints):>{con_w}}{_c('reset')}"
        )
        lines.append(line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Audit event formatting
# ---------------------------------------------------------------------------

def format_audit_event(event: Any) -> str:
    """Format an AuditEvent as a readable line.

    Args:
        event: An AuditEvent instance (duck-typed).

    Returns:
        Formatted string.
    """
    event_type = getattr(event, "event_type", "unknown")
    severity = getattr(event, "severity", "info")
    component = getattr(event, "component", "unknown")
    ts = getattr(event, "timestamp", None)

    sev_indicators = {
        "critical": status_fail("CRIT"),
        "warning": status_warn("WARN"),
        "info": status_info("INFO"),
    }
    indicator = sev_indicators.get(severity, status_info(severity.upper()[:4]))

    type_fmt = _fmt(event_type, "cyan")
    comp_fmt = _fmt(component, "magenta")

    ts_str = ""
    if ts is not None and isinstance(ts, datetime):
        ts_str = f" {_c('dim')}{ts.isoformat()}{_c('reset')}"

    return f"  {indicator} {type_fmt}  {comp_fmt}{ts_str}"


def format_audit_events(events: list[Any]) -> str:
    """Format a list of audit events.

    Returns:
        Multi-line formatted string.
    """
    if not events:
        return f"  {_c('dim')}(no audit events){_c('reset')}"

    lines: list[str] = []
    lines.append(f"  {_c('bold')}{len(events)} event(s):{_c('reset')}\n")

    for event in events:
        lines.append(format_audit_event(event))
        # Show details if present
        details = getattr(event, "details", {})
        if details:
            for key, value in details.items():
                if isinstance(value, (str, int, float, bool)):
                    lines.append(f"       {_c('dim')}{key}:{_c('reset')} {value}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Runtime status formatting
# ---------------------------------------------------------------------------

def format_runtime_status(
    state: str,
    active_schemas: list[str],
    uptime: float | None,
    component_health: dict[str, bool],
    session_count: int = 0,
) -> str:
    """Format runtime status as a multi-line string.

    Args:
        state: Current operational state string.
        active_schemas: List of active schema IDs.
        uptime: Uptime in seconds, or None.
        component_health: Dict of component name -> healthy bool.
        session_count: Number of active sessions.

    Returns:
        Formatted multi-line status display.
    """
    lines: list[str] = []

    print_header("RUNTIME STATUS")

    # State
    state_colors = {
        "standby": ("green", "bold"),
        "cognition_active": ("green", "bold"),
        "uninitialized": ("yellow", "bold"),
        "initializing": ("blue", "bold"),
        "degraded": ("yellow", "bold"),
        "fail_closed": ("red", "bold"),
        "shutdown": ("dim",),
    }
    color_args = state_colors.get(state, ("white",))
    state_fmt = _fmt(state.upper(), *color_args)
    print(f"\n  {_c('bold')}Operational State:{_c('reset')}  {state_fmt}")

    # Uptime
    if uptime is not None:
        hours, remainder = divmod(int(uptime), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        print(f"  {_c('bold')}Uptime:{_c('reset')}             {_c('white')}{uptime_str}{_c('reset')}")
    else:
        print(f"  {_c('bold')}Uptime:{_c('reset')}             {_c('dim')}not started{_c('reset')}")

    # Sessions
    print(f"  {_c('bold')}Active Sessions:{_c('reset')}    {_c('white')}{session_count}{_c('reset')}")

    # Component health
    print(f"\n  {_c('bold')}Component Health:{_c('reset')}")
    for component, healthy in component_health.items():
        indicator = status_pass("OK") if healthy else status_fail("DOWN")
        comp_fmt = _fmt(component, "blue")
        print(f"    {indicator}  {comp_fmt}")

    # Active schemas
    print(f"\n  {_c('bold')}Active Governance Schemas:{_c('reset)} {_c('white')}{len(active_schemas)}{_c('reset')}")
    for sid in active_schemas:
        print(f"    {_c('green')}●{_c('reset')} {_fmt(sid, 'magenta')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt / response formatting
# ---------------------------------------------------------------------------

def format_prompt(prompt: str, label: str = "PROMPT") -> str:
    """Format a prompt for display.

    Args:
        prompt: The prompt text.
        label: Label to show (e.g., "PROMPT", "MEDIATED PROMPT").

    Returns:
        Formatted string.
    """
    label_fmt = _fmt(label, "blue", "bold")
    lines = [
        f"",
        f"  {label_fmt}",
        f"  {_c('dim')}{'─' * 40}{_c('reset')}",
    ]
    for line in prompt.split("\n"):
        lines.append(f"  {_c('white')}{line}{_c('reset')}")
    lines.append(f"  {_c('dim')}{'─' * 40}{_c('reset')}")
    return "\n".join(lines)


def format_response(response_text: str | None, label: str = "RESPONSE") -> str:
    """Format a response for display.

    Args:
        response_text: The response text, or None if blocked.
        label: Label to show.

    Returns:
        Formatted string.
    """
    label_fmt = _fmt(label, "green", "bold")
    lines = [
        f"",
        f"  {label_fmt}",
        f"  {_c('dim')}{'─' * 40}{_c('reset')}",
    ]

    if response_text is None:
        lines.append(f"  {_c('red')}[BLOCKED BY GOVERNANCE — NO RESPONSE RELEASED]{_c('reset')}")
    else:
        for line in response_text.split("\n"):
            lines.append(f"  {_c('white')}{line}{_c('reset')}")

    lines.append(f"  {_c('dim')}{'─' * 40}{_c('reset')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Trace graph text format
# ---------------------------------------------------------------------------

def format_trace_graph_text(graph: dict[str, Any]) -> str:
    """Format a trace graph dict as human-readable text.

    Args:
        graph: Dict with nodes and edges from TraceGraphBuilder.

    Returns:
        Multi-line formatted string.
    """
    if not graph or "nodes" not in graph:
        return f"  {_c('dim')}(no trace graph available){_c('reset')}"

    lines: list[str] = []
    trace_id = graph.get("trace_id", "unknown")
    node_count = graph.get("node_count", 0)
    edge_count = graph.get("edge_count", 0)

    lines.append(f"  {_c('bold')}Trace:{_c('reset')} {_c('cyan')}{trace_id}{_c('reset')}")
    lines.append(f"  {_c('bold')}Nodes:{_c('reset')} {_c('white')}{node_count}{_c('reset')}  "
                 f"{_c('bold')}Edges:{_c('reset')} {_c('white')}{edge_count}{_c('reset')}")
    lines.append("")

    # Group nodes by type
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])

    by_type: dict[str, list[dict]] = {}
    for node_id, node_data in nodes.items():
        node_type = node_data.get("type", "unknown")
        if node_type not in by_type:
            by_type[node_type] = []
        by_type[node_type].append({"id": node_id, **node_data})

    for node_type, node_list in sorted(by_type.items()):
        type_fmt = _fmt(node_type.upper(), "blue", "bold")
        lines.append(f"  {type_fmt} ({len(node_list)})")
        for node in node_list[:20]:  # Cap at 20 per type
            label = node.get("label", node["id"])
            lines.append(f"    {_c('dim')}•{_c('reset')} {label}")
        if len(node_list) > 20:
            lines.append(f"    {_c('dim')}... and {len(node_list) - 20} more{_c('reset')}")
        lines.append("")

    # Show edges summary
    if edges:
        edge_types: dict[str, int] = {}
        for edge in edges:
            et = edge.get("type", "unknown")
            edge_types[et] = edge_types.get(et, 0) + 1

        lines.append(f"  {_c('bold')}Edge Types:{_c('reset')}")
        for et, count in sorted(edge_types.items()):
            lines.append(f"    {_c('dim')}{et}:{_c('reset')} {count}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Mermaid / DOT export
# ---------------------------------------------------------------------------

def export_mermaid(graph: dict[str, Any]) -> str:
    """Export a trace graph as a Mermaid diagram.

    Args:
        graph: Dict with nodes and edges.

    Returns:
        Mermaid diagram string.
    """
    lines = ["graph TD"]

    # Node definitions
    nodes = graph.get("nodes", {})
    for node_id, node_data in nodes.items():
        node_type = node_data.get("type", "unknown")
        label = node_data.get("label", node_id)
        # Sanitize for mermaid
        safe_id = node_id.replace(":", "_").replace("-", "_")
        safe_label = label.replace('"', "'")[:40]

        styles = {
            "trace": f"[{safe_label}]",
            "state_transition": f"({safe_label})",
            "audit_event": f"{{{safe_label}}}",
            "governance_check": f"{{{{{safe_label}}}}}",
            "inference": f"[/ {safe_label} /]",
            "memory": f"[( {safe_label} )]",
            "influence": f">{safe_label}]",
        }
        shape = styles.get(node_type, f"[{safe_label}]")
        lines.append(f"    {safe_id}{shape}")

    # Edges
    for edge in graph.get("edges", []):
        from_id = edge.get("from", "").replace(":", "_").replace("-", "_")
        to_id = edge.get("to", "").replace(":", "_").replace("-", "_")
        edge_type = edge.get("type", "")
        lines.append(f"    {from_id} --|{edge_type}| {to_id}")

    return "\n".join(lines)


def export_dot(graph: dict[str, Any]) -> str:
    """Export a trace graph as a DOT (Graphviz) diagram.

    Args:
        graph: Dict with nodes and edges.

    Returns:
        DOT diagram string.
    """
    lines = ["digraph CognitionTrace {"]
    lines.append('    rankdir=TB;')
    lines.append('    node [shape=box, fontname="monospace"];')

    # Node definitions with colours
    nodes = graph.get("nodes", {})
    colors = {
        "trace": "lightblue",
        "state_transition": "lightyellow",
        "audit_event": "lightgreen",
        "governance_check": "lightcoral",
        "inference": "plum",
        "memory": "wheat",
        "influence": "lightgray",
    }

    for node_id, node_data in nodes.items():
        node_type = node_data.get("type", "unknown")
        label = node_data.get("label", node_id).replace('"', "'")
        color = colors.get(node_type, "white")
        safe_id = node_id.replace(":", "_").replace("-", "_").replace(".", "_")
        lines.append(f'    {safe_id} [label="{label[:50]}", fillcolor={color}, style=filled];')

    # Edges
    seen_edges = set()
    for edge in graph.get("edges", []):
        from_id = edge.get("from", "").replace(":", "_").replace("-", "_").replace(".", "_")
        to_id = edge.get("to", "").replace(":", "_").replace("-", "_").replace(".", "_")
        edge_type = edge.get("type", "")
        edge_key = (from_id, to_id, edge_type)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            lines.append(f'    {from_id} -> {to_id} [label="{edge_type}"];')

    lines.append("}")
    return "\n".join(lines)


__all__ = [
    "print_header",
    "print_subheader",
    "print_separator",
    "print_label_value",
    "status_pass",
    "status_fail",
    "status_warn",
    "status_info",
    "status_governance",
    "status_blocked",
    "status_degraded",
    "status_completed",
    "status_fail_closed",
    "format_governance_check",
    "format_governance_checks",
    "format_state_transition",
    "format_state_transitions",
    "format_memory_influence",
    "format_memory_influences",
    "format_trace_summary",
    "format_schema_table",
    "format_audit_event",
    "format_audit_events",
    "format_runtime_status",
    "format_prompt",
    "format_response",
    "format_trace_graph_text",
    "export_mermaid",
    "export_dot",
]
