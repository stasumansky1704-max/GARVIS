"""
Guardian - mini-PC readiness checks (PREPARE ONLY; no deployment, no daemon).

Aggregates the operational pre-flight checks GARVIS would run before operating unattended
on a mini PC: disk headroom, writable artifact/history dirs, the kill switch responding,
safety verification, and vault completeness. All read-only; returns a structured readiness
report. It NEVER deploys, starts a daemon, or touches backend/Docker/GPU/dashboard.
"""
from __future__ import annotations

import os
import shutil

from . import ops


def check_disk(min_free_mb: int = 200, path: str | None = None) -> dict:
    target = path or ops.REPO_ROOT
    try:
        free_mb = shutil.disk_usage(target).free // (1024 * 1024)
        ok = free_mb >= min_free_mb
    except Exception as exc:
        return {"name": "disk", "ok": False, "error": str(exc)}
    return {"name": "disk", "ok": ok, "free_mb": free_mb, "min_free_mb": min_free_mb}


def check_writable(cfg=None) -> dict:
    from . import config as cfgmod
    cfg = cfg or cfgmod.load_config()
    problems = []
    for getter in (cfgmod.artifact_dir, cfgmod.history_dir):
        d = getter(cfg)
        try:
            os.makedirs(d, exist_ok=True)
            t = os.path.join(d, ".guardian_write_test")
            open(t, "w").close(); os.remove(t)
        except Exception as exc:
            problems.append(f"{d}: {exc}")
    return {"name": "writable", "ok": not problems, "problems": problems}


def check_kill_switch() -> dict:
    """Confirm the kill switch actually responds to the env var (so it can stop autonomy)."""
    from .engine import is_disabled, KILL_ENV
    prev = os.environ.get(KILL_ENV)
    try:
        os.environ[KILL_ENV] = "1"
        on = is_disabled()
        os.environ[KILL_ENV] = "0"
        off = is_disabled()
    finally:
        if prev is None:
            os.environ.pop(KILL_ENV, None)
        else:
            os.environ[KILL_ENV] = prev
    return {"name": "kill_switch", "ok": (on and not off)}


def check_safety() -> dict:
    v = ops.verify()
    return {"name": "safety", "ok": v["ok"],
            "failing": [c["name"] for c in v["checks"] if not c["ok"]]}


def check_vault(vault=None, required: list[str] | None = None) -> dict:
    """Vault completeness (presence only). If `required` is given, also require those names."""
    if vault is None:
        from .vault import VaultStore
        vault = VaultStore()
    missing = list(vault.missing())
    if required:
        present = vault.status()
        missing += [n for n in required if not present.get(n)]
    missing = sorted(set(missing))
    return {"name": "vault", "ok": not missing, "missing": missing}


def readiness_report(cfg=None, vault=None, required_secrets: list[str] | None = None,
                     min_free_mb: int = 200) -> dict:
    """Aggregate readiness. ready=True only when every check passes. No side effects beyond
    a transient write-test in the gitignored dirs."""
    checks = [check_disk(min_free_mb), check_writable(cfg), check_kill_switch(),
              check_safety(), check_vault(vault, required_secrets)]
    ready = all(c["ok"] for c in checks)
    return {"ready": ready, "checks": checks,
            "failing": [c["name"] for c in checks if not c["ok"]],
            "deployment": "not performed (prepare-only)"}
