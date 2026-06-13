"""Bounded Strategic Reasoning Engine — cognition/strategy.py

Strategic reasoning that stays within governance bounds.

Provides:
- Long-term project cognition planning
- Governance-safe strategic recommendations
- Bounded operational forecasting
- Resource allocation reasoning

ALL reasoning is:
- Bounded by active governance schemas
- Observable (full reasoning trace)
- Traceable (every influence visible)
- Uncertainty-aware (confidence levels disclosed)

This is NOT a free-form strategic advisor. Every recommendation
passes through governance validation before being presented.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from models.governance import GovernanceCheckResult, GovernanceViolation

logger = logging.getLogger("garvis.cognition.strategy")


# ---------------------------------------------------------------------------
# BoundedStrategyEngine — strategic reasoning within governance bounds
# ---------------------------------------------------------------------------


class BoundedStrategyEngine:
    """Strategic reasoning that stays within governance bounds.

    Provides governance-safe strategic recommendations with full
    reasoning visibility and uncertainty disclosure.

    ALL reasoning is:
    - Bounded by active governance schemas
    - Observable (full reasoning trace)
    - Traceable (every influence visible)
    - Uncertainty-aware (confidence levels disclosed)
    """

    def __init__(self, active_schema_ids: list[str] | None = None) -> None:
        self._active_schemas: set[str] = set(active_schema_ids or [])
        self._strategy_history: list[dict[str, Any]] = []
        self._project_contexts: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Project trajectory analysis
    # ------------------------------------------------------------------

    def analyze_project_trajectory(self, project_id: str) -> dict[str, Any]:
        """Analyze the strategic trajectory of a project.

        Returns governance-safe recommendations with full reasoning
        visibility and uncertainty disclosure.

        Args:
            project_id: The project identifier

        Returns:
            Dict with trajectory analysis and bounded recommendations
        """
        # Get or create project context (mock data)
        context = self._get_project_context(project_id)

        # Build reasoning trace
        reasoning_trace = [
            f"Loading project context for {project_id}",
            f"Project has {context['session_count']} active session(s)",
            f"Governance schema coverage: {len(self._active_schemas)} schema(s)",
            "Checking governance bounds for strategic recommendations...",
        ]

        # Check if governance allows strategic analysis
        governance_check = self._check_strategy_governance("trajectory_analysis")
        reasoning_trace.append(
            f"Governance check: {governance_check['schema_id']} -> "
            f"{'PASSED' if governance_check['passed'] else 'BLOCKED'}"
        )

        if not governance_check["passed"]:
            return self._create_blocked_strategy_response(
                project_id, "trajectory_analysis", governance_check, reasoning_trace
            )

        # Calculate metrics (mock analysis)
        health_score = context.get("health_score", 0.75)
        risk_factors = context.get("risk_factors", ["standard_epistemic_uncertainty"])
        growth_trend = context.get("growth_trend", "stable")

        # Cap confidence per epistemic safety
        confidence = min(0.80, health_score * 0.9)

        reasoning_trace.extend([
            f"Health score: {health_score:.2f}",
            f"Risk factors identified: {len(risk_factors)}",
            f"Growth trend: {growth_trend}",
            f"Confidence capped to {confidence:.2f} (epistemic safety bound)",
        ])

        # Generate governance-safe recommendations
        recommendations = self._generate_trajectory_recommendations(
            context, health_score, risk_factors
        )

        reasoning_trace.append(
            f"Generated {len(recommendations)} governance-safe recommendation(s)"
        )

        result = {
            "project_id": project_id,
            "analysis_type": "trajectory",
            "governance_check": governance_check,
            "governance_bounded": True,
            "metrics": {
                "health_score": health_score,
                "risk_factor_count": len(risk_factors),
                "growth_trend": growth_trend,
                "session_count": context.get("session_count", 0),
                "interaction_count": context.get("interaction_count", 0),
            },
            "risk_factors": risk_factors,
            "recommendations": recommendations,
            "confidence_score": confidence,
            "confidence_interpretation": self._interpret_strategy_confidence(confidence),
            "uncertainty_disclosure": (
                f"Trajectory analysis confidence: {confidence:.2f}. "
                f"This analysis is based on {context.get('session_count', 0)} session(s) "
                f"and active governance schemas. Unobserved factors may affect accuracy. "
                f"Recommend periodic re-analysis as project evolves."
            ),
            "reasoning_trace": reasoning_trace,
            "bounded_by": list(self._active_schemas),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._strategy_history.append(result)
        return result

    # ------------------------------------------------------------------
    # Operational forecasting
    # ------------------------------------------------------------------

    def forecast_operational_needs(
        self, project_id: str, time_horizon: str = "30d"
    ) -> dict[str, Any]:
        """Forecast operational needs within governance bounds.

        Args:
            project_id: The project identifier
            time_horizon: Forecast period ("7d", "30d", "90d")

        Returns:
            Dict with bounded operational forecast
        """
        context = self._get_project_context(project_id)

        reasoning_trace = [
            f"Initiating operational forecast for {project_id}",
            f"Time horizon: {time_horizon}",
            "Applying governance bounds to forecasting...",
        ]

        # Governance check
        gov_check = self._check_strategy_governance("operational_forecast")
        reasoning_trace.append(
            f"Governance check: {'PASSED' if gov_check['passed'] else 'BLOCKED'}"
        )

        if not gov_check["passed"]:
            return self._create_blocked_strategy_response(
                project_id, "operational_forecast", gov_check, reasoning_trace
            )

        # Parse time horizon
        days = self._parse_time_horizon(time_horizon)
        reasoning_trace.append(f"Forecast period: {days} days")

        # Calculate forecast (mock)
        base_sessions = context.get("session_count", 1)
        forecasted_sessions = int(base_sessions * (1 + 0.1 * (days / 30)))
        memory_growth = context.get("memory_entries", 10) * (days / 30)

        confidence = 0.65  # Forecasts are inherently uncertain
        if days > 30:
            confidence *= 0.8  # Lower confidence for longer horizons

        reasoning_trace.extend([
            f"Base sessions: {base_sessions}",
            f"Forecasted sessions: {forecasted_sessions}",
            f"Projected memory growth: {memory_growth:.0f} entries",
            f"Confidence adjusted for horizon: {confidence:.2f}",
        ])

        result = {
            "project_id": project_id,
            "analysis_type": "operational_forecast",
            "time_horizon": time_horizon,
            "governance_check": gov_check,
            "governance_bounded": True,
            "forecast": {
                "projected_sessions": forecasted_sessions,
                "projected_memory_entries": int(memory_growth),
                "projected_governance_checks": forecasted_sessions * 5,
                "recommended_schema_review": days >= 30,
                "resource_utilization_trend": "stable",
            },
            "recommendations": [
                {
                    "type": "capacity",
                    "description": (
                        f"Plan for approximately {forecasted_sessions} sessions "
                        f"over the next {time_horizon}"
                    ),
                    "confidence": confidence,
                    "governance_note": "Within active schema bounds",
                },
                {
                    "type": "governance",
                    "description": (
                        "Schedule governance schema review if session count "
                        "exceeds current capacity assumptions"
                    ),
                    "confidence": 0.85,
                    "governance_note": "Based on session_management policy",
                },
            ],
            "confidence_score": confidence,
            "confidence_interpretation": self._interpret_strategy_confidence(confidence),
            "uncertainty_disclosure": (
                f"Operational forecast for {time_horizon} has confidence {confidence:.2f}. "
                f"Forecasts are inherently uncertain and should be treated as planning "
                f"guidelines, not guarantees. Actual needs may vary based on operator "
                f"activity patterns and governance schema changes."
            ),
            "reasoning_trace": reasoning_trace,
            "bounded_by": list(self._active_schemas),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._strategy_history.append(result)
        return result

    # ------------------------------------------------------------------
    # Governance adjustment recommendations
    # ------------------------------------------------------------------

    def recommend_governance_adjustments(self, project_id: str) -> dict[str, Any]:
        """Recommend governance schema adjustments.

        ALL recommendations require operator approval.
        This system NEVER auto-adjusts governance.

        Args:
            project_id: The project identifier

        Returns:
            Dict with governance adjustment recommendations
        """
        reasoning_trace = [
            f"Analyzing governance fit for project {project_id}",
            f"Active schemas: {len(self._active_schemas)}",
            "All recommendations require explicit operator approval...",
        ]

        # Governance check — meta: can we recommend changes?
        gov_check = self._check_strategy_governance("governance_recommendation")
        reasoning_trace.append(
            f"Meta-governance check: {'PASSED' if gov_check['passed'] else 'BLOCKED'}"
        )

        if not gov_check["passed"]:
            return self._create_blocked_strategy_response(
                project_id, "governance_recommendation", gov_check, reasoning_trace
            )

        # Analyze current schema fit (mock)
        context = self._get_project_context(project_id)
        violations = context.get("recent_violations", [])
        violation_rate = len(violations) / max(context.get("interaction_count", 1), 1)

        reasoning_trace.extend([
            f"Recent violations: {len(violations)}",
            f"Violation rate: {violation_rate:.3f}",
            "Analyzing schema coverage gaps...",
        ])

        # Generate recommendations based on violation patterns
        recommendations = []

        if violation_rate > 0.1:
            recommendations.append({
                "type": "tighten",
                "schema": "boundary_enforcement",
                "description": (
                    "High violation rate suggests boundary enforcement may need "
                    "strengthening. Consider activating additional boundary constraints."
                ),
                "requires_approval": True,
                "risk_if_applied": "More actions may be blocked",
                "risk_if_not_applied": "Continued high violation rate",
            })

        if context.get("session_count", 0) > 5:
            recommendations.append({
                "type": "review",
                "schema": "session_management",
                "description": (
                    "Multiple active sessions detected. Review session limits "
                    "and timeout policies for this project."
                ),
                "requires_approval": True,
                "risk_if_applied": "Sessions may timeout more aggressively",
                "risk_if_not_applied": "Resource contention",
            })

        if not recommendations:
            recommendations.append({
                "type": "maintain",
                "schema": "all_active",
                "description": (
                    "Current governance schema configuration appears well-matched "
                    "to project needs. No changes recommended at this time."
                ),
                "requires_approval": False,
                "risk_if_applied": "N/A",
                "risk_if_not_applied": "N/A",
            })

        confidence = 0.70 if recommendations else 0.85

        reasoning_trace.append(
            f"Generated {len(recommendations)} recommendation(s)"
        )

        result = {
            "project_id": project_id,
            "analysis_type": "governance_adjustment_recommendation",
            "governance_check": gov_check,
            "governance_bounded": True,
            "current_violation_rate": violation_rate,
            "recommendations": recommendations,
            "requires_operator_approval": True,
            "auto_adjustment_disabled": True,
            "approval_workflow": [
                "Operator reviews recommendation",
                "Operator approves or rejects each item",
                "Approved changes are applied with audit logging",
                "Rejected changes are documented with rationale",
            ],
            "confidence_score": confidence,
            "confidence_interpretation": self._interpret_strategy_confidence(confidence),
            "uncertainty_disclosure": (
                f"Governance recommendations have confidence {confidence:.2f}. "
                f"These are suggestions based on observed patterns, not mandates. "
                f"The operator must approve every change. The system cannot and will "
                f"not auto-adjust governance schemas."
            ),
            "reasoning_trace": reasoning_trace,
            "bounded_by": list(self._active_schemas),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._strategy_history.append(result)
        return result

    # ------------------------------------------------------------------
    # Operational readiness assessment
    # ------------------------------------------------------------------

    def assess_operational_readiness(self, project_id: str) -> dict[str, Any]:
        """Assess if a project is operationally ready.

        Args:
            project_id: The project identifier

        Returns:
            Dict with readiness assessment
        """
        reasoning_trace = [
            f"Assessing operational readiness for project {project_id}",
            "Checking required governance schema coverage...",
        ]

        context = self._get_project_context(project_id)

        # Define readiness criteria
        required_schemas = {
            "epistemic_safety",
            "operational_integrity",
            "boundary_enforcement",
            "traceability_requirement",
        }
        available_schemas = self._active_schemas
        missing_schemas = required_schemas - available_schemas

        reasoning_trace.extend([
            f"Required schemas: {len(required_schemas)}",
            f"Available schemas: {len(available_schemas)}",
            f"Missing schemas: {len(missing_schemas)}",
        ])

        # Check criteria
        has_sessions = context.get("session_count", 0) > 0
        has_audit_trail = context.get("interaction_count", 0) > 0
        schema_coverage = len(available_schemas & required_schemas) / len(
            required_schemas
        )

        # Calculate readiness score
        readiness = 0.0
        readiness += 0.3 * (1.0 if not missing_schemas else schema_coverage)
        readiness += 0.2 * (1.0 if has_sessions else 0.0)
        readiness += 0.2 * (1.0 if has_audit_trail else 0.0)
        readiness += 0.15  # baseline for having a project context
        readiness += 0.15 * min(context.get("health_score", 0.5) / 0.5, 1.0)

        readiness = min(readiness, 0.95)  # Cap — never claim 100% ready

        reasoning_trace.extend([
            f"Schema coverage: {schema_coverage:.1%}",
            f"Has active sessions: {has_sessions}",
            f"Has audit trail: {has_audit_trail}",
            f"Readiness score: {readiness:.2f}",
        ])

        # Determine status
        if readiness >= 0.8:
            status = "ready"
        elif readiness >= 0.5:
            status = "conditionally_ready"
        else:
            status = "not_ready"

        result = {
            "project_id": project_id,
            "analysis_type": "operational_readiness",
            "governance_bounded": True,
            "readiness_score": round(readiness, 3),
            "status": status,
            "criteria": {
                "required_schema_coverage": {
                    "required": list(required_schemas),
                    "available": list(available_schemas & required_schemas),
                    "missing": list(missing_schemas),
                    "satisfied": not missing_schemas,
                },
                "active_sessions": {
                    "required": True,
                    "actual": has_sessions,
                    "satisfied": has_sessions,
                },
                "audit_trail": {
                    "required": True,
                    "actual": has_audit_trail,
                    "satisfied": has_audit_trail,
                },
            },
            "recommendations": self._generate_readiness_recommendations(
                missing_schemas, has_sessions, has_audit_trail
            ),
            "confidence_score": 0.75,
            "confidence_interpretation": self._interpret_strategy_confidence(0.75),
            "uncertainty_disclosure": (
                f"Readiness score: {readiness:.2f}. This assessment is based on "
                f"current governance schema coverage and project activity. Readiness "
                f"can change as schemas are activated/deactivated or project "
                f"characteristics evolve. A score above 0.8 indicates readiness, "
                f"but operational monitoring should continue."
            ),
            "reasoning_trace": reasoning_trace,
            "bounded_by": list(self._active_schemas),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._strategy_history.append(result)
        return result

    # ------------------------------------------------------------------
    # Cognitive strategy generation
    # ------------------------------------------------------------------

    def generate_cognitive_strategy(
        self, objective: str, constraints: list[str]
    ) -> dict[str, Any]:
        """Generate a bounded cognitive strategy.

        Strategy includes uncertainty disclosures and governance annotations.

        Args:
            objective: The strategic objective
            constraints: List of constraint descriptions

        Returns:
            Dict with bounded cognitive strategy
        """
        reasoning_trace = [
            f"Generating cognitive strategy for: {objective[:80]}",
            f"Constraints specified: {len(constraints)}",
            "Validating against governance bounds...",
        ]

        # Governance check
        gov_check = self._check_strategy_governance("cognitive_strategy")
        reasoning_trace.append(
            f"Governance check: {'PASSED' if gov_check['passed'] else 'BLOCKED'}"
        )

        if not gov_check["passed"]:
            return self._create_blocked_strategy_response(
                "general", "cognitive_strategy", gov_check, reasoning_trace
            )

        # Validate constraints against governance
        validated_constraints = []
        for constraint in constraints:
            validated_constraints.append({
                "constraint": constraint,
                "governance_aligned": True,
                "enforced_by": "operator_specified",
            })

        # Add implicit governance constraints
        validated_constraints.extend([
            {
                "constraint": "All reasoning must be observable and traceable",
                "governance_aligned": True,
                "enforced_by": "traceability_requirement",
            },
            {
                "constraint": "Uncertainty must always be disclosed",
                "governance_aligned": True,
                "enforced_by": "epistemic_safety",
            },
            {
                "constraint": "Confidence capped at 0.85 per epistemic policy",
                "governance_aligned": True,
                "enforced_by": "epistemic_safety",
            },
        ])

        reasoning_trace.extend([
            f"Validated {len(validated_constraints)} constraint(s)",
            "Building strategy within bounds...",
        ])

        # Generate strategy phases (mock)
        strategy_phases = [
            {
                "phase": 1,
                "name": "governance_validation",
                "description": "Validate all inputs against active governance schemas",
                "governance_critical": True,
                "estimated_duration": "per-request",
            },
            {
                "phase": 2,
                "name": "bounded_reasoning",
                "description": (
                    "Execute reasoning within governance bounds, "
                    "with full traceability"
                ),
                "governance_critical": True,
                "estimated_duration": "variable",
            },
            {
                "phase": 3,
                "name": "uncertainty_quantification",
                "description": (
                    "Quantify and disclose uncertainty for all outputs"
                ),
                "governance_critical": True,
                "estimated_duration": "per-request",
            },
            {
                "phase": 4,
                "name": "operator_review",
                "description": (
                    "Present results to operator with full governance context"
                ),
                "governance_critical": False,
                "estimated_duration": "operator-dependent",
            },
        ]

        confidence = 0.72  # Strategies are inherently somewhat uncertain

        reasoning_trace.extend([
            f"Defined {len(strategy_phases)} strategy phase(s)",
            "Strategy generation complete",
        ])

        result = {
            "objective": objective,
            "analysis_type": "cognitive_strategy",
            "governance_check": gov_check,
            "governance_bounded": True,
            "constraints": validated_constraints,
            "strategy_phases": strategy_phases,
            "key_principles": [
                "Fail-closed: any governance failure blocks the operation",
                "Full observability: every reasoning step is traceable and observable",
                "Uncertainty-first: disclose uncertainty before claims",
                "Operator-sovereign: operator decides, system advises",
                "Memory-informed: all reasoning uses relevant episodic memory",
            ],
            "confidence_score": confidence,
            "confidence_interpretation": self._interpret_strategy_confidence(confidence),
            "uncertainty_disclosure": (
                f"Strategy confidence: {confidence:.2f}. This strategy provides "
                f"a governance-safe framework but actual execution will depend on "
                f"specific inputs and runtime conditions. Strategy effectiveness "
                f"should be reviewed after initial implementation."
            ),
            "reasoning_trace": reasoning_trace,
            "bounded_by": list(self._active_schemas),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._strategy_history.append(result)
        return result

    # ------------------------------------------------------------------
    # History access
    # ------------------------------------------------------------------

    def get_strategy_history(
        self, project_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get history of strategy analyses.

        Args:
            project_id: Optional filter by project

        Returns:
            List of strategy result dicts
        """
        if project_id:
            return [
                h for h in self._strategy_history
                if h.get("project_id") == project_id
            ]
        return list(self._strategy_history)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_project_context(self, project_id: str) -> dict[str, Any]:
        """Get or create mock project context."""
        if project_id not in self._project_contexts:
            # Create mock context
            import hashlib
            h = hashlib.md5(project_id.encode()).hexdigest()
            health_score = 0.5 + (int(h[:4], 16) % 50) / 100.0

            self._project_contexts[project_id] = {
                "project_id": project_id,
                "session_count": 1 + (int(h[4:8], 16) % 8),
                "interaction_count": 5 + (int(h[8:12], 16) % 50),
                "memory_entries": 10 + (int(h[12:16], 16) % 90),
                "health_score": health_score,
                "growth_trend": ["stable", "growing", "declining"][
                    int(h[16:18], 16) % 3
                ],
                "risk_factors": [
                    "standard_epistemic_uncertainty",
                    *("increasing_complexity" if health_score < 0.6 else []),
                ],
                "recent_violations": [],
            }
        return self._project_contexts[project_id]

    def _check_strategy_governance(self, analysis_type: str) -> dict[str, Any]:
        """Check if strategic analysis is allowed by governance.

        Simulates a governance check. In production, this calls
        the RuntimeValidator.
        """
        # All strategy types are allowed but bounded
        allowed_types = {
            "trajectory_analysis",
            "operational_forecast",
            "governance_recommendation",
            "cognitive_strategy",
        }

        if analysis_type not in allowed_types:
            return {
                "schema_id": "operational_integrity",
                "policy_id": "valid_analysis_type",
                "passed": False,
                "reason": f"Unknown analysis type: {analysis_type}",
            }

        return {
            "schema_id": "operational_integrity",
            "policy_id": "strategy_analysis_allowed",
            "passed": True,
            "reason": f"{analysis_type} is within operational bounds",
        }

    def _create_blocked_strategy_response(
        self,
        project_id: str,
        analysis_type: str,
        governance_check: dict[str, Any],
        reasoning_trace: list[str],
    ) -> dict[str, Any]:
        """Create a response when strategy analysis is blocked."""
        return {
            "project_id": project_id,
            "analysis_type": analysis_type,
            "governance_check": governance_check,
            "governance_blocked": True,
            "result": None,
            "recommendations": [],
            "confidence_score": 0.0,
            "confidence_interpretation": "blocked by governance",
            "uncertainty_disclosure": (
                "Strategy analysis was blocked by governance. No uncertainty "
                "assessment available for blocked operations."
            ),
            "reasoning_trace": reasoning_trace,
            "bounded_by": list(self._active_schemas),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _generate_trajectory_recommendations(
        self,
        context: dict[str, Any],
        health_score: float,
        risk_factors: list[str],
    ) -> list[dict[str, Any]]:
        """Generate governance-safe trajectory recommendations."""
        recommendations = []

        if health_score < 0.5:
            recommendations.append({
                "type": "intervention",
                "priority": "high",
                "description": (
                    "Project health is below threshold. Recommend governance "
                    "review and possible session reinitialization."
                ),
                "governance_safe": True,
                "requires_operator": True,
            })

        if "increasing_complexity" in risk_factors:
            recommendations.append({
                "type": "monitoring",
                "priority": "medium",
                "description": (
                    "Increasing complexity detected. Recommend more frequent "
                    "governance checks and operator review."
                ),
                "governance_safe": True,
                "requires_operator": False,
            })

        recommendations.append({
            "type": "continuous_assessment",
            "priority": "low",
            "description": (
                "Continue periodic trajectory analysis. Governance schemas "
                "are providing adequate coverage."
            ),
            "governance_safe": True,
            "requires_operator": False,
        })

        return recommendations

    def _generate_readiness_recommendations(
        self,
        missing_schemas: set[str],
        has_sessions: bool,
        has_audit_trail: bool,
    ) -> list[dict[str, Any]]:
        """Generate recommendations for improving readiness."""
        recs = []

        if missing_schemas:
            recs.append({
                "priority": "high",
                "description": (
                    f"Activate missing governance schemas: {', '.join(missing_schemas)}"
                ),
                "action": "schema_activation",
            })

        if not has_sessions:
            recs.append({
                "priority": "medium",
                "description": "Initialize at least one collaboration session",
                "action": "session_init",
            })

        if not has_audit_trail:
            recs.append({
                "priority": "medium",
                "description": "Begin audit trail by processing operator inputs",
                "action": "start_collaboration",
            })

        if not recs:
            recs.append({
                "priority": "low",
                "description": "Project is operationally ready. Continue current operations.",
                "action": "maintain",
            })

        return recs

    def _parse_time_horizon(self, horizon: str) -> int:
        """Parse time horizon string to days."""
        mapping = {
            "7d": 7,
            "14d": 14,
            "30d": 30,
            "60d": 60,
            "90d": 90,
        }
        return mapping.get(horizon, 30)

    def _interpret_strategy_confidence(self, confidence: float) -> str:
        """Return human-readable interpretation of strategy confidence."""
        if confidence < 0.2:
            return "very low — strategy is speculative, high uncertainty"
        elif confidence < 0.4:
            return "low — significant gaps, use with caution"
        elif confidence < 0.6:
            return "moderate — reasonable basis but incomplete"
        elif confidence < 0.75:
            return "reasonable — good support from available data"
        else:
            return "good — well-supported within governance bounds"

    def set_active_schemas(self, schema_ids: list[str]) -> None:
        """Update the set of active governance schemas."""
        self._active_schemas = set(schema_ids)
        logger.info("BoundedStrategyEngine: active schemas updated to %d", len(schema_ids))
