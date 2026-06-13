"""High-level overview generator for GARVIS analytics engine.

Generates a comprehensive analytics overview for the operator console.
This is the single entry point for operators to understand system health.

All computations are PURELY OBSERVATIONAL. This module aggregates metrics
from all other analytics modules and presents them in a unified dashboard format.

All functions are pure -- same input always produces same output.
"""

from __future__ import annotations

from typing import Any

from analytics.continuity import ContinuityAnalyzer
from analytics.ecosystem import EcosystemMapper
from analytics.metrics import CognitionMetrics, GovernancePressureMetrics
from analytics.trends import TrendAnalyzer
from models.cognition import OperationalState, StateTransition
from models.governance import GovernanceCheckResult, GovernanceConstraint, GovernanceViolation
from models.memory import EpisodicMemory, MemoryInfluence


# ============================================================================
#  AnalyticsOverview — High-level overview generator
# ============================================================================


class AnalyticsOverview:
    """Generates a comprehensive analytics overview for the operator console.

    This is the primary interface for analytics consumption. It aggregates
    data from all analytics subsystems and produces a unified dashboard
    dict that the operator console can render directly.

    All methods are pure functions.
    """

    def __init__(self) -> None:
        """Initialize component analyzers."""
        self._cognition_metrics = CognitionMetrics()
        self._pressure_metrics = GovernancePressureMetrics()
        self._trend_analyzer = TrendAnalyzer()
        self._continuity_analyzer = ContinuityAnalyzer()
        self._ecosystem_mapper = EcosystemMapper()

    # ------------------------------------------------------------------
    #  Main overview generation
    # ------------------------------------------------------------------

    def generate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Generate complete overview with all metrics.

        Args:
            data: A dict containing all cognition data to analyze:
                Required keys:
                - "schemas": list of GovernanceSchema objects
                - "checks": list of GovernanceCheckResult objects
                - "violations": list of GovernanceViolation objects
                - "constraints": list of GovernanceConstraint objects
                - "responses": list of GovernedResponse objects
                - "traces": list of CognitionTrace objects
                - "transitions": list of StateTransition objects
                - "memories": list of EpisodicMemory objects
                - "influences": list of MemoryInfluence objects
                - "sessions": list of session objects
                - "current_state": str (current operational state name)
                - "audit_events": list of AuditEvent objects

        Returns a comprehensive overview dict with the following structure:
            {
                "governance": {
                    "active_schemas": int,
                    "total_constraints": int,
                    "hard_stop_rate": float,
                    "coverage_score": float,
                    "pressure": float,
                },
                "cognition": {
                    "current_state": str,
                    "session_count": int,
                    "success_rate": float,
                    "avg_response_time_ms": float,
                    "quality_score": float,
                },
                "memory": {
                    "total_memories": int,
                    "avg_retrievals": float,
                    "influences_tracked": int,
                    "trace_visible_rate": float,
                },
                "traceability": {
                    "total_traces": int,
                    "avg_governance_checks": float,
                    "violation_count": int,
                    "audit_event_count": int,
                },
                "continuity": {
                    "continuity_score": float,
                    "alignment_drift": float,
                    "resilience_score": float,
                    "equilibrium_stability": float,
                },
                "pressure": {
                    "adaptation_pressure": float,
                    "enforcement_pressure": float,
                    "conflict_pressure": float,
                    "overall_pressure": float,
                },
                "trends": {
                    "governance_trend": list[dict],
                    "state_stability_trend": list[dict],
                    "quality_trend": list[dict],
                    "degradation_trend": list[dict],
                },
                "ecosystem": {
                    "governance_nodes": int,
                    "memory_nodes": int,
                    "reasoning_nodes": int,
                    "total_edges": int,
                    "alignment_ecology": dict,
                }
            }
        """
        # Extract data
        schemas = data.get("schemas", [])
        checks = data.get("checks", [])
        violations = data.get("violations", [])
        constraints = data.get("constraints", [])
        responses = data.get("responses", [])
        traces = data.get("traces", [])
        transitions = data.get("transitions", [])
        memories = data.get("memories", [])
        influences = data.get("influences", [])
        sessions = data.get("sessions", [])
        current_state = data.get("current_state", "unknown")
        audit_events = data.get("audit_events", [])

        # ================================================================
        #  1. Governance section
        # ================================================================
        total_constraints = len(constraints)
        hard_stop_count = sum(
            1 for c in constraints if getattr(c, "enforcement", "") == "hard_stop"
        )
        hard_stop_rate = hard_stop_count / total_constraints if total_constraints else 0.0

        coverage_score = self._cognition_metrics.compute_governance_coverage(checks)
        enforcement_pressure = self._pressure_metrics.compute_enforcement_pressure(constraints)
        conflict_pressure = self._pressure_metrics.compute_conflict_pressure(violations)

        # Overall governance pressure: max of enforcement and conflict
        gov_pressure = max(enforcement_pressure, conflict_pressure)

        governance_section = {
            "active_schemas": len(schemas),
            "total_constraints": total_constraints,
            "hard_stop_rate": round(hard_stop_rate, 6),
            "coverage_score": round(coverage_score, 6),
            "pressure": round(gov_pressure, 6),
        }

        # ================================================================
        #  2. Cognition section
        # ================================================================
        success_rate = self._cognition_metrics.compute_session_success_rate(sessions)
        avg_response_time = self._cognition_metrics.compute_average_response_time(traces)

        # Quality score: composite of truthfulness, boundary compliance, and coverage
        truthfulness = self._cognition_metrics.compute_truthfulness_score(responses)
        boundary = self._cognition_metrics.compute_boundary_compliance_rate(checks)
        quality = 0.4 * truthfulness + 0.3 * boundary + 0.3 * coverage_score

        cognition_section = {
            "current_state": str(current_state),
            "session_count": len(sessions),
            "success_rate": round(success_rate, 6),
            "avg_response_time_ms": round(avg_response_time, 6),
            "quality_score": round(quality, 6),
        }

        # ================================================================
        #  3. Memory section
        # ================================================================
        avg_retrievals = self._cognition_metrics.compute_memory_retrieval_rate(memories)
        trace_visible = sum(
            1 for inf in influences if getattr(inf, "trace_visible", True)
        )
        trace_visible_rate = trace_visible / len(influences) if influences else 1.0

        memory_section = {
            "total_memories": len(memories),
            "avg_retrievals": round(avg_retrievals, 6),
            "influences_tracked": len(influences),
            "trace_visible_rate": round(trace_visible_rate, 6),
        }

        # ================================================================
        #  4. Traceability section
        # ================================================================
        total_checks_in_traces = sum(
            len(getattr(t, "governance_checks", [])) for t in traces
        )
        avg_checks = total_checks_in_traces / len(traces) if traces else 0.0

        traceability_section = {
            "total_traces": len(traces),
            "avg_governance_checks": round(avg_checks, 6),
            "violation_count": len(violations),
            "audit_event_count": len(audit_events),
        }

        # ================================================================
        #  5. Continuity section
        # ================================================================
        continuity_map = self._continuity_analyzer.generate_continuity_map(
            sessions, memories, traces
        )
        resilience = self._continuity_analyzer.compute_resilience_score(transitions)

        # Compute alignment drift
        drift_result = self._continuity_analyzer.compute_alignment_drift(checks)

        # Compute equilibrium stability from state durations
        state_durations: dict[str, float] = {}
        for t in transitions:
            state_name = str(t.to_state)
            # Use transitions as proxy for duration
            state_durations[state_name] = state_durations.get(state_name, 0) + 1.0

        equilibrium = self._continuity_analyzer.compute_equilibrium_stability(
            state_durations
        )

        continuity_section = {
            "continuity_score": continuity_map["overall_score"],
            "alignment_drift": drift_result["drift_score"],
            "resilience_score": round(resilience, 6),
            "equilibrium_stability": round(equilibrium, 6),
        }

        # ================================================================
        #  6. Pressure section
        # ================================================================
        adaptation_pressure = self._pressure_metrics.compute_adaptation_pressure(
            transitions
        )
        schema_pressure = self._pressure_metrics.compute_schema_pressure(
            violations, len(checks) if checks else 1
        )

        # Overall pressure: weighted average of all pressure types
        overall_pressure = (
            0.3 * adaptation_pressure +
            0.3 * enforcement_pressure +
            0.2 * conflict_pressure +
            0.2 * gov_pressure
        )

        pressure_section = {
            "adaptation_pressure": round(adaptation_pressure, 6),
            "enforcement_pressure": round(enforcement_pressure, 6),
            "conflict_pressure": round(conflict_pressure, 6),
            "overall_pressure": round(min(overall_pressure, 1.0), 6),
        }

        # ================================================================
        #  7. Trends section
        # ================================================================
        gov_trend = self._trend_analyzer.analyze_governance_trend(checks)
        stability_trend = self._trend_analyzer.analyze_state_stability(transitions)
        quality_trend = self._trend_analyzer.analyze_quality_trend(traces)
        degradation_trend = self._trend_analyzer.analyze_degradation_trend(transitions)

        trends_section = {
            "governance_trend": gov_trend,
            "state_stability_trend": stability_trend,
            "quality_trend": quality_trend,
            "degradation_trend": degradation_trend,
        }

        # ================================================================
        #  8. Ecosystem section
        # ================================================================
        eco_data = {
            "checks": checks,
            "violations": violations,
            "memories": memories,
            "influences": influences,
            "traces": traces,
        }
        ecosystem_graph = self._ecosystem_mapper.compute_cognition_ecosystem_graph(eco_data)
        alignment_ecology = self._ecosystem_mapper.compute_alignment_ecology(
            sessions, checks
        )

        ecosystem_section = {
            "governance_nodes": ecosystem_graph["stats"]["governance_nodes"],
            "memory_nodes": ecosystem_graph["stats"]["memory_nodes"],
            "reasoning_nodes": ecosystem_graph["stats"]["reasoning_nodes"],
            "total_edges": ecosystem_graph["stats"]["total_edges"],
            "alignment_ecology": alignment_ecology,
        }

        # ================================================================
        #  Assemble final overview
        # ================================================================
        return {
            "governance": governance_section,
            "cognition": cognition_section,
            "memory": memory_section,
            "traceability": traceability_section,
            "continuity": continuity_section,
            "pressure": pressure_section,
            "trends": trends_section,
            "ecosystem": ecosystem_section,
        }
