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

import base64
import json
import urllib.error
import urllib.request

from .base import Worker
from ..models import TaskSpec, Envelope, Status, SafetyClass
from ..registry import WorkerSpec
from ..draftpr import branch_exists, file_exists_on_branch

DEFAULT_REPO = "stasumansky1704-max/GARVIS"
_RISKY = ("docker", "gpu", "dashboard", "backend", "wdm-ks", "migration", ".env")

# These method names must NEVER exist on the client (merge / delete are forbidden).
FORBIDDEN_CLIENT_METHODS = ("merge", "merge_pr", "merge_pull", "delete_branch",
                            "delete_ref", "delete_file", "delete_pull")


class RateLimitError(RuntimeError):
    """Raised when GitHub signals the API rate limit was hit (handled, never crashes a run)."""


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

    def has_token(self) -> bool:
        """True if a token is available - WITHOUT returning or logging it."""
        if self._token:
            return True
        import os
        import re
        try:
            cred = open(os.path.expanduser("~/.git-credentials")).read()
            return bool(re.search(r"https://[^:]+:([^@]+)@github.com", cred))
        except Exception:
            return False

    def _req(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        url = path if path.startswith("https://") else "https://api.github.com/repos/%s%s" % (self.repo, path)
        req = urllib.request.Request(
            url, data=data,
            headers={"Authorization": "token " + self._tok(),
                     "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429) and "rate limit" in (exc.headers.get("x-ratelimit-remaining", "") + str(exc.reason) + (exc.read().decode("utf-8", "replace") if exc.fp else "")).lower():
                raise RateLimitError("github API rate limit hit")
            raise

    # read-only
    def branches(self): return self._req("GET", "/branches?per_page=100")
    def pulls(self, state="open"): return self._req("GET", "/pulls?state=%s&per_page=50" % state)
    def commits(self): return self._req("GET", "/commits?per_page=10")
    def issues(self): return self._req("GET", "/issues?state=open&per_page=30")
    def pull(self, num): return self._req("GET", "/pulls/%d" % int(num))
    def pull_files(self, num): return self._req("GET", "/pulls/%d/files?per_page=100" % int(num))
    def pull_comments(self, num): return self._req("GET", "/issues/%d/comments?per_page=50" % int(num))
    def get_file(self, branch, path): return self._req("GET", "/contents/%s?ref=%s" % (path, branch))
    def rate_limit(self): return self._req("GET", "https://api.github.com/rate_limit")["resources"]["core"]

    # branch + file ops (needed to back a real DRAFT PR). No merge, no delete.
    def ref_sha(self, branch):
        return self._req("GET", "/git/ref/heads/%s" % branch)["object"]["sha"]

    def create_branch(self, new_branch, from_sha):
        return self._req("POST", "/git/refs",
                         {"ref": "refs/heads/%s" % new_branch, "sha": from_sha})

    def put_file(self, branch, path, text, message):
        return self._req("PUT", "/contents/%s" % path,
                         {"message": message, "branch": branch,
                          "content": base64.b64encode(text.encode("utf-8")).decode("ascii")})

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
    score = 0
    score += 3 if risky else 0
    score += 2 if changed > 30 else (1 if changed > 8 else 0)
    score += 2 if adds > 800 else (1 if adds > 200 else 0)
    score += 1 if pr.get("mergeable_state") == "dirty" else 0
    level = "high" if score >= 3 else ("medium" if score >= 1 else "low")
    return {"level": level, "score": score, "changed_files": changed,
            "additions": adds, "risky_paths": risky,
            "recommendation": ("request changes / manual review" if level == "high"
                               else "review then proceed" if level == "medium"
                               else "low risk")}


def pr_status(pr: dict) -> dict:
    """Compact PR status read (state / draft / merged / mergeability)."""
    return {k: pr.get(k) for k in ("number", "title", "state", "draft", "merged",
                                   "mergeable", "mergeable_state")}


def is_demo_pr(pr: dict) -> bool:
    """Detect a GARVIS demo draft PR (throwaway branch under draft/garvis/)."""
    head = ((pr.get("head") or {}).get("ref")) or pr.get("head_ref") or ""
    return bool(pr.get("draft")) and head.startswith("draft/garvis/")


def cleanup_recommendation(prs: list[dict]) -> list[dict]:
    """Recommend closing demo draft PRs (never auto-acts; advice only)."""
    out = []
    for pr in prs or []:
        if is_demo_pr(pr):
            head = (pr.get("head") or {}).get("ref", "")
            out.append({"number": pr.get("number"), "branch": head,
                        "action": "close draft PR (do not merge); optionally delete branch",
                        "safe": True})
    return out


def branch_is_stale(last_commit_iso: str, days: int = 30, now_iso: str | None = None) -> bool:
    """True if a branch's last commit is older than `days` (string ISO compare, UTC)."""
    import time as _t
    if not last_commit_iso:
        return False
    try:
        last = _t.mktime(_t.strptime(last_commit_iso[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return False
    now = _t.time() if not now_iso else _t.mktime(_t.strptime(now_iso[:19], "%Y-%m-%dT%H:%M:%S"))
    return (now - last) > days * 86400


class GitHubReadWorker(Worker):
    spec = WorkerSpec(name="github_read", capabilities=["branches", "pulls", "commits",
                      "issues", "pull", "summary", "risk", "status", "comments",
                      "open_prs", "closed_prs", "cleanup", "ratelimit"],
                      tool_permissions=["github:read"],
                      safety_class=SafetyClass.READ, cost_class="cheap",
                      description="Read-only GitHub inspection (branches/PRs/commits/issues/risk/status/cleanup).")

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
            elif op == "status":
                data = pr_status(self.client.pull(task.inputs["number"]))
            elif op == "comments":
                data = [f"{c.get('user',{}).get('login','?')}: {c.get('body','')[:120]}"
                        for c in self.client.pull_comments(task.inputs["number"])]
            elif op in ("open_prs", "closed_prs"):
                state = "open" if op == "open_prs" else "closed"
                data = [pr_summary(p) for p in self.client.pulls(state)]
            elif op == "cleanup":
                data = cleanup_recommendation(self.client.pulls("open"))
            elif op == "ratelimit":
                data = self.client.rate_limit()
            elif op in ("summary", "risk"):
                num = task.inputs["number"]
                pr = self.client.pull(num)
                files = self.client.pull_files(num)
                data = pr_summary(pr) if op == "summary" else pr_risk(pr, files)
            else:
                return Envelope(task_id=task.id, status=Status.FAILED,
                                error=f"unknown github op {op!r}")
        except RateLimitError as exc:
            return Envelope(task_id=task.id, status=Status.BLOCKED,
                            error=f"github rate limit: {exc}", logs=["rate-limited; try later"])
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

    def __init__(self, client: GitHubClient | None = None, max_ops: int = 8):
        self.client = client or GitHubClient()
        self.max_ops = max_ops              # GitHub operation budget per run

    def run(self, task: TaskSpec) -> Envelope:
        i = task.inputs
        base = i.get("base", "main")
        if base == "main" and i.get("branch") in (None, "main", "master"):
            pass  # branch defaulting handled below
        title = i.get("title")
        branch = i.get("branch") or i.get("head")
        if not title or not branch:
            return Envelope(task_id=task.id, status=Status.FAILED,
                            error="draft PR requires 'title' and 'branch'")
        if branch in ("main", "master") or base == branch:
            return Envelope(task_id=task.id, status=Status.FAILED,
                            error="refusing: draft branch must differ from base (never write main)")
        preview = {"title": title, "base": base, "branch": branch,
                   "file_path": i.get("file_path"), "draft": True,
                   "will_merge": False, "will_delete_branch": False}
        # DRY-RUN unless explicitly approved -> no side effects, just the preview.
        if not i.get("approved"):
            return Envelope(task_id=task.id, status=Status.BLOCKED,
                            error="dry-run: draft PR creation requires explicit approval",
                            result={"preview": preview},
                            logs=["DRY-RUN preview (no branch/file/PR created)"])
        makes_file = bool(i.get("file_path") and i.get("file_content") is not None)
        needed = (2 if makes_file else 0) + 3 + 1  # dup-check + ref/branch/file + create_pr
        if needed > self.max_ops:
            return Envelope(task_id=task.id, status=Status.FAILED,
                            error=f"github op budget {self.max_ops} too small (need {needed})")
        steps: list[str] = []
        try:
            # Duplicate detection: never create a second identical branch / proposal file.
            if branch_exists(self.client, branch):
                return Envelope(task_id=task.id, status=Status.BLOCKED,
                                error=f"duplicate: branch {branch!r} already exists",
                                result={"preview": preview}, logs=["duplicate branch"])
            if makes_file:
                sha = self.client.ref_sha(base); steps.append("ref_sha")
                self.client.create_branch(branch, sha); steps.append("create_branch")  # never main
                if file_exists_on_branch(self.client, branch, i["file_path"]):
                    return Envelope(task_id=task.id, status=Status.BLOCKED,
                                    error=f"duplicate: file {i['file_path']!r} already on branch",
                                    result={"branch": branch}, logs=steps)
                self.client.put_file(branch, i["file_path"], i["file_content"],
                                     "docs(proposal): %s" % title); steps.append("put_file")
            pr = self.client.create_draft_pr(title, branch, base, i.get("body", ""))
            steps.append("create_draft_pr")
        except RateLimitError as exc:
            return Envelope(task_id=task.id, status=Status.BLOCKED,
                            error=f"github rate limit: {exc}", logs=steps + ["rate-limited"])
        except Exception as exc:
            return Envelope(task_id=task.id, status=Status.FAILED,
                            error=f"create_draft_pr: {type(exc).__name__}: {exc}", logs=steps)
        return Envelope(task_id=task.id, status=Status.DONE,
                        result={"number": pr.get("number"), "url": pr.get("html_url"),
                                "draft": pr.get("draft"), "branch": branch, "base": base,
                                "steps": steps},
                        logs=steps + ["created DRAFT PR (never merged, never deleted branch)"])
