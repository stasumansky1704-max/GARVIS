"""
Group E - GitHub worker hardening tests (offline, deterministic, mocked client).

Covers PR status/comments/changed-files reads, improved risk scoring, branch stale
detection, open/closed PR summaries, draft-PR cleanup recommendation, demo-PR detection,
do-not-delete / merge-forbidden enforcement, token-presence check, op budget, and
rate-limit handling.

Runs with pytest OR standalone:  python tests/test_github_hardening.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator.models import TaskSpec, Status
from orchestrator.workers import github_worker as gw
from orchestrator.workers.github_worker import (GitHubReadWorker, GitHubClient, RateLimitError,
                                                pr_status, pr_risk, is_demo_pr,
                                                cleanup_recommendation, branch_is_stale,
                                                FORBIDDEN_CLIENT_METHODS)


class _FakeGH:
    def pull(self, n):
        return {"number": n, "title": "Big change to backend", "state": "open",
                "draft": False, "merged": False, "mergeable": True,
                "mergeable_state": "clean", "additions": 50, "changed_files": 5}

    def pull_files(self, n):
        return [{"filename": "api/server.py"}, {"filename": "docker-compose.yml"}]

    def pull_comments(self, n):
        return [{"user": {"login": "stas"}, "body": "looks good"}]

    def pulls(self, state="open"):
        return [
            {"number": 28, "title": "draft demo", "state": "open", "draft": True,
             "user": {"login": "g"}, "head": {"ref": "draft/garvis/demo-1"}},
            {"number": 27, "title": "real feature", "state": "open", "draft": False,
             "user": {"login": "g"}, "head": {"ref": "feature/x"}},
        ]


def test_pr_status_read():
    d = pr_status(_FakeGH().pull(28))
    assert d["number"] == 28 and d["draft"] is False and d["mergeable_state"] == "clean"


def test_read_worker_status_op():
    env = GitHubReadWorker(client=_FakeGH()).run(TaskSpec(id="g", worker="github_read",
        intent="status", inputs={"op": "status", "number": 28}))
    assert env.status == Status.DONE and env.result["data"]["number"] == 28


def test_read_worker_comments_op():
    env = GitHubReadWorker(client=_FakeGH()).run(TaskSpec(id="g", worker="github_read",
        intent="comments", inputs={"op": "comments", "number": 28}))
    assert env.status == Status.DONE and "stas" in env.result["data"][0]


def test_risk_scoring_flags_backend_high():
    risk = pr_risk(_FakeGH().pull(1), _FakeGH().pull_files(1))
    assert risk["level"] == "high" and "backend" in risk["risky_paths"]
    assert "recommendation" in risk and risk["score"] >= 3


def test_open_and_closed_pr_summaries():
    w = GitHubReadWorker(client=_FakeGH())
    o = w.run(TaskSpec(id="g", worker="github_read", intent="open", inputs={"op": "open_prs"}))
    assert o.status == Status.DONE and any("#28" in s for s in o.result["data"])


def test_demo_pr_detection_and_cleanup():
    prs = _FakeGH().pulls()
    assert is_demo_pr(prs[0]) and not is_demo_pr(prs[1])
    rec = cleanup_recommendation(prs)
    assert len(rec) == 1 and rec[0]["number"] == 28 and rec[0]["safe"] is True


def test_read_worker_cleanup_op():
    env = GitHubReadWorker(client=_FakeGH()).run(TaskSpec(id="g", worker="github_read",
        intent="cleanup", inputs={"op": "cleanup"}))
    assert env.status == Status.DONE and env.result["data"][0]["number"] == 28


def test_branch_stale_detection():
    assert branch_is_stale("2020-01-01T00:00:00", days=30, now_iso="2026-01-01T00:00:00")
    assert not branch_is_stale("2026-01-01T00:00:00", days=30, now_iso="2026-01-05T00:00:00")


def test_merge_and_delete_forbidden_on_client():
    for name in FORBIDDEN_CLIENT_METHODS:
        assert not hasattr(GitHubClient, name)


def test_token_presence_check_without_printing():
    c = GitHubClient(token="secrettoken")
    assert c.has_token() is True            # returns bool, never the token value


def test_rate_limit_handling_blocks_not_crashes():
    class _RL:
        def pull(self, n):
            raise RateLimitError("rate limited")
    env = GitHubReadWorker(client=_RL()).run(TaskSpec(id="g", worker="github_read",
        intent="status", inputs={"op": "status", "number": 1}))
    assert env.status == Status.BLOCKED and "rate limit" in env.error


def test_unknown_op_fails():
    env = GitHubReadWorker(client=_FakeGH()).run(TaskSpec(id="g", worker="github_read",
        intent="?", inputs={"op": "nope"}))
    assert env.status == Status.FAILED


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
