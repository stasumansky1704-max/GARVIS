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
from orchestrator.decompose import decompose, decompose_smart
from orchestrator.llm_planner import LLMPlanner
from orchestrator import draftpr
from orchestrator.workers.research_worker import ResearchWorker
from orchestrator.workers.docs_worker import DocsWorker
from orchestrator.secret_scan import scan_dir
from orchestrator.memory import MemoryStore, record_run
from orchestrator import generators as gen
from orchestrator import artifacts as artmod
from orchestrator.goals import GoalRegistry
from orchestrator.queue import ResearchQueue
from orchestrator.brief import daily_brief, daily_brief_full, weekly_brief, review_run
from orchestrator import scheduler
from orchestrator import ops
from orchestrator import selflearn
from orchestrator import planning
from orchestrator.workers.github_worker import GitHubReadWorker, GitHubDraftPRWorker


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
    n_cap = max(1, budget.max_tasks - (1 if with_doc else 0))
    n_research = min(n_cap, planning.recommended_task_count(goal, n_cap))  # size to complexity
    subs = decompose(goal, n_research)
    fb = [TaskSpec(id=f"r{i}", worker="research", intent=s, inputs={"query": s})
          for i, s in enumerate(subs)]
    if with_doc:
        fb.append(TaskSpec(id="docs", worker="docs", intent="document findings",
                           inputs={"title": goal}, deps=[t.id for t in fb],
                           needs_approval=True))
    mem = MemoryStore(os.path.join(cfgmod.history_dir(cfg), "memory.jsonl"))
    planner = LLMPlanner(orch.registry) if cfg["default_planner"] == "llm" else None
    run = orch.run_goal(goal, planner=planner, fallback_tasks=fb, approvals=approvals,
                        history=hist, budget=budget, audit=audit,
                        memory_context=mem.planner_context(goal))
    record_run(mem, run)                                 # feedback loop: learn from this run
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


def _stores(cfg):
    hd = cfgmod.history_dir(cfg)
    return (MemoryStore(os.path.join(hd, "memory.jsonl")),
            GoalRegistry(os.path.join(hd, "goals.jsonl")),
            ResearchQueue(os.path.join(hd, "queue.jsonl")),
            RunHistory(os.path.join(hd, "history.jsonl")))


def cmd_memory(rest, cfg):
    mem, *_ = _stores(cfg)
    sub = rest[0] if rest else "list"
    if sub == "add" and len(rest) >= 3:
        print("added:", mem.add(rest[1], " ".join(rest[2:]))); return 0
    if sub == "search" and len(rest) >= 2:
        for r in mem.search(" ".join(rest[1:])):
            print(f"  [{r['layer']}] {r['text']}")
        return 0
    if sub == "compress":
        n = mem.compress()
        print("removed duplicates:", n, "| valid:", mem.validate_compression()["valid"]); return 0
    if sub == "consolidate":
        print("merged near-duplicates:", mem.consolidate()); return 0
    if sub == "decay":
        print("decayed (old/unused):", mem.decay()); return 0
    if sub == "promote" and len(rest) >= 2:
        print("promoted:", mem.promote(rest[1])); return 0
    if sub == "inspect":
        for k, v in mem.inspect().items():
            print(f"  {k}: {v}")
        return 0
    if sub == "export":
        print(mem.export_jsonl()); return 0
    if sub == "expire":
        print("archived (ttl elapsed):", mem.expire()); return 0
    if sub == "delete" and len(rest) >= 2:
        approve = "--approve-delete" in rest
        print(mem.delete(rest[1], approve=approve)); return 0
    for r in mem.list(rest[1] if len(rest) > 1 and not rest[1].startswith("--") else None):
        if r.get("archived"):
            continue
        print(f"  [{r['layer']}] (imp={r.get('importance')}) {r['text']}")
    return 0


