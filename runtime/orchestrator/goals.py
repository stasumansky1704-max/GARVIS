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

    def add(self, text: str, priority: int = 3, due: str | None = None,
            tags=None, deps=None) -> str:
        gid = uuid.uuid4().hex[:10]
        self._append({"id": gid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "text": text, "status": "open", "runs": [],
                      "priority": int(priority), "due": due, "tags": list(tags or []),
                      "deps": list(deps or []), "blockers": [], "progress": 0})
        return gid

    def set_status(self, gid: str, status: str, run_id: str | None = None) -> bool:
        if status not in _STATES:
            raise ValueError(f"bad status {status!r} (use {_STATES})")
        if not self._current(gid):
            return False
        prog = 100 if status == "done" else None
        ev = {"id": gid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "status": status, "run_id": run_id}
        if prog is not None:
            ev["progress"] = prog
        self._append(ev)
        return True

    def set_priority(self, gid: str, priority: int) -> bool:
        if not self._current(gid):
            return False
        self._append({"id": gid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "priority": int(priority)})
        return True

    def set_progress(self, gid: str, pct: int) -> bool:
        if not self._current(gid):
            return False
        self._append({"id": gid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "progress": max(0, min(100, int(pct)))})
        return True

    def add_blocker(self, gid: str, reason: str) -> bool:
        cur = self._current(gid)
        if not cur:
            return False
        blockers = list(cur.get("blockers", [])) + [reason]
        self._append({"id": gid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "blockers": blockers, "status": "blocked"})
        return True

    def clear_blockers(self, gid: str) -> bool:
        cur = self._current(gid)
        if not cur:
            return False
        self._append({"id": gid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "blockers": [], "status": "open"})
        return True

    def is_ready(self, gid: str) -> bool:
        """A goal is ready when it has no blockers and all dependency goals are done."""
        cur = self._current(gid)
        if not cur or cur.get("blockers"):
            return False
        done = {g["id"] for g in self.list() if g.get("status") == "done"}
        return all(d in done for d in cur.get("deps", []))

    def review(self, gid: str) -> dict:
        """Compact review of a single goal (status, progress, blockers, readiness, runs)."""
        cur = self._current(gid)
        if not cur:
            return {"found": False}
        g = next((x for x in self.list() if x["id"] == gid), cur)
        return {"found": True, "id": gid, "text": g.get("text", ""),
                "status": g.get("status", "open"), "priority": g.get("priority", 3),
                "progress": g.get("progress", 0), "due": g.get("due"),
                "tags": g.get("tags", []), "deps": g.get("deps", []),
                "blockers": g.get("blockers", []), "ready": self.is_ready(gid),
                "runs": g.get("runs", [])}

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

    def prioritized(self) -> list[dict]:
        """Open/in-progress goals ordered by priority (1=highest) then due date."""
        active = [g for g in self.list() if g.get("status") in ("open", "in_progress")]
        return sorted(active, key=lambda g: (g.get("priority", 3), g.get("due") or "9999"))

    def metrics(self) -> dict:
        m = {s: 0 for s in _STATES}
        goals = self.list()
        for g in goals:
            m[g.get("status", "open")] = m.get(g.get("status", "open"), 0) + 1
        m["total"] = len(goals)
        m["completion_rate"] = round(m["done"] / m["total"], 2) if goals else 0.0
        return m
