"""Time-series trend computation for GARVIS analytics engine.

All trend analysis is PURELY OBSERVATIONAL. It analyzes what happened over time.
It NEVER influences what happens. Trends are computed using configurable time
windows (default 60 minutes) and returned as time-ordered lists of data points.

All functions are pure -- same input always produces same output.
Empty input is handled gracefully (returns empty lists, never crashes).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from models.cognition import OperationalState, StateTransition
from models.governance import GovernanceCheckResult
from models.memory import EpisodicMemory, MemoryInfluence


# ============================================================================
#  Helper: time-window bucket assignment
# ============================================================================

def _assign_to_windows(
    items: list[Any],
    timestamp_attr: str,
    window_minutes: int,
) -> dict[datetime, list[Any]]:
    """Assign items to time windows based on their timestamp.

    Args:
        items: Objects with a timestamp attribute.
        timestamp_attr: Name of the datetime attribute on each item.
        window_minutes: Width of each time window in minutes.

    Returns:
        Mapping from window start time -> list of items in that window.
    """
    if not items or window_minutes <= 0:
        return {}

    windows: dict[datetime, list[Any]] = {}
    for item in items:
        ts = getattr(item, timestamp_attr, None)
        if ts is None:
            continue
        # Normalize to naive UTC for bucketing
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)

        # Bucket start: round down to window boundary
        bucket_minute = (ts.minute // window_minutes) * window_minutes
        bucket = ts.replace(minute=bucket_minute, second=0, microsecond=0)
        windows.setdefault(bucket, []).append(item)

    return dict(sorted(windows.items()))


def _governance_pass_rate(checks: list[GovernanceCheckResult]) -> float:
    """Compute governance check pass rate for a window."""
    if not checks:
        return 0.0
    passed = sum(1 for c in checks if c.passed)
    return passed / len(checks)


# ============================================================================
#  TrendAnalyzer — Time-series trend computation
# ============================================================================


class TrendAnalyzer:
    """Analyzes trends in cognition data over time.

    All methods are pure functions producing time-ordered trend data.
    Trends are computed using configurable time windows (default 60 minutes).
    Each trend point is a dict with "window_start", "value", and optional counts.
    """

    # ------------------------------------------------------------------
    #  Governance pass rate trend
    # ------------------------------------------------------------------

    def analyze_governance_trend(
        self,
        checks: list[GovernanceCheckResult],
        window_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """Governance pass rate trend over time windows.

        Tracks how governance check pass rates change over time.
        A declining trend suggests increasing governance pressure.

        Args:
            checks: All governance check results.
            window_minutes: Time window width in minutes.

        Returns a list of dicts, each containing:
            - window_start: datetime of window start
            - pass_rate: float in [0.0, 1.0]
            - total_checks: int
            - passed_checks: int
        """
        windows = _assign_to_windows(checks, "timestamp", window_minutes)
        if not windows:
            return []

        trend: list[dict[str, Any]] = []
        for window_start, window_checks in windows.items():
            passed = sum(1 for c in window_checks if c.passed)
            trend.append({
                "window_start": window_start.isoformat(),
                "pass_rate": round(passed / len(window_checks), 6),
                "total_checks": len(window_checks),
                "passed_checks": passed,
            })
        return trend

    # ------------------------------------------------------------------
    #  State stability trend
    # ------------------------------------------------------------------

    def analyze_state_stability(
        self,
        transitions: list[StateTransition],
        window_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """State stability trend -- how often states change.

        Measures the frequency of state transitions per window.
        Higher values indicate less stability (more state churn).

        Args:
            transitions: All state transition records.
            window_minutes: Time window width in minutes.

        Returns a list of dicts, each containing:
            - window_start: datetime of window start
            - transition_count: int
            - stability_score: float in [0.0, 1.0] (1.0 = most stable)
            - unique_states: int (number of distinct states visited)
        """
        windows = _assign_to_windows(transitions, "timestamp", window_minutes)
        if not windows:
            return []

        trend: list[dict[str, Any]] = []
        for window_start, window_transitions in windows.items():
            count = len(window_transitions)
            states = set()
            for t in window_transitions:
                states.add(str(t.from_state))
                states.add(str(t.to_state))
            # Stability: inverse of transition count, normalized
            # ~10 transitions per window = 0.0 stability, 0 = 1.0
            stability = max(0.0, 1.0 - (count / 10.0))
            trend.append({
                "window_start": window_start.isoformat(),
                "transition_count": count,
                "stability_score": round(stability, 6),
                "unique_states": len(states),
            })
        return trend

    # ------------------------------------------------------------------
    #  Uncertainty disclosure trend
    # ------------------------------------------------------------------

    def analyze_uncertainty_trend(
        self,
        responses: list[Any],
        window_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """Uncertainty disclosure rate trend over time.

        Tracks how often responses include uncertainty disclosures.
        An increasing trend suggests the model is becoming more
        transparent about its limitations.

        Args:
            responses: All governed responses.
            window_minutes: Time window width in minutes.

        Returns a list of dicts, each containing:
            - window_start: datetime of window start
            - disclosure_rate: float in [0.0, 1.0]
            - total_responses: int
            - disclosures: int
        """
        windows = _assign_to_windows(responses, "generated_at", window_minutes)
        if not windows:
            return []

        indicators = [
            "uncertain", "not sure", "i don't know", "cannot determine",
            "insufficient information", "insufficient", "low confidence",
            "ambiguous", "unclear", "inconclusive", "unverified",
            "i'm not certain", "limited information", "cannot confirm",
        ]

        trend: list[dict[str, Any]] = []
        for window_start, window_responses in windows.items():
            disclosed = 0
            for resp in window_responses:
                raw = getattr(resp, "raw_response", "")
                validated = getattr(resp, "validated_response", None)
                text = validated if validated else raw
                text_lower = text.lower()
                if any(ind in text_lower for ind in indicators):
                    disclosed += 1
            trend.append({
                "window_start": window_start.isoformat(),
                "disclosure_rate": round(disclosed / len(window_responses), 6) if window_responses else 0.0,
                "total_responses": len(window_responses),
                "disclosures": disclosed,
            })
        return trend

    # ------------------------------------------------------------------
    #  Degradation trend
    # ------------------------------------------------------------------

    def analyze_degradation_trend(
        self,
        transitions: list[StateTransition],
        window_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """Degradation/recovery frequency trend.

        Tracks how often the system enters DEGRADED or RECOVERING states.
        An increasing trend indicates growing operational stress.

        Args:
            transitions: All state transition records.
            window_minutes: Time window width in minutes.

        Returns a list of dicts, each containing:
            - window_start: datetime of window start
            - degradation_events: int (transitions TO degraded/recovering/fail_closed)
            - recovery_events: int (transitions FROM degraded TO normal)
            - degradation_rate: float in [0.0, 1.0]
        """
        windows = _assign_to_windows(transitions, "timestamp", window_minutes)
        if not windows:
            return []

        stress_states = {"degraded", "recovering", "fail_closed"}
        trend: list[dict[str, Any]] = []
        for window_start, window_transitions in windows.items():
            degradations = 0
            recoveries = 0
            for t in window_transitions:
                to_name = str(t.to_state).lower()
                from_name = str(t.from_state).lower()
                if to_name in stress_states:
                    degradations += 1
                if from_name == "degraded" and to_name not in stress_states:
                    recoveries += 1
            total = len(window_transitions)
            rate = degradations / total if total > 0 else 0.0
            trend.append({
                "window_start": window_start.isoformat(),
                "degradation_events": degradations,
                "recovery_events": recoveries,
                "degradation_rate": round(rate, 6),
            })
        return trend

    # ------------------------------------------------------------------
    #  Memory usage trend
    # ------------------------------------------------------------------

    def analyze_memory_usage_trend(
        self,
        memories: list[EpisodicMemory],
        window_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """Memory creation and retrieval rate trend.

        Tracks memory activity over time: creation rate and
        average retrieval count per window.

        Args:
            memories: All episodic memories.
            window_minutes: Time window width in minutes.

        Returns a list of dicts, each containing:
            - window_start: datetime of window start
            - memories_created: int
            - avg_retrievals: float
            - total_retrievals: int
        """
        windows = _assign_to_windows(memories, "timestamp", window_minutes)
        if not windows:
            return []

        trend: list[dict[str, Any]] = []
        for window_start, window_memories in windows.items():
            total_retrievals = sum(m.retrieval_count for m in window_memories)
            avg_retrievals = total_retrievals / len(window_memories) if window_memories else 0.0
            trend.append({
                "window_start": window_start.isoformat(),
                "memories_created": len(window_memories),
                "avg_retrievals": round(avg_retrievals, 6),
                "total_retrievals": total_retrievals,
            })
        return trend

    # ------------------------------------------------------------------
    #  Quality trend
    # ------------------------------------------------------------------

    def analyze_quality_trend(
        self,
        traces: list[Any],
        window_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """Overall cognition quality score trend.

        Computes a composite quality score per window based on:
        - Governance check pass rate (40%)
        - Session completion rate (30%)
        - Response validation rate (30%)

        Args:
            traces: All cognition traces.
            window_minutes: Time window width in minutes.

        Returns a list of dicts, each containing:
            - window_start: datetime of window start
            - quality_score: float in [0.0, 1.0]
            - traces_in_window: int
            - governance_pass_rate: float
        """
        windows = _assign_to_windows(traces, "start_time", window_minutes)
        if not windows:
            return []

        from models.cognition import OperationalState

        trend: list[dict[str, Any]] = []
        for window_start, window_traces in windows.items():
            # Governance pass rate within traces
            total_checks = 0
            passed_checks = 0
            completed = 0
            validated = 0

            for trace in window_traces:
                checks = getattr(trace, "governance_checks", [])
                total_checks += len(checks)
                passed_checks += sum(1 for c in checks if c.passed)

                final = getattr(trace, "final_state", None)
                if isinstance(final, str):
                    final = OperationalState(final)
                if final and final != OperationalState.FAIL_CLOSED:
                    completed += 1

                # Check if response has validation failures
                failures = getattr(trace, "validation_failures", None)
                if failures is None or len(failures) == 0:
                    validated += 1

            gov_rate = passed_checks / total_checks if total_checks > 0 else 0.0
            completion_rate = completed / len(window_traces) if window_traces else 0.0
            validation_rate = validated / len(window_traces) if window_traces else 0.0

            # Composite: 40% gov + 30% completion + 30% validation
            quality = 0.4 * gov_rate + 0.3 * completion_rate + 0.3 * validation_rate

            trend.append({
                "window_start": window_start.isoformat(),
                "quality_score": round(quality, 6),
                "traces_in_window": len(window_traces),
                "governance_pass_rate": round(gov_rate, 6),
                "completion_rate": round(completion_rate, 6),
                "validation_rate": round(validation_rate, 6),
            })
        return trend

    # ------------------------------------------------------------------
    #  Moving average
    # ------------------------------------------------------------------

    @staticmethod
    def compute_moving_average(
        values: list[float],
        window: int = 5,
    ) -> list[float]:
        """Simple moving average.

        Computes the moving average of a list of values.
        The first (window - 1) entries will be averages of fewer elements.

        Args:
            values: Numeric values to average.
            window: Number of elements in each average window.

        Returns a list of moving averages. Returns empty list for empty input.
        """
        if not values or window <= 0:
            return []

        result: list[float] = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            window_vals = values[start:i + 1]
            result.append(round(sum(window_vals) / len(window_vals), 6))
        return result

    # ------------------------------------------------------------------
    #  Rate of change
    # ------------------------------------------------------------------

    @staticmethod
    def compute_rate_of_change(
        values: list[float],
    ) -> list[float]:
        """Rate of change between consecutive values.

        Computes the percentage change between each consecutive pair:
        (current - previous) / |previous| for each position.

        Args:
            values: Numeric values.

        Returns a list with len(values) - 1 elements.
        Returns empty list for empty input or single element.
        """
        if len(values) < 2:
            return []

        result: list[float] = []
        for i in range(1, len(values)):
            prev = values[i - 1]
            curr = values[i]
            if abs(prev) < 1e-12:
                # Avoid division by zero -- use absolute difference
                roc = 0.0 if abs(curr) < 1e-12 else (1.0 if curr > 0 else -1.0)
            else:
                roc = (curr - prev) / abs(prev)
            result.append(round(roc, 6))
        return result
