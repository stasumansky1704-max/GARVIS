"""
Self-learning - GARVIS analyzes its OWN run history + audit log and turns recurring
problems into durable lessons (memory) and actionable recommendations.

This closes a real feedback loop:
- analyze_failures        : failed-run rate + common error families
- analyze_empty_results   : runs that found nothing + a concrete broader-query suggestion
- analyze_weak_plans      : runs that completed but produced little/no signal
- analyze_blocked         : blocked tasks + reasons (from audit)
- analyze_denials         : approval denials (from audit)
- recommend               : structured, machine-usable improvement suggestions (not docs)
- learn                   : writes deduped lessons into memory so future planning improves

All functions are read-only except learn(), which only appends to the memory store.
"""
from __future__ import annotations

import re

from .research_quality import broaden_query, clean_query, extract_terms

# Project tokens whose presence in an empty-result goal is a learnable signal.
_PROJECT_TOKENS = ("garvis", "jarvis", "alphaflow")


def _summary_is_empty(rec: dict) -> bool:
    s = (rec.get("result_summary") or "").lower()
    return (not s) or ("no results found" in s) or ("no findings" in s) or s.startswith("0 ")


def analyze_failures(history) -> dict:
    runs = history.list()
    failed = [r for r in runs if r.get("status") in ("failed", "blocked")]
    families: dict[str, int] = {}
    for r in failed:
        for t in r.get("tasks", []):
            err = (t.get("error") or "").lower()
            if not err:
                continue
            fam = ("approval" if "approval" in err else
                   "safety" if "safety" in err else
                   "network" if ("http" in err or "url" in err or "timeout" in err) else
                   "rate_limit" if "rate limit" in err else
                   "missing_input" if "missing" in err else "other")
            families[fam] = families.get(fam, 0) + 1
    total = len(runs)
    return {"total": total, "failed": len(failed),
            "failure_rate": round(len(failed) / total, 3) if total else 0.0,
            "error_families": families}


def analyze_empty_results(history) -> dict:
    runs = history.list()
    empty = [r for r in runs if r.get("status") == "done" and _summary_is_empty(r)]
    items = []
    for r in empty:
        goal = r.get("goal", "")
        items.append({"id": r.get("id"), "goal": goal,
                      "suggested_query": broaden_query(goal) or " ".join(extract_terms(goal)),
                      "has_project_token": any(t in goal.lower() for t in _PROJECT_TOKENS)})
    return {"empty_runs": len(empty), "items": items,
            "with_project_tokens": sum(1 for i in items if i["has_project_token"])}


def analyze_weak_plans(history) -> dict:
    """Runs that completed but produced little signal (single/zero-task or empty summary)."""
    runs = history.list()
    weak = []
    for r in runs:
        if r.get("status") != "done":
            continue
        tasks = r.get("tasks", [])
        done_tasks = [t for t in tasks if t.get("status") == "done"]
        if _summary_is_empty(r) or (tasks and len(done_tasks) <= 1):
            weak.append({"id": r.get("id"), "goal": r.get("goal", ""),
                         "done_tasks": len(done_tasks)})
    return {"weak_runs": len(weak), "items": weak}


def analyze_blocked(audit) -> dict:
    if audit is None:
        return {"blocked_tasks": 0, "reasons": {}}
    events = [e for e in audit.list() if e.get("kind") == "task_blocked"]
    reasons: dict[str, int] = {}
    for e in events:
        err = (e.get("error") or "unknown").split(":")[0].strip().lower()
        reasons[err] = reasons.get(err, 0) + 1
    return {"blocked_tasks": len(events), "reasons": reasons}


def analyze_denials(audit) -> dict:
    if audit is None:
        return {"approval_denials": 0}
    denied = [e for e in audit.list()
              if e.get("kind") in ("task_blocked", "draft_pr_blocked_empty")
              and "approval" in (e.get("error", "") + e.get("kind", "")).lower()]
    return {"approval_denials": len(denied)}


def analyze_repeat_failures(history) -> dict:
    """Goals that failed/empty more than once - the strongest signal to change approach."""
    counts: dict[str, int] = {}
    for r in history.list():
        if r.get("status") in ("failed", "blocked") or _summary_is_empty(r):
            g = (r.get("goal") or "").strip().lower()
            if g:
                counts[g] = counts.get(g, 0) + 1
    repeats = {g: n for g, n in counts.items() if n >= 2}
    return {"repeat_goals": len(repeats),
            "items": [{"goal": g, "count": n} for g, n in
                      sorted(repeats.items(), key=lambda x: -x[1])]}


