"""
Operational safety + self-check commands (executable, offline).

Provides regression guards and health/verify/status commands so GARVIS can validate its
own safety posture without a human:
- check_isolation     : backend/dashboard/execution never import the orchestrator
- check_no_wdm_ks     : the orchestrator package never references WDM-KS (BSOD cause)
- check_no_sd_rec     : the orchestrator package never uses sd.rec (unsafe capture)
- check_gitignored    : _runs/_artifacts are gitignored (no secrets/artifacts committed)
- config_doctor       : config loads, dirs writable, at least one research source
- verify / health / version_status / validation_summary : aggregate, human-readable

All checks are read-only and scoped to the agent core; none touch backend runtime.
The CI definition that runs these lives at runtime/orchestrator/ci/orchestrator.yml
(copy to .github/workflows/ to activate).
"""
from __future__ import annotations

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))            # runtime/orchestrator
RUNTIME_DIR = os.path.dirname(_DIR)                          # runtime
REPO_ROOT = os.path.dirname(RUNTIME_DIR)                     # repo root
VERSION = "garvis-orchestrator 1.0 (production agent core)"

# Directories that must NEVER import the orchestrator package (isolation guarantee).
_BACKEND_DIRS = ("api", os.path.join("runtime", "execution"), "mission_control")


def _py_files(root: str):
    for base, _, files in os.walk(root):
        if "__pycache__" in base or os.sep + ".git" in base:
            continue
        for fn in files:
            if fn.endswith(".py"):
                yield os.path.join(base, fn)


def _scan(root: str, needles: tuple[str, ...]) -> list[str]:
    hits = []
    for fp in _py_files(root):
        try:
            text = open(fp, encoding="utf-8", errors="replace").read().lower()
        except Exception:
            continue
        if any(n in text for n in needles):
            hits.append(os.path.relpath(fp, REPO_ROOT))
    return hits


# Audio-context words that, alongside a WDM token, indicate REAL device usage (not a
# safety reference/risk-keyword/comment that merely names the forbidden thing).
_AUDIO_CTX = ("hostapi", "host_api", "sounddevice", "pyaudio", "wasapi", "inputstream",
              "rawinputstream", "open_stream", "audio_device", "paudio")


def _scan_lines(root: str, predicate) -> list[str]:
    """Flag files where any non-comment line satisfies predicate(line_lower)."""
    hits = []
    for fp in _py_files(root):
        try:
            lines = open(fp, encoding="utf-8", errors="replace").read().splitlines()
        except Exception:
            continue
        for ln in lines:
            stripped = ln.lstrip()
            if stripped.startswith("#"):
                continue                      # comments only describe; they don't execute
            if predicate(ln.lower()):
                hits.append(os.path.relpath(fp, REPO_ROOT))
                break
    return hits


def _is_string_literal_hit(line: str, needle: str) -> bool:
    """True if the needle appears only as a quoted string literal (a reference, not a call)."""
    return (('"' + needle) in line) or (("'" + needle) in line)


