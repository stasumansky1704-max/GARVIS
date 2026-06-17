"""
Super-sprint capability tests (offline/deterministic): memory, generators, artifacts,
github (mocked client), router evolution (retry + prioritization), autonomy (goals,
queue, brief, review).

Runs with pytest OR standalone:  python tests/test_super_sprint.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator.memory import MemoryStore, record_run
from orchestrator import generators as gen
from orchestrator import artifacts as art
from orchestrator.models import TaskSpec, Status, SafetyClass, Run, Envelope, Plan
from orchestrator.registry import WorkerRegistry, WorkerSpec
from orchestrator.gates import SafetyGate, ApprovalGate
from orchestrator.router import TaskRouter
from orchestrator.workers.github_worker import (GitHubReadWorker, GitHubDraftPRWorker,
                                                pr_summary, pr_risk)
from orchestrator.goals import GoalRegistry
from orchestrator.queue import ResearchQueue
from orchestrator.brief import daily_brief, review_run
from orchestrator.history import RunHistory


# ---------- Group A: memory ----------
def test_memory_add_get_list():
    with tempfile.TemporaryDirectory() as t:
        m = MemoryStore(os.path.join(t, "m.jsonl"))
        mid = m.add("rule", "no WDM-KS ever", tags=["safety"])
        assert m.get(mid)["text"] == "no WDM-KS ever"
        assert len(m.list("rule")) == 1


def test_memory_search():
    with tempfile.TemporaryDirectory() as t:
        m = MemoryStore(os.path.join(t, "m.jsonl"))
        m.add("decision", "use ElevenLabs for English voice")
        m.add("decision", "Hebrew TTS deferred to dedicated provider")
        hits = m.search("hebrew voice provider")
        assert hits and "Hebrew" in hits[0]["text"]


def test_memory_compress_dedup():
    with tempfile.TemporaryDirectory() as t:
        m = MemoryStore(os.path.join(t, "m.jsonl"))
        m.add("rule", "same", confidence=0.5)
        m.add("rule", "same", confidence=0.9)
        removed = m.compress()
        assert removed == 1 and len(m.list("rule")) == 1
        assert m.list("rule")[0]["confidence"] == 0.9


def test_memory_planner_context():
    with tempfile.TemporaryDirectory() as t:
        m = MemoryStore(os.path.join(t, "m.jsonl"))
        m.add("rule", "always require approval for writes")
        m.add("user", "owner is Stas; concise")
        m.add("decision", "research best avatar tools")
        ctx = m.planner_context("avatar tools")
        assert ctx["rules"] and ctx["user"] and "relevant" in ctx


def test_memory_record_run_feedback():
    with tempfile.TemporaryDirectory() as t:
        m = MemoryStore(os.path.join(t, "m.jsonl"))
        run = Run(id="r1", goal="g", status=Status.DONE)
        run.results = {"x": Envelope("x", Status.DONE, result={"summary": "found 3"})}
        record_run(m, run)
        assert m.list("run") and "found 3" in m.list("run")[0]["text"]


# ---------- Group B: generators + artifacts ----------
def _run_with_findings():
    run = Run(id="r1", goal="best agents", status=Status.DONE)
    run.results = {"r0": Envelope("r0", Status.DONE, result={"query": "best agents",
                   "findings": [{"title": "LangGraph", "url": "u", "source": "wikipedia"}],
                   "summary": "s", "count": 1})}
    return run


def test_generators_markdown():
    md = gen.markdown("Title", [("A", "alpha"), ("B", "beta")])
    assert md.startswith("# Title") and "## A" in md and "beta" in md


def test_research_summary():
    s = gen.research_summary(_run_with_findings())
    assert "LangGraph" in s and "1 findings" in s


def test_change_proposal():
    md = gen.change_proposal("pick agent fw", [{"title": "LangGraph", "source": "w"}])
    assert "Change proposal" in md and "Recommendation" in md and "LangGraph" in md


def test_draft_pr_content():
    d = gen.draft_pr_content("Add X", body="do X", findings=[{"title": "t", "url": "u"}])
    assert d["draft"] is True and d["title"].startswith("draft:") and d["branch"].startswith("draft/")


def test_artifacts_catalog_and_search():
    with tempfile.TemporaryDirectory() as t:
        open(os.path.join(t, "report-1.md"), "w").write("LangGraph is great")
        open(os.path.join(t, "note.md"), "w").write("unrelated")
        assert len(art.catalog(t)) == 2
        hits = art.search(t, "langgraph")
        assert len(hits) == 1 and hits[0]["name"] == "report-1.md"


# ---------- Group C: github (mocked client) ----------
class _FakeGH:
    def branches(self): return [{"name": "main"}, {"name": "feature/x"}]
    def pulls(self, state="open"): return [{"number": 7, "title": "PR7", "state": "open",
                                            "user": {"login": "stas"}, "additions": 10,
                                            "deletions": 2, "changed_files": 3}]
    def commits(self): return [{"commit": {"message": "fix: a\n\nbody"}}]
    def issues(self): return [{"number": 5, "title": "bug"}]
    def pull(self, n): return {"number": n, "title": "Big", "state": "open",
                               "additions": 900, "deletions": 5, "changed_files": 40,
                               "user": {"login": "s"}}
    def pull_files(self, n): return [{"filename": "docker-compose.yml"}]
    def create_draft_pr(self, title, head, base, body):
        return {"number": 99, "html_url": "https://x/99", "draft": True}


def test_github_read_branches():
    w = GitHubReadWorker(client=_FakeGH())
    env = w.run(TaskSpec(id="g", worker="github_read", intent="b", inputs={"op": "branches"}))
    assert env.status == Status.DONE and "main" in env.result["data"]


def test_github_pr_summary_and_risk():
    assert "#7" in pr_summary(_FakeGH().pulls()[0])
    risk = pr_risk(_FakeGH().pull(1), _FakeGH().pull_files(1))
    assert risk["level"] == "high" and "docker" in risk["risky_paths"]


def test_github_unknown_op_failed():
    w = GitHubReadWorker(client=_FakeGH())
    env = w.run(TaskSpec(id="g", worker="github_read", intent="?", inputs={"op": "nope"}))
    assert env.status == Status.FAILED


def test_github_draft_pr_worker():
    w = GitHubDraftPRWorker(client=_FakeGH())
    dry = w.run(TaskSpec(id="g", worker="github_draft_pr", intent="pr",
                         inputs={"title": "t", "branch": "h", "base": "main", "body": "b"}))
    assert dry.status == Status.BLOCKED          # no approval -> dry-run, no side effects
    env = w.run(TaskSpec(id="g", worker="github_draft_pr", intent="pr",
                         inputs={"title": "t", "branch": "h", "base": "main", "body": "b",
                                 "approved": True}))
    assert env.status == Status.DONE and env.result["draft"] is True and env.result["number"] == 99


def test_github_draft_pr_requires_approval_classding():
    # safety_class EXTERNAL => approval gate must clear it
    assert GitHubDraftPRWorker.spec.safety_class == SafetyClass.EXTERNAL


# ---------- Group D: router evolution ----------
class _Flaky:
    spec = WorkerSpec(name="flaky", capabilities=["x"], safety_class=SafetyClass.READ)

    def __init__(self): self.calls = 0
    def run(self, task):
        self.calls += 1
        if self.calls < 3:
            return Envelope(task.id, Status.FAILED, error="transient")
        return Envelope(task.id, Status.DONE, result={"ok": True})


def test_router_read_worker_retries():
    reg = WorkerRegistry(); reg.register(_Flaky.spec)
    router = TaskRouter(reg, SafetyGate(), ApprovalGate())
    flaky = _Flaky()
    res = router.dispatch(Plan(run_id="r", goal="g",
                          tasks=[TaskSpec(id="t", worker="flaky", intent="x")]),
                          workers={"flaky": flaky})
    assert res["t"].status == Status.DONE and flaky.calls == 3


def test_router_prioritizes_reads_before_writes():
    order = []

    class _Rec:
        def __init__(self, name, sc):
            self.spec = WorkerSpec(name=name, capabilities=["x"], safety_class=sc)
        def run(self, task):
            order.append(task.worker)
            return Envelope(task.id, Status.DONE)

    reg = WorkerRegistry()
    rd = _Rec("rd", SafetyClass.READ); wr = _Rec("wr", SafetyClass.WRITE)
    reg.register(rd.spec); reg.register(wr.spec)
    router = TaskRouter(reg, SafetyGate(), ApprovalGate(approved={"w"}))
    plan = Plan(run_id="r", goal="g", tasks=[
        TaskSpec(id="w", worker="wr", intent="x"),
        TaskSpec(id="r", worker="rd", intent="x"),
    ])
    router.dispatch(plan, workers={"rd": rd, "wr": wr})
    assert order[0] == "rd"                       # read ran before write


# ---------- Group E: autonomy ----------
def test_goal_registry_status_metrics():
    with tempfile.TemporaryDirectory() as t:
        g = GoalRegistry(os.path.join(t, "g.jsonl"))
        gid = g.add("ship orchestrator")
        g.set_status(gid, "done", run_id="run1")
        goals = g.list()
        assert goals[0]["status"] == "done" and "run1" in goals[0]["runs"]
        assert g.metrics()["done"] == 1 and g.metrics()["completion_rate"] == 1.0


def test_research_queue():
    with tempfile.TemporaryDirectory() as t:
        q = ResearchQueue(os.path.join(t, "q.jsonl"))
        qid = q.enqueue("research X")
        assert len(q.pending()) == 1 and len(q.due_now()) == 1
        q.mark_done(qid, run_id="r1")
        assert len(q.pending()) == 0


def test_daily_brief():
    with tempfile.TemporaryDirectory() as t:
        h = RunHistory(os.path.join(t, "h.jsonl"))
        h.save({"id": "r1", "timestamp": "t", "goal": "g1", "status": "done",
                "tasks": [], "result_summary": "", "approvals": []})
        m = MemoryStore(os.path.join(t, "m.jsonl"))
        m.add("rule", "no WDM-KS")
        brief = daily_brief(h, m)
        assert "daily brief" in brief and "r1" in brief and "no WDM-KS" in brief


def test_review_run_writes_memory():
    with tempfile.TemporaryDirectory() as t:
        h = RunHistory(os.path.join(t, "h.jsonl"))
        h.save({"id": "r1", "timestamp": "t", "goal": "g1", "status": "done",
                "tasks": [], "result_summary": "", "approvals": []})
        m = MemoryStore(os.path.join(t, "m.jsonl"))
        fb = review_run(h, m, "r1", "good", "useful findings")
        assert fb["found_run"] and m.list("decision")
        assert "good" in m.list("decision")[0]["text"]


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
