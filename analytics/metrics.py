"""Core metrics computation for GARVIS analytics engine.

All metrics are PURELY OBSERVATIONAL. They analyze what happened.
They NEVER influence what happens. The operator uses these metrics
to understand system behavior, not to autonomously adjust it.

All metric functions return values between 0.0 and 1.0 where possible.
All functions are pure -- same input always produces same output.
Empty input is handled gracefully (returns 0.0 or empty lists, never crashes).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from models.governance import GovernanceCheckResult, GovernanceConstraint, GovernanceViolation
from models.memory import EpisodicMemory, MemoryInfluence


# ============================================================================
#  CognitionMetrics — Quality and governance metrics
# ============================================================================


class CognitionMetrics:
    """Computes cognition quality and governance metrics.

    Each method is a pure function: same input always produces same output.
    All return values are normalized to [0.0, 1.0] where applicable.
    """

    # ------------------------------------------------------------------
    #  Governance coverage
    # ------------------------------------------------------------------

    def compute_governance_coverage(
        self, checks: list[GovernanceCheckResult]
    ) -> float:
        """Percentage of governance checks that passed.

        Returns a value in [0.0, 1.0] where:
        - 1.0 = all checks passed (perfect coverage)
        - 0.0 = no checks passed (complete governance failure)
        - Returns 0.0 for empty input (no checks to evaluate)
        """
        if not checks:
            return 0.0
        passed = sum(1 for c in checks if c.passed)
        return passed / len(checks)

    # ------------------------------------------------------------------
    #  Uncertainty disclosure
    # ------------------------------------------------------------------

    def compute_uncertainty_disclosure_rate(
        self, responses: list[Any]
    ) -> float:
        """Percentage of responses that included uncertainty disclosure.

        Analyzes governed responses to determine how often uncertainty
        was disclosed to the user. Higher rates indicate better
        transparency about model confidence limits.

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not responses:
            return 0.0

        disclosed = 0
        for resp in responses:
            raw = getattr(resp, "raw_response", "")
            validated = getattr(resp, "validated_response", None)
            # Check for uncertainty indicators in either raw or validated response
            text = validated if validated else raw
            indicators = [
                "uncertain", "not sure", "i don't know", "cannot determine",
                "insufficient information", "insufficient", "low confidence",
                "ambiguous", "unclear", "inconclusive", "unverified",
                "i'm not certain", "limited information", "cannot confirm",
            ]
            text_lower = text.lower()
            if any(ind in text_lower for ind in indicators):
                disclosed += 1

        return disclosed / len(responses)

    # ------------------------------------------------------------------
    #  Truthfulness score
    # ------------------------------------------------------------------

    def compute_truthfulness_score(
        self, responses: list[Any]
    ) -> float:
        """Score based on truthfulness validation results.

        Measures how many responses passed governance validation.
        A truthfulness score of 1.0 means all responses were validated
        as truthful (passed all governance checks).

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not responses:
            return 0.0

        truthful = sum(
            1 for r in responses
            if getattr(r, "passed_validation", False)
        )
        return truthful / len(responses)

    # ------------------------------------------------------------------
    #  Boundary compliance
    # ------------------------------------------------------------------

    def compute_boundary_compliance_rate(
        self, checks: list[GovernanceCheckResult]
    ) -> float:
        """Percentage of operations that stayed within boundaries.

        Boundary compliance is the rate at which governance checks pass
        without triggering hard-stop violations. It differs from general
        governance coverage by focusing specifically on boundary
        enforcement (constraints vs. policies).

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not checks:
            return 0.0
        # Boundary compliance = checks that passed OR failed with non-critical violation
        compliant = 0
        for check in checks:
            if check.passed:
                compliant += 1
            elif check.violation and check.violation.severity != "critical":
                compliant += 1
        return compliant / len(checks)

    # ------------------------------------------------------------------
    #  Session success rate
    # ------------------------------------------------------------------

    def compute_session_success_rate(
        self, sessions: list[Any]
    ) -> float:
        """Percentage of sessions that completed without fail-closed.

        A session is considered successful if it did NOT end in a
        FAIL_CLOSED state. This metric indicates how often the system
        can operate within governance boundaries without hard stops.

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not sessions:
            return 0.0

        from models.cognition import OperationalState

        successful = 0
        for session in sessions:
            final = getattr(session, "final_state", None)
            if isinstance(final, str):
                final = OperationalState(final)
            if final is not None and final != OperationalState.FAIL_CLOSED:
                successful += 1
        return successful / len(sessions)

    # ------------------------------------------------------------------
    #  Average response time
    # ------------------------------------------------------------------

    def compute_average_response_time(
        self, traces: list[Any]
    ) -> float:
        """Average cognition cycle duration in milliseconds.

        Computes the mean duration from trace start to end time.
        A lower value indicates faster cognition cycles.

        Returns average duration in milliseconds.
        Returns 0.0 for empty input or traces without end times.
        """
        if not traces:
            return 0.0

        durations: list[float] = []
        for trace in traces:
            start = getattr(trace, "start_time", None)
            end = getattr(trace, "end_time", None)
            if start and end:
                delta = end - start
                durations.append(delta.total_seconds() * 1000.0)

        if not durations:
            return 0.0
        return sum(durations) / len(durations)

    # ------------------------------------------------------------------
    #  Memory retrieval rate
    # ------------------------------------------------------------------

    def compute_memory_retrieval_rate(
        self, memories: list[EpisodicMemory]
    ) -> float:
        """Average retrievals per memory.

        Measures how often stored memories are retrieved on average.
        Higher rates indicate active memory utilization.

        Returns average retrievals per memory as a float.
        Returns 0.0 for empty input.
        """
        if not memories:
            return 0.0
        total_retrievals = sum(m.retrieval_count for m in memories)
        return total_retrievals / len(memories)


# ============================================================================
#  GovernancePressureMetrics — Pressure indicator computation
# ============================================================================


class GovernancePressureMetrics:
    """Computes governance pressure indicators.

    Pressure metrics quantify how much stress the governance system is under.
    Higher pressure values suggest the system is operating near its
    governance boundaries and may need operator attention.

    All methods are pure functions returning normalized values where possible.
    """

    # ------------------------------------------------------------------
    #  Schema pressure
    # ------------------------------------------------------------------

    def compute_schema_pressure(
        self,
        violations: list[GovernanceViolation],
        total_checks: int,
    ) -> dict[str, Any]:
        """Pressure per schema: violation_rate and check_density.

        Groups violations by schema and computes per-schema metrics:
        - violation_rate: fraction of checks that resulted in violations
        - check_density: total checks normalized (placeholder for future)

        Args:
            violations: All recorded governance violations.
            total_checks: Total number of governance checks performed.

        Returns a dict mapping schema_id -> {"violation_rate": float, "check_density": float}
        """
        if not violations or total_checks <= 0:
            return {}

        # Group violations by schema
        by_schema: dict[str, int] = {}
        for v in violations:
            sid = v.schema_id
            by_schema[sid] = by_schema.get(sid, 0) + 1

        result: dict[str, Any] = {}
        for schema_id, vcount in by_schema.items():
            violation_rate = min(vcount / total_checks, 1.0)
            check_density = min(total_checks / max(len(by_schema), 1), 1.0)
            result[schema_id] = {
                "violation_rate": round(violation_rate, 6),
                "check_density": round(check_density, 6),
            }

        return result

    # ------------------------------------------------------------------
    #  Scope pressure
    # ------------------------------------------------------------------

    def compute_scope_pressure(
        self,
        checks_by_scope: dict[str, list[GovernanceCheckResult]],
    ) -> dict[str, float]:
        """Pressure per governance scope.

        Computes the pass rate for each governance scope (global, session,
        inference, memory). Lower pass rates indicate higher pressure
        in that scope.

        Args:
            checks_by_scope: Mapping of scope name -> list of check results.

        Returns a dict mapping scope -> pressure_score in [0.0, 1.0],
        where higher values mean more pressure (lower pass rate).
        """
        if not checks_by_scope:
            return {}

        result: dict[str, float] = {}
        for scope, checks in checks_by_scope.items():
            if not checks:
                result[scope] = 0.0
                continue
            passed = sum(1 for c in checks if c.passed)
            pass_rate = passed / len(checks)
            # Pressure = inverse of pass rate
            result[scope] = round(1.0 - pass_rate, 6)

        return result

    # ------------------------------------------------------------------
    #  Enforcement pressure
    # ------------------------------------------------------------------

    def compute_enforcement_pressure(
        self,
        constraints: list[GovernanceConstraint],
    ) -> float:
        """Overall enforcement pressure score in [0.0, 1.0].

        Measures how restrictive the governance environment is based on:
        - Ratio of hard_stop enforcement constraints
        - Total number of active constraints

        More hard_stop constraints = higher enforcement pressure.

        Args:
            constraints: All active governance constraints.

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not constraints:
            return 0.0

        hard_stop_count = sum(
            1 for c in constraints if c.enforcement == "hard_stop"
        )
        # Pressure scales with proportion of hard stops, capped at 1.0
        base_pressure = hard_stop_count / len(constraints)
        # Also factor in total constraint density (more constraints = more pressure)
        density_factor = min(len(constraints) / 20.0, 1.0)  # normalize to ~20 constraints

        # Weighted: 70% hard_stop ratio, 30% density
        pressure = 0.7 * base_pressure + 0.3 * density_factor
        return round(min(pressure, 1.0), 6)

    # ------------------------------------------------------------------
    #  Adaptation pressure
    # ------------------------------------------------------------------

    def compute_adaptation_pressure(
        self,
        state_transitions: list[Any],
    ) -> float:
        """Pressure from frequent state changes and recoveries.

        Measures how often the system is changing states or recovering
        from degraded states. Frequent transitions indicate the system
        is under stress and adapting frequently.

        Args:
            state_transitions: List of StateTransition records.

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not state_transitions:
            return 0.0

        from models.cognition import OperationalState

        total = len(state_transitions)
        # Count transitions involving degraded, recovering, or fail_closed states
        stress_transitions = 0
        for t in state_transitions:
            to_state = t.to_state
            if isinstance(to_state, str):
                to_state = OperationalState(to_state)
            from_state = t.from_state
            if isinstance(from_state, str):
                from_state = OperationalState(from_state)

            if to_state in (
                OperationalState.DEGRADED,
                OperationalState.RECOVERING,
                OperationalState.FAIL_CLOSED,
            ):
                stress_transitions += 1
            elif from_state in (
                OperationalState.DEGRADED,
                OperationalState.FAIL_CLOSED,
            ) and to_state not in (
                OperationalState.DEGRADED,
                OperationalState.FAIL_CLOSED,
            ):
                # Recovery transitions also indicate prior pressure
                stress_transitions += 0.5

        ratio = stress_transitions / total
        # Scale: up to ~20% stress transitions is "normal", beyond is high pressure
        return round(min(ratio * 5.0, 1.0), 6)

    # ------------------------------------------------------------------
    #  Conflict pressure
    # ------------------------------------------------------------------

    def compute_conflict_pressure(
        self,
        violations: list[GovernanceViolation],
    ) -> float:
        """Pressure from conflicting governance constraints.

        Detects when multiple schemas are generating violations, which
        may indicate conflicting constraints between schemas. Also
        factors in unresolved violations.

        Args:
            violations: All recorded governance violations.

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not violations:
            return 0.0

        # Count unique schemas with violations
        schema_ids = set(v.schema_id for v in violations)
        # Multiple schemas with violations suggests potential conflicts
        schema_diversity = min(len(schema_ids) / 5.0, 1.0)

        # Unresolved violations add pressure
        unresolved = sum(1 for v in violations if v.resolution is None)
        unresolved_rate = unresolved / len(violations)

        # Weighted: 60% schema diversity, 40% unresolved rate
        pressure = 0.6 * schema_diversity + 0.4 * unresolved_rate
        return round(min(pressure, 1.0), 6)
