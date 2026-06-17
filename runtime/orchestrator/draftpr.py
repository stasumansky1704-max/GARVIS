"""
Draft-PR workflow helpers - pure, testable building blocks for safe Draft PR creation.

- clean_title / safe_slug : human-quality PR title + length-bounded branch slug
- proposal_quality / is_empty_proposal : block empty proposals unless overridden
- rollback_instructions  : exact, copy-pasteable undo steps for a created draft PR
- dry_run_diff           : a unified-diff-style preview of the file that would be added
- duplicate detection helpers operate on a GitHub client (injectable -> offline tests)

Nothing here performs a network call or a side effect; the GitHub worker does the I/O.
Safety posture: never merge, never delete, default to dry-run, never write main.
"""
from __future__ import annotations

from .research_quality import extract_terms

MAX_SLUG_LEN = 48
MAX_TITLE_LEN = 72


def clean_title(goal: str) -> str:
    """Produce a readable PR title: trim filler, collapse spaces, cap length, add prefix."""
    terms = extract_terms(goal, keep_short=True) or (goal or "").split()
    phrase = " ".join(terms).strip() or "proposal"
    phrase = phrase[0].upper() + phrase[1:] if phrase else phrase
    title = f"draft: {phrase}"
    return title[:MAX_TITLE_LEN].rstrip()


def safe_slug(text: str, maxlen: int = MAX_SLUG_LEN) -> str:
    """Lowercase, hyphenated, length-bounded slug. Never empty; never leading/trailing '-'."""
    s = "".join(c.lower() if c.isalnum() else "-" for c in (text or "").strip())
    while "--" in s:
        s = s.replace("--", "-")
    s = s.strip("-")[:maxlen].strip("-")
    return s or "proposal"


def is_empty_proposal(findings: list[dict] | None, body: str = "") -> bool:
    """A proposal is 'empty' when there are no findings (the body is just a template)."""
    if findings:
        return False
    low = (body or "").lower()
    return ("no findings" in low) or ("no options gathered" in low) or not body.strip()


def proposal_quality(body: str, findings: list[dict] | None) -> dict:
    """Score a proposal body 0..1 and flag emptiness with reasons."""
    findings = findings or []
    reasons = []
    n = len(findings)
    has_rec = "recommendation" in (body or "").lower()
    length_ok = len(body or "") >= 200
    score = 0.0
    if n:
        score += min(0.6, 0.2 * n)
    else:
        reasons.append("no findings gathered")
    if has_rec:
        score += 0.2
    else:
        reasons.append("no recommendation section")
    if length_ok:
        score += 0.2
    else:
        reasons.append("body is very short")
    empty = is_empty_proposal(findings, body)
    return {"score": round(min(1.0, score), 3), "is_empty": empty,
            "findings": n, "reasons": reasons}


def rollback_instructions(branch: str, number: int | None = None, repo: str = "") -> str:
    """Exact undo steps for a created draft PR (close PR + delete the throwaway branch)."""
    pr = f"#{number}" if number else "<pr-number>"
    lines = [
        "# Rollback (safe, reversible):",
        f"#   1. Close the draft PR {pr} on GitHub (do NOT merge).",
        f"#   2. Delete the throwaway branch when you no longer need it:",
        f"#        git push origin --delete {branch}",
        "#   main is never modified by this workflow, so nothing to revert there.",
    ]
    if repo:
        lines.insert(1, f"#   repo: {repo}")
    return "\n".join(lines)


def dry_run_diff(file_path: str, content: str, max_lines: int = 20) -> str:
    """Unified-diff-style preview of the NEW file that would be committed to the branch."""
    body_lines = (content or "").splitlines()
    shown = body_lines[:max_lines]
    out = ["--- /dev/null", f"+++ b/{file_path}",
           f"@@ new file: {len(body_lines)} line(s) @@"]
    out += ["+" + ln for ln in shown]
    if len(body_lines) > max_lines:
        out.append(f"... (+{len(body_lines) - max_lines} more lines)")
    return "\n".join(out)


# --------- duplicate detection (operate on an injectable GitHub client) ---------

def branch_exists(client, branch: str) -> bool:
    """True if a branch already exists on the remote (avoid duplicate draft branches)."""
    try:
        names = {b.get("name") for b in client.branches()}
    except Exception:
        return False
    return branch in names


def file_exists_on_branch(client, branch: str, path: str) -> bool:
    """True if the proposal file already exists on the target branch (avoid duplicates)."""
    getter = getattr(client, "get_file", None)
    if getter is None:
        return False
    try:
        return bool(getter(branch, path))
    except Exception:
        return False
