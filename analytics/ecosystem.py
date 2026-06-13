"""Cognition ecosystem mapping for GARVIS analytics engine.

Maps the relationships between components of the cognition system:
- How governance schemas influence each other
- How memories relate to each other through provenance
- How reasoning influences flow through the system
- Overall ecosystem graph with nodes and edges

All mapping is PURELY OBSERVATIONAL -- it describes what relationships exist.
It NEVER creates or modifies any relationships.

All functions are pure -- same input always produces same output.
Empty input is handled gracefully (returns empty dicts/lists, never crashes).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from models.governance import GovernanceCheckResult, GovernanceViolation
from models.memory import EpisodicMemory, MemoryInfluence


# ============================================================================
#  EcosystemMapper — Cognition ecosystem mapping
# ============================================================================


class EcosystemMapper:
    """Maps the cognition ecosystem -- relationships between components.

    Produces graph-like structures showing how governance, memory,
    and reasoning components interact. These maps help operators
    understand system topology and identify central vs. peripheral
    components.

    All methods are pure functions.
    """

    # ------------------------------------------------------------------
    #  Governance influence ecosystem
    # ------------------------------------------------------------------

    def map_governance_influence_ecosystem(
        self,
        checks: list[GovernanceCheckResult],
        violations: list[GovernanceViolation],
    ) -> dict[str, Any]:
        """Maps how governance schemas influence each other.

        Analyzes co-occurrence of schemas in governance checks and
        violation patterns to infer influence relationships. Schemas
        that frequently check or violate together are considered
        influencing each other.

        Returns a dict with:
        - nodes: list of schema_id dicts
        - edges: list of {source, target, weight} dicts
        - centrality: dict of schema_id -> centrality score
        """
        if not checks and not violations:
            return {"nodes": [], "edges": [], "centrality": {}}

        # Build co-occurrence graph from checks
        schema_pairs: dict[tuple[str, str], int] = defaultdict(int)
        schema_check_counts: dict[str, int] = defaultdict(int)
        schema_violation_counts: dict[str, int] = defaultdict(int)

        # Group checks by their context (trace/response) to find co-occurrences
        # We'll use a sliding window approach: schemas checked near each other
        all_schemas = sorted(set(
            c.schema_id for c in checks
        ) | set(v.schema_id for v in violations))

        for check in checks:
            schema_check_counts[check.schema_id] += 1

        for violation in violations:
            schema_violation_counts[violation.schema_id] += 1

        # Build edges from co-occurrence in the same "transaction"
        # Group checks by a simple heuristic: consecutive checks with
        # timestamps within a short window are considered co-occurring
        if checks:
            sorted_checks = sorted(checks, key=lambda c: c.timestamp)
            window_checks: list[GovernanceCheckResult] = []
            for check in sorted_checks:
                window_checks.append(check)
                if len(window_checks) >= 3:
                    # Form edges between all pairs in this window
                    for i in range(len(window_checks)):
                        for j in range(i + 1, len(window_checks)):
                            s1 = window_checks[i].schema_id
                            s2 = window_checks[j].schema_id
                            if s1 != s2:
                                pair = tuple(sorted((s1, s2)))
                                schema_pairs[pair] += 1
                    window_checks.pop(0)

        # Also add violation-based edges
        for v in violations:
            for schema_id in all_schemas:
                if schema_id != v.schema_id:
                    pair = tuple(sorted((schema_id, v.schema_id)))
                    schema_pairs[pair] += 1

        # Build nodes
        nodes: list[dict[str, Any]] = []
        for sid in all_schemas:
            nodes.append({
                "id": sid,
                "check_count": schema_check_counts.get(sid, 0),
                "violation_count": schema_violation_counts.get(sid, 0),
                "pressure": round(
                    schema_violation_counts.get(sid, 0)
                    / max(schema_check_counts.get(sid, 1), 1),
                    6,
                ),
            })

        # Build edges (threshold: weight >= 1)
        max_weight = max(schema_pairs.values()) if schema_pairs else 1
        edges: list[dict[str, Any]] = []
        for (s1, s2), weight in schema_pairs.items():
            normalized_weight = weight / max_weight
            edges.append({
                "source": s1,
                "target": s2,
                "weight": round(normalized_weight, 6),
                "raw_count": weight,
            })

        # Compute simple degree centrality
        centrality: dict[str, float] = defaultdict(float)
        for edge in edges:
            centrality[edge["source"]] += edge["weight"]
            centrality[edge["target"]] += edge["weight"]

        # Normalize centrality
        if centrality:
            max_cent = max(centrality.values())
            if max_cent > 0:
                centrality = {
                    k: round(v / max_cent, 6)
                    for k, v in centrality.items()
                }

        return {
            "nodes": nodes,
            "edges": edges,
            "centrality": dict(centrality),
        }

    # ------------------------------------------------------------------
    #  Memory relationship ecosystem
    # ------------------------------------------------------------------

    def map_memory_relationship_ecosystem(
        self,
        memories: list[EpisodicMemory],
        influences: list[MemoryInfluence],
    ) -> dict[str, Any]:
        """Maps relationships between memories.

        Analyzes parent-child relationships, governance schema sharing,
        and influence patterns to map the memory ecosystem.

        Returns a dict with:
        - nodes: list of memory node dicts
        - edges: list of {source, target, type, weight} dicts
        - clusters: dict of cluster_id -> list of memory_ids
        """
        if not memories:
            return {"nodes": [], "edges": [], "clusters": {}}

        # Build nodes
        nodes: list[dict[str, Any]] = []
        memory_ids = set(str(m.memory_id) for m in memories)
        for m in memories:
            nodes.append({
                "id": str(m.memory_id),
                "episode_type": m.episode_type,
                "retrieval_count": m.retrieval_count,
                "schema_count": len(m.governance_influences),
                "confidence": m.confidence,
            })

        # Build edges
        edges: list[dict[str, Any]] = []

        # Parent-child edges (provenance)
        for m in memories:
            parent_id = m.provenance.parent_memory_id
            if parent_id is not None and str(parent_id) in memory_ids:
                edges.append({
                    "source": str(parent_id),
                    "target": str(m.memory_id),
                    "type": "parent_child",
                    "weight": 1.0,
                })

        # Schema-sharing edges (memories influenced by same schemas)
        schema_to_memories: dict[str, list[str]] = defaultdict(list)
        for m in memories:
            for schema_id in m.governance_influences:
                schema_to_memories[schema_id].append(str(m.memory_id))

        for schema_id, mem_ids in schema_to_memories.items():
            if len(mem_ids) >= 2:
                for i in range(len(mem_ids)):
                    for j in range(i + 1, len(mem_ids)):
                        edges.append({
                            "source": mem_ids[i],
                            "target": mem_ids[j],
                            "type": "shared_schema",
                            "weight": 0.5,
                            "schema": schema_id,
                        })

        # Influence edges
        for inf in influences:
            src = str(inf.memory_id)
            if src in memory_ids:
                edges.append({
                    "source": src,
                    "target": str(inf.target_inference_id),
                    "type": f"influence_{inf.influence_type}",
                    "weight": inf.strength,
                })

        # Cluster by episode type
        clusters: dict[str, list[str]] = defaultdict(list)
        for m in memories:
            clusters[m.episode_type].append(str(m.memory_id))

        return {
            "nodes": nodes,
            "edges": edges,
            "clusters": dict(clusters),
        }

    # ------------------------------------------------------------------
    #  Reasoning influence ecosystem
    # ------------------------------------------------------------------

    def map_reasoning_influence_ecosystem(
        self,
        traces: list[Any],
    ) -> dict[str, Any]:
        """Maps how reasoning influences flow through the system.

        Analyzes cognition traces to understand:
        - Which governance schemas most influence reasoning
        - How memory influences propagate through traces
        - What event types are most common in reasoning chains

        Returns a dict with:
        - nodes: list of reasoning component dicts
        - edges: list of {source, target, weight} dicts
        - flow_summary: dict with influence statistics
        """
        if not traces:
            return {"nodes": [], "edges": [], "flow_summary": {}}

        # Count components
        schema_influence_counts: dict[str, int] = defaultdict(int)
        memory_influence_counts: dict[str, int] = defaultdict(int)
        event_type_counts: dict[str, int] = defaultdict(int)
        total_traces = len(traces)

        for trace in traces:
            # Governance schemas checked
            checks = getattr(trace, "governance_checks", [])
            for c in checks:
                schema_influence_counts[c.schema_id] += 1

            # Memory influences
            mem_infs = getattr(trace, "memory_influences", [])
            for mi in mem_infs:
                schema_influence_counts[str(mi.influence_type)] += 1

            # Events
            events = getattr(trace, "events", [])
            for e in events:
                event_type_counts[e.event_type] += 1

        # Build nodes (schemas + event types + memory influence types)
        nodes: list[dict[str, Any]] = []
        node_ids: set[str] = set()

        for schema_id, count in schema_influence_counts.items():
            nodes.append({
                "id": schema_id,
                "type": "governance_schema",
                "influence_count": count,
                "frequency": round(count / total_traces, 6),
            })
            node_ids.add(schema_id)

        for event_type, count in event_type_counts.items():
            nid = f"event:{event_type}"
            nodes.append({
                "id": nid,
                "type": "event",
                "influence_count": count,
                "frequency": round(count / total_traces, 6),
            })
            node_ids.add(nid)

        # Build edges: connect schemas that appear in the same trace
        edges: list[dict[str, Any]] = []
        schema_pair_counts: dict[tuple[str, str], int] = defaultdict(int)

        for trace in traces:
            checks = getattr(trace, "governance_checks", [])
            schemas_in_trace = sorted(set(c.schema_id for c in checks))
            for i in range(len(schemas_in_trace)):
                for j in range(i + 1, len(schemas_in_trace)):
                    pair = tuple(sorted((schemas_in_trace[i], schemas_in_trace[j])))
                    schema_pair_counts[pair] += 1

        max_pair_count = max(schema_pair_counts.values()) if schema_pair_counts else 1
        for (s1, s2), count in schema_pair_counts.items():
            edges.append({
                "source": s1,
                "target": s2,
                "weight": round(count / max_pair_count, 6),
                "co_occurrence_count": count,
            })

        # Flow summary
        top_schemas = sorted(
            schema_influence_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        top_events = sorted(
            event_type_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        flow_summary = {
            "total_traces_analyzed": total_traces,
            "unique_schemas_involved": len(schema_influence_counts),
            "unique_event_types": len(event_type_counts),
            "top_influencing_schemas": [
                {"schema": s, "count": c} for s, c in top_schemas
            ],
            "top_event_types": [
                {"event": e, "count": c} for e, c in top_events
            ],
        }

        return {
            "nodes": nodes,
            "edges": edges,
            "flow_summary": flow_summary,
        }

    # ------------------------------------------------------------------
    #  Full cognition ecosystem graph
    # ------------------------------------------------------------------

    def compute_cognition_ecosystem_graph(
        self,
        all_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Computes the full cognition ecosystem graph with nodes and edges.

        Combines governance, memory, and reasoning ecosystems into
        a single unified graph.

        Args:
            all_data: Dict containing:
                - "checks": list[GovernanceCheckResult]
                - "violations": list[GovernanceViolation]
                - "memories": list[EpisodicMemory]
                - "influences": list[MemoryInfluence]
                - "traces": list[CognitionTrace]

        Returns a dict with:
        - nodes: unified list of all nodes with type labels
        - edges: unified list of all edges with type labels
        - stats: ecosystem statistics
        """
        checks = all_data.get("checks", [])
        violations = all_data.get("violations", [])
        memories = all_data.get("memories", [])
        influences = all_data.get("influences", [])
        traces = all_data.get("traces", [])

        # Get sub-ecosystems
        gov_eco = self.map_governance_influence_ecosystem(checks, violations)
        mem_eco = self.map_memory_relationship_ecosystem(memories, influences)
        rea_eco = self.map_reasoning_influence_ecosystem(traces)

        # Unify nodes with type prefixes
        all_nodes: list[dict[str, Any]] = []
        for n in gov_eco.get("nodes", []):
            node = dict(n)
            node["ecosystem"] = "governance"
            all_nodes.append(node)
        for n in mem_eco.get("nodes", []):
            node = dict(n)
            node["ecosystem"] = "memory"
            all_nodes.append(node)
        for n in rea_eco.get("nodes", []):
            node = dict(n)
            node["ecosystem"] = "reasoning"
            all_nodes.append(node)

        # Unify edges with type labels
        all_edges: list[dict[str, Any]] = []
        for e in gov_eco.get("edges", []):
            edge = dict(e)
            edge["ecosystem"] = "governance"
            all_edges.append(edge)
        for e in mem_eco.get("edges", []):
            edge = dict(e)
            edge["ecosystem"] = "memory"
            all_edges.append(edge)
        for e in rea_eco.get("edges", []):
            edge = dict(e)
            edge["ecosystem"] = "reasoning"
            all_edges.append(edge)

        # Stats
        stats = {
            "total_nodes": len(all_nodes),
            "total_edges": len(all_edges),
            "governance_nodes": len(gov_eco.get("nodes", [])),
            "memory_nodes": len(mem_eco.get("nodes", [])),
            "reasoning_nodes": len(rea_eco.get("nodes", [])),
            "governance_edges": len(gov_eco.get("edges", [])),
            "memory_edges": len(mem_eco.get("edges", [])),
            "reasoning_edges": len(rea_eco.get("edges", [])),
            "avg_node_degree": (
                round(len(all_edges) * 2 / len(all_nodes), 6)
                if all_nodes else 0.0
            ),
        }

        return {
            "nodes": all_nodes,
            "edges": all_edges,
            "stats": stats,
        }

    # ------------------------------------------------------------------
    #  Alignment ecology
    # ------------------------------------------------------------------

    def compute_alignment_ecology(
        self,
        sessions: list[Any],
        checks: list[GovernanceCheckResult],
    ) -> dict[str, Any]:
        """Computes alignment persistence ecology -- drift, durability, stability.

        Analyzes how well alignment persists across sessions by measuring
        drift (change in pass rates), durability (resistance to violation),
        and stability (consistency over time).

        Returns a dict with:
        - drift_rate: float in [0.0, 1.0]
        - durability_score: float in [0.0, 1.0]
        - stability_score: float in [0.0, 1.0]
        - alignment_health: str ("healthy", "degrading", "critical")
        """
        if not checks:
            return {
                "drift_rate": 0.0,
                "durability_score": 0.0,
                "stability_score": 0.0,
                "alignment_health": "unknown",
            }

        # Compute per-session pass rates if sessions are provided
        session_rates: list[float] = []
        if sessions:
            for session in sessions:
                session_checks = getattr(session, "governance_checks", [])
                if not session_checks:
                    continue
                passed = sum(1 for c in session_checks if c.passed)
                rate = passed / len(session_checks)
                session_rates.append(rate)

        # Fallback: overall rate
        if not session_rates:
            passed = sum(1 for c in checks if c.passed)
            session_rates = [passed / len(checks)]

        # Drift rate: standard deviation of pass rates
        if len(session_rates) >= 2:
            mean_rate = sum(session_rates) / len(session_rates)
            variance = sum((r - mean_rate) ** 2 for r in session_rates) / len(session_rates)
            drift_rate = (variance ** 0.5)
        else:
            drift_rate = 0.0

        # Durability: overall pass rate
        all_passed = sum(1 for c in checks if c.passed)
        durability = all_passed / len(checks)

        # Stability: inverse of drift, scaled
        stability = max(0.0, 1.0 - drift_rate)

        # Health classification
        if durability >= 0.9 and drift_rate < 0.1:
            health = "healthy"
        elif durability >= 0.7 and drift_rate < 0.2:
            health = "stable"
        elif durability >= 0.5:
            health = "degrading"
        else:
            health = "critical"

        return {
            "drift_rate": round(min(drift_rate, 1.0), 6),
            "durability_score": round(durability, 6),
            "stability_score": round(stability, 6),
            "alignment_health": health,
            "session_pass_rates": [round(r, 6) for r in session_rates],
        }

    # ------------------------------------------------------------------
    #  Governance durability
    # ------------------------------------------------------------------

    def compute_governance_durability(
        self,
        schemas: list[Any],
        checks: list[GovernanceCheckResult],
    ) -> float:
        """How durable governance remains under operational pressure.

        Measures the ratio of passed checks to total checks per schema,
        then averages across all schemas. A durable governance system
        maintains high pass rates even under load.

        Args:
            schemas: List of governance schemas.
            checks: All governance check results.

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not schemas or not checks:
            return 0.0

        # Group checks by schema
        schema_check_counts: dict[str, int] = defaultdict(int)
        schema_pass_counts: dict[str, int] = defaultdict(int)

        for c in checks:
            schema_check_counts[c.schema_id] += 1
            if c.passed:
                schema_pass_counts[c.schema_id] += 1

        # Compute per-schema durability
        durabilities: list[float] = []
        for schema in schemas:
            sid = getattr(schema, "schema_id", str(schema))
            total = schema_check_counts.get(sid, 0)
            if total > 0:
                passed = schema_pass_counts.get(sid, 0)
                durabilities.append(passed / total)

        if not durabilities:
            return 0.0

        return round(sum(durabilities) / len(durabilities), 6)
