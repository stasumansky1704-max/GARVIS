"""Long-term continuity analysis for GARVIS analytics engine.

Continuity analytics measure how well the cognition system maintains
coherence, alignment, and thematic consistency across sessions and time.

All analysis is PURELY OBSERVATIONAL -- it analyzes what happened across
time periods. It NEVER influences what happens.

All functions are pure -- same input always produces same output.
Empty input is handled gracefully (returns 0.0 or empty dicts, never crashes).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from models.cognition import OperationalState, StateTransition
from models.memory import EpisodicMemory, MemoryInfluence


# ============================================================================
#  ContinuityAnalyzer — Long-term continuity analysis
# ============================================================================


class ContinuityAnalyzer:
    """Analyzes cognitive continuity across sessions and time.

    Continuity measures how well the system maintains coherence,
    alignment persistence, and thematic consistency over extended
    periods of operation. Higher scores indicate more stable,
    predictable, and coherent cognition.

    All methods are pure functions returning normalized scores.
    """

    # ------------------------------------------------------------------
    #  Session continuity
    # ------------------------------------------------------------------

    def compute_session_continuity_score(
        self,
        sessions: list[Any],
    ) -> float:
        """Score for how well cognition maintains continuity across sessions.

        Measures continuity by analyzing:
        - Session completion rate (did sessions end normally?)
        - State consistency (did sessions follow expected state progressions?)
        - Average session duration consistency

        Returns a value in [0.0, 1.0] where:
        - 1.0 = perfect continuity (all sessions complete, consistent durations)
        - 0.0 = no continuity (all sessions failed, highly variable)
        Returns 0.0 for empty input.
        """
        if not sessions:
            return 0.0

        from models.cognition import OperationalState

        # Completion rate
        completed = 0
        durations: list[float] = []
        for session in sessions:
            final = getattr(session, "final_state", None)
            if isinstance(final, str):
                try:
                    final = OperationalState(final)
                except (ValueError, KeyError):
                    final = None
            if final and final not in (
                OperationalState.FAIL_CLOSED,
                OperationalState.UNINITIALIZED,
            ):
                completed += 1

            # Session duration if available
            start = getattr(session, "start_time", None)
            end = getattr(session, "end_time", None)
            if start and end:
                delta = (end - start).total_seconds()
                durations.append(delta)

        completion_rate = completed / len(sessions)

        # Duration consistency: coefficient of variation
        duration_score = 1.0
        if len(durations) >= 2:
            mean_d = sum(durations) / len(durations)
            if mean_d > 0:
                variance = sum((d - mean_d) ** 2 for d in durations) / len(durations)
                std_dev = variance ** 0.5
                cv = std_dev / mean_d  # coefficient of variation
                # CV > 1.0 is highly variable, CV < 0.2 is very consistent
                duration_score = max(0.0, 1.0 - cv)

        # Weighted: 60% completion, 40% duration consistency
        return round(0.6 * completion_rate + 0.4 * duration_score, 6)

    # ------------------------------------------------------------------
    #  Governance persistence
    # ------------------------------------------------------------------

    def compute_governance_persistence(
        self,
        schemas_active: list[list[str]],
    ) -> float:
        """How consistently governance schemas remain active.

        Measures the stability of active governance schemas over time.
        High persistence means the same set of schemas stays active,
        indicating stable governance. Low persistence means schemas
        are frequently activated/deactivated.

        Args:
            schemas_active: A list where each element is a list of active
                schema IDs at a point in time (e.g., per session or per window).

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not schemas_active:
            return 0.0

        if len(schemas_active) == 1:
            return 1.0  # Only one observation = perfect persistence by default

        # Compute Jaccard similarity between consecutive schema sets
        similarities: list[float] = []
        for i in range(1, len(schemas_active)):
            prev = set(schemas_active[i - 1])
            curr = set(schemas_active[i])
            if not prev and not curr:
                similarities.append(1.0)
            elif not prev or not curr:
                similarities.append(0.0)
            else:
                intersection = len(prev & curr)
                union = len(prev | curr)
                similarities.append(intersection / union if union > 0 else 0.0)

        return round(sum(similarities) / len(similarities), 6)

    # ------------------------------------------------------------------
    #  Alignment drift
    # ------------------------------------------------------------------

    def compute_alignment_drift(
        self,
        checks_over_time: list[Any],
    ) -> dict[str, Any]:
        """Detects gradual alignment drift over time.

        Analyzes governance check results over time to detect if the
        system is gradually drifting out of alignment. Computes:
        - drift_score: overall drift magnitude in [0.0, 1.0]
        - trend_direction: "improving", "degrading", or "stable"
        - per_period_rates: list of pass rates per period

        Args:
            checks_over_time: List of (timestamp, GovernanceCheckResult) tuples
                or list of GovernanceCheckResult objects with timestamps.

        Returns a dict with drift analysis results.
        """
        if not checks_over_time:
            return {
                "drift_score": 0.0,
                "trend_direction": "stable",
                "per_period_rates": [],
            }

        # Normalize to (timestamp, passed) pairs
        pairs: list[tuple[datetime, bool]] = []
        for item in checks_over_time:
            if isinstance(item, tuple) and len(item) == 2:
                ts, check = item
                passed = check.passed if hasattr(check, "passed") else bool(check)
            else:
                ts = getattr(item, "timestamp", None)
                passed = getattr(item, "passed", False)
            if ts is not None:
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        continue
                if ts.tzinfo is not None:
                    ts = ts.replace(tzinfo=None)
                pairs.append((ts, passed))

        if not pairs:
            return {
                "drift_score": 0.0,
                "trend_direction": "stable",
                "per_period_rates": [],
            }

        # Sort by timestamp
        pairs.sort(key=lambda x: x[0])

        # Split into periods (use 3+ periods if enough data)
        n_periods = min(max(len(pairs) // 10, 2), 6)
        period_size = len(pairs) // n_periods if n_periods > 0 else len(pairs)

        if period_size == 0:
            period_size = len(pairs)
            n_periods = 1

        period_rates: list[float] = []
        for i in range(n_periods):
            start = i * period_size
            end = start + period_size if i < n_periods - 1 else len(pairs)
            period_pairs = pairs[start:end]
            if period_pairs:
                passed_count = sum(1 for _, p in period_pairs if p)
                rate = passed_count / len(period_pairs)
                period_rates.append(rate)

        if len(period_rates) < 2:
            return {
                "drift_score": 0.0,
                "trend_direction": "stable",
                "per_period_rates": [round(r, 6) for r in period_rates],
            }

        # Compute drift as the absolute difference between first and last period
        first_rate = period_rates[0]
        last_rate = period_rates[-1]
        drift = abs(last_rate - first_rate)

        # Also compute overall trend using linear regression on period rates
        n = len(period_rates)
        x_mean = (n - 1) / 2.0
        y_mean = sum(period_rates) / n
        numerator = sum((i - x_mean) * (period_rates[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0.0

        if slope > 0.05:
            direction = "improving"
        elif slope < -0.05:
            direction = "degrading"
        else:
            direction = "stable"

        # Drift score combines magnitude and trend
        drift_score = min(drift + abs(slope), 1.0)

        return {
            "drift_score": round(drift_score, 6),
            "trend_direction": direction,
            "slope": round(slope, 6),
            "per_period_rates": [round(r, 6) for r in period_rates],
        }

    # ------------------------------------------------------------------
    #  Memory continuity
    # ------------------------------------------------------------------

    def compute_memory_continuity(
        self,
        memories: list[EpisodicMemory],
    ) -> float:
        """How well memory influences persist and connect across sessions.

        Measures memory continuity by analyzing:
        - Retrieval persistence (are memories being re-accessed?)
        - Cross-session memory sharing (do sessions reference similar schemas?)
        - Memory chain depth (parent-child relationships)

        Args:
            memories: All episodic memories.

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not memories:
            return 0.0

        # Retrieval persistence: fraction of memories accessed more than once
        accessed_multiple = sum(1 for m in memories if m.retrieval_count > 1)
        persistence = accessed_multiple / len(memories) if memories else 0.0

        # Schema cross-referencing: how many unique schemas are shared
        all_schemas: set[str] = set()
        for m in memories:
            all_schemas.update(m.governance_influences)
        # Having multiple schemas referenced indicates richer memory ecosystem
        schema_diversity = min(len(all_schemas) / 5.0, 1.0)

        # Parent-child chain depth
        parent_ids = set()
        for m in memories:
            if m.provenance.parent_memory_id is not None:
                parent_ids.add(str(m.provenance.parent_memory_id))
        chain_ratio = len(parent_ids) / len(memories) if memories else 0.0

        # Weighted: 40% persistence, 30% diversity, 30% chaining
        return round(0.4 * persistence + 0.3 * schema_diversity + 0.3 * chain_ratio, 6)

    # ------------------------------------------------------------------
    #  Reasoning continuity
    # ------------------------------------------------------------------

    def compute_reasoning_continuity(
        self,
        traces: list[Any],
    ) -> float:
        """How well reasoning maintains thematic consistency.

        Analyzes cognition traces to measure whether reasoning follows
        consistent patterns. Looks at:
        - Governance check consistency (same schemas checked)
        - State sequence coherence (expected progressions)
        - Event type diversity (not too chaotic)

        Args:
            traces: All cognition traces.

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not traces:
            return 0.0

        # Schema consistency: Jaccard similarity of checked schemas across traces
        schema_sets: list[set[str]] = []
        for trace in traces:
            checks = getattr(trace, "governance_checks", [])
            schemas = set(c.schema_id for c in checks)
            if schemas:
                schema_sets.append(schemas)

        schema_consistency = 1.0
        if len(schema_sets) >= 2:
            similarities: list[float] = []
            for i in range(1, len(schema_sets)):
                prev = schema_sets[i - 1]
                curr = schema_sets[i]
                intersection = len(prev & curr)
                union = len(prev | curr)
                similarities.append(intersection / union if union > 0 else 0.0)
            schema_consistency = sum(similarities) / len(similarities) if similarities else 1.0

        # State sequence coherence: check for expected patterns
        expected_progressions: set[tuple[str, str]] = {
            ("uninitialized", "initializing"),
            ("initializing", "standby"),
            ("standby", "cognition_active"),
            ("standby", "governance_check"),
            ("governance_check", "cognition_active"),
            ("cognition_active", "inference_executing"),
            ("cognition_active", "memory_retrieving"),
            ("inference_executing", "trace_logging"),
            ("trace_logging", "auditing"),
            ("degraded", "recovering"),
            ("recovering", "standby"),
        }

        coherent_transitions = 0
        total_transitions = 0
        for trace in traces:
            states = getattr(trace, "state_sequence", [])
            for j in range(1, len(states)):
                prev = str(states[j - 1].from_state).lower()
                curr = str(states[j].to_state).lower()
                total_transitions += 1
                if (prev, curr) in expected_progressions:
                    coherent_transitions += 1

        coherence = coherent_transitions / total_transitions if total_transitions > 0 else 0.5

        # Weighted: 50% schema, 50% coherence
        return round(0.5 * schema_consistency + 0.5 * coherence, 6)

    # ------------------------------------------------------------------
    #  Full continuity map
    # ------------------------------------------------------------------

    def generate_continuity_map(
        self,
        sessions: list[Any],
        memories: list[EpisodicMemory],
        traces: list[Any],
    ) -> dict[str, Any]:
        """Generates a full continuity map showing connections across all dimensions.

        Computes continuity scores across all dimensions and produces
        a comprehensive map for the operator console.

        Returns a dict with:
        - session_continuity: float
        - memory_continuity: float
        - reasoning_continuity: float
        - governance_persistence: float (requires sessions with schema lists)
        - overall_score: float (average of all dimensions)
        - dimensions: dict with per-dimension scores and descriptions
        """
        session_score = self.compute_session_continuity_score(sessions)
        memory_score = self.compute_memory_continuity(memories)
        reasoning_score = self.compute_reasoning_continuity(traces)

        # Extract schema activation history from sessions if available
        schemas_active: list[list[str]] = []
        for session in sessions:
            schemas = getattr(session, "governance_context", None)
            if schemas and isinstance(schemas, list):
                schemas_active.append([str(s) for s in schemas])

        gov_persistence = (
            self.compute_governance_persistence(schemas_active)
            if schemas_active else 0.5
        )

        overall = (session_score + memory_score + reasoning_score + gov_persistence) / 4.0

        return {
            "session_continuity": round(session_score, 6),
            "memory_continuity": round(memory_score, 6),
            "reasoning_continuity": round(reasoning_score, 6),
            "governance_persistence": round(gov_persistence, 6),
            "overall_score": round(overall, 6),
            "dimensions": {
                "session": {
                    "score": round(session_score, 6),
                    "description": (
                        "How well sessions maintain completion and "
                        "duration consistency across runs"
                    ),
                },
                "memory": {
                    "score": round(memory_score, 6),
                    "description": (
                        "How well memory retrievals persist and connect "
                        "across sessions"
                    ),
                },
                "reasoning": {
                    "score": round(reasoning_score, 6),
                    "description": (
                        "How well reasoning maintains thematic and "
                        "schema consistency"
                    ),
                },
                "governance": {
                    "score": round(gov_persistence, 6),
                    "description": (
                        "How consistently governance schemas remain "
                        "active over time"
                    ),
                },
            },
        }

    # ------------------------------------------------------------------
    #  Resilience score
    # ------------------------------------------------------------------

    def compute_resilience_score(
        self,
        transitions: list[StateTransition],
    ) -> float:
        """Measures system resilience: recovery speed after degradation.

        Analyzes state transitions to measure how quickly the system
        recovers after entering a degraded state. Higher scores mean
        faster recovery.

        Args:
            transitions: All state transition records.

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not transitions:
            return 0.0

        # Find degradation-recovery pairs
        recovery_steps: list[int] = []
        last_degraded_idx: int | None = None

        for i, t in enumerate(transitions):
            to_name = str(t.to_state).lower()
            if to_name in {"degraded", "fail_closed"}:
                last_degraded_idx = i
            elif to_name == "recovering" and last_degraded_idx is not None:
                steps = i - last_degraded_idx
                recovery_steps.append(steps)
                last_degraded_idx = None

        if not recovery_steps:
            # No degradations = perfect resilience
            has_degraded = any(
                str(t.to_state).lower() in {"degraded", "fail_closed"}
                for t in transitions
            )
            return 1.0 if not has_degraded else 0.3

        avg_steps = sum(recovery_steps) / len(recovery_steps)
        # Fewer steps = faster recovery = higher score
        # 1 step = perfect, 5+ steps = poor
        resilience = max(0.0, 1.0 - (avg_steps - 1.0) / 4.0)
        return round(resilience, 6)

    # ------------------------------------------------------------------
    #  Equilibrium stability
    # ------------------------------------------------------------------

    def compute_equilibrium_stability(
        self,
        state_durations: dict[str, float],
    ) -> float:
        """How stable the system stays in productive states.

        Measures the proportion of time spent in productive states
        (cognition_active, inference_executing, standby) versus
        non-productive states (degraded, fail_closed, recovering).

        Args:
            state_durations: Mapping of state name -> total duration (seconds).

        Returns a value in [0.0, 1.0]. Returns 0.0 for empty input.
        """
        if not state_durations:
            return 0.0

        productive_states = {
            "cognition_active", "inference_executing", "standby",
            "governance_check", "memory_retrieving", "trace_logging", "auditing",
        }
        non_productive_states = {"degraded", "fail_closed", "recovering"}

        total_time = sum(state_durations.values())
        if total_time <= 0:
            return 0.0

        productive_time = sum(
            duration for state, duration in state_durations.items()
            if state.lower() in productive_states
        )
        non_productive_time = sum(
            duration for state, duration in state_durations.items()
            if state.lower() in non_productive_states
        )

        # Base: productive ratio
        productive_ratio = productive_time / total_time

        # Penalty for non-productive time
        non_productive_penalty = non_productive_time / total_time

        stability = max(0.0, productive_ratio - 0.3 * non_productive_penalty)
        return round(min(stability, 1.0), 6)
