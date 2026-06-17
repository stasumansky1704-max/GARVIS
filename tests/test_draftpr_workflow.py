"""
Group B - draft-PR workflow safety + quality tests (offline, deterministic).

Covers title cleanup, branch slug limits, empty-proposal detection/blocking, quality
scoring, rollback instructions, dry-run diff, duplicate branch/file detection, per-step
tracking, op budget, and the worker's never-merge / never-write-main guards.

Runs with pytest OR standalone:  python tests/test_draftpr_workflow.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator import draftpr
from orchestrator.models import TaskSpec, Status
from orchestrator.workers.github_worker import GitHubDraftPRWorker, FORBIDDEN_CLIENT_METHODS, GitHubClient


def test_clean_title_strips_filler_and_prefixes():
    t = draftpr.clean_title("best open source AI agent frameworks for GARVIS")
    assert t.startswith("draft: ") and "garvis" not in t.lower()


def test_clean_title_length_bounded():
    t = draftpr.clean_title("x " * 200)
    assert len(t) <= draftpr.MAX_TITLE_LEN


def test_safe_slug_bounds_and_never_empty():
    s = draftpr.safe_slug("Best Open Source!! AI / Agent  Frameworks for GARVIS", maxlen=20)
    assert len(s) <= 20 and not s.startswith("-") and not s.endswith("-")
    assert draftpr.safe_slug("!!!") == "proposal"


def test_is_empty_proposal():
    assert draftpr.is_empty_proposal([], "No findings for goal: x")
    assert draftpr.is_empty_proposal(None, "")
    assert not draftpr.is_empty_proposal([{"title": "t"}], "has content")


def test_proposal_quality_scores():
    empty = draftpr.proposal_quality("No findings for goal: x", [])
    rich = draftpr.proposal_quality("## Recommendation\n" + ("detail " * 60),
                                    [{"title": "a"}, {"title": "b"}])
    assert empty["is_empty"] and empty["score"] < rich["score"]
    assert rich["findings"] == 2


def test_rollback_instructions_mention_close_and_delete():
    txt = draftpr.rollback_instructions("draft/garvis/x-1", number=28)
    assert "#28" in txt and "delete" in txt.lower() and "do NOT merge" in txt


def test_dry_run_diff_preview():
    d = draftpr.dry_run_diff("docs/proposals/x.md", "line1\nline2\nline3", max_lines=2)
    assert "+++ b/docs/proposals/x.md" in d and "+line1" in d and "more lines" in d


# ---- duplicate detection helpers (injectable client) ----
class _Client:
    def __init__(self, branches=(), files=()):
        self._branches = list(branches)
        self._files = set(files)

    def branches(self):
        return [{"name": b} for b in self._branches]

    def get_file(self, branch, path):
        if (branch, path) in self._files:
            return {"path": path}
        raise Exception("404")


def test_branch_exists_detection():
    c = _Client(branches=["main", "draft/garvis/x-1"])
    assert draftpr.branch_exists(c, "draft/garvis/x-1")
    assert not draftpr.branch_exists(c, "draft/garvis/y-2")


def test_file_exists_on_branch_detection():
    c = _Client(files=[("b", "docs/proposals/x.md")])
    assert draftpr.file_exists_on_branch(c, "b", "docs/proposals/x.md")
    assert not draftpr.file_exists_on_branch(c, "b", "docs/proposals/other.md")


# ---- worker hardening ----
class _FakeGH:
    def __init__(self, existing_branches=()):
        self.calls = []
        self._existing = list(existing_branches)

    def branches(self):
        self.calls.append(("branches",))
        return [{"name": b} for b in self._existing]

    def ref_sha(self, base):
        self.calls.append(("ref_sha", base)); return "sha123"

    def create_branch(self, b, sha):
        self.calls.append(("create_branch", b)); self._existing.append(b)

    def get_file(self, branch, path):
        raise Exception("404")

    def put_file(self, b, p, t, m):
        self.calls.append(("put_file", p))

    def create_draft_pr(self, title, head, base, body):
        self.calls.append(("create_draft_pr", head))
        return {"number": 99, "html_url": "https://x/99", "draft": True}


def _inputs(**kw):
    base = {"title": "draft: t", "branch": "draft/garvis/x-1", "base": "main",
            "file_path": "docs/proposals/x.md", "file_content": "body", "approved": True}
    base.update(kw)
    return base


def test_worker_dry_run_blocks_without_approval():
    c = _FakeGH()
    env = GitHubDraftPRWorker(client=c).run(TaskSpec(id="d", worker="github_draft_pr",
        intent="x", inputs=_inputs(approved=False)))
    assert env.status == Status.BLOCKED and c.calls == []


def test_worker_creates_with_steps():
    c = _FakeGH()
    env = GitHubDraftPRWorker(client=c).run(TaskSpec(id="d", worker="github_draft_pr",
        intent="x", inputs=_inputs()))
    assert env.status == Status.DONE
    assert env.result["steps"] == ["ref_sha", "create_branch", "put_file", "create_draft_pr"]


def test_worker_refuses_to_write_main():
    c = _FakeGH()
    env = GitHubDraftPRWorker(client=c).run(TaskSpec(id="d", worker="github_draft_pr",
        intent="x", inputs=_inputs(branch="main")))
    assert env.status == Status.FAILED and c.calls == []


def test_worker_blocks_duplicate_branch():
    c = _FakeGH(existing_branches=["draft/garvis/x-1"])
    env = GitHubDraftPRWorker(client=c).run(TaskSpec(id="d", worker="github_draft_pr",
        intent="x", inputs=_inputs()))
    assert env.status == Status.BLOCKED and "duplicate" in env.error
    assert not any(k[0] == "create_branch" for k in c.calls)


def test_worker_op_budget_too_small():
    c = _FakeGH()
    env = GitHubDraftPRWorker(client=c, max_ops=2).run(TaskSpec(id="d",
        worker="github_draft_pr", intent="x", inputs=_inputs()))
    assert env.status == Status.FAILED and "budget" in env.error


def test_client_has_no_merge_or_delete():
    for name in FORBIDDEN_CLIENT_METHODS:
        assert not hasattr(GitHubClient, name), f"client must not have {name}"


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
