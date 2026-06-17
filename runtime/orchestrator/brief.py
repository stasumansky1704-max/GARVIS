"""
Daily brief + run review - reuse RunHistory and MemoryStore.

daily_brief(history, memory) -> markdown string (recent runs + memory highlights).
review_run(history, memory, run_id, rating, note) -> records human feedback into memory
(so the planner learns) and returns the feedback record.
"""
from __future__ import annotations

import time


def daily_brief(history, memory) -> str:
    runs = history.list()[-10:]
    lines = [f"# GARVIS daily brief - {time.strftime('%Y-%m-%d')}", "",
             f"## Recent runs ({len(runs)})"]
    if not runs:
        lines.append("- (no runs yet)")
    for r in reversed(runs):
        lines.append(f"- `{r['id']}` [{r['status']}] {r['goal'][:60]}")
    rules = memory.list("rule")
    decisions = memory.list("decision")
    lines += ["", "## Active rules", *([f"- {m['text']}" for m in rules] or ["- (none)"]),
              "", "## Recent decisions",
              *([f"- {m['text']}" for m in decisions[-5:]] or ["- (none)"])]
    return "\n".join(lines) + "\n"


def daily_brief_full(history, memory, goals=None, queue=None, audit=None) -> str:
    """Full daily brief: recent runs + due goals + due queue + failed runs + new lessons +
    memory insights + recommended next actions (self-learning)."""
    text = daily_brief(history, memory)
    extra = []
    if goals is not None:
        active = goals.prioritized()[:8]
        extra += ["", "## Active goals (by priority)",
                  *([f"- P{g.get('priority',3)} [{g.get('progress',0)}%] {g['text'][:55]}"
                     for g in active] or ["- (none)"])]
    if queue is not None:
        due = queue.prioritized_due()[:8]
        extra += ["", "## Due research queue",
                  *([f"- {q['goal'][:60]}" for q in due] or ["- (none)"])]
        rws = queue.rewrites()[:8] if hasattr(queue, "rewrites") else []
        if rws:
            extra += ["", "## Self-learned query rewrites",
                      *[f"- '{(r['original'] or '')[:35]}' -> '{(r['rewritten'] or '')[:35]}'"
                        for r in rws]]
    # Failed runs
    failed = [r for r in history.list() if r.get("status") in ("failed", "blocked")][-5:]
    extra += ["", "## Failed / blocked runs",
              *([f"- `{r['id']}` {r.get('goal','')[:55]}" for r in failed] or ["- (none)"])]
    # New lessons (self-learned memory)
    lessons = [m for m in memory.list() if "self-learned" in (m.get("tags") or [])][-5:]
    extra += ["", "## Recent lessons",
              *([f"- {m['text'][:80]}" for m in lessons] or ["- (none)"])]
    # Memory insights
    snap = memory.inspect()
    extra += ["", "## Memory insights",
              f"- {snap['total']} memories | protected {snap['protected']} | "
              f"avg importance {snap['avg_importance']} | dup groups {snap['duplicate_groups']}"]
    # Recommended next actions (self-learning)
    if audit is not None:
        from .selflearn import recommend
        recs = recommend(history, audit)
        extra += ["", "## Recommended next actions",
                  *([f"- [{r['area']}] {r['action']}" for r in recs] or ["- (none)"])]
    return text.rstrip() + "\n" + "\n".join(extra) + "\n"


def weekly_brief(history, memory, goals=None) -> str:
    """Weekly summary: run throughput + status mix + goal completion metrics + key rules."""
    runs = history.list()
    by_status: dict[str, int] = {}
    for r in runs:
        by_status[r.get("status", "?")] = by_status.get(r.get("status", "?"), 0) + 1
    lines = [f"# GARVIS weekly brief - {time.strftime('%Y-%m-%d')}", "",
             f"## Throughput", f"- total runs recorded: {len(runs)}",
             *[f"- {k}: {v}" for k, v in sorted(by_status.items())]]
    if goals is not None:
        m = goals.metrics()
        lines += ["", "## Goals",
                  f"- total: {m.get('total', 0)}  done: {m.get('done', 0)}  "
                  f"completion: {m.get('completion_rate', 0)}"]
    rules = memory.list("rule")
    lines += ["", "## Standing rules", *([f"- {r['text']}" for r in rules[:8]] or ["- (none)"])]
    return "\n".join(lines) + "\n"


def review_run(history, memory, run_id: str, rating: str, note: str = "") -> dict:
    rec = history.get(run_id)
    goal = rec["goal"] if rec else "(unknown run)"
    text = f"review of run {run_id} (goal='{goal}'): rating={rating}. {note}".strip()
    mid = memory.add("decision", text, tags=["review", rating],
                     meta={"run_id": run_id, "rating": rating})
    return {"memory_id": mid, "run_id": run_id, "rating": rating, "note": note,
            "found_run": rec is not None}


def auto_review(history, memory, limit: int = 10) -> dict:
    """Autonomy: auto-rate recent runs not yet reviewed. Empty/failed -> 'weak' (prompts a
    broadening lesson); good runs -> 'auto-good' and reinforce related memory. Idempotent
    per run id (won't re-review)."""
    reviewed = {m.get("meta", {}).get("run_id") for m in memory.list("decision")
                if "review" in (m.get("tags") or [])}
    new = 0
    for rec in history.list()[-limit:]:
        rid = rec.get("id")
        if not rid or rid in reviewed:
            continue
        s = (rec.get("result_summary") or "").lower()
        empty = (not s) or ("no results found" in s) or ("no findings" in s)
        weak = rec.get("status") != "done" or empty
        review_run(history, memory, rid, "weak" if weak else "auto-good",
                   "auto-reviewed: empty/failed" if weak else "auto-reviewed: produced signal")
        reviewed.add(rid)
        new += 1
    return {"reviewed": new}
