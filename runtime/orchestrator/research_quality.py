"""
Research quality - pure helpers that make research results useful, ranked, and honest.

Used by the ResearchWorker and the proposal / draft-PR flow:
- query shaping : clean_query, expand_query, broaden_query, extract_terms, source_query
- result shaping: dedup_findings, rank_findings, score_confidence
- judgement     : quality_score, completeness_score, source_coverage, explain_empty

Why this exists: the first live draft-PR demo produced an EMPTY proposal because the exact
phrase ("best open source AI agent frameworks for GARVIS") matched nothing. These helpers
clean project-specific / filler words and broaden niche queries so reasonable broader
searches find information. All functions are pure (no I/O, no network).
"""
from __future__ import annotations

# Minimum findings for a research result to be considered "useful".
MIN_USEFUL_FINDINGS = 3

# Filler/marketing words that hurt search recall when left in a query.
_FILLER = {
    "best", "top", "good", "great", "greatest", "leading", "popular", "recommended",
    "list", "tools", "tool", "options", "option", "alternatives", "alternative",
    "comparison", "compare", "vs", "review", "reviews", "guide", "the", "a", "an",
    "of", "for", "to", "in", "on", "with", "and", "or", "my", "our", "your",
    "2023", "2024", "2025", "2026",
}
# Project-specific tokens that should never be sent to a general search engine.
_PROJECT_TOKENS = {"garvis", "jarvis", "alphaflow"}
# Source-specific weighting used in ranking (higher = more authoritative here).
_SOURCE_WEIGHT = {"wikipedia": 1.0, "duckduckgo": 0.6}


def _norm(s: str) -> str:
    return "".join(c.lower() if (c.isalnum() or c.isspace()) else " " for c in (s or "")).strip()


def _words(s: str) -> list[str]:
    return [w for w in _norm(s).split() if w]


def extract_terms(goal: str, keep_short: bool = False) -> list[str]:
    """Significant search terms: drop filler + project tokens, keep order, dedup."""
    out, seen = [], set()
    for w in _words(goal):
        if w in _FILLER or w in _PROJECT_TOKENS:
            continue
        if not keep_short and len(w) < 2:       # drop only single chars; keep ai/ml/os
            continue
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out


def clean_query(query: str, source: str | None = None) -> str:
    """Source-specific cleaning: strip filler + project tokens to a core noun phrase.

    Wikipedia prefers a tight noun phrase; DuckDuckGo tolerates more, so we keep it as-is
    after the generic clean. Falls back to the original normalized query if cleaning would
    empty it.
    """
    terms = extract_terms(query)
    if not terms:
        return _norm(query)
    if source == "wikipedia":
        # Wikipedia: keep the most specific 4 terms (the head noun phrase).
        return " ".join(terms[:4])
    return " ".join(terms)


def source_query(query: str, source: str) -> str:
    """The actual string to send to a given source."""
    return clean_query(query, source) or _norm(query)


def expand_query(goal: str, limit: int = 5) -> list[str]:
    """Generate broader keyword variants for a niche goal (recall-boosting fallbacks)."""
    terms = extract_terms(goal)
    variants: list[str] = []

    def _add(q: str) -> None:
        q = q.strip()
        if q and q not in variants:
            variants.append(q)

    _add(clean_query(goal))
    if terms:
        _add(" ".join(terms))               # core terms only
        _add(" ".join(terms[-3:]))          # head noun phrase (last 3 significant terms)
        _add(" ".join(terms[-2:]))          # broader head (last 2)
        _add(terms[-1])                      # broadest single concept
    return variants[:limit] or [_norm(goal)]


def broaden_query(query: str) -> str:
    """Return a strictly broader version of a query (drop the leading qualifier).

    "open source ai agent frameworks" -> "ai agent frameworks" -> "agent frameworks" ...
    Returns the same string only when it cannot be broadened further.
    """
    terms = extract_terms(query)
    if len(terms) <= 1:
        return " ".join(terms)
    return " ".join(terms[1:])