def cmd_goal(rest, cfg):
    _, goals, _, _ = _stores(cfg)
    sub = rest[0] if rest else "list"
    if sub == "add" and len(rest) >= 2:
        print("goal:", goals.add(" ".join(rest[1:]))); return 0
    if sub == "status" and len(rest) >= 3:
        print("ok" if goals.set_status(rest[1], rest[2]) else "not found"); return 0
    if sub == "priority" and len(rest) >= 3:
        print("ok" if goals.set_priority(rest[1], int(rest[2])) else "not found"); return 0
    if sub == "progress" and len(rest) >= 3:
        print("ok" if goals.set_progress(rest[1], int(rest[2])) else "not found"); return 0
    if sub == "block" and len(rest) >= 3:
        print("ok" if goals.add_blocker(rest[1], " ".join(rest[2:])) else "not found"); return 0
    if sub == "unblock" and len(rest) >= 2:
        print("ok" if goals.clear_blockers(rest[1]) else "not found"); return 0
    if sub == "review" and len(rest) >= 2:
        print(goals.review(rest[1])); return 0
    if sub == "metrics":
        print(goals.metrics()); return 0
    if sub == "next":
        for g in goals.prioritized():
            print(f"  P{g.get('priority',3)} {g['id']}  [{g.get('progress',0)}%]  {g['text'][:50]}")
        return 0
    for g in goals.list():
        print(f"  {g['id']}  {g.get('status','open'):<11}  P{g.get('priority',3)}  "
              f"{g['text'][:46]}  runs={len(g.get('runs',[]))}")
    return 0


def cmd_queue(rest, cfg):
    _, _, q, _ = _stores(cfg)
    sub = rest[0] if rest else "list"
    if sub == "add" and len(rest) >= 2:
        print("queued:", q.enqueue(" ".join(rest[1:]))); return 0
    if sub == "dry-run":
        for p in q.dry_run():
            print(f"  P{p['priority']} {p['id']}  attempts={p['attempts']}  {p['goal'][:50]}")
        return 0
    for item in q.list():
        print(f"  {item['id']}  {item.get('status','pending'):<8}  P{item.get('priority',3)}  "
              f"{item['goal'][:46]}")
    return 0


def cmd_scheduler(rest, cfg):
    """SAFE dry-run scheduler: show what would run now. Never executes (no daemon)."""
    _, _, q, _ = _stores(cfg)
    out = scheduler.dry_run(q)
    print(f"scheduler [{out['mode']}] - {out['due']} item(s) due:")
    for p in out["plan"]:
        print(f"  P{p['priority']} {p['id']}  attempts={p['attempts']}  {p['goal'][:50]}")
    print("  (dry-run only; execution is explicit and not enabled here)")
    return 0


def cmd_brief(rest, cfg):
    mem, goals, q, hist = _stores(cfg)
    art = cfgmod.artifact_dir(cfg); os.makedirs(art, exist_ok=True)
    if rest and rest[0] == "weekly":
        text = weekly_brief(hist, mem, goals); path = os.path.join(art, "weekly-brief.md")
    else:
        text = daily_brief_full(hist, mem, goals, q); path = os.path.join(art, "daily-brief.md")
    open(path, "w", encoding="utf-8").write(text)
    print(text)
    print("brief written:", path)
    return 0


def cmd_review(rest, cfg):
    if len(rest) < 2:
        print("usage: review <run_id> <rating> [note...]"); return 2
    mem, _, _, hist = _stores(cfg)
    fb = review_run(hist, mem, rest[0], rest[1], " ".join(rest[2:]))
    print("recorded review:", fb)
    return 0


def cmd_github(rest, cfg):
    if is_disabled():
        print("[DISABLED] refusing to run."); return 3
    op = rest[0] if rest else "pulls"
    inputs = {"op": op}
    if len(rest) > 1 and rest[1].isdigit():
        inputs["number"] = int(rest[1])
    env = GitHubReadWorker().run(TaskSpec(id="gh", worker="github_read", intent=op, inputs=inputs))
    if env.status != Status.DONE:
        print("  error:", env.error); return 1
    data = env.result["data"]
    if isinstance(data, list):
        for d in data:
            print("  -", d)
    else:
        print(" ", data)
    return 0


