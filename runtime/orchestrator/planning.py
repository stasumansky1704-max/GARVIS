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


def topic_centrality(memory) -> list[dict]:
    """Rank memory topics by centrality (cluster size). Returns [{topic, terms, score}]."""
    try:
        topics = memory.topics()
    except Exception:
        return []
    total = sum(t["size"] for t in topics) or 1
    return [{"topic": t["topic"], "terms": t["topic"].split(),
             "score": round(t["size"] / total, 3)} for t in topics]


def rank_queries_by_centrality(queries: list[str], memory) -> list[str]:
    """Order queries so those touching the most central memory topics come first.
    Stable for queries with no topic signal (keeps original order)."""
    central = topic_centrality(memory)
    if not central:
        return list(queries)
    weight = {}
    for c in central:
        for term in c["terms"]:
            weight[term] = max(weight.get(term, 0.0), c["score"])

    def qscore(q):
        toks = set(extract_terms(q, keep_short=True))
        return sum(weight.get(t, 0.0) for t in toks)

    return [q for _, q in sorted(enumerate(queries),
            key=lambda iq: (-qscore(iq[1]), iq[0]))]


def multi_strategy_decompose(goal: str, memory=None, max_tasks: int = 5) -> dict:
    """Combine multiple decomposition strategies (smart + graph + facet), dedup, and rank
    by topic centrality. Returns {queries, strategies_used} - measurably broader than one."""
    from .decompose import decompose_smart, decompose_graph, decompose
    strategies = {"smart": decompose_smart(goal, max_tasks),
                  "facet": decompose(goal, max_tasks)}
    if memory is not None:
        strategies["graph"] = decompose_graph(goal, memory, max_tasks)
    merged, seen = [], set()
    for qs in strategies.values():
        for q in qs:
            if q and q.lower() not in seen:
                seen.add(q.lower())
                merged.append(q)
    if memory is not None:
        merged = rank_queries_by_centrality(merged, memory)
    return {"queries": merged[:max_tasks],
            "strategies_used": [k for k, v in strategies.items() if v]}


def planning_confidence(tasks: list, memory=None, goal: str = "") -> float:
    """0..1 confidence in a plan: blends plan quality, memory coverage of the goal, and
    whether the task count matches the goal's complexity."""
    pq = plan_quality(tasks)
    coverage = 0.0
    if memory is not None and goal:
        try:
            ctx = memory.planner_context(goal)
            signal = len(ctx.get("relevant", [])) + len(ctx.get("graph_terms", []))
            coverage = min(1.0, signal / 5.0)
        except Exception:
            coverage = 0.0
    want = recommended_task_count(goal, cap=max(2, len(tasks) or 2)) if goal else len(tasks)
    fit = 1.0 - min(1.0, abs(len(tasks) - want) / max(1, want))
    return round(0.5 * pq + 0.3 * coverage + 0.2 * fit, 3)


def self_review(tasks: list) -> dict:
    """Planner self-review: surface concrete plan issues before dispatch."""
    issues = []
    sp = score_plan(tasks)
    if not tasks:
        issues.append("empty plan")
    if sp["duplicates"]:
        issues.append(f"{sp['duplicates']} duplicate task(s)")
    if sp["dangling_deps"]:
        issues.append(f"{sp['dangling_deps']} task(s) depend on unknown ids")
    if len(tasks) == 1:
        issues.append("single-task plan (low breadth)")
    return {"ok": not issues, "issues": issues, "score": sp["score"]}


def explain_plan(goal: str, tasks: list, memory=None) -> dict:
    """Human-readable explanation of WHY this plan (queries, strategies, confidence)."""
    return {"goal": goal, "tasks": len(tasks),
            "queries": [(t.inputs or {}).get("query", t.intent) for t in tasks],
            "confidence": planning_confidence(tasks, memory, goal),
            "complexity": estimate_complexity(goal),
            "review": self_review(tasks),
            "central_topics": [c["topic"] for c in topic_centrality(memory)][:3]
                              if memory is not None else []}


def planning_diagnostics(tasks: list, memory=None, goal: str = "") -> dict:
    """Aggregate planning health for the metrics surface."""
    return {"plan_quality": plan_quality(tasks),
            "confidence": planning_confidence(tasks, memory, goal),
            "review": self_review(tasks),
            "complexity": estimate_complexity(goal) if goal else 0}


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
