"""
Group G - real user workflow tests (offline, deterministic, injected fakes).

Each workflow is exercised end-to-end through the Workflows facade with a fake research
function and a fake GitHub client, proving the composed flows run and stay safe by default
(no live PR creation unless explicitly approved with a client present).

Runs with pytest OR standalone:  python tests/test_user_workflows.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator.workflows import Workflows
from orchestrator.memory import MemoryStore
from orchestrator.goals import GoalRegistry
from orchestrator.queue import ResearchQueue
from orchestrator.history import RunHistory


_FINDINGS = [{"title": "LangGraph", "url": "u1", "source": "wikipedia", "snippet": "agent framework"},
             {"title": "AutoGen", "url": "u2", "source": "duckduckgo", "snippet": "agents"},
             {"title": "CrewAI", "url": "u3", "source": "wikipedia", "snippet": "multi agent"}]


def _research_fn(goal):
    return {"run_id": "run123", "findings": list(_FINDINGS),
            "summary": f"3 findings for {goal}", "quality": 0.8}


def _empty_research_fn(goal):
    return {"run_id": "run000", "findings": [], "summary": "No findings", "quality": 0.0}


class _FakeGH:
    def __init__(self):
        self.created = False
        self._branches = []

    def pull(self, n):
        return {"number": n, "title": "backend change", "changed_files": 40, "additions": 900,
                "mergeable_state": "clean"}

    def pull_files(self, n):
        return [{"filename": "api/server.py"}]

    def branches(self):
        return [{"name": b} for b in self._branches]

    def ref_sha(self, base):
        return "sha"

    def create_branch(self, b, sha):
        self._branches.append(b)

    def get_file(self, b, p):
        raise Exception("404")

    def put_file(self, b, p, t, m):
        pass

    def create_draft_pr(self, title, head, base, body):
        self.created = True
        return {"number": 200, "html_url": "https://x/200", "draft": True}


def _wf(github=None):
    d = tempfile.mkdtemp()
    return Workflows(research_fn=_research_fn, github_client=github,
                     memory=MemoryStore(os.path.join(d, "m.jsonl")),
                     goals=GoalRegistry(os.path.join(d, "g.jsonl")),
                     queue=ResearchQueue(os.path.join(d, "q.jsonl")),
                     history=RunHistory(os.path.join(d, "h.jsonl")))


def test_research_to_report():
    out = _wf().research_to_report("agent frameworks")
    assert out["findings"] == 3 and out["quality"] == 0.8


def test_research_to_proposal_not_empty():
    out = _wf().research_to_proposal("agent frameworks")
    assert "LangGraph" in out["proposal_md"] and out["is_empty"] is False


def test_draft_pr_preview_never_creates():
    out = _wf().research_to_draft_pr_preview("best agent frameworks for GARVIS")
    assert out["created"] is False and out["branch"].startswith("draft/garvis/")
    assert "garvis" not in out["title"].lower()


def test_live_draft_pr_dry_run_by_default():
    gh = _FakeGH()
    out = _wf(github=gh).research_to_live_draft_pr("agent frameworks", approve=False)
    assert out["created"] is False and gh.created is False


def test_live_draft_pr_creates_only_when_approved():
    gh = _FakeGH()
    out = _wf(github=gh).research_to_live_draft_pr("agent frameworks", approve=True)
    assert out["created"] is True and gh.created is True


def test_live_draft_pr_blocks_empty_proposal():
    gh = _FakeGH()
    wf = Workflows(research_fn=_empty_research_fn, github_client=gh,
                   memory=None, goals=None, queue=None, history=None)
    out = wf.research_to_live_draft_pr("obscure", approve=True)
    assert out["created"] is False and "empty" in out.get("blocked", "")
    assert gh.created is False


def test_goal_to_queue():
    out = _wf().goal_to_queue("ship agent core", priority=1)
    assert out["goal_id"] and out["queue_id"]


def test_queue_to_brief():
    wf = _wf()
    wf.queue.enqueue("due research")
    out = wf.queue_to_brief()
    assert "GARVIS daily brief" in out["brief"] and out["due"] >= 1


def test_review_to_memory():
    wf = _wf()
    wf.history.save({"id": "r1", "timestamp": "t", "goal": "g", "status": "done",
                     "tasks": [], "result_summary": "", "approvals": []})
    out = wf.review_to_memory("r1", "good", "useful")
    assert out["found_run"] and wf.memory.list("decision")


def test_memory_to_planner_context():
    wf = _wf()
    wf.memory.add("decision", "langgraph chosen for agents")
    out = wf.memory_to_planner_context("agent frameworks")
    assert "context" in out and "suggested_terms" in out


def test_github_pr_risk_review():
    out = _wf(github=_FakeGH()).github_pr_risk_review(27)
    assert out["risk"]["level"] == "high" and "backend" in out["risk"]["risky_paths"]


def test_safe_demo_has_no_live_actions():
    out = _wf().safe_demo("agent frameworks")
    assert out["live_actions"].startswith("none")
    assert out["draft_pr_preview"]["created"] is False and "health" in out


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