def recommend(history, audit) -> list[dict]:
    """Structured, actionable recommendations derived from observed patterns."""
    recs = []
    fails = analyze_failures(history)
    empties = analyze_empty_results(history)
    weak = analyze_weak_plans(history)
    blocked = analyze_blocked(audit)
    if empties["with_project_tokens"]:
        recs.append({"area": "research", "severity": "high",
                     "finding": f"{empties['with_project_tokens']} empty run(s) had "
                                f"project-specific tokens in the goal",
                     "action": "strip project tokens before searching (decompose_smart already "
                               "does this; ensure all research paths use it)"})
    if fails["error_families"].get("network", 0) >= 2:
        recs.append({"area": "reliability", "severity": "medium",
                     "finding": "repeated network errors",
                     "action": "increase retries/backoff and broaden source fallback"})
    if fails["failure_rate"] > 0.3 and fails["total"] >= 3:
        recs.append({"area": "reliability", "severity": "high",
                     "finding": f"failure rate {fails['failure_rate']}",
                     "action": "inspect error_families; add targeted recovery"})
    if weak["weak_runs"] >= 2:
        recs.append({"area": "planning", "severity": "medium",
                     "finding": f"{weak['weak_runs']} weak run(s) with little signal",
                     "action": "increase decomposition breadth / enable broadening retry"})
    if blocked["blocked_tasks"] >= 3:
        recs.append({"area": "autonomy", "severity": "low",
                     "finding": f"{blocked['blocked_tasks']} blocked tasks",
                     "action": "review approval gating and dependency ordering"})
    repeats = analyze_repeat_failures(history)
    if repeats["repeat_goals"]:
        top = repeats["items"][0]
        recs.append({"area": "self-improvement", "severity": "high",
                     "finding": f"{repeats['repeat_goals']} goal(s) failed repeatedly "
                                f"(e.g. '{top['goal'][:40]}' x{top['count']})",
                     "action": "stop retrying as-is; rewrite the query or de-prioritize"})
    return recs


def learn(history, audit, memory) -> list[str]:
    """Write deduped lessons into memory (feedback loop). Returns the lessons written."""
    existing = {m["text"] for m in memory.list()}
    written = []

    def _remember(layer, text, tags):
        if text not in existing:
            memory.add(layer, text, tags=tags, source="self-learned")
            existing.add(text)
            written.append(text)

    empties = analyze_empty_results(history)
    if empties["with_project_tokens"]:
        _remember("rule",
                  "strip project-specific tokens (e.g. GARVIS) from research queries; "
                  "they cause empty results", ["self-learned", "research"])
    for it in empties["items"][:5]:
        if it["suggested_query"]:
            _remember("decision",
                      f"for goal '{it['goal'][:60]}' prefer broader query "
                      f"'{it['suggested_query']}'", ["self-learned", "query"])

    fails = analyze_failures(history)
    if fails["error_families"].get("network", 0) >= 2:
        _remember("rule", "research is network-sensitive; retry with broadened queries and "
                          "fall back across sources", ["self-learned", "reliability"])
    for rec in recommend(history, audit):
        _remember("decision",
                  f"[{rec['area']}] {rec['finding']} -> {rec['action']}",
                  ["self-learned", rec["area"]])
    return written


def rewrite_query(goal: str, memory=None) -> str:
    """Apply self-learned lessons to rewrite a goal into a better research query BEFORE
    planning. Strips project/filler tokens, and if memory holds a specific broader-query
    lesson for a similar goal, prefers that suggestion. Returns a (usually) improved query.

    This is the active half of the feedback loop: empty-result lessons recorded by learn()
    now change how future queries are phrased.
    """
    base = clean_query(goal) or " ".join(extract_terms(goal)) or (goal or "").strip()
    if memory is None:
        return base
    try:
        hits = memory.search(goal, limit=6)
    except Exception:
        return base
    for m in hits:
        text = m.get("text", "")
        if "prefer broader query" in text:
            quoted = re.findall(r"'([^']+)'", text)
            if quoted:
                return quoted[-1]                       # the learned broader query
    return base


def learning_history(memory) -> list[dict]:
    """All self-learned memories, newest last - GARVIS's record of what it has learned."""
    return [{"ts": m.get("ts"), "layer": m["layer"], "text": m["text"],
             "importance": m.get("importance")}
            for m in memory.list() if "self-learned" in (m.get("tags") or [])]


def learning_confidence(memory) -> float:
    """0..1 confidence in accumulated learning: scales with lesson count + avg importance +
    reinforcement (uses)."""
    lessons = [m for m in memory.list() if "self-learned" in (m.get("tags") or [])]
    if not lessons:
        return 0.0
    volume = min(1.0, len(lessons) / 8.0)
    avg_imp = sum(float(m.get("importance", 0.5)) for m in lessons) / len(lessons)
    reinforced = min(1.0, sum(int(m.get("uses", 0)) for m in lessons) / 5.0)
    return round(0.5 * volume + 0.3 * avg_imp + 0.2 * reinforced, 3)


def learning_quality(history, memory) -> dict:
    """Lessons learned vs problems observed - are we actually learning from mistakes?"""
    problems = (analyze_empty_results(history)["empty_runs"]
                + analyze_weak_plans(history)["weak_runs"]
                + analyze_repeat_failures(history)["repeat_goals"])
    lessons = len(learning_history(memory))
    return {"problems": problems, "lessons": lessons,
            "coverage": round(min(1.0, lessons / problems), 3) if problems else 1.0,
            "confidence": learning_confidence(memory)}


def learning_diagnostics(history, audit, memory) -> dict:
    """One-call learning health for the metrics surface."""
    return {"history_count": len(learning_history(memory)),
            "confidence": learning_confidence(memory),
            "quality": learning_quality(history, memory),
            "open_recommendations": len(recommend(history, audit))}


def insights(history, audit) -> dict:
    """One-call snapshot of everything self-learning observed."""
    return {"failures": analyze_failures(history),
            "empty_results": analyze_empty_results(history),
            "weak_plans": analyze_weak_plans(history),
            "blocked": analyze_blocked(audit),
            "denials": analyze_denials(audit),
            "repeat_failures": analyze_repeat_failures(history),
            "recommendations": recommend(history, audit)}
