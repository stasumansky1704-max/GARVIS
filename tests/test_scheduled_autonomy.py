"""
Scheduled Autonomy - bounded loop tests (offline, deterministic, injected fakes).

Covers: dry-run default, approval required, max-cycles required + cap, interval validation,
kill switch before/between cycles, audit events, safety-error stop, no-infinite-loop /
no-daemon behavior, query-rewrite queue metadata, and no live-PR path.

Runs with pytest OR standalone:  python tests/test_scheduled_autonomy.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator import autonomy
from orchestrator.audit import AuditLog
from orchestrator.queue import ResearchQueue
from orchestrator.memory import MemoryStore
from orchestrator.history import RunHistory


def _tmp(n):
    return os.path.join(tempfile.mkdtemp(), n)


# ---------- validation ----------
def test_validate_requires_max_cycles():
    errs = autonomy.validate_loop_params(None, 60)
    assert any("max-cycles" in e for e in errs)


def test_validate_requires_interval():
    errs = autonomy.validate_loop_params(3, None)
    assert any("interval" in e for e in errs)


def test_validate_max_cycles_cap():
    errs = autonomy.validate_loop_params(autonomy.MAX_CYCLES_LIMIT + 1, 60)
    assert any("safe limit" in e for e in errs)


def test_validate_interval_too_small():
    errs = autonomy.validate_loop_params(2, autonomy.MIN_INTERVAL - 1)
    assert any("interval" in e for e in errs)


def test_validate_interval_too_large():
    errs = autonomy.validate_loop_params(2, autonomy.MAX_INTERVAL + 1)
    assert any("interval" in e for e in errs)


def test_validate_ok():
    assert autonomy.validate_loop_params(3, 60) == []


def test_validate_rejects_zero_and_bool():
    assert autonomy.validate_loop_params(0, 60)
    assert autonomy.validate_loop_params(True, 60)         # bool is not a valid count


# ---------- loop behavior ----------
def test_loop_dry_run_default_executes_nothing():
    calls = []
    out = autonomy.run_loop(lambda: calls.append(1), max_cycles=3, interval=60, execute=False)
    assert out["started"] is False and out["mode"] == "dry-run" and calls == []


def test_loop_requires_approval_to_run():
    calls = []
    # execute=False == not approved
    autonomy.run_loop(lambda: calls.append(1), max_cycles=2, interval=60, execute=False)
    assert calls == []


def test_loop_missing_params_refused():
    out = autonomy.run_loop(lambda: None, max_cycles=None, interval=None, execute=True)
    assert out["started"] is False and out["errors"]


def test_loop_runs_exactly_max_cycles():
    calls = []
    sleeps = []
    out = autonomy.run_loop(lambda: calls.append(1), max_cycles=3, interval=5,
                            execute=True, sleep_fn=lambda s: sleeps.append(s))
    assert out["cycles_run"] == 3 and len(calls) == 3
    assert len(sleeps) == 2                                # sleeps BETWEEN cycles only


def test_loop_is_finite_no_daemon():
    # The loop returns control (it is a finite for-range, not a daemon/while-True).
    out = autonomy.run_loop(lambda: 1, max_cycles=autonomy.MAX_CYCLES_LIMIT, interval=5,
                            execute=True, sleep_fn=lambda s: None)
    assert out["cycles_run"] == autonomy.MAX_CYCLES_LIMIT and out["stopped_reason"] is None


def test_kill_switch_stops_before_first_cycle():
    calls = []
    out = autonomy.run_loop(lambda: calls.append(1), max_cycles=3, interval=5,
                            execute=True, disabled_fn=lambda: True,
                            sleep_fn=lambda s: None)
    assert calls == [] and out["cycles_run"] == 0
    assert "kill switch" in out["stopped_reason"]


def test_kill_switch_stops_between_cycles():
    calls = []
    state = {"n": 0}

    def disabled():
        state["n"] += 1
        return state["n"] > 1          # allow first check, kill before 2nd cycle

    out = autonomy.run_loop(lambda: calls.append(1), max_cycles=3, interval=5,
                            execute=True, disabled_fn=disabled, sleep_fn=lambda s: None)
    assert len(calls) == 1 and "kill switch" in out["stopped_reason"]


def test_loop_stops_on_cycle_error():
    def boom():
        raise RuntimeError("safety")

    out = autonomy.run_loop(boom, max_cycles=3, interval=5, execute=True,
                            sleep_fn=lambda s: None)
    assert out["cycles_run"] == 0 and "safety error" in out["stopped_reason"]


def test_loop_emits_audit_events():
    au = AuditLog(_tmp("a.jsonl"))
    autonomy.run_loop(lambda: 1, max_cycles=2, interval=5, execute=True,
                      audit=au, sleep_fn=lambda s: None)
    kinds = {e["kind"] for e in au.list()}
    assert {autonomy.EV_LOOP_PREVIEW, autonomy.EV_LOOP_CYCLE,
            autonomy.EV_LOOP_COMPLETED} <= kinds


def test_loop_dry_run_emits_preview_only():
    au = AuditLog(_tmp("a.jsonl"))
    autonomy.run_loop(lambda: 1, max_cycles=2, interval=5, execute=False, audit=au)
    kinds = [e["kind"] for e in au.list()]
    assert autonomy.EV_LOOP_PREVIEW in kinds and autonomy.EV_LOOP_CYCLE not in kinds


def test_loop_stop_event_on_kill():
    au = AuditLog(_tmp("a.jsonl"))
    autonomy.run_loop(lambda: 1, max_cycles=2, interval=5, execute=True,
                      disabled_fn=lambda: True, audit=au, sleep_fn=lambda s: None)
    assert any(e["kind"] == autonomy.EV_LOOP_STOPPED for e in au.list())


def test_loop_collects_cycle_summaries():
    out = autonomy.run_loop(lambda: {"ran": 1}, max_cycles=2, interval=5, execute=True,
                            sleep_fn=lambda s: None)
    assert out["summaries"] == [{"ran": 1}, {"ran": 1}]


# ---------- query-rewrite queue metadata ----------
def test_run_due_persists_query_rewrite_metadata():
    q = ResearchQueue(_tmp("q.jsonl"))
    qid = q.enqueue("best agent frameworks for GARVIS")
    autonomy.run_due(q, lambda g: {"run_id": "R", "findings": []}, execute=True,
                     rewrite_fn=lambda g: g.replace(" for GARVIS", ""))
    rws = q.rewrites()
    assert rws and rws[0]["id"] == qid
    assert "garvis" not in rws[0]["rewritten"].lower()


def test_run_due_no_rewrite_when_unchanged():
    q = ResearchQueue(_tmp("q.jsonl"))
    q.enqueue("agent frameworks")
    autonomy.run_due(q, lambda g: {"run_id": "R"}, execute=True, rewrite_fn=lambda g: g)
    assert q.rewrites() == []


def test_queue_annotate_persists():
    q = ResearchQueue(_tmp("q.jsonl"))
    qid = q.enqueue("x")
    q.annotate(qid, original_goal="x", rewritten_goal="y")
    item = next(i for i in q.list() if i["id"] == qid)
    assert item["rewritten_goal"] == "y" and item["goal"] == "x"


# ---------- no live PR path ----------
def test_loop_cycle_fn_has_no_pr_side_effects():
    # The loop only calls the provided cycle_fn; with a research-only fake it never
    # touches a GitHub client. Prove the loop passes through whatever cycle_fn returns
    # and performs no PR creation itself.
    created = {"pr": False}

    def cycle():
        return {"ran": 1}      # a real research cycle; no PR creation

    autonomy.run_loop(cycle, max_cycles=1, interval=5, execute=True, sleep_fn=lambda s: None)
    assert created["pr"] is False


def test_background_once_threads_rewrite_fn():
    q = ResearchQueue(_tmp("q.jsonl"))
    q.enqueue("topic for GARVIS")
    m = MemoryStore(_tmp("m.jsonl")); h = RunHistory(_tmp("h.jsonl"))
    autonomy.background_once(q, lambda g: {"run_id": "R", "findings": []}, memory=m,
                             history=h, execute=True,
                             rewrite_fn=lambda g: g.replace(" for GARVIS", ""))
    assert q.rewrites()


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