# ---------------------------------------------------------------- result shaping

def _finding_url(f: dict) -> str:
    return (f.get("url") or "").strip().rstrip("/").lower()


def dedup_findings(findings: list[dict]) -> list[dict]:
    """Remove duplicate findings by URL (then by normalized title). Keeps the highest
    confidence on collision; preserves first-seen order otherwise."""
    best: dict[str, dict] = {}
    order: list[str] = []
    for f in findings or []:
        key = _finding_url(f) or ("title::" + _norm(f.get("title", "")))
        if not key or key == "title::":
            key = "id::" + str(id(f))
        if key not in best:
            best[key] = f
            order.append(key)
        elif float(f.get("confidence", 0)) > float(best[key].get("confidence", 0)):
            best[key] = f
    return [best[k] for k in order]


def score_confidence(finding: dict, query: str) -> float:
    """Blend the source's base confidence with query-term overlap. Clamped to [0, 1]."""
    base = float(finding.get("confidence", 0.4) or 0.4)
    q = set(extract_terms(query))
    text = set(_words(finding.get("title", "") + " " + finding.get("snippet", "")))
    overlap = (len(q & text) / len(q)) if q else 0.0
    return round(max(0.0, min(1.0, 0.6 * base + 0.4 * overlap)), 3)


def rank_findings(findings: list[dict], query: str) -> list[dict]:
    """Sort findings by relevance to the query (term overlap + source weight + confidence).
    Returns new list of findings, each annotated with a 'relevance' score."""
    q = set(extract_terms(query))
    scored = []
    for f in findings or []:
        text = set(_words(f.get("title", "") + " " + f.get("snippet", "")))
        overlap = len(q & text)
        weight = _SOURCE_WEIGHT.get(f.get("source", ""), 0.5)
        rel = round(overlap * weight + float(f.get("confidence", 0) or 0), 3)
        g = dict(f)
        g["relevance"] = rel
        scored.append(g)
    scored.sort(key=lambda x: (-x["relevance"], x.get("title", "")))
    return scored


# ---------------------------------------------------------------- judgement

def source_coverage(findings: list[dict]) -> dict:
    """Per-source counts + how many distinct sources contributed."""
    counts: dict[str, int] = {}
    for f in findings or []:
        s = f.get("source", "unknown")
        counts[s] = counts.get(s, 0) + 1
    return {"by_source": counts, "distinct_sources": len(counts), "total": sum(counts.values())}


def quality_score(findings: list[dict]) -> float:
    """0..1 score: blends volume (vs MIN_USEFUL_FINDINGS), avg confidence, source diversity."""
    findings = findings or []
    if not findings:
        return 0.0
    volume = min(1.0, len(findings) / MIN_USEFUL_FINDINGS)
    avg_conf = sum(float(f.get("confidence", 0) or 0) for f in findings) / len(findings)
    diversity = min(1.0, source_coverage(findings)["distinct_sources"] / 2.0)
    return round(0.5 * volume + 0.3 * avg_conf + 0.2 * diversity, 3)


def completeness_score(goal: str, findings: list[dict]) -> float:
    """Fraction of the goal's significant terms that appear somewhere in the findings."""
    terms = set(extract_terms(goal))
    if not terms:
        return 0.0
    corpus = set()
    for f in findings or []:
        corpus |= set(_words(f.get("title", "") + " " + f.get("snippet", "")))
    return round(len(terms & corpus) / len(terms), 3)


def is_useful(findings: list[dict]) -> bool:
    return len(findings or []) >= MIN_USEFUL_FINDINGS


def explain_empty(goal: str, errors: list[str] | None = None) -> str:
    """Human-readable explanation + concrete broader query suggestion for empty results."""
    suggestion = broaden_query(goal) or " ".join(extract_terms(goal)) or goal
    msg = (f"No useful findings for '{goal}'. The query may be too specific or contain "
           f"project-specific terms. Suggested broader query: '{suggestion}'.")
    if errors:
        msg += " Source notes: " + "; ".join(errors)
    return msg
