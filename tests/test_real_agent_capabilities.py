"""
End-to-end real-agent capability tests (offline/deterministic).

Research network is injected (fake fetch) so tests never hit the network; docs writes go
to a temp dir; history goes to a temp file. Validates: research worker, run history, real
docs worker, approval workflow, and the full goal->plan->worker->merge->history flow.

Runs with pytest OR standalone:  python tests/test_real_agent_capabilities.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator.models import TaskSpec, Status
from orchestrator.registry import WorkerRegistry
from orchestrator.engine import Orchestrator
from orchestrator.history import RunHistory, run_to_record
from orchestrator.workers.research_worker import ResearchWorker
from orchestrator.workers.docs_worker import DocsWorker

FAKE = lambda q: ([{"title": "Result A", "url": "https://e/a", "snippet": "alpha",
                    "source": "wikipedia"}], [])


def _orchestrator(tmp):
    research = ResearchWorker(fetch=FAKE)              # no network
    docs = DocsWorker(out_dir=os.path.join(tmp, "artifacts"))
    reg = WorkerRegistry()
    reg.register(research.spec)
    reg.register(docs.spec)
    return Orchestrator(reg, {"research": research, "docs": docs})


# ---------- run history ----------
def test_history_save_get_list():
    with tempfile.TemporaryDirectory() as tmp:
        h = RunHistory(os.path.join(tmp, "h.jsonl"))
        h.save({"id": "r1", "timestamp": "t", "goal": "g1", "status": "done",
                "tasks": [], "result_summary": "s", "approvals": []})
        h.save({"id": "r2", "timestamp": "t", "goal": "g2", "status": "blocked",
                "tasks": [], "result_summary": "", "approvals": []})
        assert len(h.list()) == 2
        assert h.get("r2")["status"] == "blocked"
        assert h.get("nope") is None


# ---------- real docs worker ----------
def test_docs_worker_writes_real_file():
    with tempfile.TemporaryDirectory() as tmp:
        w = DocsWorker(out_dir=tmp)
        env = w.run(TaskSpec(id="d", worker="docs", intent="doc",
                             inputs={"title": "My Report", "body": "hello"}))
        assert env.status == Status.DONE
        path = env.result["path"]
        assert os.path.exists(path)
        assert "# My Report" in open(path, encoding="utf-8").read()


# ---------- end-to-end research ----------
def test_end_to_end_research_flow():
    with tempfile.TemporaryDirectory() as tmp:
        orch = _orchestrator(tmp)
        hist = RunHistory(os.path.join(tmp, "h.jsonl"))
        fb = [TaskSpec(id="research", worker="research", intent="r",
                       inputs={"query": "best ai coding agents"})]
        run = orch.run_goal("best ai coding agents", planner=None, fallback_tasks=fb,
                            history=hist)
        assert run.status == Status.DONE
        env = run.results["research"]
        assert env.status == Status.DONE and env.result["count"] == 1
        # run was persisted to history
        rec = hist.get(run.id)
        assert rec is not None and rec["status"] == "done"
        assert "alpha" in rec["result_summary"]


# ---------- approval workflow visible ----------
def test_end_to_end_docs_blocked_without_approval():
    with tempfile.TemporaryDirectory() as tmp:
        orch = _orchestrator(tmp)
        fb = [
            TaskSpec(id="research", worker="research", intent="r", inputs={"query": "q"}),
            TaskSpec(id="docs", worker="docs", intent="d", inputs={"title": "Doc"},
                     deps=["research"], needs_approval=True),
        ]
        run = orch.run_goal("g", planner=None, fallback_tasks=fb)
        assert run.results["research"].status == Status.DONE
        assert run.results["docs"].status == Status.BLOCKED
        assert "approval" in run.results["docs"].error.lower()
        assert run.status == Status.BLOCKED


def test_end_to_end_docs_runs_with_approval():
    with tempfile.TemporaryDirectory() as tmp:
        orch = _orchestrator(tmp)
        fb = [
            TaskSpec(id="research", worker="research", intent="r", inputs={"query": "q"}),
            TaskSpec(id="docs", worker="docs", intent="d", inputs={"title": "Doc"},
                     deps=["research"], needs_approval=True),
        ]
        run = orch.run_goal("g", planner=None, fallback_tasks=fb, approvals={"docs"})
        assert run.results["docs"].status == Status.DONE
        assert os.path.exists(run.results["docs"].result["path"])


def test_run_to_record_shape():
    with tempfile.TemporaryDirectory() as tmp:
        orch = _orchestrator(tmp)
        fb = [TaskSpec(id="research", worker="research", intent="r", inputs={"query": "q"})]
        run = orch.run_goal("g", planner=None, fallback_tasks=fb)
        rec = run_to_record(run, approvals={"x"})
        for k in ("id", "timestamp", "goal", "status", "tasks", "result_summary", "approvals"):
            assert k in rec
        assert rec["approvals"] == ["x"]


def test_research_worker_default_fetch_is_real():
    # default (no injection) wires the real network fetcher - proves it is not a mock
    from orchestrator.workers.research_worker import real_fetch
    assert ResearchWorker()._fetch is real_fetch


def test_docs_slug_is_filesystem_safe():
    from orchestrator.workers.docs_worker import _slug
    s = _slug("Best: AI/Agents! 2026")
    assert "/" not in s and ":" not in s and " " not in s and s


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
