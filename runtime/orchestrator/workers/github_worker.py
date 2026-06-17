"""
GitHub workers - READ-ONLY inspection + DRAFT-PR creation. Never merge, never delete.

- GitHubClient: thin urllib client. Token read lazily from ~/.git-credentials and NEVER
  logged/returned. Read ops are GETs; create_draft_pr is the only write (draft=True).
- GitHubReadWorker (READ): op in task.inputs -> branches/pulls/commits/issues/pull/
  pull_files/summary/risk. No approval needed.
- GitHubDraftPRWorker (EXTERNAL): creates a DRAFT PR only -> Approval Gate must clear it.

The client is injectable so tests run fully offline (no token, no network).
pr_summary()/pr_risk() are pure functions usable by other capabilities.
"""
from __future__ import annotations

import json
import urllib.request

from .base import Worker
from ..models import TaskSpec, Envelope, Status, SafetyClass
from ..registry import WorkerSpec

DEFAULT_REPO = "stasumansky1704-max/GARVIS"
_RISKY = ("docker", "gpu", "dashboard", "backend", "wdm-ks", "migration", ".env")


class GitHubClient:
    def __init__(self, repo: str = DEFAULT_REPO, token: str | None = None):
        self.repo = repo
        self._token = token

    def _tok(self) -> str:
        if self._token:
            return self._token
        import os
        import re
        cred = open(os.path.expanduser("~/.git-credentials")).read()
        self._token = re.search(r"https://[^:]+:([^@]+)@github.com", cred).group(1)
        return self._token

    def _req(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            "https://api.github.com/repos/%s%s" % (self.repo, path), data=data,
            headers={"Authorization": "token " + self._tok(),
                     "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json"}, method=method)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())

    # read-only
    def branches(self): return self._req("GET", "/branches?per_page=50")
    def pulls(self, state="open"): return self._req("GET", "/pulls?state=%s&per_page=50" % state)
    def commits(self): return self._req("GET", "/commits?per_page=10")
    def issues(self): return self._req("GET", "/issues?state=open&per_page=30")
    def pull(self, num): return self._req("GET", "/pulls/%d" % int(num))
    def pull_files(self, num): return self._req("GET", "/pulls/%d/files?per_page=100" % int(num))

    # write (DRAFT only)
    def create_draft_pr(self, title, head, base, body):
        return self._req("POST", "/pulls", {"title": title, "head": head, "base": base,
                                            "body": body, "draft": True})


def pr_summary(pr: dict) -> str:
    return ("#%s %s [%s] by %s  +%s/-%s files=%s" % (
        pr.get("number", "?"), pr.get("title", ""), pr.get("state", "?"),
        (pr.get("user") or {}).get("login", "?"),
        pr.get("additions", "?"), pr.get("deletions", "?"), pr.get("changed_files", "?")))


def pr_risk(pr: dict, files: list[dict] | None = None) -> dict:
    changed = pr.get("changed_files") or (len(files) if files else 0)
    adds = pr.get("additions", 0) or 0
    names = " ".join(f.get("filename", "") for f in (files or [])).lower() + " " + pr.get("title", "").lower()
    risky = sorted({r for r in _RISKY if r in names})
    if risky or changed > 30 or adds > 800:
        level = "high"
    elif changed > 8 or adds > 200:
        level = "medium"
    else:
        level = "low"
    return {"level": level, "changed_files": changed, "additions": adds, "risky_paths": risky}


class GitHubReadWorker(Worker):
    spec = WorkerSpec(name="github_read", capabilities=["branches", "pulls", "commits",
                      "issues", "pull", "summary", "risk"], tool_permissions=["github:read"],
                      safety_class=SafetyClass.READ, cost_class="cheap",
                      description="Read-only GitHub inspection (branches/PRs/commits/issues/risk).")

    def __init__(self, client: GitHubClient | None = None):
        self.client = client or GitHubClient()

    def run(self, task: TaskSpec) -> Envelope:
        op = str(task.inputs.get("op", "")).strip()
        try:
            if op == "branches":
                data = [b["name"] for b in self.client.branches()]
            elif op == "pulls":
                data = [pr_summary(p) for p in self.client.pulls(task.inputs.get("state", "open"))]
            elif op == "commits":
                data = [c["commit"]["message"].splitlines()[0] for c in self.client.commits()]
            elif op == "issues":
                data = [f"#{i['number']} {i['title']}" for i in self.client.issues()
                        if "pull_request" not in i]
            elif op == "pull":
                num = task.inputs["number"]
                pr = self.client.pull(num)
                data = {"summary": pr_summary(pr), "pr": {k: pr.get(k) for k in
                        ("number", "title", "state", "additions", "deletions", "changed_files")}}
            elif op in ("summary", "risk"):
                num = task.inputs["number"]
                pr = self.client.pull(num)
                files = self.client.pull_files(num)
                data = pr_summary(pr) if op == "summary" else pr_risk(pr, files)
            else:
                return Envelope(task_id=task.id, status=Status.FAILED,
                                error=f"unknown github op {op!r}")
        except Exception as exc:
            return Envelope(task_id=task.id, status=Status.FAILED,
                            error=f"github_read {op}: {type(exc).__name__}: {exc}")
        return Envelope(task_id=task.id, status=Status.DONE,
                        result={"op": op, "data": data}, logs=[f"github_read {op}"])


class GitHubDraftPRWorker(Worker):
    spec = WorkerSpec(name="github_draft_pr", capabilities=["create_draft_pr"],
                      tool_permissions=["github:write_draft_pr"],
                      safety_class=SafetyClass.EXTERNAL,  # -> Approval Gate; never merge/delete
                      cost_class="moderate",
                      description="Create a DRAFT PR only (approval-gated; never merge/delete).")

    def __init__(self, client: GitHubClient | None = None):
        self.client = client or GitHubClient()

    def run(self, task: TaskSpec) -> Envelope:
        i = task.inputs
        for req in ("title", "head", "base"):
            if not i.get(req):
                return Envelope(task_id=task.id, status=Status.FAILED,
                                error=f"create_draft_pr missing {req!r}")
        try:
            pr = self.client.create_draft_pr(i["title"], i["head"], i["base"], i.get("body", ""))
        except Exception as exc:
            return Envelope(task_id=task.id, status=Status.FAILED,
                            error=f"create_draft_pr: {type(exc).__name__}: {exc}")
        return Envelope(task_id=task.id, status=Status.DONE,
                        result={"number": pr.get("number"), "url": pr.get("html_url"),
                                "draft": pr.get("draft")},
                        logs=["created DRAFT PR (never merged)"])