def cmd_propose(goal, cfg):
    """Research a goal then write a change proposal artifact (read-only research)."""
    if is_disabled():
        print("[DISABLED] refusing to run."); return 3
    orch, hist, audit, art = build(cfg)
    sub = decompose(goal, 3)
    fb = [TaskSpec(id=f"r{i}", worker="research", intent=s, inputs={"query": s})
          for i, s in enumerate(sub)]
    run = orch.run_goal(goal, planner=None, fallback_tasks=fb, history=hist,
                        budget=RunBudget.from_config(cfg), audit=audit)
    findings = []
    for e in run.results.values():
        if isinstance(e.result, dict):
            findings.extend(e.result.get("findings", []))
    md = gen.change_proposal(goal, findings)
    path = os.path.join(art, "proposal-" + run.id + ".md")
    os.makedirs(art, exist_ok=True); open(path, "w", encoding="utf-8").write(md)
    print(f"proposal written ({len(findings)} findings):", path)
    return 0


def cmd_artifacts(rest, cfg):
    art = cfgmod.artifact_dir(cfg)
    if rest and rest[0] == "search" and len(rest) >= 2:
        items = artmod.search(art, " ".join(rest[1:]))
    else:
        items = artmod.catalog(art)
    for it in items:
        print(f"  {it['mtime']}  {it['size']:>7}  {it['name']}")
    return 0


def cmd_autodemo(goal, cfg):
    """Full flow: goal -> research -> memory -> proposal doc -> draft-PR content -> review."""
    if is_disabled():
        print("[DISABLED] refusing to run."); return 3
    mem, goals, _, hist = _stores(cfg)
    gid = goals.add(goal); goals.set_status(gid, "in_progress")
    orch, _, audit, art = build(cfg)
    sub = decompose(goal, 4)
    fb = [TaskSpec(id=f"r{i}", worker="research", intent=s, inputs={"query": s})
          for i, s in enumerate(sub)]
    run = orch.run_goal(goal, planner=None, fallback_tasks=fb, history=hist,
                        budget=RunBudget.from_config(cfg), audit=audit,
                        memory_context=mem.planner_context(goal))
    record_run(mem, run)
    findings = [f for e in run.results.values() if isinstance(e.result, dict)
                for f in e.result.get("findings", [])]
    os.makedirs(art, exist_ok=True)
    prop = os.path.join(art, "proposal-" + run.id + ".md")
    open(prop, "w", encoding="utf-8").write(gen.change_proposal(goal, findings))
    pr = gen.draft_pr_content(goal, body=gen.research_summary(run), findings=findings)
    import json as _json
    prpath = os.path.join(art, "draftpr-" + run.id + ".json")
    open(prpath, "w", encoding="utf-8").write(_json.dumps(pr, ensure_ascii=False, indent=2))
    goals.set_status(gid, "done", run_id=run.id)
    review_run(hist, mem, run.id, "auto", "autodemo completed")
    print("=" * 60)
    print(f"  AUTODEMO complete  goal_id={gid}  run={run.id}  status={run.status.value}")
    print(f"  findings: {len(findings)}")
    print(f"  proposal:      {prop}")
    print(f"  draft-PR content: {prpath} (content only; opening a DRAFT PR is approval-gated)")
    print(f"  goal status:   done   |   review recorded in memory")
    print("=" * 60)
    return 0


def _slug(text: str) -> str:
    s = "".join(c.lower() if c.isalnum() else "-" for c in text.strip())
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")[:48] or "proposal"


