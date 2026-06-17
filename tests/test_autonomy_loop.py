"""
Activate + Close Autonomy Loop - tests (offline, deterministic, temp-dir backed).

Covers: ci_check (no recursion), self-learned query rewrite, run_due (dry-run + execute +
budgets + kill switch + audit events), background_once cycle (review + learn), and the
upgraded daily brief.

Runs with pytest OR standalone:  python tests/test_autonomy_loop.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator import ops, selflearn, autonomy
from orchestrator.brief import daily_brief_full
from orchestrator.memory import MemoryStore
from orchestrator.history import RunHistory
from orchestrator.audit import AuditLog
from orchestrator.goals import GoalRegistry
from orchestrator.queue import ResearchQueue


def _tmp(n):
    return os.path.join(tempfile.mkdtemp(), n)


# ---------- ci-check ----------
def test_ci_check_no_tests_passes():
    res = ops.ci_check(run_tests=False)               # run_tests=False avoids recursion
    assert res["compile"]["ok"] and res["verify"]["ok"] and res["secret_scan"]["ok"]
    assert res["ok"] is True and "tests" not in res


def test_ci_check_structure_with_tests_flag_shape():
    # Only assert the SHAPE here (don't run the full suite inside a unit test).
    res = ops.ci_check(run_tests=False)
    assert set(res) >= {"compile", "verify", "secret_scan", "ok"}


# ---------- self-learned query rewrite ----------
def test_rewrite_query_strips_project_and_filler():
    out = selflearn.rewrite_query("best open source AI agent frameworks for GARVIS")
    assert "garvis" not in out.lower() and "best" not in out.lower()
    assert "agent" in out.lower()


def test_rewrite_query_uses_memory_lesson():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("decision",
          "for goal 'obscure niche topic xyz' prefer broader query 'niche topic'",
          tags=["self-learned", "query"])
    out = selflearn.rewrite_query("obscure niche topic xyz", m)
    assert out == "niche topic"


def test_rewrite_query_niche_is_improved():
    raw = "best open source AI agent frameworks for GARVIS"
    out = selflearn.rewrite_query(raw, MemoryStore(_tmp("m.jsonl")))
    assert out != raw and len(out) < len(raw)


# ---------- run-due ----------
def _queue_with(n, **kw):
    q = ResearchQueue(_tmp("q.jsonl"))
    for i in range(n):
        q.enqueue(f"goal {i}", **kw)
    return q


def test_run_due_dry_run_default_executes_nothing():
    q = _queue_with(3)
    calls = []
    out = autonomy.run_due(q, lambda g: calls.append(g), execute=False)
    assert out["executed"] is False and out["would_run"] == 3 and calls == []
    assert len(q.pending()) == 3                       # nothing consumed


def test_run_due_executes_only_when_approved():
    q = _queue_with(2)
    ran = []
    out = autonomy.run_due(q, lambda g: (ran.append(g) or {"run_id": "R", "findings": []}),
                           execute=True)
    assert out["executed"] is True and len(out["ran"]) == 2 and len(ran) == 2
    assert len(q.pending()) == 0                        # consumed


def test_run_due_respects_max_tasks():
    q = _queue_with(5)
    out = autonomy.run_due(q, lambda g: {"run_id": "R"}, execute=True, max_tasks=2)
    assert len(out["ran"]) == 2 and len(q.pending()) == 3


def test_run_due_kill_switch_refuses():
    q = _queue_with(2)
    out = autonomy.run_due(q, lambda g: {"run_id": "R"}, execute=True, disabled=True)
    assert out["executed"] is False and "kill switch" in out["reason"]
    assert len(q.pending()) == 2


def test_run_due_budget_skips_when_no_time():
    q = _queue_with(3)
    out = autonomy.run_due(q, lambda g: {"run_id": "R"}, execute=True, max_seconds=-1)
    assert out["ran"] == [] and len(out["skipped"]) == 3


def test_run_due_captures_failures():
    q = _queue_with(1, max_retries=0)

    def boom(_):
        raise RuntimeError("nope")

    out = autonomy.run_due(q, boom, execute=True)
    assert out["failed"] and q.failed()


def test_run_due_emits_audit_events():
    q = _queue_with(1)
    au = AuditLog(_tmp("a.jsonl"))
    autonomy.run_due(q, lambda g: {"run_id": "R", "findings": []}, execute=True, audit=au)
    kinds = {e["kind"] for e in au.list()}
    assert {autonomy.EV_PREVIEW, autonomy.EV_STARTED, autonomy.EV_TASK_DONE,
            autonomy.EV_COMPLETED} <= kinds


def test_run_due_preview_event_on_dry_run():
    q = _queue_with(1)
    au = AuditLog(_tmp("a.jsonl"))
    autonomy.run_due(q, lambda g: {"run_id": "R"}, execute=False, audit=au)
    assert any(e["kind"] == autonomy.EV_PREVIEW for e in au.list())


# ---------- background-once ----------
def _seed_history_with_empty_run(h):
    h.save({"id": "e1", "goal": "topic for GARVIS", "status": "done",
            "result_summary": "No results found for: topic for GARVIS",
            "tasks": [], "approvals": []})


def test_background_once_dry_run_default():
    q = _queue_with(2)
    m = MemoryStore(_tmp("m.jsonl")); h = RunHistory(_tmp("h.jsonl"))
    out = autonomy.background_once(q, lambda g: {"run_id": "R"}, memory=m, history=h,
                                   execute=False)
    assert out["mode"] == "dry-run" and out["run_due"]["executed"] is False
    assert len(q.pending()) == 2


def test_background_once_executes_reviews_and_learns():
    q = _queue_with(1)
    m = MemoryStore(_tmp("m.jsonl")); h = RunHistory(_tmp("h.jsonl"))
    au = AuditLog(_tmp("a.jsonl"))
    _seed_history_with_empty_run(h)                    # so learn() has something to learn
    out = autonomy.background_once(q, lambda g: {"run_id": "R", "findings": []},
                                   memory=m, history=h, audit=au, execute=True)
    assert out["mode"] == "live" and out["run_due"]["executed"] is True
    assert out["reviewed"] >= 1                        # auto-review ran
    assert isinstance(out["lessons"], list) and len(out["lessons"]) >= 1   # learned
    assert any(e["kind"] == autonomy.EV_BG_COMPLETED for e in au.list())


def test_background_once_kill_switch():
    q = _queue_with(1)
    m = MemoryStore(_tmp("m.jsonl")); h = RunHistory(_tmp("h.jsonl"))
    out = autonomy.background_once(q, lambda g: {"run_id": "R"}, memory=m, history=h,
                                   execute=True, disabled=True)
    assert out["run_due"]["executed"] is False and len(q.pending()) == 1


# ---------- upgraded daily brief ----------
def test_daily_brief_full_has_all_sections():
    h = RunHistory(_tmp("h.jsonl"))
    h.save({"id": "f1", "goal": "broken", "status": "failed", "result_summary": "",
            "tasks": [], "approvals": []})
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("rule", "lesson learned", tags=["self-learned"])
    g = GoalRegistry(_tmp("g.jsonl")); g.add("goal", priority=1)
    q = ResearchQueue(_tmp("q.jsonl")); q.enqueue("due")
    au = AuditLog(_tmp("a.jsonl"))
    brief = daily_brief_full(h, m, g, q, au)
    for section in ("Active goals", "Due research queue", "Failed / blocked runs",
                    "Recent lessons", "Memory insights", "Recommended next actions"):
        assert section in brief, f"missing section: {section}"


def test_run_due_audit_blocked_on_failure():
    q = _queue_with(1, max_retries=0)
    au = AuditLog(_tmp("a.jsonl"))

    def boom(_):
        raise RuntimeError("x")

    autonomy.run_due(q, boom, execute=True, audit=au)
    assert any(e["kind"] == autonomy.EV_TASK_BLOCKED for e in au.list())


def test_run_due_more_tasks_than_queue():
    q = _queue_with(2)
    out = autonomy.run_due(q, lambda g: {"run_id": "R"}, execute=True, max_tasks=10)
    assert len(out["ran"]) == 2


def test_run_due_dry_run_lists_plan_ids():
    q = _queue_with(2)
    out = autonomy.run_due(q, None, execute=False)
    assert len(out["plan"]) == 2 and all(isinstance(i, str) for i in out["plan"])


def test_run_due_retry_keeps_pending():
    q = _queue_with(1, max_retries=1)

    def boom(_):
        raise RuntimeError("x")

    autonomy.run_due(q, boom, execute=True)
    assert len(q.pending()) == 1 and not q.failed()    # retried, still pending


def test_rewrite_query_empty_goal():
    assert selflearn.rewrite_query("") == ""


def test_rewrite_query_no_matching_lesson_returns_clean():
    m = MemoryStore(_tmp("m.jsonl"))
    m.add("decision", "unrelated note about cooking", tags=["self-learned"])
    out = selflearn.rewrite_query("python testing frameworks", m)
    assert "python" in out.lower() and "testing" in out.lower()


def test_background_once_dry_run_no_review_or_learn():
    q = _queue_with(1)
    m = MemoryStore(_tmp("m.jsonl")); h = RunHistory(_tmp("h.jsonl"))
    _seed_history_with_empty_run(h)
    out = autonomy.background_once(q, lambda g: {"run_id": "R"}, memory=m, history=h,
                                   execute=False)
    assert out["reviewed"] == 0 and out["lessons"] == []


def test_background_once_returns_run_due_summary():
    q = _queue_with(1)
    m = MemoryStore(_tmp("m.jsonl")); h = RunHistory(_tmp("h.jsonl"))
    out = autonomy.background_once(q, lambda g: {"run_id": "R", "findings": []},
                                   memory=m, history=h, execute=True)
    assert "run_due" in out and out["run_due"]["executed"] is True


def test_ci_check_ok_true_without_tests():
    res = ops.ci_check(run_tests=False)
    assert res["ok"] is True


def test_run_due_no_due_items():
    q = ResearchQueue(_tmp("q.jsonl"))
    out = autonomy.run_due(q, lambda g: {"run_id": "R"}, execute=True)
    assert out["ran"] == [] and out["executed"] is True


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
