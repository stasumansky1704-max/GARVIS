"""
GARVIS orchestrator CLI - end-to-end, runnable from one command.

  python runtime/orchestrator/cli.py research "best AI coding agents"
  python runtime/orchestrator/cli.py research "..." --doc                 # + approval-gated docs task
  python runtime/orchestrator/cli.py research "..." --doc --approve docs
  python runtime/orchestrator/cli.py history
  python runtime/orchestrator/cli.py show <run_id>
  python runtime/orchestrator/cli.py smoke "<query>"                       # explicit LIVE smoke
  python runtime/orchestrator/cli.py secret-scan                          # scan artifacts/history

Flow: goal -> decomposed into focused research tasks -> LLM planner (fallback) ->
Router (Safety+Approval gates, budgets) -> REAL Research Worker -> Merger -> History +
Audit -> markdown report (gitignored). Read-only research; docs approval-gated; env kill
switch GARVIS_ORCHESTRATOR_DISABLED=1 refuses to run.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # add runtime/

from orchestrator import config as cfgmod
from orchestrator.engine import Orchestrator, RunBudget, is_disabled
from orchestrator.models import TaskSpec, Status
from orchestrator.registry import WorkerRegistry
from orchestrator.history import RunHistory
from orchestrator.audit import AuditLog
from orchestrator.report import generate_report
from orchestrator.decompose import decompose
from orchestrator.llm_planner import LLMPlanner
from orchestrator.workers.research_worker import ResearchWorker
from orchestrator.workers.docs_worker import DocsWorker
from orchestrator.secret_scan import scan_dir


def build(cfg):
    art = cfgmod.artifact_dir(cfg)
    his = cfgmod.history_dir(cfg)
    research = ResearchWorker(max_findings=cfg["limits"]["max_findings"],
                              sources=cfgmod.enabled_sources(cfg))
    docs = DocsWorker(out_dir=art)
    reg = WorkerRegistry()
    reg.register(research.spec)
    reg.register(docs.spec)
    orch = Orchestrator(reg, {"research": research, "docs": docs})
    return orch, RunHistory(os.path.join(his, "history.jsonl")), AuditLog(os.path.join(his, "audit.jsonl")), art


def cmd_research(goal, with_doc, approvals, cfg):
    if is_disabled():
        print("[DISABLED] GARVIS_ORCHESTRATOR_DISABLED is set - refusing to run.")
        return 3
    orch, hist, audit, art = build(cfg)
    budget = RunBudget.from_config(cfg)
    n_research = max(1, budget.max_tasks - (1 if with_doc else 0))
    subs = decompose(goal, n_research)
    fb = [TaskSpec(id=f"r{i}", worker="research", intent=s, inputs={"query": s})
          for i, s in enumerate(subs)]
    if with_doc:
        fb.append(TaskSpec(id="docs", worker="docs", intent="document findings",
                           inputs={"title": goal}, deps=[t.id for t in fb],
                           needs_approval=True))
    planner = LLMPlanner(orch.registry) if cfg["default_planner"] == "llm" else None
    run = orch.run_goal(goal, planner=planner, fallback_tasks=fb, approvals=approvals,
                        history=hist, budget=budget, audit=audit)
    report_path = generate_report(run, art)

    findings_total = sum(len(e.result.get("findings", [])) for e in run.results.values()
                         if isinstance(e.result, dict))
    print("=" * 66)
    print(f"  GARVIS run {run.id}   status={run.status.value}")
    print(f"  goal: {run.goal}")
    print(f"  planner: {cfg['default_planner']} (deterministic decomposition fallback)")
    print(f"  tasks executed: {len(run.results)}   findings: {findings_total}")
    print("=" * 66)
    for tid, env in run.results.items():
        line = f"  [{tid}] {env.status.value}"
        if isinstance(env.result, dict) and "summary" in env.result:
            line += f"  ({env.result['count']} findings)"
        if env.error:
            line += f"  - {env.error}"
        print(line)
    pend = [tid for tid, e in run.results.items()
            if e.status == Status.BLOCKED and e.error and "approval" in e.error.lower()]
    if pend:
        print("  PENDING APPROVAL:", ", ".join(pend), "(re-run with --approve <task_id>)")
    print(f"  report:  {report_path}")
    print(f"  history: {hist.path}")
    print(f"  audit:   {audit.path}")
    return 0


def cmd_history(cfg):
    _, hist, _, _ = build(cfg)
    recs = hist.list()
    print(f"{len(recs)} run(s):")
    for r in recs[-20:]:
        print(f"  {r['id']}  {r['timestamp']}  {r['status']:<8}  {r['goal'][:48]}")
    return 0


def cmd_show(run_id, cfg):
    _, hist, _, _ = build(cfg)
    rec = hist.get(run_id)
    if not rec:
        print("not found:", run_id); return 1
    print(f"run {rec['id']}  {rec['timestamp']}  status={rec['status']}")
    print(f"goal: {rec['goal']}")
    print(f"summary: {rec['result_summary']}")
    print("tasks:")
    for t in rec["tasks"]:
        print(f"  [{t['id']}] {t['status']}" + (f"  {t.get('error')}" if t.get("error") else ""))
    if rec.get("approvals"):
        print("approvals:", ", ".join(rec["approvals"]))
    return 0


def cmd_smoke(query, cfg):
    if is_disabled():
        print("[DISABLED] refusing to run smoke."); return 3
    print("[SMOKE] LIVE network research (explicit). query:", query)
    return cmd_research(query, False, set(), cfg)


def cmd_secret_scan(cfg):
    art = cfgmod.artifact_dir(cfg)
    his = cfgmod.history_dir(cfg)
    hits = scan_dir(art) + scan_dir(his)
    if not hits:
        print("  clean: no obvious secrets in artifacts/history"); return 0
    for fp, name in hits:
        print(f"  [SECRET?] {name} in {fp}")
    return 1


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if not argv:
        print(__doc__); return 0
    try:
        cfg = cfgmod.load_config()
    except cfgmod.ConfigError as exc:
        print("[CONFIG ERROR]", exc); return 2

    cmd = argv[0]
    rest = argv[1:]
    if cmd == "research":
        with_doc = "--doc" in rest
        approvals = set()
        if "--approve" in rest:
            i = rest.index("--approve")
            if i + 1 < len(rest):
                approvals.add(rest[i + 1])
        goal = " ".join(a for a in rest if not a.startswith("--") and a not in approvals).strip()
        if not goal:
            print("usage: cli.py research \"<goal>\" [--doc] [--approve <task>]"); return 2
        return cmd_research(goal, with_doc, approvals, cfg)
    if cmd == "history":
        return cmd_history(cfg)
    if cmd == "show" and rest:
        return cmd_show(rest[0], cfg)
    if cmd == "smoke" and rest:
        return cmd_smoke(" ".join(rest).strip(), cfg)
    if cmd == "secret-scan":
        return cmd_secret_scan(cfg)
    print(__doc__); return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