def cmd_draft_pr(goal, approve, allow_empty, cfg):
    """Research -> quality-checked proposal -> PREVIEW a Draft PR; create ONLY with
    --approve-draft-pr. Empty proposals are blocked unless --allow-empty-proposal.
    Never pushes to main, never merges, never deletes branches."""
    if is_disabled():
        print("[DISABLED] GARVIS_ORCHESTRATOR_DISABLED is set - refusing."); return 3
    orch, hist, audit, art = build(cfg)
    sub = decompose_smart(goal, 5)                    # niche-friendly, broadens for recall
    fb = [TaskSpec(id=f"r{i}", worker="research", intent=s, inputs={"query": s})
          for i, s in enumerate(sub)]
    run = orch.run_goal(goal, planner=None, fallback_tasks=fb, history=hist,
                        budget=RunBudget.from_config(cfg), audit=audit)
    findings = [f for e in run.results.values() if isinstance(e.result, dict)
                for f in e.result.get("findings", [])]
    title = draftpr.clean_title(goal)
    slug = draftpr.safe_slug(goal)
    branch = f"draft/garvis/{slug}-{run.id}"          # safe, length-bounded; never main
    file_path = f"docs/proposals/{slug}-{run.id}.md"
    file_content = gen.change_proposal(goal, findings)
    quality = draftpr.proposal_quality(file_content, findings)
    artifact_link = os.path.relpath(generate_report(run, art))
    content = gen.draft_pr_content(title.replace("draft: ", ""),
                                   body=gen.research_summary(run), findings=findings,
                                   artifact_link=artifact_link)
    content["title"] = title

    print("=" * 64)
    print("  DRAFT PR PREVIEW (dry-run)" if not approve else "  DRAFT PR (CREATING)")
    print("=" * 64)
    print(f"  title   : {content['title']}")
    print(f"  base    : main      (never pushed to / never merged)")
    print(f"  branch  : {branch}")
    print(f"  file    : {file_path}  ({len(file_content)} chars)")
    print(f"  findings: {len(findings)}   proposal quality: {quality['score']}"
          + ("  [EMPTY]" if quality["is_empty"] else ""))
    print(f"  --- dry-run diff preview ---")
    for ln in draftpr.dry_run_diff(file_path, file_content, max_lines=8).splitlines():
        print(f"    {ln}")
    audit.event("draft_pr_preview", goal=goal, branch=branch, title=content["title"],
                quality=quality["score"], findings=len(findings))

    if quality["is_empty"] and not allow_empty:
        print("\n  [BLOCKED] proposal is empty (" + "; ".join(quality["reasons"]) + ").")
        print("  Refusing to create an empty draft PR. Options:")
        print("    - broaden the goal, or")
        print("    - re-run with --allow-empty-proposal to override explicitly.")
        audit.event("draft_pr_blocked_empty", goal=goal, reasons=quality["reasons"])
        return 1

    if not approve:
        print("\n  DRY-RUN: no branch/file/PR created.")
        print("  To create the REAL draft PR, re-run with:  --approve-draft-pr")
        return 0

    env = GitHubDraftPRWorker().run(TaskSpec(id="draftpr", worker="github_draft_pr",
        intent="create draft pr", inputs={"title": content["title"], "base": "main",
        "branch": branch, "file_path": file_path, "file_content": file_content,
        "body": content["body"], "approved": True}))
    if env.status != Status.DONE:
        print("\n  [FAILED/BLOCKED]", env.error); return 1
    number = env.result.get("number")
    for step in env.result.get("steps", []):         # audit each GitHub step
        audit.event("draft_pr_step", step=step, branch=branch)
    audit.event("draft_pr_created", number=number, url=env.result.get("url"), branch=branch)
    hist.save({"id": run.id, "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
               "goal": goal, "status": "draft_pr_created", "tasks": [],
               "result_summary": str(env.result.get("url")), "approvals": ["draft-pr"],
               "draft_pr": {"number": number, "branch": branch, "quality": quality["score"]}})
    mem, *_ = _stores(cfg)
    mem.add("decision", f"opened draft PR #{number} for '{goal}' (branch {branch})",
            tags=["draft-pr", "github"], meta={"number": number, "branch": branch})
    print(f"\n  [OK] DRAFT PR created: {env.result.get('url')}  (draft={env.result.get('draft')})")
    print("\n" + draftpr.rollback_instructions(branch, number))
    return 0


