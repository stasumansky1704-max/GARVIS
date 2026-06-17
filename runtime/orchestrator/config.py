"""
Orchestrator config loader + validator (non-secret).

Loads runtime/orchestrator/orchestrator_config.json (or defaults if absent). Validates
types/ranges and raises ConfigError with a clear message on invalid config. No secrets.
"""
from __future__ import annotations

import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_DIR, "orchestrator_config.json")

DEFAULTS = {
    "default_planner": "llm",                 # "llm" | "manual"
    "artifact_dir": "_artifacts",
    "history_dir": "_runs",
    "limits": {"max_tasks": 8, "max_findings": 5,
               "max_external_requests": 12, "max_seconds": 120},
    "research_sources": {"wikipedia": True, "duckduckgo": True},
}


class ConfigError(Exception):
    pass


def _validate(cfg: dict) -> dict:
    if not isinstance(cfg, dict):
        raise ConfigError("config root must be a JSON object")
    planner = cfg.get("default_planner", DEFAULTS["default_planner"])
    if planner not in ("llm", "manual"):
        raise ConfigError("default_planner must be 'llm' or 'manual'")
    for key in ("limits", "research_sources"):
        if key in cfg and not isinstance(cfg[key], dict):
            raise ConfigError(f"'{key}' must be an object")
    limits = {**DEFAULTS["limits"], **(cfg.get("limits") or {})}
    for k, v in limits.items():
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            raise ConfigError(f"limit '{k}' must be a positive integer (got {v!r})")
    sources = {**DEFAULTS["research_sources"], **(cfg.get("research_sources") or {})}
    for k, v in sources.items():
        if not isinstance(v, bool):
            raise ConfigError(f"research_sources['{k}'] must be a boolean (got {v!r})")
    art = cfg.get("artifact_dir", DEFAULTS["artifact_dir"])
    his = cfg.get("history_dir", DEFAULTS["history_dir"])
    if not isinstance(art, str) or not art or not isinstance(his, str) or not his:
        raise ConfigError("artifact_dir and history_dir must be non-empty strings")
    return {"default_planner": planner, "artifact_dir": art, "history_dir": his,
            "limits": limits, "research_sources": sources}


def load_config(path: str | None = None) -> dict:
    p = path or CONFIG_PATH
    if not os.path.exists(p):
        return _validate({})
    try:
        raw = json.load(open(p, encoding="utf-8"))
    except Exception as exc:
        raise ConfigError(f"invalid JSON in {p}: {exc}")
    return _validate(raw)


def artifact_dir(cfg: dict) -> str:
    return os.path.join(_DIR, cfg["artifact_dir"])


def history_dir(cfg: dict) -> str:
    return os.path.join(_DIR, cfg["history_dir"])


def enabled_sources(cfg: dict) -> tuple[str, ...]:
    return tuple(k for k, v in cfg["research_sources"].items() if v)
