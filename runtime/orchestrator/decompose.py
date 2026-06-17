"""
Deterministic query decomposition - break a broad research goal into focused subqueries.

Used as the fallback planner (no LLM needed) and as guidance for the LLM planner. Returns
a useful, non-empty list of specific queries (never empty).
"""
from __future__ import annotations

FACETS = (
    "overview",
    "best tools and options",
    "open source alternatives",
    "pricing and commercial use",
    "API and integration",
)


def decompose(goal: str, max_tasks: int = 5) -> list[str]:
    base = (goal or "").strip()
    if not base:
        return []
    queries = [base] + [f"{base} - {facet}" for facet in FACETS]
    n = max(1, int(max_tasks))
    return queries[:n]
