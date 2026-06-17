"""
Vault - a registry of REQUIRED secret *references*, never the secret values.

GARVIS needs to know WHICH credentials must exist (e.g. ELEVENLABS_API_KEY) without ever
storing, returning, or printing their values. The vault stores only the logical name + the
environment variable it resolves from, plus a description. Presence is resolved at call
time from os.environ and exposed ONLY as booleans.

Safety: never reads a value into a return/print; status() returns presence booleans; this
keeps secret-scan clean and makes the vault safe to commit (it holds no secrets).
"""
from __future__ import annotations

import json
import os
import uuid

_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_runs", "vault.jsonl")


class VaultStore:
    def __init__(self, path: str | None = None, env: dict | None = None):
        self.path = path or _DEFAULT
        self._env = env if env is not None else os.environ
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def _append(self, rec):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _events(self):
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
        return out

    def register(self, name: str, env_var: str, description: str = "",
                 required: bool = True) -> str:
        """Register a secret REFERENCE (name + env var). Never accepts a value."""
        if not name or not env_var:
            raise ValueError("name and env_var are required")
        rid = uuid.uuid4().hex[:10]
        self._append({"id": rid, "name": name, "env_var": env_var,
                      "description": description, "required": bool(required)})
        return rid

    def list(self) -> list[dict]:
        latest: dict[str, dict] = {}
        for e in self._events():
            latest[e["name"]] = {**latest.get(e["name"], {}), **e}
        return [r for r in latest.values() if not r.get("removed")]

    def remove(self, name: str) -> bool:
        if not any(r["name"] == name for r in self.list()):
            return False
        self._append({"id": uuid.uuid4().hex[:10], "name": name, "removed": True})
        return True

    def is_present(self, name: str) -> bool:
        """True if the referenced env var is set to a non-empty value. Never returns it."""
        ref = next((r for r in self.list() if r["name"] == name), None)
        if not ref:
            return False
        return bool((self._env.get(ref["env_var"]) or "").strip())

    def status(self) -> dict:
        """Presence map {name: bool} - booleans only, no values."""
        return {r["name"]: self.is_present(r["name"]) for r in self.list()}

    def missing(self) -> list[str]:
        """Names of REQUIRED references that are not currently present."""
        return [r["name"] for r in self.list()
                if r.get("required", True) and not self.is_present(r["name"])]

    def ready(self) -> bool:
        return not self.missing()
