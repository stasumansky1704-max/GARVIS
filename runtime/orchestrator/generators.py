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
    findings = _all_findings(run)
    if not findings:
        return f"No findings for goal: {run.goal}"
    bullets = []
    for f in findings[:10]:
        t = f.get("title", ""); u = f.get("url", ""); s = f.get("source", "")
        bullets.append(f"- {t} ({s})" + (f" - {u}" if u else ""))
    return f"{len(findings)} findings for '{run.goal}':\n" + "\n".join(bullets)


def change_proposal(goal: str, findings: list[dict]) -> str:
    options = "\n".join(f"- {f.get('title','')} ({f.get('source','')})"
                        for f in (findings or [])[:8]) or "- (no options gathered)"
    rec = (findings[0]["title"] if findings else "gather more data before deciding")
    return markdown(f"Change proposal: {goal}", [
        ("Context", f"Proposal generated from research on: {goal}."),
        ("Options considered", options),
        ("Recommendation", f"Start with: **{rec}**. Validate against constraints before adopting."),
        ("Risk / next step", "Spike the top option; keep changes reversible; require review."),
    ])


def draft_pr_content(title: str, body: str = "", findings: list[dict] | None = None) -> dict:
    sections = [("Summary", body or f"Draft changes for: {title}")]
    if findings:
        sections.append(("Research basis",
                         "\n".join(f"- {f.get('title','')} {f.get('url','')}"
                                   for f in findings[:8])))
    sections.append(("Checklist", "- [ ] Reviewed\n- [ ] Tests pass\n- [ ] No secrets"))
    return {
        "title": f"draft: {title}",
        "body": markdown(title, sections),
        "branch": "draft/" + "".join(c.lower() if c.isalnum() else "-" for c in title)[:48].strip("-"),
        "labels": ["draft", "garvis-generated"],
        "draft": True,
    }
