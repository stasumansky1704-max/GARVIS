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


# Per-source authority weight (higher = more trustworthy for ranking/decisions).
_SOURCE_AUTHORITY = {"wikipedia": 0.9, "duckduckgo": 0.6}
# Words that hint at risk in a finding (for decision support).
_RISK_WORDS = ("deprecated", "discontinued", "vulnerability", "cve", "unmaintained",
               "abandoned", "license", "paid", "proprietary", "beta", "experimental")


def source_authority(finding: dict) -> float:
    """Authority weight for a finding's source (0..1)."""
    return _SOURCE_AUTHORITY.get((finding.get("source") or "").lower(), 0.5)


def rank_evidence(findings: list[dict], query: str, n: int = 5) -> list[dict]:
    """Rank findings as decision EVIDENCE: relevance x source authority x confidence.
    Returns top-n with an 'evidence_score'."""
    from .research_quality import rank_findings, dedup_findings
    ranked = rank_findings(dedup_findings(findings or []), query)
    out = []
    for f in ranked:
        score = round(float(f.get("relevance", 0)) * source_authority(f)
                      * (0.5 + 0.5 * float(f.get("confidence", 0) or 0)), 4)
        g = dict(f); g["evidence_score"] = score
        out.append(g)
    out.sort(key=lambda x: -x["evidence_score"])
    return out[:n]


def risk_flags(findings: list[dict]) -> list[str]:
    """Surface risk signals found in the evidence (deprecated/licensing/security/...)."""
    flags = set()
    for f in findings or []:
        text = (f.get("title", "") + " " + f.get("snippet", "")).lower()
        for w in _RISK_WORDS:
            if w in text:
                flags.add(w)
    return sorted(flags)


def decision_support(goal: str, findings: list[dict]) -> dict:
    """Structured decision support: top recommendation + evidence + confidence + risks.
    Turns research into an actually-decidable answer."""
    from .research_quality import quality_score
    ev = rank_evidence(findings or [], goal, 5)
    rec = ev[0]["title"] if ev else "insufficient evidence - broaden research"
    risks = risk_flags(findings or [])
    q = quality_score(findings or [])
    confidence = "high" if (ev and q >= 0.7 and not risks) else \
                 "low" if (not ev or q < 0.4) else "medium"
    return {"goal": goal, "recommendation": rec, "confidence": confidence,
            "quality": q, "risks": risks,
            "evidence": [{"title": e.get("title"), "score": e["evidence_score"],
                          "source": e.get("source")} for e in ev]}


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
