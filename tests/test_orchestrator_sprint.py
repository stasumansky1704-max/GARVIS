"""
Sprint capability tests (offline/deterministic): config, audit, report, decompose,
budgets, kill switch, secret scan, attribution, error handling.

Runs with pytest OR standalone:  python tests/test_orchestrator_sprint.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator import config as cfgmod
from orchestrator.audit import AuditLog
from orchestrator.report import generate_report
from orchestrator.decompose import decompose
from orchestrator.engine import Orchestrator, RunBudget, is_disabled, KILL_ENV
from orchestrator.registry import WorkerRegistry
from orchestrator.models import TaskSpec, Status
from orchestrator.workers.research_worker import ResearchWorker
from orchestrator.secret_scan import scan_dir, scan_text

FAKE1 = lambda q: ([{"title": "A", "url": "https://e/a", "snippet": "alpha",
                     "source": "wikipedia", "confidence": 0.7, "timestamp": "t"}], [])


def _orch():
    rw = ResearchWorker(fetch=FAKE1)
    reg = WorkerRegistry(); reg.register(rw.spec)
    return Orchestrator(reg, {"research": rw}), rw


# ---------- config ----------
def test_config_defaults_when_missing():
    cfg = cfgmod.load_config(os.path.join(tempfile.gettempdir(), "nope-xyz.json"))
    assert cfg["default_planner"] in ("llm", "manual")
    assert cfg["limits"]["max_tasks"] > 0


def test_config_valid_file():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "c.json")
        json.dump({"default_planner": "manual", "limits": {"max_tasks": 3}}, open(p, "w"))
        cfg = cfgmod.load_config(p)
        assert cfg["default_planner"] == "manual" and cfg["limits"]["max_tasks"] == 3


def test_config_invalid_planner_raises():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "c.json"); json.dump({"default_planner": "x"}, open(p, "w"))
        try:
            cfgmod.load_config(p); assert False, "expected ConfigError"
        except cfgmod.ConfigError:
            pass


def test_config_invalid_limit_raises():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "c.json"); json.dump({"limits": {"max_tasks": -1}}, open(p, "w"))
        try:
            cfgmod.load_config(p); assert False, "expected ConfigError"
        except cfgmod.ConfigError:
            pass


# ---------- audit ----------
def test_audit_event_and_list():
    with tempfile.TemporaryDirectory() as tmp:
        a = AuditLog(os.path.join(tmp, "a.jsonl"))
        a.event("run_started", run="r1")
        a.event("run_completed", run="r1", status="done")
        recs = a.list()
        assert [r["kind"] for r in recs] == ["run_started", "run_completed"]


# ---------- report ----------
def test_report_generates_markdown():
    with tempfile.TemporaryDirectory() as tmp:
        orch, _ = _orch()
        fb = [TaskSpec(id="r0", worker="research", intent="x", inputs={"query": "q"})]
        run = orch.run_goal("g", planner=None, fallback_tasks=fb)
        path = generate_report(run, tmp)
        assert os.path.exists(path)
        text = open(path, encoding="utf-8").read()
        assert "# Research report" in text and "alpha" in text


# ---------- decompose ----------
def test_decompose_nonempty_and_capped():
    subs = decompose("best avatar tools", max_tasks=3)
    assert len(subs) == 3 and subs[0] == "best avatar tools"


def test_decompose_empty_goal():
    assert decompose("   ", 5) == []


# ---------- budgets ----------
def test_engine_caps_max_tasks():
    orch, _ = _orch()
    tasks = [TaskSpec(id=f"r{i}", worker="research", intent="x", inputs={"query": "q"})
             for i in range(5)]
    run = orch.run_manual("g", tasks, budget=RunBudget(max_tasks=2))
    assert len(run.results) == 2                     # plan truncated to 2


def test_engine_sets_worker_request_budget():
    orch, rw = _orch()
    fb = [TaskSpec(id="r0", worker="research", intent="x", inputs={"query": "q"})]
    orch.run_goal("g", planner=None, fallback_tasks=fb,
                  budget=RunBudget(max_external_requests=7))
    assert rw.request_budget == 7                    # injected fetch doesn't decrement


def test_research_caps_max_findings():
    many = [{"title": str(i), "url": f"u{i}", "snippet": "s", "source": "wikipedia"}
            for i in range(10)]
    rw = ResearchWorker(fetch=lambda q: (many, []), max_findings=3)
    env = rw.run(TaskSpec(id="r", worker="research", intent="x", inputs={"query": "q"}))
    assert env.result["count"] == 3


# ---------- kill switch ----------
def test_kill_switch_blocks_run():
    orch, _ = _orch()
    fb = [TaskSpec(id="r0", worker="research", intent="x", inputs={"query": "q"})]
    os.environ[KILL_ENV] = "1"
    try:
        assert is_disabled()
        run = orch.run_goal("g", planner=None, fallback_tasks=fb)
        assert run.status == Status.BLOCKED and run.results == {}
    finally:
        del os.environ[KILL_ENV]


# ---------- secret scan ----------
def test_secret_scan_clean_dir():
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, "ok.md"), "w").write("# clean report\nno secrets here")
        assert scan_dir(tmp) == []


def test_secret_scan_detects_planted_secret():
    assert scan_text('api_key="ABCD1234EFGH5678"') != []
    assert scan_text("sk-" + "a" * 30) != []


# ---------- attribution ----------
def test_research_findings_have_confidence_and_timestamp():
    rw = ResearchWorker(fetch=FAKE1)
    env = rw.run(TaskSpec(id="r", worker="research", intent="x", inputs={"query": "q"}))
    f = env.result["findings"][0]
    assert "confidence" in f and "timestamp" in f and "source" in f


# ---------- error handling ----------
def test_research_fetch_exception_is_structured_failed():
    def boom(q):
        raise RuntimeError("network down")
    rw = ResearchWorker(fetch=boom)
    env = rw.run(TaskSpec(id="r", worker="research", intent="x", inputs={"query": "q"}))
    assert env.status == Status.FAILED and "network down" in env.error


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
