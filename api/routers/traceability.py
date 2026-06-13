"""Traceability router for the GARVIS Operator API.

Exposes cognition traces, lineage graphs, and trace rendering in
multiple formats (text, dot, mermaid, json).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from api.dependencies import get_mock_traces, get_mock_memories, get_mock_influences
from api.models import TraceListResponse, TraceGraphResponse, TraceRenderResponse
from models.memory import MemoryInfluence

router = APIRouter()


# ── Traces ────────────────────────────────────────────────────────────────


@router.get("/traces", response_model=TraceListResponse)
async def list_traces(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session_id: UUID | None = Query(None),
    status: str | None = Query(None),
) -> TraceListResponse:
    """List cognition traces (paginated, filterable)."""
    traces = get_mock_traces()

    if session_id:
        traces = [t for t in traces if t.get("session_id") == session_id]
    if status:
        traces = [t for t in traces if t.get("status") == status]

    total = len(traces)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = traces[start:end]

    return TraceListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


@router.get("/traces/{trace_id}")
async def get_trace(
    trace_id: UUID,
) -> dict[str, Any]:
    """Get a specific trace by ID with full details."""
    traces = get_mock_traces()
    for t in traces:
        if t.get("trace_id") == trace_id:
            return t
    raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")


@router.get("/traces/{trace_id}/graph", response_model=TraceGraphResponse)
async def get_trace_graph(
    trace_id: UUID,
) -> TraceGraphResponse:
    """Get the lineage graph for a trace.

    Returns a graph structure with nodes (transitions, events, checks,
    influences, memories) and edges (relationships).
    """
    traces = get_mock_traces()
    trace = None
    for t in traces:
        if t.get("trace_id") == trace_id:
            trace = t
            break

    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")

    # Build a mock lineage graph
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    trace_node = f"trace:{trace_id}"
    nodes[trace_node] = {
        "type": "trace",
        "id": str(trace_id),
        "session_id": str(trace.get("session_id")),
        "start_time": trace.get("start_time").isoformat() if trace.get("start_time") else None,
        "final_state": trace.get("final_state"),
    }

    # Add transition nodes
    for i in range(trace.get("transition_count", 0)):
        node_id = f"transition_{i}"
        nodes[node_id] = {
            "type": "state_transition",
            "index": i,
        }
        edges.append({"from": trace_node, "to": node_id, "type": "contains"})

    # Add event nodes
    for i in range(trace.get("event_count", 0)):
        node_id = f"event_{i}"
        nodes[node_id] = {
            "type": "audit_event",
            "index": i,
        }
        edges.append({"from": trace_node, "to": node_id, "type": "contains"})

    # Add check nodes
    for i in range(trace.get("check_count", 0)):
        node_id = f"check_{i}"
        nodes[node_id] = {
            "type": "governance_check",
            "index": i,
        }
        edges.append({"from": trace_node, "to": node_id, "type": "governed_by"})

    # Add influence nodes from mock data
    influences = get_mock_influences()
    for i, inf in enumerate(influences[:trace.get("influence_count", 1)]):
        inf_node = f"influence_{i}"
        mem_node = f"memory_{i}"
        nodes[inf_node] = {
            "type": "influence",
            "id": str(inf.influence_id),
            "influence_type": inf.influence_type,
            "strength": inf.strength,
        }
        nodes[mem_node] = {
            "type": "memory",
            "id": str(inf.memory_id),
        }
        edges.append({"from": mem_node, "to": inf_node, "type": "exerts"})
        edges.append({"from": inf_node, "to": trace_node, "type": "affects"})

    graph = {
        "trace_id": str(trace_id),
        "session_id": str(trace.get("session_id")),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }

    return TraceGraphResponse(trace_id=trace_id, graph=graph)


@router.get("/traces/{trace_id}/render")
async def render_trace(
    trace_id: UUID,
    format: str = Query("text", description="Render format: text|dot|mermaid|json"),
) -> dict[str, Any]:
    """Render a trace in the requested format.

    Supported formats:
    - **text**: ANSI-colored structured text
    - **dot**: Graphviz DOT format
    - **mermaid**: Mermaid flowchart for Markdown
    - **json**: Pretty-printed JSON
    """
    if format not in ("text", "dot", "mermaid", "json"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format: '{format}'. Must be one of: text, dot, mermaid, json"
        )

    traces = get_mock_traces()
    trace = None
    for t in traces:
        if t.get("trace_id") == trace_id:
            trace = t
            break

    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")

    # Build trace_data dict for renderer
    trace_data = dict(trace)
    trace_data["trace_id"] = str(trace_id)
    if trace_data.get("start_time") and hasattr(trace_data["start_time"], "isoformat"):
        trace_data["start_time"] = trace_data["start_time"].isoformat()
    if trace_data.get("end_time") and hasattr(trace_data["end_time"], "isoformat"):
        trace_data["end_time"] = trace_data["end_time"].isoformat()

    # Build state_sequence mock
    from api.dependencies import get_mock_transitions
    all_transitions = get_mock_transitions()
    from api.dependencies import get_audit_events as get_mock_audit_events
    trace_data["state_sequence"] = [
        {
            "from_state": t.from_state.value,
            "to_state": t.to_state.value,
            "trigger": t.trigger,
            "governance_check": t.governance_check,
            "timestamp": t.timestamp.isoformat() if hasattr(t.timestamp, "isoformat") else str(t.timestamp),
        }
        for t in all_transitions[:3]
    ]

    # Build events, checks, influences mocks
    from api.dependencies import get_mock_checks, get_mock_influences
    events = get_mock_audit_events()
    checks = get_mock_checks()
    influences = get_mock_influences()

    trace_data["events"] = [
        {
            "event_type": e.event_type,
            "severity": e.severity,
            "component": e.component,
            "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, "isoformat") else str(e.timestamp),
        }
        for e in events[:3]
    ]

    trace_data["governance_checks"] = [
        {
            "schema_id": c.schema_id,
            "policy_id": c.policy_id,
            "passed": c.passed,
            "violation": c.violation.model_dump() if c.violation else None,
        }
        for c in checks[:3]
    ]

    trace_data["memory_influences"] = [
        {
            "memory_id": str(inf.memory_id),
            "influence_id": str(inf.influence_id),
            "target_inference_id": str(inf.target_inference_id),
            "influence_type": inf.influence_type,
            "strength": inf.strength,
        }
        for inf in influences[:2]
    ]

    # Lazy import to avoid pulling in asyncpg via traceability.__init__
    try:
        from traceability.renderer import TraceRenderer
        renderer = TraceRenderer()

        if format == "text":
            content = renderer.render_text(trace_data)
        elif format == "dot":
            content = renderer.render_dot(trace_data)
        elif format == "mermaid":
            content = renderer.render_mermaid(trace_data)
        else:  # json
            content = renderer.render_json(trace_data)
    except ImportError:
        # Fallback: render without TraceRenderer if dependencies unavailable
        if format == "json":
            import json as _json
            content = _json.dumps(trace_data, indent=2, default=str)
        else:
            content = f"[{format.upper()}] Trace {trace_id}\n\n"
            for key, value in trace_data.items():
                content += f"{key}: {value}\n"

    return {"trace_id": str(trace_id), "format": format, "content": content}


@router.get("/traces/session/{session_id}", response_model=TraceListResponse)
async def get_session_traces(
    session_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> TraceListResponse:
    """Get all traces for a specific session."""
    traces = get_mock_traces()
    filtered = [t for t in traces if t.get("session_id") == session_id]

    total = len(filtered)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = filtered[start:end]

    return TraceListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)
