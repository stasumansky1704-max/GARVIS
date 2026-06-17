"""
GARVIS orchestrator CLI - end-to-end, runnable from one command.

    python runtime/orchestrator/cli.py research "best AI coding agents"
    python runtime/orchestrator/cli.py research "..." --doc          # add a docs task (needs approval)
    python runtime/orchestrator/cli.py research "..." --doc --approve docs
    python runtime/orchestrator/cli.py history
    python runtime/orchestrator/cli.py show <run_id>

Flow:  goal -> LLM Planner (fallback to a research task) -> Router (Safety+Approval gates)
       -> Research Worker (REAL, read-only) -> Merger -> Run History -> printed report.

No backend wiring; research is read-only web; docs is approval-gated and writes only to a
gitignored artifacts dir.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # add runtime/

from orchestrator.engine import Orchestrator
from orchestrator.models import TaskSpec, Status
from orchestrator.registry import WorkerRegistry
from orchestrator.history import RunHistory
from orchestrator.llm_planner import LLMPlanner
from orchestrator.workers.research_worker import ResearchWorker
from orchestrator.workers.docs_worker import DocsWorker


def build():
    research, docs = ResearchWorker(), DocsWorker()
    reg = WorkerRegistry()
    reg.register(research.spec)
    reg.register(docs.spec)
    workers = {research.spec.name: research, docs.spec.name: docs}
    return Orchestrator(reg, workers), RunHistory()


def _print_report(run, history_path):
    print("=" * 64)
    print(f"  GARVIS run {run.id}  status={run.status.value}")
    print(f"  goal: {run.goal}")
    print("=" * 64)
    for tid, env in run.results.items():
        print(f"  [{tid}] {env.status.value}" + (f"  ({env.error})" if env.error else ""))
        res = env.result if isinstance(env.result, dict) else None
        if res and "summary" in res:
            print(f"      {res['summary']}")
            for f in (res.get("findings") or [])[:5]:
                print(f"        - {f.get('title','')}  {f.get('url','')}")
        if res and res.get("action") == "wrote_doc":
            print(f"      doc written: {res['path']}")
    pend = [tid for tid, e in run.results.items()
            if e.status == Status.BLOCKED and e.error and "approval" in e.error.lower()]
    if pend:
        print("  PENDING APPROVAL:", ", ".join(pend),
              "(re-run with --approve <task_id>)")
    print(f"  saved to history: {history_path}")


def cmd_research(goal: str, with_doc: bool, approvals: set[str]) -> int:
    orch, hist = build()
    fb = [TaskSpec(id="research", worker="research", intent="research the goal",
                   inputs={"query": goal})]
    if with_doc:
        fb.append(TaskSpec(id="docs", worker="docs", intent="document findings",
                           inputs={"title": goal}, deps=["research"], needs_approval=True))
    planner = LLMPlanner(orch.registry)
    run = orch.run_goal(goal, planner=planner, fallback_tasks=fb,
                        approvals=approvals, history=hist)
    _print_report(run, hist.path)
    return 0


def cmd_history() -> int:
    _, hist = build()
    recs = hist.list()
    print(f"{len(recs)} run(s):")
    for r in recs[-20:]:
        print(f"  {r['id']}  {r['timestamp']}  {r['status']:<8}  {r['goal'][:50]}")
    return 0


def cmd_show(run_id: str) -> int:
    _, hist = build()
    rec = hist.get(run_id)
    if not rec:
        print("not found:", run_id); return 1
    import json
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if not argv:
        print(__doc__); return 0
    cmd = argv[0]
    if cmd == "research":
        rest = argv[1:]
        with_doc = "--doc" in rest
        approvals = set()
        if "--approve" in rest:
            i = rest.index("--approve")
            if i + 1 < len(rest):
                approvals.add(rest[i + 1])
        goal = " ".join(a for a in rest if not a.startswith("--")
                        and a not in approvals)
        if not goal.strip():
            print("usage: cli.py research \"<goal>\" [--doc] [--approve <task>]"); return 2
        return cmd_research(goal.strip(), with_doc, approvals)
    if cmd == "history":
        return cmd_history()
    if cmd == "show" and len(argv) > 1:
        return cmd_show(argv[1])
    print(__doc__); return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
