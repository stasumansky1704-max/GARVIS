"""
Graph-aware planning + schedule-to-loop integration tests (offline, deterministic).

Covers: memory graph_terms / related_context / graph-aware planner_context, graph-aware
decomposition, durable self-learned rewrites as goal/queue defaults, schedule->loop
auto-enqueue + audit event.

Runs with pytest OR standalone:  python tests/test_graph_planning.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator.memory import MemoryStore
from orchestrator.decompose import decompose_graph, decompose_smart
from orchestrator.goals import GoalRegistry
from orchestrator.queue import ResearchQueue
from orchestrator.schedule import ScheduleStore
from orchestrator.audit import AuditLog
from orchestrator import autonomy, selflearn


def _tmp(n):
    return os.path.join(tempfile.mkdtemp(), n)


def _graph_memory():
    m = MemoryStore(_tmp("m.jsonl"))
    a = m.add("decision", "langgraph is a strong agent framework")
    b = m.add("decision", "langgraph supports stateful multi-agent orchestration")
    m.add("decision", "unrelated note about pasta recipes")
    m.link(a, b, "related")
    return m, a, b


# ---------- Track 1: graph-aware planner context ----------
def test_graph_terms_pulls_from_linked_memories():
    m, a, b = _graph_memory()
    terms = m.graph_terms("langgraph agent framework")
    assert any(t in ("stateful", "orchestration", "multi") for t in terms)


def test_related_context_returns_neighbors():
    m, a, b = _graph_memory()
    rc = m.related_context("langgraph agent framework")
    assert any("orchestration" in t for t in rc)


def test_planner_context_has_graph_fields():
    m, a, b = _graph_memory()
    ctx = m.planner_context("langgraph agent framework")
    assert "graph_terms" in ctx and "related" in ctx and "topics" in ctx


def test_planner_context_topics_present_after_autolink():
    m, a, b = _graph_memory()
    ctx = m.planner_context("agent framework")
    assert isinstance(ctx["topics"], list)


# ---------- Track 2: graph-aware decomposition ----------
def test_decompose_graph_enriches_with_graph_terms():
    m, a, b = _graph_memory()
    qs = decompose_graph("langgraph agent framework", m, 5)
    smart = decompose_smart("langgraph agent framework", 5)
    assert qs != smart                                   # graph added an enriched query
    assert qs[0] != smart[0] or len(qs) >= len(smart)


def test_decompose_graph_falls_back_without_memory():
    qs = decompose_graph("agent framework", None, 5)
    assert qs == decompose_smart("agent framework", 5)


def test_decompose_graph_no_graph_terms_uses_smart():
    m = MemoryStore(_tmp("m.jsonl"))                     # empty memory -> no graph terms
    qs = decompose_graph("agent framework", m, 5)
    assert qs == decompose_smart("agent framework", 5)


# ---------- Track 3: durable self-learned rewrites ----------
def test_queue_enqueue_applies_rewrite_and_stores_original():
    q = ResearchQueue(_tmp("q.jsonl"))
    qid = q.enqueue("best agents for GARVIS",
                    rewrite_fn=lambda g: g.replace(" for GARVIS", ""))
    item = next(i for i in q.list() if i["id"] == qid)
    assert item["goal"] == "best agents" and item["original_goal"] == "best agents for GARVIS"


def test_queue_enqueue_no_rewrite_keeps_goal():
    q = ResearchQueue(_tmp("q.jsonl"))
    qid = q.enqueue("plain goal", rewrite_fn=lambda g: g)
    item = next(i for i in q.list() if i["id"] == qid)
    assert item["goal"] == "plain goal" and "original_goal" not in item


def test_goal_add_applies_rewrite_and_stores_original():
    g = GoalRegistry(_tmp("g.jsonl"))
    gid = g.add("research agents for GARVIS",
                rewrite_fn=lambda t: t.replace(" for GARVIS", ""))
    rec = next(x for x in g.list() if x["id"] == gid)
    assert rec["text"] == "research agents" and rec["original_text"] == "research agents for GARVIS"


def test_rewrite_via_memory_lesson_is_durable_default():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("decision", "for goal 'niche topic xyz' prefer broader query 'topic'",
          tags=["self-learned", "query"])
    q = ResearchQueue(_tmp("q.jsonl"))
    qid = q.enqueue("niche topic xyz", rewrite_fn=lambda gg: selflearn.rewrite_query(gg, m))
    item = next(i for i in q.list() if i["id"] == qid)
    assert item["goal"] == "topic" and item.get("original_goal") == "niche topic xyz"


# ---------- Track 4/5: schedule -> loop ----------
def test_enqueue_due_schedules_feeds_queue_and_audits():
    s = ScheduleStore(_tmp("s.jsonl"))
    q = ResearchQueue(_tmp("q.jsonl"))
    au = AuditLog(_tmp("a.jsonl"))
    s.add("recurring research", interval=100, now_ts=1000.0)   # due after 1100
    out = autonomy.enqueue_due_schedules(s, q, au, now_ts=2000.0)
    assert out["enqueued"] == 1 and len(q.pending()) == 1
    assert any(e["kind"] == autonomy.EV_SCHED_ENQUEUED for e in au.list())


def test_enqueue_due_schedules_none_due():
    s = ScheduleStore(_tmp("s.jsonl"))
    q = ResearchQueue(_tmp("q.jsonl"))
    s.add("future", interval=100000, now_ts=1000.0)
    out = autonomy.enqueue_due_schedules(s, q, None, now_ts=1001.0)
    assert out["enqueued"] == 0 and q.pending() == []


def test_schedule_enqueue_then_run_due_executes():
    s = ScheduleStore(_tmp("s.jsonl"))
    q = ResearchQueue(_tmp("q.jsonl"))
    s.add("recurring", interval=100, now_ts=1000.0)
    autonomy.enqueue_due_schedules(s, q, None, now_ts=2000.0)
    ran = []
    out = autonomy.run_due(q, lambda g: (ran.append(g) or {"run_id": "R", "findings": []}),
                           execute=True)
    assert out["executed"] and len(ran) == 1 and not q.pending()


def test_schedule_advances_after_enqueue_not_due_again():
    s = ScheduleStore(_tmp("s.jsonl"))
    q = ResearchQueue(_tmp("q.jsonl"))
    sid = s.add("recurring", interval=100, now_ts=1000.0)
    autonomy.enqueue_due_schedules(s, q, None, now_ts=2000.0)
    assert s.due(now_ts=2050.0) == []                    # advanced, not due again yet


def test_sched_enqueued_event_constant():
    assert autonomy.EV_SCHED_ENQUEUED == "loop_schedules_enqueued"


# ---------- integration: graph context end-to-end shape ----------
def test_planner_context_graph_terms_exclude_goal_tokens():
    m, a, b = _graph_memory()
    ctx = m.planner_context("langgraph")
    assert "langgraph" not in ctx["graph_terms"]         # only NEW terms surfaced


def test_graph_stats_after_planning_use():
    m, a, b = _graph_memory()
    m.graph_terms("langgraph")                            # read-only, no mutation
    st = m.graph_stats()
    assert st["nodes"] == 3 and st["edges"] == 1


def test_decompose_graph_respects_max_tasks():
    m, a, b = _graph_memory()
    qs = decompose_graph("langgraph agent framework", m, 3)
    assert len(qs) <= 3


def test_planner_context_fields_are_lists():
    m, a, b = _graph_memory()
    ctx = m.planner_context("agent")
    for k in ("graph_terms", "related", "topics", "suggested_terms"):
        assert isinstance(ctx[k], list)


def test_queue_rewrite_preserves_deps_and_priority():
    q = ResearchQueue(_tmp("q.jsonl"))
    dep = q.enqueue("dep")
    qid = q.enqueue("goal for GARVIS", priority=1, deps=[dep],
                    rewrite_fn=lambda g: g.replace(" for GARVIS", ""))
    item = next(i for i in q.list() if i["id"] == qid)
    assert item["priority"] == 1 and item["deps"] == [dep] and item["goal"] == "goal"


def test_goal_add_rewrite_noop_keeps_text():
    g = GoalRegistry(_tmp("g.jsonl"))
    gid = g.add("plain goal", rewrite_fn=lambda t: t)
    rec = next(x for x in g.list() if x["id"] == gid)
    assert rec["text"] == "plain goal" and "original_text" not in rec


def test_enqueue_due_schedules_item_detail():
    s = ScheduleStore(_tmp("s.jsonl"))
    q = ResearchQueue(_tmp("q.jsonl"))
    s.add("recurring detail", interval=100, now_ts=1000.0)
    out = autonomy.enqueue_due_schedules(s, q, None, now_ts=2000.0)
    assert out["items"][0]["goal"] == "recurring detail" and "queue_id" in out["items"][0]


def test_graph_terms_empty_goal():
    m = MemoryStore(_tmp("m.jsonl"))
    assert m.graph_terms("") == []


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