def _build_workflows(cfg, with_github=False):
    """Construct a Workflows facade backed by the real orchestrator (read-only research)."""
    from orchestrator.workflows import Workflows
    from orchestrator.workers.github_worker import GitHubReadWorker
    mem, goals, queue, hist = _stores(cfg)

    def research_fn(goal):
        orch, _, audit, art = build(cfg)
        fb = [TaskSpec(id=f"r{i}", worker="research", intent=s, inputs={"query": s})
              for i, s in enumerate(decompose_smart(goal, 5))]
        run = orch.run_goal(goal, planner=None, fallback_tasks=fb, history=hist,
                            budget=RunBudget.from_config(cfg), audit=audit,
                            memory_context=mem.planner_context(goal))
        findings = [f for e in run.results.values() if isinstance(e.result, dict)
                    for f in e.result.get("findings", [])]
        qual = max((e.result.get("quality", 0.0) for e in run.results.values()
                    if isinstance(e.result, dict)), default=0.0)
        return {"run_id": run.id, "findings": findings,
                "summary": gen.research_summary(run), "quality": qual}

    gh = GitHubReadWorker().client if with_github else None
    return Workflows(research_fn=research_fn, github_client=gh, memory=mem,
                     goals=goals, queue=queue, history=hist)


def cmd_workflow(rest, cfg):
    """Run a real end-to-end workflow from the CLI. Safe by default (no live PR creation)."""
    if is_disabled():
        print("[DISABLED] refusing to run."); return 3
    if not rest:
        from orchestrator.workflows import WORKFLOW_NAMES
        print("usage: cli.py workflow <name> [args]"); print("names:", ", ".join(WORKFLOW_NAMES))
        return 2
    name = rest[0]
    args = rest[1:]
    goal = " ".join(a for a in args if not a.isdigit()).strip()
    needs_gh = name in ("pr-risk",)
    wf = _build_workflows(cfg, with_github=needs_gh)
    if name == "research-to-report":
        out = wf.research_to_report(goal)
    elif name == "research-to-proposal":
        out = wf.research_to_proposal(goal); out.pop("proposal_md", None)
    elif name == "draft-pr-preview":
        out = wf.research_to_draft_pr_preview(goal); out.pop("diff", None)
    elif name == "goal-to-queue":
        out = wf.goal_to_queue(goal)
    elif name == "queue-to-brief":
        out = wf.queue_to_brief(); out["brief"] = "(written)"
    elif name == "review-to-memory" and len(args) >= 2:
        out = wf.review_to_memory(args[0], args[1], " ".join(args[2:]))
    elif name == "planner-context":
        out = wf.memory_to_planner_context(goal)
    elif name == "pr-risk" and args and args[0].isdigit():
        out = wf.github_pr_risk_review(int(args[0]))
    elif name == "safe-demo":
        out = wf.safe_demo(goal or "open source AI agent frameworks")
    else:
        print("unknown/invalid workflow:", name); return 2
    import json as _j
    print(_j.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_insights(cfg):
    """Show what GARVIS has learned about its own runs (failures/empty/weak/blocked)."""
    mem, _, _, hist = _stores(cfg)
    audit = AuditLog(os.path.join(cfgmod.history_dir(cfg), "audit.jsonl"))
    import json as _j
    print(_j.dumps(selflearn.insights(hist, audit), ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_learn(cfg):
    """Analyze own history+audit and write deduped lessons into memory (feedback loop)."""
    mem, _, _, hist = _stores(cfg)
    audit = AuditLog(os.path.join(cfgmod.history_dir(cfg), "audit.jsonl"))
    lessons = selflearn.learn(hist, audit, mem)
    if not lessons:
        print("  no new lessons (already learned or nothing to learn)"); return 0
    print(f"  learned {len(lessons)} lesson(s):")
    for t in lessons:
        print("   -", t)
    return 0


def cmd_verify(cfg):
    """Run all safety regression checks (isolation, no-WDM-KS, no-sd.rec, gitignored, config)."""
    res = ops.verify()
    for c in res["checks"]:
        flag = "OK " if c["ok"] else "FAIL"
        detail = c.get("offenders") or c.get("missing") or c.get("problems") or ""
        print(f"  [{flag}] {c['name']}" + (f"  -> {detail}" if detail else ""))
    print("  => verify:", "PASS" if res["ok"] else "FAIL")
    return 0 if res["ok"] else 1


def cmd_validate(cfg):
    s = ops.validation_summary()
    print("  safety_ok:", s["safety_ok"])
    for name, ok in s["checks"].items():
        print(f"    {name}: {'ok' if ok else 'FAIL'}")
    print(f"  test suites discoverable: {len(s['test_suites'])}")
    for t in s["test_suites"]:
        print("    -", t)
    return 0 if s["safety_ok"] else 1


def cmd_health(cfg):
    h = ops.health()
    print(f"  {h['version']}")
    print(f"  health: {'OK' if h['ok'] else 'DEGRADED'}  ({h['passed']}/{h['total']} checks)")
    if h["failing"]:
        print("  failing:", ", ".join(h["failing"]))
    return 0 if h["ok"] else 1


def cmd_version(cfg):
    for k, v in ops.version_status().items():
        print(f"  {k}: {v}")
    return 0


def cmd_config(rest, cfg):
    sub = rest[0] if rest else "explain"
    if sub == "doctor":
        d = ops.config_doctor()
        print("  config doctor:", "OK" if d["ok"] else "PROBLEMS")
        for p in d.get("problems", []):
            print("   -", p)
        return 0 if d["ok"] else 1
    for k, v in ops.config_explain().items():
        print(f"  {k}: {v}")
    return 0


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
    if cmd == "memory":
        return cmd_memory(rest, cfg)
    if cmd == "goal":
        return cmd_goal(rest, cfg)
    if cmd == "queue":
        return cmd_queue(rest, cfg)
    if cmd == "brief":
        return cmd_brief(rest, cfg)
    if cmd == "scheduler":
        return cmd_scheduler(rest, cfg)
    if cmd == "verify":
        return cmd_verify(cfg)
    if cmd == "validate":
        return cmd_validate(cfg)
    if cmd == "health":
        return cmd_health(cfg)
    if cmd == "version":
        return cmd_version(cfg)
    if cmd == "config":
        return cmd_config(rest, cfg)
    if cmd == "workflow":
        return cmd_workflow(rest, cfg)
    if cmd == "insights":
        return cmd_insights(cfg)
    if cmd == "learn":
        return cmd_learn(cfg)
    if cmd == "review":
        return cmd_review(rest, cfg)
    if cmd == "github":
        return cmd_github(rest, cfg)
    if cmd == "propose" and rest:
        return cmd_propose(" ".join(rest).strip(), cfg)
    if cmd == "artifacts":
        return cmd_artifacts(rest, cfg)
    if cmd == "autodemo" and rest:
        return cmd_autodemo(" ".join(rest).strip(), cfg)
    if cmd == "draft-pr" and rest:
        approve = "--approve-draft-pr" in rest
        allow_empty = "--allow-empty-proposal" in rest
        goal = " ".join(a for a in rest if not a.startswith("--")).strip()
        if not goal:
            print("usage: cli.py draft-pr \"<goal>\" [--approve-draft-pr] [--allow-empty-proposal]")
            return 2
        return cmd_draft_pr(goal, approve, allow_empty, cfg)
    print(__doc__); return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
