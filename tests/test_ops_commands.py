"""
Group F - operational safety / self-check tests (offline, deterministic).

Covers isolation guard, no-WDM-KS regression, no-sd.rec regression, gitignored-artifact
check, config doctor/explain, version/status, verify, health, validation summary, and
test discovery. These let GARVIS validate its own safety posture without a human.

Runs with pytest OR standalone:  python tests/test_ops_commands.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator import ops


def test_isolation_check_passes_on_repo():
    res = ops.check_isolation()
    assert res["ok"] is True, f"backend imports orchestrator: {res['offenders']}"


def test_no_wdm_ks_in_orchestrator():
    res = ops.check_no_wdm_ks()
    assert res["ok"] is True, f"WDM-KS referenced in: {res['offenders']}"


def test_no_sd_rec_in_orchestrator():
    res = ops.check_no_sd_rec()
    assert res["ok"] is True, f"sd.rec used in: {res['offenders']}"


def test_wdm_ks_check_detects_real_usage():
    d = tempfile.mkdtemp()
    open(os.path.join(d, "bad.py"), "w").write(
        "import sounddevice as sd\nstream = sd.RawInputStream(hostapi='WDM-KS')\n")
    res = ops.check_no_wdm_ks(paths=(d,))
    assert res["ok"] is False and res["offenders"]


def test_wdm_ks_check_allows_safety_reference():
    d = tempfile.mkdtemp()
    open(os.path.join(d, "safe.py"), "w").write(
        'FORBIDDEN = ("use_wdm_ks",)  # never allow WDM-KS\n')
    res = ops.check_no_wdm_ks(paths=(d,))
    assert res["ok"] is True       # naming it to forbid it is fine


def test_sd_rec_check_detects_offender():
    d = tempfile.mkdtemp()
    open(os.path.join(d, "bad.py"), "w").write("import sounddevice as sd\nsd.rec(100)\n")
    res = ops.check_no_sd_rec(paths=(d,))
    assert res["ok"] is False and res["offenders"]


def test_gitignored_artifacts_check():
    res = ops.check_gitignored()
    assert res["ok"] is True, f"missing gitignore entries: {res.get('missing')}"


def test_config_doctor_ok():
    res = ops.config_doctor()
    assert res["ok"] is True, f"config problems: {res.get('problems')}"


def test_config_explain_fields():
    cfg = ops.config_explain()
    assert "limits" in cfg and "research_sources" in cfg and "default_planner" in cfg


def test_version_status():
    v = ops.version_status()
    assert v["version"].startswith("garvis-orchestrator") and "python" in v


def test_verify_aggregates_all_checks():
    res = ops.verify()
    names = {c["name"] for c in res["checks"]}
    assert {"isolation", "no_wdm_ks", "no_sd_rec", "gitignored_artifacts",
            "config_doctor"} <= names
    assert res["ok"] is True


def test_health_snapshot():
    h = ops.health()
    assert h["ok"] is True and h["passed"] == h["total"] and not h["failing"]


def test_validation_summary_lists_test_suites():
    s = ops.validation_summary()
    assert s["safety_ok"] is True and len(s["test_suites"]) >= 8


def test_discover_orchestrator_tests_present():
    tests = ops.discover_orchestrator_tests()
    assert any("test_super_sprint" in t for t in tests)


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
