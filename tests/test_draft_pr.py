"""
Draft-PR close-the-loop tests (offline; mocked GitHub client, no network/token).

Verifies: dry-run blocks with NO side effects; explicit approval creates branch+file+
draft PR; missing inputs fail; the client exposes no merge/delete capability.

Runs with pytest OR standalone:  python tests/test_draft_pr.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator.models import TaskSpec, Status
from orchestrator.workers.github_worker import GitHubDraftPRWorker, GitHubClient


class _FakeClient:
    def __init__(self):
        self.calls = []

    def ref_sha(self, branch):
        self.calls.append(("ref_sha", branch)); return "deadbeef"

    def create_branch(self, new, sha):
        self.calls.append(("create_branch", new, sha)); return {"ref": "refs/heads/" + new}

    def put_file(self, branch, path, text, message):
        self.calls.append(("put_file", branch, path)); return {"commit": {"sha": "c1"}}

    def create_draft_pr(self, title, head, base, body):
        self.calls.append(("create_draft_pr", title, head, base))
        return {"number": 123, "html_url": "https://github.com/x/y/pull/123", "draft": True}


def _task(**inputs):
    return TaskSpec(id="d", worker="github_draft_pr", intent="pr", inputs=inputs)


def test_draft_pr_dry_run_blocks_and_no_side_effects():
    c = _FakeClient()
    env = GitHubDraftPRWorker(client=c).run(
        _task(title="T", base="main", branch="draft/x", file_path="docs/p.md",
              file_content="body"))  # no approved flag
    assert env.status == Status.BLOCKED
    assert "approval" in env.error.lower()
    assert env.result["preview"]["will_merge"] is False
    assert c.calls == []                      # NOTHING was created


def test_draft_pr_approved_creates_branch_file_and_pr():
    c = _FakeClient()
    env = GitHubDraftPRWorker(client=c).run(
        _task(title="Add proposal", base="main", branch="draft/garvis/x-1",
              file_path="docs/proposals/x-1.md", file_content="# proposal",
              body="b", approved=True))
    assert env.status == Status.DONE
    assert env.result["number"] == 123 and env.result["draft"] is True
    kinds = [c0[0] for c0 in c.calls]
    assert kinds == ["ref_sha", "create_branch", "put_file", "create_draft_pr"]


def test_draft_pr_existing_branch_no_file():
    c = _FakeClient()
    env = GitHubDraftPRWorker(client=c).run(
        _task(title="T", base="main", branch="existing-branch", approved=True))
    assert env.status == Status.DONE
    assert [c0[0] for c0 in c.calls] == ["create_draft_pr"]   # no branch/file creation


def test_draft_pr_missing_title_fails():
    env = GitHubDraftPRWorker(client=_FakeClient()).run(_task(base="main", branch="b", approved=True))
    assert env.status == Status.FAILED


def test_github_client_has_no_merge_or_delete():
    # safety: the client must not expose any merge/delete capability
    assert not hasattr(GitHubClient, "merge")
    assert not hasattr(GitHubClient, "merge_pr")
    assert not hasattr(GitHubClient, "delete_branch")
    assert not hasattr(GitHubClient, "delete_ref")


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
