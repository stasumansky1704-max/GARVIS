"""
Summarization quality - pure helpers that turn raw findings into high-signal output.

Improves research/proposal/PR/report/summary quality by ranking + deduping first, then
extracting the highest-relevance points, an executive summary, source breakdown, and a
confidence band. All pure; reused by generators.py and report.py.
"""
from __future__ import annotations

from .research_quality import dedup_findings, rank_findings, quality_score, source_coverage


def top_findings(findings: list[dict], query: str, n: int = 5) -> list[dict]:
    """Deduped, relevance-ranked top-N findings."""
    return rank_findings(dedup_findings(findings or []), query)[:n]


def key_points(findings: list[dict], query: str, n: int = 5) -> list[str]:
    """High-signal bullet points (title + trimmed snippet) from the top findings."""
    out = []
    for f in top_findings(findings, query, n):
        title = (f.get("title") or "").strip()
        snip = (f.get("snippet") or "").strip().replace("\n", " ")
        if snip and len(snip) > 160:
            snip = snip[:157] + "..."
        out.append(f"{title} - {snip}" if snip else title)
    return [p for p in out if p]


def confidence_band(findings: list[dict]) -> str:
    findings = findings or []
    if not findings:
        return "none"
    avg = sum(float(f.get("confidence", 0) or 0) for f in findings) / len(findings)
    return "high" if avg >= 0.7 else "medium" if avg >= 0.45 else "low"


def source_breakdown(findings: list[dict]) -> str:
    cov = source_coverage(findings or [])
    if not cov["total"]:
        return "no sources"
    return ", ".join(f"{s}: {c}" for s, c in sorted(cov["by_source"].items()))


def executive_summary(goal: str, findings: list[dict]) -> str:
    """A tight 2-3 sentence executive summary grounded in the findings."""
    findings = findings or []
    if not findings:
        return (f"No usable findings for '{goal}'. Broaden the query or remove "
                f"project-specific terms, then retry.")
    top = top_findings(findings, goal, 3)
    leads = ", ".join(f.get("title", "") for f in top if f.get("title"))
    q = quality_score(findings)
    return (f"Researched '{goal}': {len(findings)} findings "
            f"({source_breakdown(findings)}); confidence {confidence_band(findings)}, "
            f"quality {q}. Leading results: {leads}.")
