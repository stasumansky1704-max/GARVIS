"""
Advisor - autonomy reporting that reduces supervision: turns observations into concrete
goal suggestions, next steps, and an autonomy report. Read-only; the human/loop still
decides what to act on. No execution here.
"""
from __future__ import annotations

from . import selflearn


def suggest_goals(history, memory, limit: int = 5) -> list[dict]:
    """Propose new goals from observed gaps: rephrase repeat-failed / empty goals into
    better queries; surface high-influence decisions worth following up."""
    out, seen = [], set()

    def _add(text, reason):
        key = text.strip().lower()
        if text and key not in seen:
            seen.add(key)
            out.append({"goal": text, "reason": reason})

    for it in selflearn.analyze_empty_results(history)["items"][:limit]:
        if it["suggested_query"]:
            _add(it["suggested_query"], f"empty result for '{it['goal'][:40]}'")
    for it in selflearn.analyze_repeat_failures(history)["items"][:limit]:
        sq = selflearn.rewrite_query(it["goal"], memory)
        _add(sq, f"repeat failure x{it['count']}")
    return out[:limit]


def next_steps(history, audit, memory, goals=None, queue=None, limit: int = 8) -> list[str]:
    """Actionable next steps: due queue items, blocked/ready goals, self-learning actions."""
    steps = []
    if queue is not None:
        due = queue.due_now()
        if due:
            steps.append(f"run {len(due)} due queue item(s) via approved run-due/loop")
    if goals is not None:
        ready = [g for g in goals.prioritized() if goals.is_ready(g["id"])]
        if ready:
            steps.append(f"start top-priority ready goal: '{ready[0]['text'][:40]}'")
        blocked = [g for g in goals.list() if g.get("status") == "blocked"]
        if blocked:
            steps.append(f"unblock {len(blocked)} blocked goal(s)")
    for rec in selflearn.recommend(history, audit)[:3]:
        steps.append(f"[{rec['area']}] {rec['action']}")
    for s in suggest_goals(history, memory, 2):
        steps.append(f"consider goal: '{s['goal'][:40]}' ({s['reason']})")
    return steps[:limit]


def autonomy_report(history, audit, memory, goals=None, queue=None) -> dict:
    """One-call autonomy report: how self-sufficient is GARVIS right now?"""
    from . import metrics
    return {"autonomy": metrics.autonomy_metrics(history, queue, audit) if queue else {},
            "learning_confidence": selflearn.learning_confidence(memory),
            "suggested_goals": suggest_goals(history, memory, 3),
            "next_steps": next_steps(history, audit, memory, goals, queue),
            "open_recommendations": len(selflearn.recommend(history, audit))}
