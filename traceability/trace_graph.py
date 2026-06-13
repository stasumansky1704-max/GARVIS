"""
Cognition Trace Graph

Graph construction for cognition traces.
Builds directed graphs representing the full lineage of a cognition session,
including inferences, memories, governance checks, state transitions, and
their relationships.

Provides:
- build_graph: Construct a full DiGraph from a trace
- add_node / add_edge: Extend graphs incrementally
- get_critical_path: Find the most important nodes in a trace
- get_governance_hotspots: Areas with most governance activity
- export_graph: Dict representation for serialization
"""

from __future__ import annotations

import logging
from uuid import UUID

from database.connection import DatabaseConnection
from models.audit import AuditEvent, CognitionTrace
from models.governance import GovernanceCheckResult
from models.memory import MemoryInfluence

logger = logging.getLogger(__name__)


class TraceGraphBuilder:
    """Builds and analyzes cognition trace graphs.

    Constructs directed graphs from trace data, enabling:
    - Visualization of reasoning lineage
    - Critical path analysis
    - Governance hotspot detection
    - Export to various formats
    """

    def __init__(self, db: DatabaseConnection | None = None) -> None:
        self.db = db
        self._graphs: dict[UUID, dict] = {}  # Cache for built graphs

    async def build_graph(self, trace_id: UUID) -> dict:
        """Build a directed graph representation of a cognition trace.

        If the trace is not in the local cache, it will be reconstructed
        from the database (requires db connection).

        Args:
            trace_id: The trace to build the graph for.

        Returns:
            Dict with:
                - trace_id: UUID of the trace
                - node_count: Total number of nodes
                - edge_count: Total number of edges
                - nodes: dict of node_id -> {type, data}
                - edges: list of {from, to, type, weight}
                - critical_score: dict of node_id -> importance score
        """
        if trace_id in self._graphs:
            return self._graphs[trace_id]

        logger.info("Building trace graph for: %s", trace_id)

        # If we have a db connection, reconstruct the trace
        if self.db is not None:
            from traceability.lineage import LineageTracker

            tracker = LineageTracker(self.db)
            trace = await tracker.get_trace(trace_id)
        else:
            logger.warning("No DB connection, cannot reconstruct trace %s", trace_id)
            trace = None

        if trace is None:
            empty_graph = {
                "trace_id": str(trace_id),
                "node_count": 0,
                "edge_count": 0,
                "nodes": {},
                "edges": [],
                "critical_score": {},
            }
            self._graphs[trace_id] = empty_graph
            return empty_graph

        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        critical_score: dict[str, float] = {}

        # --- Trace root node ---
        trace_node = f"trace:{trace_id}"
        nodes[trace_node] = {
            "type": "trace",
            "label": f"Trace {str(trace_id)[:8]}",
            "session_id": str(trace.session_id),
            "start_time": trace.start_time.isoformat(),
            "final_state": trace.final_state.value,
        }
        critical_score[trace_node] = 1.0

        # --- State transition nodes ---
        for transition in trace.state_sequence:
            node_id = f"transition:{transition.transition_id}"
            nodes[node_id] = {
                "type": "state_transition",
                "label": f"{transition.from_state.value} -> {transition.to_state.value}",
                "from_state": transition.from_state.value,
                "to_state": transition.to_state.value,
                "trigger": transition.trigger,
                "governance_check": transition.governance_check,
                "timestamp": transition.timestamp.isoformat(),
            }
            edges.append({
                "from": trace_node,
                "to": node_id,
                "type": "contains",
                "weight": 1.0,
            })
            critical_score[node_id] = 0.5

            # Special scoring for critical transitions
            if transition.to_state.value in ("fail_closed", "degraded"):
                critical_score[node_id] = 1.0

        # --- Audit event nodes ---
        for event in trace.events:
            node_id = f"event:{event.event_id}"
            nodes[node_id] = {
                "type": "audit_event",
                "label": f"{event.event_type} ({event.severity})",
                "event_type": event.event_type,
                "severity": event.severity,
                "component": event.component,
                "timestamp": event.timestamp.isoformat(),
            }
            edges.append({
                "from": trace_node,
                "to": node_id,
                "type": "logged",
                "weight": 0.5,
            })
            critical_score[node_id] = (
                1.0 if event.severity == "critical" else 0.3 if event.severity == "warning" else 0.1
            )

        # --- Governance check nodes ---
        for check in trace.governance_checks:
            node_id = f"check:{check.check_id}"
            nodes[node_id] = {
                "type": "governance_check",
                "label": f"Check {check.schema_id}/{check.policy_id}",
                "schema_id": check.schema_id,
                "policy_id": check.policy_id,
                "passed": check.passed,
                "timestamp": check.timestamp.isoformat(),
            }
            edges.append({
                "from": trace_node,
                "to": node_id,
                "type": "governed_by",
                "weight": 1.0 if not check.passed else 0.5,
            })
            critical_score[node_id] = 0.8 if not check.passed else 0.3

        # --- Memory influence nodes and edges ---
        for influence in trace.memory_influences:
            influence_node = f"influence:{influence.influence_id}"
            memory_node = f"memory:{influence.memory_id}"
            inference_node = f"inference:{influence.target_inference_id}"

            # Influence node
            if influence_node not in nodes:
                nodes[influence_node] = {
                    "type": "influence",
                    "label": f"Influence ({influence.influence_type}, {influence.strength:.2f})",
                    "influence_type": influence.influence_type,
                    "strength": influence.strength,
                    "trace_visible": influence.trace_visible,
                }
                critical_score[influence_node] = influence.strength

            # Memory node
            if memory_node not in nodes:
                nodes[memory_node] = {
                    "type": "memory",
                    "label": f"Memory {str(influence.memory_id)[:8]}",
                    "memory_id": str(influence.memory_id),
                }
                critical_score[memory_node] = 0.4

            # Inference node
            if inference_node not in nodes:
                nodes[inference_node] = {
                    "type": "inference",
                    "label": f"Inference {str(influence.target_inference_id)[:8]}",
                    "inference_id": str(influence.target_inference_id),
                }
                critical_score[inference_node] = 0.6

            edges.append({
                "from": memory_node,
                "to": influence_node,
                "type": "exerts",
                "weight": influence.strength,
            })
            edges.append({
                "from": influence_node,
                "to": inference_node,
                "type": "affects",
                "weight": influence.strength,
            })

        graph = {
            "trace_id": str(trace_id),
            "session_id": str(trace.session_id),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
            "critical_score": critical_score,
        }

        # Cache the graph
        self._graphs[trace_id] = graph

        logger.info(
            "Trace graph built for %s: %d nodes, %d edges",
            trace_id,
            len(nodes),
            len(edges),
        )
        return graph

    def add_node(
        self,
        trace_id: UUID,
        node_id: str,
        node_type: str,
        data: dict,
        label: str | None = None,
    ) -> None:
        """Add a node to an existing graph.

        Args:
            trace_id: The trace graph to modify.
            node_id: Unique identifier for the node.
            node_type: Type of node (memory, inference, check, etc.)
            data: Additional node attributes.
            label: Optional display label.
        """
        if trace_id not in self._graphs:
            logger.warning(
                "Cannot add node: graph for trace %s not built yet", trace_id
            )
            return

        graph = self._graphs[trace_id]

        node_data = {"type": node_type, "label": label or node_id}
        node_data.update(data)

        graph["nodes"][node_id] = node_data
        graph["node_count"] = len(graph["nodes"])

        logger.debug(
            "Added node %s (type=%s) to trace graph %s",
            node_id,
            node_type,
            trace_id,
        )

    def add_edge(
        self,
        trace_id: UUID,
        from_id: str,
        to_id: str,
        edge_type: str,
        weight: float = 1.0,
    ) -> None:
        """Add an edge to an existing graph.

        Args:
            trace_id: The trace graph to modify.
            from_id: Source node ID.
            to_id: Target node ID.
            edge_type: Type of relationship.
            weight: Edge weight (0.0-1.0).
        """
        if trace_id not in self._graphs:
            logger.warning(
                "Cannot add edge: graph for trace %s not built yet", trace_id
            )
            return

        graph = self._graphs[trace_id]

        graph["edges"].append({
            "from": from_id,
            "to": to_id,
            "type": edge_type,
            "weight": weight,
        })
        graph["edge_count"] = len(graph["edges"])

        logger.debug(
            "Added edge %s -> %s (type=%s) to trace graph %s",
            from_id,
            to_id,
            edge_type,
            trace_id,
        )

    def get_critical_path(self, trace_id: UUID) -> list[dict]:
        """Find the most important nodes in a trace.

        Returns nodes sorted by critical_score (highest first),
        representing the most significant elements of the trace.

        Args:
            trace_id: The trace to analyze.

        Returns:
            List of {node_id, type, score, data} dicts.
        """
        if trace_id not in self._graphs:
            logger.warning(
                "Cannot get critical path: graph for trace %s not built", trace_id
            )
            return []

        graph = self._graphs[trace_id]
        scores = graph.get("critical_score", {})

        sorted_nodes = sorted(
            scores.items(), key=lambda x: x[1], reverse=True
        )

        critical_path = []
        for node_id, score in sorted_nodes:
            if node_id in graph["nodes"]:
                node_data = dict(graph["nodes"][node_id])
                critical_path.append({
                    "node_id": node_id,
                    "type": node_data.get("type", "unknown"),
                    "score": score,
                    "label": node_data.get("label", node_id),
                    "data": node_data,
                })

        logger.debug(
            "Critical path for trace %s: %d nodes",
            trace_id,
            len(critical_path),
        )
        return critical_path

    def get_governance_hotspots(self, trace_id: UUID) -> dict:
        """Find areas with the most governance activity in a trace.

        Analyzes governance checks, violations, and state transitions
        to identify governance-dense regions.

        Args:
            trace_id: The trace to analyze.

        Returns:
            Dict with:
                - total_checks: Number of governance checks
                - failed_checks: Number of failed checks
                - critical_events: Number of critical audit events
                - hotspot_nodes: List of most active governance nodes
                - governance_density: Ratio of governance nodes to total
        """
        if trace_id not in self._graphs:
            logger.warning(
                "Cannot get hotspots: graph for trace %s not built", trace_id
            )
            return {
                "total_checks": 0,
                "failed_checks": 0,
                "critical_events": 0,
                "hotspot_nodes": [],
                "governance_density": 0.0,
            }

        graph = self._graphs[trace_id]
        nodes = graph.get("nodes", {})
        edges = graph.get("edges", [])

        total_checks = 0
        failed_checks = 0
        critical_events = 0
        hotspot_nodes = []

        for node_id, node_data in nodes.items():
            node_type = node_data.get("type", "")

            if node_type == "governance_check":
                total_checks += 1
                if not node_data.get("passed", True):
                    failed_checks += 1
                    hotspot_nodes.append({
                        "node_id": node_id,
                        "type": "failed_check",
                        "schema_id": node_data.get("schema_id", "unknown"),
                        "policy_id": node_data.get("policy_id", "unknown"),
                        "score": 1.0,
                    })

            if node_type == "audit_event":
                if node_data.get("severity") == "critical":
                    critical_events += 1
                    hotspot_nodes.append({
                        "node_id": node_id,
                        "type": "critical_event",
                        "event_type": node_data.get("event_type", "unknown"),
                        "score": 0.9,
                    })
                elif node_data.get("severity") == "warning":
                    hotspot_nodes.append({
                        "node_id": node_id,
                        "type": "warning_event",
                        "event_type": node_data.get("event_type", "unknown"),
                        "score": 0.5,
                    })

            if node_type == "state_transition":
                to_state = node_data.get("to_state", "")
                if to_state in ("fail_closed", "degraded"):
                    hotspot_nodes.append({
                        "node_id": node_id,
                        "type": f"transition_to_{to_state}",
                        "trigger": node_data.get("trigger", ""),
                        "score": 1.0,
                    })

        # Sort by score descending
        hotspot_nodes.sort(key=lambda x: x["score"], reverse=True)

        total_nodes = len(nodes)
        governance_nodes = sum(
            1 for n in nodes.values() if n.get("type") in ("governance_check", "audit_event")
        )
        governance_density = governance_nodes / total_nodes if total_nodes > 0 else 0.0

        result = {
            "trace_id": str(trace_id),
            "total_checks": total_checks,
            "failed_checks": failed_checks,
            "critical_events": critical_events,
            "hotspot_nodes": hotspot_nodes[:20],  # Top 20
            "governance_density": round(governance_density, 4),
        }

        logger.debug(
            "Governance hotspots for trace %s: %d checks (%d failed), "
            "%d critical events, density=%.2f",
            trace_id,
            total_checks,
            failed_checks,
            critical_events,
            governance_density,
        )
        return result

    def export_graph(
        self,
        trace_id: UUID,
        format: str = "dict",
    ) -> dict:
        """Export a graph in the specified format.

        Args:
            trace_id: The trace to export.
            format: Export format. Currently supports "dict" only.

        Returns:
            Dict representation of the graph.
        """
        if trace_id not in self._graphs:
            logger.warning(
                "Cannot export: graph for trace %s not built", trace_id
            )
            return {"error": f"Graph for trace {trace_id} not found"}

        graph = self._graphs[trace_id]

        if format == "dict":
            export = {
                "format": "dict",
                "trace_id": graph["trace_id"],
                "session_id": graph.get("session_id", ""),
                "node_count": graph["node_count"],
                "edge_count": graph["edge_count"],
                "nodes": graph["nodes"],
                "edges": graph["edges"],
            }
        elif format == "summary":
            export = {
                "format": "summary",
                "trace_id": graph["trace_id"],
                "session_id": graph.get("session_id", ""),
                "node_count": graph["node_count"],
                "edge_count": graph["edge_count"],
                "node_types": self._count_node_types(graph),
                "edge_types": self._count_edge_types(graph),
            }
        else:
            export = {"error": f"Unsupported format: {format}"}

        logger.debug(
            "Exported graph for trace %s in format '%s'",
            trace_id,
            format,
        )
        return export

    def invalidate_cache(self, trace_id: UUID | None = None) -> None:
        """Invalidate the graph cache.

        Args:
            trace_id: Specific trace to invalidate, or None to clear all.
        """
        if trace_id is None:
            self._graphs.clear()
            logger.debug("Graph cache cleared")
        elif trace_id in self._graphs:
            del self._graphs[trace_id]
            logger.debug("Graph cache invalidated for trace %s", trace_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _count_node_types(self, graph: dict) -> dict[str, int]:
        """Count occurrences of each node type."""
        counts: dict[str, int] = {}
        for node_data in graph.get("nodes", {}).values():
            node_type = node_data.get("type", "unknown")
            counts[node_type] = counts.get(node_type, 0) + 1
        return counts

    def _count_edge_types(self, graph: dict) -> dict[str, int]:
        """Count occurrences of each edge type."""
        counts: dict[str, int] = {}
        for edge in graph.get("edges", []):
            edge_type = edge.get("type", "unknown")
            counts[edge_type] = counts.get(edge_type, 0) + 1
        return counts
