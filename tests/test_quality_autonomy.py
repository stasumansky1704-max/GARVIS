"""
Self-evolution tests - Tracks D (agent quality), E (autonomy), F (operations).
Offline, deterministic, temp-dir backed.

Runs with pytest OR standalone:  python tests/test_quality_autonomy.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator import summarize, monitor, ops
from orchestrator import generators as gen
from orchestrator.report import generate_report
from orchestrator.brief import auto_review
from orchestrator.memory import MemoryStore
from orchestrator.history import RunHistory
from orchestrator.goals import GoalRegistry
from orchestrator.queue import ResearchQueue
from orchestrator.models import Run, Envelope, Status


def _tmp(n):
    return os.path.join(tempfile.mkdtemp(), n)


_FINDINGS = [
    {"title": "LangGraph", "url": "u1", "source": "wikipedia", "confidence": 0.8,
     "snippet": "LangGraph is an agent framework for building stateful agents"},
    {"title": "AutoGen", "url": "u2", "source": "duckduckgo", "confidence": 0.6,
     "snippet": "AutoGen multi agent conversation framework"},
    {"title": "AutoGen", "url": "u2", "source": "duckduckgo", "confidence": 0.6,
     "snippet": "duplicate"},
    {"title": "CrewAI", "url": "u3", "source": "wikipedia", "confidence": 0.7,
     "snippet": "CrewAI orchestrates role-playing autonomous agents"},
]


# ---------- Track D: agent quality ----------
def test_top_findings_dedupes_and_ranks():
    top = summarize.top_findings(_FINDINGS, "agent framework", 5)
    urls = [f["url"] for f in top]
    assert len(urls) == len(set(urls))                 # deduped
    assert top[0].get("relevance") is not None


def test_key_points_are_high_signal():
    pts = summarize.key_points(_FINDINGS, "agent framework", 3)
    assert pts and any("LangGraph" in p for p in pts)


def test_confidence_band_and_source_breakdown():
    assert summarize.confidence_band(_FINDINGS) in ("low", "medium", "high")
    assert "wikipedia" in summarize.source_breakdown(_FINDINGS)


def test_executive_summary_grounded():
    s = summarize.executive_summary("agent frameworks", _FINDINGS)
    assert "agent frameworks" in s and "quality" in s


def test_executive_summary_empty_is_honest():
    s = summarize.executive_summary("x", [])
    assert "no usable findings" in s.lower()


def test_change_proposal_richer():
    md = gen.change_proposal("pick agent framework", _FINDINGS)
    assert "Executive summary" in md and "Key evidence" in md and "ranked" in md.lower()
    assert "LangGraph" in md


def test_report_has_exec_summary_and_metrics():
    run = Run(id="r1", goal="agent frameworks", status=Status.DONE)
    run.results = {"r0": Envelope("r0", Status.DONE,
                   result={"query": "agent frameworks", "findings": _FINDINGS,
                           "summary": "s", "count": len(_FINDINGS)})}
    d = tempfile.mkdtemp()
    path = generate_report(run, d)
    text = open(path, encoding="utf-8").read()
    assert "Executive summary" in text and "Key findings" in text and "quality:" in text


# ---------- Track E: autonomy ----------
def test_auto_review_rates_unreviewed_runs():
    h = RunHistory(_tmp("h.jsonl"))
    h.save({"id": "good1", "goal": "g", "status": "done", "result_summary": "found 3 things",
            "tasks": [], "approvals": []})
    h.save({"id": "empty1", "goal": "g2", "status": "done",
            "result_summary": "No results found for: g2", "tasks": [], "approvals": []})
    m = MemoryStore(_tmp("m.jsonl"))
    out = auto_review(h, m)
    assert out["reviewed"] == 2
    again = auto_review(h, m)                           # idempotent
    assert again["reviewed"] == 0
    ratings = " ".join(d["text"] for d in m.list("decision"))
    assert "weak" in ratings and "auto-good" in ratings


def test_monitor_run_metrics():
    h = RunHistory(_tmp("h.jsonl"))
    h.save({"id": "1", "goal": "g", "status": "done", "result_summary": "ok",
            "tasks": [], "approvals": []})
    h.save({"id": "2", "goal": "g", "status": "done",
            "result_summary": "No results found for: g", "tasks": [], "approvals": []})
    h.save({"id": "3", "goal": "g", "status": "failed", "result_summary": "",
            "tasks": [], "approvals": []})
    rm = monitor.run_metrics(h)
    assert rm["total"] == 3 and rm["empty_runs"] == 1
    assert 0.0 < rm["success_rate"] < 1.0


def test_monitor_queue_and_dashboard():
    q = ResearchQueue(_tmp("q.jsonl")); q.enqueue("a")
    h = RunHistory(_tmp("h.jsonl"))
    m = MemoryStore(_tmp("m.jsonl")); m.add("rule", "x")
    g = GoalRegistry(_tmp("g.jsonl")); g.add("goal")
    dash = monitor.dashboard(h, m, g, q)
    assert "self_audit" in dash and dash["queue"]["total"] == 1 and "healthy" in dash


def test_self_audit_passes():
    a = monitor.self_audit()
    assert a["ok"] is True and not a["failing"]


# ---------- Track F: operations ----------
def test_no_dangerous_calls_in_orchestrator():
    res = ops.check_no_dangerous_calls()
    assert res["ok"] is True, f"dangerous calls in: {res['offenders']}"


def test_dangerous_calls_check_detects_offender():
    d = tempfile.mkdtemp()
    open(os.path.join(d, "bad.py"), "w").write("x = eval('1+1')\nos.system('ls')\n")
    res = ops.check_no_dangerous_calls(paths=(d,))
    assert res["ok"] is False and res["offenders"]


def test_dangerous_calls_check_allows_string_reference():
    d = tempfile.mkdtemp()
    open(os.path.join(d, "ok.py"), "w").write('NEEDLES = ("eval(", "exec(")\n')
    res = ops.check_no_dangerous_calls(paths=(d,))
    assert res["ok"] is True


def test_verify_includes_dangerous_check():
    names = {c["name"] for c in ops.verify()["checks"]}
    assert "no_dangerous_calls" in names


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
