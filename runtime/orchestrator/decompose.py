"""
Deterministic query decomposition - break a broad research goal into focused subqueries.

Used as the fallback planner (no LLM needed) and as guidance for the LLM planner. Returns
a useful, non-empty list of specific queries (never empty). For niche goals it mixes
facet queries with progressively broader keyword variants (see research_quality) so the
search has a real chance of returning findings instead of an empty result.
"""
from __future__ import annotations

from .research_quality import clean_query, expand_query, extract_terms

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
    cleaned = clean_query(base)
    queries: list[str] = [base]
    if cleaned and cleaned != base.lower():
        queries.append(cleaned)                              # cleaned core noun phrase
    queries += [f"{base} - {facet}" for facet in FACETS]
    out, seen = [], set()
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
    n = max(1, int(max_tasks))
    return out[:n]


def decompose_smart(goal: str, max_tasks: int = 5) -> list[str]:
    """Niche-friendly decomposition: cleaned query + broader keyword variants + a facet.

    Prioritizes queries most likely to return findings (cleaned/broadened) over verbose
    facet strings, which fixes empty results for project-specific goals.
    """
    base = (goal or "").strip()
    if not base:
        return []
    out, seen = [], set()

    def _add(q: str) -> None:
        q = (q or "").strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)

    for q in expand_query(base):                              # cleaned + progressively broader
        _add(q)
    terms = extract_terms(base)
    if terms:
        _add(" ".join(terms) + " overview")
    _add(base)                                                # keep the literal goal too
    n = max(1, int(max_tasks))
    return out[:n]
