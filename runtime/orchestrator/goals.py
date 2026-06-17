"""
Goal registry - track goals, their status, and completion metrics. File-backed JSONL.

Statuses: open -> in_progress -> done (or blocked). Reused by the autonomy demo flow.
"""
from __future__ import annotations

import json
import os
import time
import uuid

_STATES = ("open", "in_progress", "done", "blocked")
_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_runs", "goals.jsonl")


class GoalRegistry:
    def __init__(self, path: str | None = None):
        self.path = path or _DEFAULT
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

    def add(self, text: str) -> str:
        gid = uuid.uuid4().hex[:10]
        self._append({"id": gid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "text": text, "status": "open", "runs": []})
        return gid

    def set_status(self, gid: str, status: str, run_id: str | None = None) -> bool:
        if status not in _STATES:
            raise ValueError(f"bad status {status!r} (use {_STATES})")
        if not self._current(gid):
            return False
        self._append({"id": gid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "status": status, "run_id": run_id})
        return True

    def _current(self, gid: str) -> dict | None:
        cur = None
        for e in self._events():
            if e["id"] == gid:
                cur = {**(cur or {}), **e}
        return cur

    def list(self) -> list[dict]:
        latest: dict[str, dict] = {}
        runs: dict[str, list] = {}
        for e in self._events():
            gid = e["id"]
            latest[gid] = {**latest.get(gid, {}), **{k: v for k, v in e.items() if k != "run_id"}}
            if e.get("run_id"):
                runs.setdefault(gid, []).append(e["run_id"])
        for gid, g in latest.items():
            g["runs"] = runs.get(gid, [])
        return list(latest.values())

    def metrics(self) -> dict:
        m = {s: 0 for s in _STATES}
        goals = self.list()
        for g in goals:
            m[g.get("status", "open")] = m.get(g.get("status", "open"), 0) + 1
        m["total"] = len(goals)
        m["completion_rate"] = round(m["done"] / m["total"], 2) if goals else 0.0
        return m
