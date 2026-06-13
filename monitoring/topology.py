"""System Topology Mapper — monitoring/topology.py

Maps the complete GARVIS system topology — all components and their
relationships. Produces a graph of nodes (components) and edges
(dependencies/influences) for visualization and analysis.

The topology is STATIC — system structure does not change at runtime.
This mapper defines the canonical system layout.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

logger = logging.getLogger("garvis.monitoring.topology")


# -----------------------------------------------------------------------------
# SystemTopology — static system topology mapper
# -----------------------------------------------------------------------------


class SystemTopology:
    """Maps the complete GARVIS system topology.

    Produces a graph of nodes (components) and edges (dependencies/influences)
    for visualization and analysis.

    The topology is STATIC — system structure does not change at runtime.
    """

    # ------------------------------------------------------------------
    # Canonical system layers
    # ------------------------------------------------------------------

    LAYERS: list[str] = [
        "governance",
        "cognition",
        "memory",
        "traceability",
        "inference",
        "runtime",
        "analytics",
        "monitoring",
    ]

    # ------------------------------------------------------------------
    # Canonical node definitions
    # Each node: id, layer, type, description
    # ------------------------------------------------------------------

    NODES: list[dict[str, str]] = [
        # ── Governance layer ──
        {"id": "governance.loader", "layer": "governance", "type": "component",
         "description": "Loads and validates governance schemas from YAML"},
        {"id": "governance.registry", "layer": "governance", "type": "component",
         "description": "Central registry for all loaded governance schemas"},
        {"id": "governance.validator", "layer": "governance", "type": "component",
         "description": "Validates runtime operations against governance schemas"},
        {"id": "governance.enforcer", "layer": "governance", "type": "component",
         "description": "Fail-closed enforcement engine for violations"},
        {"id": "governance.middleware", "layer": "governance", "type": "component",
         "description": "Middleware wrapping all cognition operations"},

        # ── Cognition layer ──
        {"id": "cognition.state_machine", "layer": "cognition", "type": "component",
         "description": "Governed operational state machine"},
        {"id": "cognition.session", "layer": "cognition", "type": "component",
         "description": "Cognition session manager"},
        {"id": "cognition.transitions", "layer": "cognition", "type": "component",
         "description": "State transition definitions and validation"},
        {"id": "cognition.forbidden", "layer": "cognition", "type": "component",
         "description": "Forbidden pattern detector"},

        # ── Memory layer ──
        {"id": "memory.episodic", "layer": "memory", "type": "component",
         "description": "Episodic memory store and retrieval"},
        {"id": "memory.influence", "layer": "memory", "type": "component",
         "description": "Memory influence tracking"},
        {"id": "memory.retrieval", "layer": "memory", "type": "component",
         "description": "Memory retrieval engine"},
        {"id": "memory.store", "layer": "memory", "type": "component",
         "description": "Memory persistence layer"},

        # ── Traceability layer ──
        {"id": "traceability.audit", "layer": "traceability", "type": "component",
         "description": "Comprehensive audit logging pipeline"},
        {"id": "traceability.lineage", "layer": "traceability", "type": "component",
         "description": "Data lineage tracking"},
        {"id": "traceability.trace_exporter", "layer": "traceability", "type": "component",
         "description": "Trace export functionality"},
        {"id": "traceability.trace_graph", "layer": "traceability", "type": "component",
         "description": "Trace graph builder"},
        {"id": "traceability.renderer", "layer": "traceability", "type": "component",
         "description": "Trace visualization renderer"},
        {"id": "traceability.stream_viewer", "layer": "traceability", "type": "component",
         "description": "Real-time trace stream viewer"},

        # ── Inference layer ──
        {"id": "inference.executor", "layer": "inference", "type": "component",
         "description": "Governed inference execution engine"},
        {"id": "inference.mediator", "layer": "inference", "type": "component",
         "description": "Prompt mediation and validation"},

        # ── Runtime layer ──
        {"id": "runtime.bootstrap", "layer": "runtime", "type": "component",
         "description": "System bootstrap and initialization"},
        {"id": "runtime.lifecycle", "layer": "runtime", "type": "component",
         "description": "Runtime lifecycle management"},
        {"id": "runtime.session_controller", "layer": "runtime", "type": "component",
         "description": "Session controller"},
        {"id": "runtime.event_bus", "layer": "runtime", "type": "component",
         "description": "Internal event bus"},
        {"id": "runtime.health", "layer": "runtime", "type": "component",
         "description": "Health check system"},
        {"id": "runtime.config", "layer": "runtime", "type": "component",
         "description": "Configuration management"},
        {"id": "runtime.operator_interface", "layer": "runtime", "type": "component",
         "description": "Operator control interface"},

        # ── Analytics layer ──
        {"id": "analytics.metrics", "layer": "analytics", "type": "component",
         "description": "Core metrics computation"},
        {"id": "analytics.trends", "layer": "analytics", "type": "component",
         "description": "Time-series trend analysis"},
        {"id": "analytics.continuity", "layer": "analytics", "type": "component",
         "description": "Continuity analysis"},
        {"id": "analytics.ecosystem", "layer": "analytics", "type": "component",
         "description": "Ecosystem analysis"},
        {"id": "analytics.overview", "layer": "analytics", "type": "component",
         "description": "System overview dashboard"},

        # ── Monitoring layer ──
        {"id": "monitoring.alert_engine", "layer": "monitoring", "type": "component",
         "description": "Governance alert engine"},
        {"id": "monitoring.topology", "layer": "monitoring", "type": "component",
         "description": "System topology mapper"},

        # ── Data models ──
        {"id": "models.governance", "layer": "governance", "type": "data_model",
         "description": "Governance schema, violation, check models"},
        {"id": "models.cognition", "layer": "cognition", "type": "data_model",
         "description": "Operational state, transition models"},
        {"id": "models.memory", "layer": "memory", "type": "data_model",
         "description": "Episodic memory, provenance models"},
        {"id": "models.audit", "layer": "traceability", "type": "data_model",
         "description": "Audit event, cognition trace models"},
        {"id": "models.inference", "layer": "inference", "type": "data_model",
         "description": "Inference request, governed response models"},

        # ── Database ──
        {"id": "database.connection", "layer": "runtime", "type": "infrastructure",
         "description": "PostgreSQL connection pool"},
        {"id": "database.queries", "layer": "runtime", "type": "infrastructure",
         "description": "SQL query definitions"},
    ]

    # ------------------------------------------------------------------
    # Canonical edge definitions
    # Each edge: from, to, type
    # type: "dependency" | "influence" | "data_flow" | "control"
    # ------------------------------------------------------------------

    EDGES: list[dict[str, str]] = [
        # ── Governance layer internal ──
        {"from": "governance.loader", "to": "governance.registry", "type": "dependency"},
        {"from": "governance.registry", "to": "governance.validator", "type": "dependency"},
        {"from": "governance.registry", "to": "governance.enforcer", "type": "influence"},
        {"from": "governance.validator", "to": "governance.enforcer", "type": "control"},
        {"from": "governance.middleware", "to": "governance.validator", "type": "dependency"},
        {"from": "governance.middleware", "to": "governance.enforcer", "type": "control"},
        {"from": "governance.enforcer", "to": "cognition.state_machine", "type": "control"},

        # ── Cognition layer internal ──
        {"from": "cognition.state_machine", "to": "cognition.session", "type": "control"},
        {"from": "cognition.state_machine", "to": "cognition.transitions", "type": "dependency"},
        {"from": "cognition.state_machine", "to": "cognition.forbidden", "type": "control"},
        {"from": "cognition.session", "to": "cognition.transitions", "type": "dependency"},
        {"from": "cognition.forbidden", "to": "cognition.state_machine", "type": "control"},

        # ── Memory layer internal ──
        {"from": "memory.episodic", "to": "memory.retrieval", "type": "dependency"},
        {"from": "memory.retrieval", "to": "memory.store", "type": "dependency"},
        {"from": "memory.influence", "to": "memory.episodic", "type": "influence"},
        {"from": "memory.store", "to": "database.connection", "type": "dependency"},

        # ── Traceability layer internal ──
        {"from": "traceability.audit", "to": "database.connection", "type": "dependency"},
        {"from": "traceability.lineage", "to": "traceability.trace_graph", "type": "dependency"},
        {"from": "traceability.trace_exporter", "to": "traceability.lineage", "type": "dependency"},
        {"from": "traceability.trace_graph", "to": "traceability.renderer", "type": "dependency"},
        {"from": "traceability.stream_viewer", "to": "traceability.audit", "type": "dependency"},

        # ── Inference layer internal ──
        {"from": "inference.executor", "to": "inference.mediator", "type": "dependency"},

        # ── Runtime layer internal ──
        {"from": "runtime.bootstrap", "to": "runtime.lifecycle", "type": "control"},
        {"from": "runtime.lifecycle", "to": "runtime.session_controller", "type": "control"},
        {"from": "runtime.session_controller", "to": "runtime.event_bus", "type": "dependency"},
        {"from": "runtime.health", "to": "runtime.operator_interface", "type": "influence"},
        {"from": "runtime.config", "to": "runtime.bootstrap", "type": "dependency"},
        {"from": "runtime.operator_interface", "to": "runtime.lifecycle", "type": "control"},

        # ── Analytics layer internal ──
        {"from": "analytics.metrics", "to": "analytics.trends", "type": "influence"},
        {"from": "analytics.trends", "to": "analytics.continuity", "type": "influence"},
        {"from": "analytics.continuity", "to": "analytics.overview", "type": "influence"},
        {"from": "analytics.ecosystem", "to": "analytics.overview", "type": "influence"},

        # ── Monitoring layer internal ──
        {"from": "monitoring.alert_engine", "to": "monitoring.topology", "type": "influence"},
        {"from": "monitoring.alert_engine", "to": "runtime.operator_interface", "type": "control"},

        # ── Cross-layer: Governance → Cognition ──
        {"from": "governance.validator", "to": "cognition.state_machine", "type": "control"},
        {"from": "governance.enforcer", "to": "cognition.session", "type": "control"},
        {"from": "cognition.state_machine", "to": "governance.middleware", "type": "dependency"},

        # ── Cross-layer: Cognition → Memory ──
        {"from": "cognition.session", "to": "memory.episodic", "type": "dependency"},
        {"from": "memory.influence", "to": "cognition.session", "type": "influence"},
        {"from": "cognition.state_machine", "to": "memory.retrieval", "type": "dependency"},

        # ── Cross-layer: Cognition → Traceability ──
        {"from": "cognition.state_machine", "to": "traceability.audit", "type": "data_flow"},
        {"from": "cognition.session", "to": "traceability.lineage", "type": "data_flow"},
        {"from": "traceability.audit", "to": "cognition.state_machine", "type": "influence"},

        # ── Cross-layer: Inference → Governance ──
        {"from": "inference.executor", "to": "governance.middleware", "type": "dependency"},
        {"from": "inference.mediator", "to": "governance.validator", "type": "dependency"},
        {"from": "governance.middleware", "to": "inference.executor", "type": "control"},

        # ── Cross-layer: Inference → Cognition ──
        {"from": "inference.executor", "to": "cognition.state_machine", "type": "dependency"},
        {"from": "inference.executor", "to": "cognition.session", "type": "dependency"},
        {"from": "cognition.state_machine", "to": "inference.executor", "type": "control"},

        # ── Cross-layer: Inference → Memory ──
        {"from": "inference.executor", "to": "memory.episodic", "type": "data_flow"},
        {"from": "memory.retrieval", "to": "inference.executor", "type": "data_flow"},

        # ── Cross-layer: Runtime → Governance ──
        {"from": "runtime.bootstrap", "to": "governance.loader", "type": "dependency"},
        {"from": "runtime.lifecycle", "to": "governance.registry", "type": "dependency"},
        {"from": "runtime.session_controller", "to": "governance.middleware", "type": "dependency"},
        {"from": "runtime.operator_interface", "to": "governance.enforcer", "type": "control"},

        # ── Cross-layer: Runtime → Cognition ──
        {"from": "runtime.bootstrap", "to": "cognition.state_machine", "type": "control"},
        {"from": "runtime.session_controller", "to": "cognition.session", "type": "control"},
        {"from": "runtime.health", "to": "cognition.state_machine", "type": "influence"},

        # ── Cross-layer: Runtime → Traceability ──
        {"from": "runtime.event_bus", "to": "traceability.audit", "type": "data_flow"},
        {"from": "runtime.lifecycle", "to": "traceability.audit", "type": "data_flow"},

        # ── Cross-layer: Analytics → All ──
        {"from": "analytics.metrics", "to": "governance.validator", "type": "influence"},
        {"from": "analytics.metrics", "to": "cognition.state_machine", "type": "influence"},
        {"from": "analytics.trends", "to": "traceability.audit", "type": "influence"},
        {"from": "analytics.overview", "to": "runtime.operator_interface", "type": "influence"},
        {"from": "analytics.overview", "to": "monitoring.alert_engine", "type": "influence"},

        # ── Cross-layer: Monitoring → All ──
        {"from": "monitoring.alert_engine", "to": "governance.enforcer", "type": "influence"},
        {"from": "monitoring.alert_engine", "to": "cognition.state_machine", "type": "influence"},
        {"from": "monitoring.alert_engine", "to": "runtime.operator_interface", "type": "control"},
        {"from": "monitoring.alert_engine", "to": "runtime.health", "type": "influence"},
        {"from": "monitoring.topology", "to": "analytics.overview", "type": "influence"},

        # ── Data model edges ──
        {"from": "models.governance", "to": "governance.loader", "type": "dependency"},
        {"from": "models.governance", "to": "governance.registry", "type": "dependency"},
        {"from": "models.governance", "to": "governance.validator", "type": "dependency"},
        {"from": "models.governance", "to": "governance.enforcer", "type": "dependency"},
        {"from": "models.cognition", "to": "cognition.state_machine", "type": "dependency"},
        {"from": "models.cognition", "to": "cognition.session", "type": "dependency"},
        {"from": "models.memory", "to": "memory.episodic", "type": "dependency"},
        {"from": "models.audit", "to": "traceability.audit", "type": "dependency"},
        {"from": "models.inference", "to": "inference.executor", "type": "dependency"},
        {"from": "models.inference", "to": "inference.mediator", "type": "dependency"},

        # ── Database edges ──
        {"from": "database.queries", "to": "database.connection", "type": "dependency"},
        {"from": "traceability.audit", "to": "database.queries", "type": "dependency"},
        {"from": "memory.store", "to": "database.queries", "type": "dependency"},
    ]

    # ------------------------------------------------------------------
    # Full topology mapping
    # ------------------------------------------------------------------

    def map_full_topology(self) -> dict[str, Any]:
        """Map the complete system topology.

        Returns a dict with:
        - nodes: list of node dicts with id, layer, type, description, status
        - edges: list of edge dicts with from, to, type
        - layers: list of layer names
        - metadata: topology metadata
        """
        nodes = [
            {
                "id": n["id"],
                "layer": n["layer"],
                "type": n["type"],
                "status": "healthy",
                "description": n["description"],
            }
            for n in self.NODES
        ]

        edges = [
            {
                "from": e["from"],
                "to": e["to"],
                "type": e["type"],
            }
            for e in self.EDGES
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "layers": list(self.LAYERS),
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "total_layers": len(self.LAYERS),
                "edge_types": list(set(e["type"] for e in edges)),
            },
        }

    def map_governance_topology(self) -> dict[str, Any]:
        """Map just the governance layer topology."""
        return self._filter_by_layers(["governance"])

    def map_cognition_topology(self) -> dict[str, Any]:
        """Map just the cognition layer topology."""
        return self._filter_by_layers(["cognition"])

    def map_data_flow(self) -> dict[str, Any]:
        """Map data flow through the system.

        Shows the path: prompt -> mediation -> inference -> validation -> trace
        """
        full = self.map_full_topology()

        # Filter to only data_flow edges
        data_edges = [e for e in full["edges"] if e["type"] == "data_flow"]

        # Include the primary data-flow path nodes
        flow_node_ids = set()
        for e in data_edges:
            flow_node_ids.add(e["from"])
            flow_node_ids.add(e["to"])

        flow_nodes = [n for n in full["nodes"] if n["id"] in flow_node_ids]

        return {
            "nodes": flow_nodes,
            "edges": data_edges,
            "flow_path": [
                "inference.mediator",
                "inference.executor",
                "governance.middleware",
                "governance.validator",
                "traceability.audit",
                "traceability.lineage",
                "memory.episodic",
            ],
            "metadata": {
                "description": (
                    "Primary data flow: prompt mediation -> inference execution "
                    "-> governance validation -> audit logging -> lineage tracking "
                    "-> memory storage"
                ),
            },
        }

    def _filter_by_layers(self, layers: list[str]) -> dict[str, Any]:
        """Filter topology to specified layers."""
        full = self.map_full_topology()
        node_ids = {n["id"] for n in full["nodes"] if n["layer"] in layers}

        nodes = [n for n in full["nodes"] if n["id"] in node_ids]
        edges = [
            e for e in full["edges"]
            if e["from"] in node_ids and e["to"] in node_ids
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "layers": layers,
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "layer_filter": layers,
            },
        }

    # ------------------------------------------------------------------
    # Graph analysis
    # ------------------------------------------------------------------

    def compute_centrality(self, topology: dict[str, Any]) -> dict[str, float]:
        """Compute centrality scores for each node.

        Uses degree centrality (in-degree + out-degree) normalized.
        Higher scores indicate nodes that are more connected and
        thus more critical to system function.

        Returns a dict mapping node_id -> centrality_score.
        """
        nodes = topology.get("nodes", [])
        edges = topology.get("edges", [])
        if not nodes or not edges:
            return {}

        node_ids = {n["id"] for n in nodes}
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
        out_degree: dict[str, int] = {nid: 0 for nid in node_ids}

        for edge in edges:
            src = edge["from"]
            dst = edge["to"]
            if src in out_degree:
                out_degree[src] += 1
            if dst in in_degree:
                in_degree[dst] += 1

        max_possible = len(nodes) - 1 if len(nodes) > 1 else 1
        centrality: dict[str, float] = {}
        for nid in node_ids:
            total_degree = in_degree[nid] + out_degree[nid]
            centrality[nid] = round(total_degree / max_possible, 6)

        # Sort by centrality descending
        return dict(sorted(centrality.items(), key=lambda x: x[1], reverse=True))

    def find_critical_paths(self, topology: dict[str, Any]) -> list[list[str]]:
        """Find critical paths through the system.

        A critical path is a sequence of nodes where failure at any
        point has maximum impact. We find these by looking for paths
        from entry points (no incoming edges) to exit points
        (no outgoing edges) that pass through high-centrality nodes.

        Returns a list of node-id paths, sorted by estimated impact.
        """
        nodes = topology.get("nodes", [])
        edges = topology.get("edges", [])
        if not nodes or not edges:
            return []

        node_ids = {n["id"] for n in nodes}
        adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

        for edge in edges:
            src = edge["from"]
            dst = edge["to"]
            if src in adjacency and dst in adjacency:
                adjacency[src].append(dst)
                in_degree[dst] += 1

        # Find entry points (no incoming edges within this topology)
        entry_points = [nid for nid, deg in in_degree.items() if deg == 0]

        # Find exit points (no outgoing edges)
        exit_points = [
            nid for nid in node_ids if not adjacency[nid]
        ]

        # If no clear entry/exit points, use governance.loader as entry
        # and runtime.operator_interface as exit
        if not entry_points:
            entry_points = ["governance.loader"]
        if not exit_points:
            exit_points = ["runtime.operator_interface"]

        # BFS to find all paths from entry to exit (capped)
        all_paths: list[list[str]] = []
        max_paths_per_entry = 10
        max_path_length = 20

        for entry in entry_points:
            if entry not in node_ids:
                continue
            queue: deque[tuple[str, list[str]]] = deque()
            queue.append((entry, [entry]))
            count = 0
            while queue and count < max_paths_per_entry:
                current, path = queue.popleft()
                if current in exit_points and len(path) > 1:
                    all_paths.append(path)
                    count += 1
                    continue
                if len(path) >= max_path_length:
                    continue
                for neighbor in adjacency.get(current, []):
                    if neighbor not in path:  # Avoid cycles
                        queue.append((neighbor, path + [neighbor]))

        # Score paths by number of governance/critical nodes
        def path_score(path: list[str]) -> float:
            score = 0.0
            for nid in path:
                if "governance" in nid:
                    score += 2.0
                if "enforcer" in nid or "validator" in nid:
                    score += 3.0
                if "state_machine" in nid:
                    score += 2.5
                if "middleware" in nid:
                    score += 2.0
            return score

        all_paths.sort(key=lambda p: (-path_score(p), len(p)))
        return all_paths[:5]  # Return top 5 critical paths

    # ------------------------------------------------------------------
    # Visualization renderers
    # ------------------------------------------------------------------

    def render_dot(self, topology: dict[str, Any]) -> str:
        """Render topology as Graphviz DOT format.

        Returns a DOT string that can be rendered with graphviz.
        """
        nodes = topology.get("nodes", [])
        edges = topology.get("edges", [])
        layers = topology.get("layers", [])

        lines = [
            "digraph GARVIS {",
            '    rankdir="TB";',
            '    node [shape=box, style="rounded,filled", fontname="Helvetica"];',
            '    edge [fontname="Helvetica", fontsize=10];',
            "",
        ]

        # Layer colors
        layer_colors = {
            "governance": "#ffcccc",
            "cognition": "#ccffcc",
            "memory": "#ccccff",
            "traceability": "#ffffcc",
            "inference": "#ccffff",
            "runtime": "#ffccff",
            "analytics": "#ffe4cc",
            "monitoring": "#e4ccff",
        }

        # Declare subgraphs per layer
        for layer in layers:
            color = layer_colors.get(layer, "#f0f0f0")
            layer_nodes = [n for n in nodes if n["layer"] == layer]
            if not layer_nodes:
                continue
            lines.append(f'    subgraph cluster_{layer.replace(".", "_")} {{')
            lines.append(f'        label="{layer.capitalize()} Layer";')
            lines.append(f'        style="rounded";')
            lines.append(f'        color="{color}";')
            lines.append(f'        bgcolor="{color}";')
            for node in layer_nodes:
                status_color = "#90EE90" if node.get("status") == "healthy" else "#FFB6C1"
                node_id = node["id"].replace(".", "_")
                lines.append(
                    f'        {node_id} [label="{node["id"]}", '
                    f'fillcolor="{status_color}"];'
                )
            lines.append("    }")
            lines.append("")

        # Edges
        edge_styles = {
            "dependency": '[color="#333333", style=solid]',
            "influence": '[color="#666666", style=dashed]',
            "data_flow": '[color="#0066cc", style=bold]',
            "control": '[color="#cc0000", style=bold]',
        }

        for edge in edges:
            src = edge["from"].replace(".", "_")
            dst = edge["to"].replace(".", "_")
            style = edge_styles.get(edge["type"], "")
            lines.append(f'    {src} -> {dst} {style};')

        lines.append("}")
        return "\n".join(lines)

    def render_mermaid(self, topology: dict[str, Any]) -> str:
        """Render topology as Mermaid diagram.

        Returns a Mermaid flowchart string.
        """
        nodes = topology.get("nodes", [])
        edges = topology.get("edges", [])

        lines = ["flowchart TB"]

        # Subgraph per layer
        layers = topology.get("layers", [])
        for layer in layers:
            layer_nodes = [n for n in nodes if n["layer"] == layer]
            if not layer_nodes:
                continue
            layer_label = layer.capitalize() + " Layer"
            lines.append(f'    subgraph {layer}["{layer_label}"]')
            for node in layer_nodes:
                node_id = node["id"].replace(".", "_")
                node_label = node["id"]
                lines.append(f'        {node_id}["{node_label}"]')
            lines.append("    end")
            lines.append("")

        # Edges (deduplicate)
        seen_edges: set[str] = set()
        for edge in edges:
            src = edge["from"].replace(".", "_")
            dst = edge["to"].replace(".", "_")
            edge_str = f"{src} --> {dst}"
            if edge_str not in seen_edges:
                seen_edges.add(edge_str)
                edge_label = edge.get("type", "")
                if edge_label:
                    lines.append(f"    {src} -- {edge_label} --> {dst}")
                else:
                    lines.append(f"    {src} --> {dst}")

        return "\n".join(lines)