def check_isolation() -> dict:
    """Backend/execution/dashboard must not import the orchestrator package."""
    offenders = []
    for d in _BACKEND_DIRS:
        root = os.path.join(REPO_ROOT, d)
        if not os.path.isdir(root):
            continue
        for fp in _py_files(root):
            try:
                text = open(fp, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            if "import orchestrator" in text or "from orchestrator" in text:
                offenders.append(os.path.relpath(fp, REPO_ROOT))
    return {"name": "isolation", "ok": not offenders, "offenders": offenders}


def check_no_wdm_ks(paths: tuple[str, ...] | None = None) -> dict:
    """The orchestrator package must never USE WDM-KS audio (caused the BSOD).

    Flags real device usage: a WDM token together with audio-context on the same line.
    Safety-list references / risk keywords / comments that merely name it are allowed.
    """
    roots = paths or (_DIR,)

    def pred(line: str) -> bool:
        has_wdm = ("wdm-ks" in line) or ("wdmks" in line) or ("wdm_ks" in line) or ("wdm " in line)
        return has_wdm and any(ctx in line for ctx in _AUDIO_CTX)

    hits = []
    for r in roots:
        hits += _scan_lines(r, pred)
    return {"name": "no_wdm_ks", "ok": not hits, "offenders": hits}


def check_no_sd_rec(paths: tuple[str, ...] | None = None) -> dict:
    """The orchestrator package must never CALL sd.rec (unsafe per-chunk capture).

    Flags actual calls; ignores quoted string literals (e.g. this scanner's own needles).
    """
    roots = paths or (_DIR,)

    def pred(line: str) -> bool:
        for needle in ("sd.rec(", "sounddevice.rec("):
            if needle in line and not _is_string_literal_hit(line, needle):
                return True
        return False

    hits = []
    for r in roots:
        hits += _scan_lines(r, pred)
    return {"name": "no_sd_rec", "ok": not hits, "offenders": hits}


def check_no_dangerous_calls(paths: tuple[str, ...] | None = None) -> dict:
    """The agent core must not use eval/exec/os.system/subprocess-shell (code-exec risk).

    Flags real calls; ignores quoted-string references and comments.
    """
    roots = paths or (_DIR,)
    needles = ("eval(", "exec(", "os.system(", "subprocess.call(", "subprocess.popen(",
               "shell=true")

    def pred(line: str) -> bool:
        for n in needles:
            if n in line and not _is_string_literal_hit(line, n):
                return True
        return False

    hits = []
    for r in roots:
        hits += _scan_lines(r, pred)
    return {"name": "no_dangerous_calls", "ok": not hits, "offenders": hits}


def check_gitignored() -> dict:
    """_runs and _artifacts must be covered by .gitignore (no artifacts/secrets committed)."""
    gi = os.path.join(REPO_ROOT, ".gitignore")
    text = ""
    if os.path.exists(gi):
        text = open(gi, encoding="utf-8", errors="replace").read()
    needed = ("_runs", "_artifacts")
    missing = [n for n in needed if n not in text]
    return {"name": "gitignored_artifacts", "ok": not missing, "missing": missing}


def config_doctor() -> dict:
    """Config loads + validates, dirs are writable, at least one research source enabled."""
    from . import config as cfgmod
    problems = []
    try:
        cfg = cfgmod.load_config()
    except Exception as exc:
        return {"name": "config_doctor", "ok": False, "problems": [f"config error: {exc}"]}
    for getter in (cfgmod.artifact_dir, cfgmod.history_dir):
        d = getter(cfg)
        try:
            os.makedirs(d, exist_ok=True)
            test = os.path.join(d, ".write_test")
            open(test, "w").close(); os.remove(test)
        except Exception as exc:
            problems.append(f"dir not writable: {d} ({exc})")
    if not cfgmod.enabled_sources(cfg):
        problems.append("no research sources enabled")
    return {"name": "config_doctor", "ok": not problems, "problems": problems}


def config_explain() -> dict:
    """Human-readable view of effective config (non-secret)."""
    from . import config as cfgmod
    cfg = cfgmod.load_config()
    return {"default_planner": cfg["default_planner"],
            "artifact_dir": cfgmod.artifact_dir(cfg),
            "history_dir": cfgmod.history_dir(cfg),
            "limits": cfg["limits"],
            "research_sources": cfgmod.enabled_sources(cfg)}


def version_status() -> dict:
    from .engine import is_disabled
    return {"version": VERSION, "python": sys.version.split()[0],
            "kill_switch_active": is_disabled(),
            "repo_root": REPO_ROOT}


def verify() -> dict:
    """Run all safety regression checks. ok=True only if every check passes."""
    checks = [check_isolation(), check_no_wdm_ks(), check_no_sd_rec(),
              check_no_dangerous_calls(), check_gitignored(), config_doctor()]
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def health() -> dict:
    """One-call health snapshot: version + verify summary."""
    v = verify()
    return {"ok": v["ok"], "version": VERSION,
            "passed": sum(1 for c in v["checks"] if c["ok"]),
            "total": len(v["checks"]),
            "failing": [c["name"] for c in v["checks"] if not c["ok"]]}


def discover_orchestrator_tests() -> list[str]:
    """List orchestrator test files (offline, safe-to-run suites)."""
    tdir = os.path.join(REPO_ROOT, "tests")
    names = ("test_orchestrator_mvp", "test_orchestrator_hardening",
             "test_real_agent_capabilities", "test_orchestrator_sprint",
             "test_super_sprint", "test_draft_pr", "test_research_quality",
             "test_draftpr_workflow", "test_github_hardening", "test_memory_evolution",
             "test_goals_queue_scheduler", "test_ops_commands", "test_user_workflows",
             "test_self_evolution", "test_quality_autonomy", "test_autonomy_loop",
             "test_scheduled_autonomy", "test_mega_evolution", "test_graph_planning",
             "test_ascension_intelligence", "test_ascension_systems")
    return [os.path.join("tests", n + ".py") for n in names
            if os.path.exists(os.path.join(tdir, n + ".py"))]


def validation_summary() -> dict:
    """Summary used by `validate` CLI: safety checks + count of discoverable test suites."""
    v = verify()
    return {"safety_ok": v["ok"],
            "checks": {c["name"]: c["ok"] for c in v["checks"]},
            "test_suites": discover_orchestrator_tests()}


def _run_test_suites(exclude: tuple[str, ...] = ()) -> dict:
    """Run every discoverable orchestrator test suite IN-PROCESS (no subprocess). Returns
    {passed, total, failures}. Each suite's test_* functions are executed directly."""
    import importlib.util
    import io
    import contextlib
    passed = total = 0
    failures = []
    for rel in discover_orchestrator_tests():
        name = os.path.basename(rel)[:-3]
        if name in exclude:
            continue
        fp = os.path.join(REPO_ROOT, rel)
        try:
            spec = importlib.util.spec_from_file_location("ci_" + name, fp)
            mod = importlib.util.module_from_spec(spec)
            with contextlib.redirect_stdout(io.StringIO()):
                spec.loader.exec_module(mod)
        except Exception as exc:                          # import-time failure
            failures.append(f"{name}: import {type(exc).__name__}")
            total += 1
            continue
        fns = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
        for fn in fns:
            total += 1
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    fn()
                passed += 1
            except Exception as exc:
                failures.append(f"{name}.{fn.__name__}: {type(exc).__name__}")
    return {"passed": passed, "total": total, "failures": failures}


_PRE_PUSH_HOOK = """#!/bin/sh
# GARVIS orchestrator pre-push gate - runs ci-check, blocks push on failure.
# Installed by: python runtime/orchestrator/cli.py ci-install
echo "[garvis] running orchestrator ci-check before push..."
python runtime/orchestrator/cli.py ci-check || {
    echo "[garvis] ci-check FAILED - push aborted"; exit 1;
}
"""


def install_git_hook(hooks_dir: str | None = None) -> dict:
    """Install a pre-push hook that runs ci-check (tests become automatic on every push).
    Lives under .git/hooks (NOT version-controlled), so no GitHub `workflow` scope needed."""
    hooks_dir = hooks_dir or os.path.join(REPO_ROOT, ".git", "hooks")
    if not os.path.isdir(hooks_dir):
        return {"installed": False, "reason": f"hooks dir not found: {hooks_dir}"}
    path = os.path.join(hooks_dir, "pre-push")
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(_PRE_PUSH_HOOK)
        try:
            os.chmod(path, 0o755)
        except Exception:
            pass
    except Exception as exc:
        return {"installed": False, "reason": str(exc)}
    return {"installed": True, "path": path, "runs": "ci-check on every git push"}


def install_ci_workflow(force: bool = False) -> dict:
    """Copy the CI definition into .github/workflows/ (activates GitHub Actions). Pushing it
    still requires a token with `workflow` scope; this only stages the file locally."""
    src = os.path.join(_DIR, "ci", "orchestrator.yml")
    dst_dir = os.path.join(REPO_ROOT, ".github", "workflows")
    dst = os.path.join(dst_dir, "orchestrator.yml")
    if not os.path.exists(src):
        return {"installed": False, "reason": "ci/orchestrator.yml not found"}
    if os.path.exists(dst) and not force:
        return {"installed": False, "reason": "already present (use force=True to overwrite)"}
    try:
        os.makedirs(dst_dir, exist_ok=True)
        import shutil
        shutil.copyfile(src, dst)
    except Exception as exc:
        return {"installed": False, "reason": str(exc)}
    return {"installed": True, "path": os.path.relpath(dst, REPO_ROOT),
            "note": "commit/push needs a token with GitHub 'workflow' scope"}


def ci_check(run_tests: bool = True) -> dict:
    """Local CI: py_compile + verify + secret-scan (+ all offline tests). In-process; no
    subprocess, no network, no backend. ok=True only when every stage passes."""
    import glob
    import py_compile
    from . import secret_scan, config as cfgmod

    comp_errors = []
    for fp in (glob.glob(os.path.join(_DIR, "*.py"))
               + glob.glob(os.path.join(_DIR, "workers", "*.py"))):
        try:
            py_compile.compile(fp, doraise=True)
        except Exception:
            comp_errors.append(os.path.basename(fp))
    res = {"compile": {"ok": not comp_errors, "errors": comp_errors}}

    v = verify()
    res["verify"] = {"ok": v["ok"], "failing": [c["name"] for c in v["checks"] if not c["ok"]]}

    cfg = cfgmod.load_config()
    hits = secret_scan.scan_dir(cfgmod.artifact_dir(cfg)) + secret_scan.scan_dir(cfgmod.history_dir(cfg))
    res["secret_scan"] = {"ok": not hits, "hits": len(hits)}

    if run_tests:
        # Exclude the autonomy-loop suite to avoid recursion (it calls ci_check itself).
        t = _run_test_suites(exclude=("test_autonomy_loop",))
        res["tests"] = {"ok": t["passed"] == t["total"], "passed": t["passed"],
                        "total": t["total"], "failures": t["failures"][:10]}

    res["ok"] = all(stage["ok"] for stage in res.values() if isinstance(stage, dict))
    return res
