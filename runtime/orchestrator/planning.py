"""
Planning quality - pure helpers that make the orchestrator plan better and recover better.

- estimate_complexity / recommended_task_count : size a plan to the goal (not a fixed N)
- select_worker        : capability-based worker selection from the registry
- dedupe_tasks         : drop duplicate intents/queries before dispatch
- score_plan / plan_quality : a measurable 0..1 quality score for a task plan
- is_transient_error / classify_error : reliability - decide what is worth retrying

All pure; no I/O. Used by the CLI/engine to build stronger plans and by the router to
recover from transient failures.
"""
from __future__ import annotations

from .research_quality import extract_terms

_CONJUNCTIONS = (" and ", " vs ", " versus ", " compare", " comparison", ",", " or ")
_TRANSIENT = ("timeout", "timed out", "temporarily", "connection", "reset by peer",
              "rate limit", "ratelimit", "503", "502", "504", "429", "urlerror",
              "httperror", "name or service not known", "ssl")


def estimate_complexity(goal: str) -> int:
    """Rough goal complexity 1..5 from significant-term count + conjunctions."""
    g = (goal or "").lower()
    terms = extract_terms(goal)
    score = 1
    score += min(2, len(terms) // 3)
    score += sum(1 for c in _CONJUNCTIONS if c in g)
    return max(1, min(5, score))


def recommended_task_count(goal: str, cap: int = 8) -> int:
    """Plan size proportional to complexity, bounded by the run's task cap."""
    return max(2, min(cap, estimate_complexity(goal) + 1))


def select_worker(intent: str, registry, default: str = "research") -> str:
    """Pick the worker whose capabilities best match an intent (keyword overlap)."""
    words = set(extract_terms(intent, keep_short=True))
    best, best_score = default, 0
    caps = registry.capabilities() if hasattr(registry, "capabilities") else {}
    for name, capabilities in caps.items():
        score = 0
        hay = set()
        for c in capabilities:
            hay |= set(c.replace("_", " ").split())
        score = len(words & hay)
        # direct name mention is a strong signal
        if name in (intent or "").lower():
            score += 3
        if score > best_score:
            best, best_score = name, score
    return best


def dedupe_tasks(tasks: list) -> list:
    """Remove tasks with duplicate (worker,intent) or duplicate query input. Order-preserving."""
    seen = set()
    out = []
    for t in tasks:
        q = (t.inputs or {}).get("query", "")
        key = (t.worker, (t.intent or "").strip().lower(), q.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def score_plan(tasks: list) -> dict:
    """Measurable plan quality 0..1: rewards multiple distinct tasks, penalizes duplicates
    and unrunnable dependencies (deps referencing unknown task ids)."""
    if not tasks:
        return {"score": 0.0, "tasks": 0, "duplicates": 0, "dangling_deps": 0}
    ids = {t.id for t in tasks}
    distinct = len(dedupe_tasks(tasks))
    duplicates = len(tasks) - distinct
    dangling = sum(1 for t in tasks for d in (t.deps or []) if d not in ids)
    breadth = min(1.0, distinct / 4.0)
    penalty = 0.15 * duplicates + 0.25 * dangling
    score = max(0.0, round(0.6 * breadth + 0.4 - penalty, 3))
    return {"score": min(1.0, score), "tasks": len(tasks),
            "duplicates": duplicates, "dangling_deps": dangling}


def plan_quality(tasks: list) -> float:
    return score_plan(tasks)["score"]


def classify_error(msg: str) -> str:
    m = (msg or "").lower()
    if any(t in m for t in ("rate limit", "ratelimit", "429")):
        return "rate_limit"
    if any(t in m for t in _TRANSIENT):
        return "transient"
    if "approval" in m:
        return "approval"
    if "safety" in m:
        return "safety"
    if "missing" in m:
        return "missing_input"
    return "permanent"


def is_transient_error(msg: str) -> bool:
    return classify_error(msg) in ("transient", "rate_limit")
