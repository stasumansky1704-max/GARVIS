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


def review_run(history, memory, run_id: str, rating: str, note: str = "") -> dict:
    rec = history.get(run_id)
    goal = rec["goal"] if rec else "(unknown run)"
    text = f"review of run {run_id} (goal='{goal}'): rating={rating}. {note}".strip()
    mid = memory.add("decision", text, tags=["review", rating],
                     meta={"run_id": run_id, "rating": rating})
    return {"memory_id": mid, "run_id": run_id, "rating": rating, "note": note,
            "found_run": rec is not None}
