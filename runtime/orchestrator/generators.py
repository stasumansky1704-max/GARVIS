"""
Content generators - turn data (research runs, findings) into real text artifacts.

markdown()            : generic section renderer
research_summary()    : aggregate a run's findings into a summary
change_proposal()     : a structured proposal (context / options / recommendation)
draft_pr_content()    : draft-PR-ready {title, body, branch, labels} (content only; the
                        GitHub worker opens the DRAFT PR separately, approval-gated)
All pure functions (no I/O); callers write to gitignored artifacts.
"""
from __future__ import annotations


def markdown(title: str, sections: list[tuple[str, str]]) -> str:
    lines = [f"# {title}", ""]
    for heading, body in sections:
        lines += [f"## {heading}", body, ""]
    return "\n".join(lines).rstrip() + "\n"


def _all_findings(run) -> list[dict]:
    out = []
    for env in run.results.values():
        if isinstance(env.result, dict):
            out.extend(env.result.get("findings", []))
    return out


def research_summary(run) -> str:
    from .summarize import top_findings, executive_summary
    findings = _all_findings(run)
    if not findings:
        return f"No findings for goal: {run.goal}"
    bullets = []
    for f in top_findings(findings, run.goal, 10):           # ranked + deduped, highest signal
        t = f.get("title", ""); u = f.get("url", ""); s = f.get("source", "")
        c = f.get("confidence", "")
        meta = f"{s}" + (f", conf={c}" if c != "" else "")
        bullets.append(f"- {t} ({meta})" + (f" - {u}" if u else ""))
    return executive_summary(run.goal, findings) + "\n\n" + "\n".join(bullets)


def change_proposal(goal: str, findings: list[dict]) -> str:
    from .summarize import top_findings, executive_summary, key_points, confidence_band
    ranked = top_findings(findings or [], goal, 8)
    options = "\n".join(
        f"- {f.get('title','')} ({f.get('source','')}, conf={f.get('confidence','?')})"
        for f in ranked) or "- (no options gathered)"
    evidence = "\n".join(f"- {p}" for p in key_points(findings or [], goal, 5)) or "- (none)"
    rec = (ranked[0]["title"] if ranked else "gather more data before deciding")
    return markdown(f"Change proposal: {goal}", [
        ("Executive summary", executive_summary(goal, findings or [])),
        ("Context", f"Proposal generated from research on: {goal}."),
        ("Options considered (ranked)", options),
        ("Key evidence", evidence),
        ("Recommendation",
         f"Start with: **{rec}** (evidence confidence: {confidence_band(findings or [])}). "
         f"Validate against constraints before adopting."),
        ("Risk / next step", "Spike the top option; keep changes reversible; require review."),
    ])


def draft_pr_content(title: str, body: str = "", findings: list[dict] | None = None,
                     artifact_link: str | None = None) -> dict:
    sections = [("Summary", body or f"Draft changes for: {title}")]
    if findings:
        sections.append(("Research basis",
                         "\n".join(f"- {f.get('title','')} {f.get('url','')}"
                                   for f in findings[:8])))
    if artifact_link:
        sections.append(("Artifact", f"Local research artifact: `{artifact_link}`"))
    sections.append(("Safety", "- Draft only (not for merge as-is)\n- main is never modified\n"
                               "- Reversible: close PR + delete the throwaway branch"))
    sections.append(("Checklist", "- [ ] Reviewed\n- [ ] Tests pass\n- [ ] No secrets"))
    return {
        "title": f"draft: {title}",
        "body": markdown(title, sections),
        "branch": "draft/" + "".join(c.lower() if c.isalnum() else "-" for c in title)[:48].strip("-"),
        "labels": ["draft", "garvis-generated"],
        "draft": True,
    }
