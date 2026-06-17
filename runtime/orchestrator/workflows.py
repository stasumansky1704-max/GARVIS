"""
Real user workflows - compose the agent-core capabilities into end-to-end flows.

Every workflow is executable from the CLI (`cli.py workflow <name> ...`) and SAFE by
default: research is read-only, draft-PR flows default to dry-run/preview, and the live
draft-PR path stays behind the existing `draft-pr --approve-draft-pr` command.

The Workflows facade takes injectable dependencies so the whole module is testable offline
(no network, no GitHub) - tests pass fakes; the CLI passes the real orchestrator + client.

`research_fn(goal) -> dict` contract:
    {"run_id": str, "findings": list[dict], "summary": str, "quality": float}
"""
from __future__ import annotations

from . import generators as gen
from . import draftpr
from .workers.github_worker import pr_risk


class Workflows:
    def __init__(self, *, research_fn, github_client=None, memory=None, goals=None,
                 queue=None, history=None):
        self._research = research_fn
        self._gh = github_client
        self.memory = memory
        self.goals = goals
        self.queue = queue
        self.history = history

    # 91 - research -> report
    def research_to_report(self, goal: str) -> dict:
        r = self._research(goal)
        return {"workflow": "research_to_report", "run_id": r["run_id"],
                "findings": len(r["findings"]), "quality": r.get("quality", 0.0),
                "summary": r.get("summary", "")}

    # 92 - research -> change proposal
    def research_to_proposal(self, goal: str) -> dict:
        r = self._research(goal)
        md = gen.change_proposal(goal, r["findings"])
        q = draftpr.proposal_quality(md, r["findings"])
        return {"workflow": "research_to_proposal", "run_id": r["run_id"],
                "proposal_md": md, "quality": q["score"], "is_empty": q["is_empty"]}

    # 93 - research -> draft-PR preview (dry-run; never creates)
    def research_to_draft_pr_preview(self, goal: str) -> dict:
        r = self._research(goal)
        title = draftpr.clean_title(goal)
        slug = draftpr.safe_slug(goal)
        branch = f"draft/garvis/{slug}-{r['run_id']}"
        file_path = f"docs/proposals/{slug}-{r['run_id']}.md"
        body = gen.change_proposal(goal, r["findings"])
        q = draftpr.proposal_quality(body, r["findings"])
        return {"workflow": "research_to_draft_pr_preview", "title": title,
                "branch": branch, "file_path": file_path, "base": "main",
                "quality": q["score"], "is_empty": q["is_empty"], "created": False,
                "diff": draftpr.dry_run_diff(file_path, body)}

    # 94 - research -> live draft PR (ONLY when approve=True AND a client is present)
    def research_to_live_draft_pr(self, goal: str, approve: bool = False,
                                  allow_empty: bool = False) -> dict:
        preview = self.research_to_draft_pr_preview(goal)
        if preview["is_empty"] and not allow_empty:
            return {**preview, "created": False,
                    "blocked": "empty proposal (use allow_empty to override)"}
        if not approve or self._gh is None:
            return {**preview, "created": False,
                    "note": "dry-run; create with draft-pr --approve-draft-pr"}
        from .workers.github_worker import GitHubDraftPRWorker
        from .models import TaskSpec
        body = gen.change_proposal(goal, [])  # body content already in file; PR body minimal
        env = GitHubDraftPRWorker(client=self._gh).run(TaskSpec(
            id="wf", worker="github_draft_pr", intent="create draft pr",
            inputs={"title": preview["title"], "base": "main", "branch": preview["branch"],
                    "file_path": preview["file_path"], "file_content": body,
                    "body": preview["title"], "approved": True}))
        ok = getattr(env.status, "value", str(env.status)) == "done"
        return {**preview, "created": ok, "result": env.result, "error": env.error}

    # 95 - goal -> queue
    def goal_to_queue(self, goal: str, priority: int = 3) -> dict:
        gid = self.goals.add(goal, priority=priority)
        qid = self.queue.enqueue(goal, priority=priority)
        return {"workflow": "goal_to_queue", "goal_id": gid, "queue_id": qid}

    # 96 - queue -> brief
    def queue_to_brief(self) -> dict:
        from .brief import daily_brief_full
        text = daily_brief_full(self.history, self.memory, self.goals, self.queue)
        return {"workflow": "queue_to_brief", "brief": text,
                "due": len(self.queue.prioritized_due())}

    # 97 - review -> memory
    def review_to_memory(self, run_id: str, rating: str, note: str = "") -> dict:
        from .brief import review_run
        fb = review_run(self.history, self.memory, run_id, rating, note)
        return {"workflow": "review_to_memory", **fb}

    # 98 - memory -> planner context
    def memory_to_planner_context(self, goal: str) -> dict:
        ctx = self.memory.planner_context(goal)
        return {"workflow": "memory_to_planner_context", "context": ctx,
                "suggested_terms": ctx.get("suggested_terms", [])}

    # 99 - GitHub PR risk review (read-only)
    def github_pr_risk_review(self, number: int) -> dict:
        pr = self._gh.pull(number)
        files = self._gh.pull_files(number)
        return {"workflow": "github_pr_risk_review", "number": number,
                "risk": pr_risk(pr, files)}

    # 100 - end-to-end safe demo (NO live actions)
    def safe_demo(self, goal: str = "open source AI agent frameworks") -> dict:
        from . import ops
        report = self.research_to_report(goal)
        preview = self.research_to_draft_pr_preview(goal)
        return {"workflow": "safe_demo", "health": ops.health(),
                "research": report, "draft_pr_preview": {
                    "branch": preview["branch"], "quality": preview["quality"],
                    "created": False},
                "live_actions": "none (safe demo)"}


WORKFLOW_NAMES = ("research-to-report", "research-to-proposal", "draft-pr-preview",
                  "goal-to-queue", "queue-to-brief", "review-to-memory",
                  "planner-context", "pr-risk", "safe-demo")
