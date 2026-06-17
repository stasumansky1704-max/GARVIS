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
              check_gitignored(), config_doctor()]
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
             "test_goals_queue_scheduler", "test_ops_commands", "test_user_workflows")
    return [os.path.join("tests", n + ".py") for n in names
            if os.path.exists(os.path.join(tdir, n + ".py"))]


def validation_summary() -> dict:
    """Summary used by `validate` CLI: safety checks + count of discoverable test suites."""
    v = verify()
    return {"safety_ok": v["ok"],
            "checks": {c["name"]: c["ok"] for c in v["checks"]},
            "test_suites": discover_orchestrator_tests()}
