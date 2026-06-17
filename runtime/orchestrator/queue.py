"""
Research queue - file-backed pending research goals, with optional 'due' scheduling.

enqueue(goal, due=None) -> id ; list() ; pending() ; due_now() ; mark_done(id).
'Scheduled runs/reports' = items with a due timestamp surfaced by due_now(); execution is
explicit (a `run-due` CLI command), never a hidden background loop.
"""
from __future__ import annotations

import json
import os
import time
import uuid

_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_runs", "queue.jsonl")


class ResearchQueue:
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

    def enqueue(self, goal: str, due: str | None = None) -> str:
        qid = uuid.uuid4().hex[:10]
        self._append({"id": qid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "goal": goal, "status": "pending", "due": due})
        return qid

    def mark_done(self, qid: str, run_id: str | None = None) -> None:
        self._append({"id": qid, "status": "done", "run_id": run_id,
                      "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})

    def list(self) -> list[dict]:
        latest: dict[str, dict] = {}
        for e in self._events():
            latest[e["id"]] = {**latest.get(e["id"], {}), **e}
        return list(latest.values())

    def pending(self) -> list[dict]:
        return [q for q in self.list() if q.get("status") == "pending"]

    def due_now(self) -> list[dict]:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        return [q for q in self.pending() if not q.get("due") or q["due"] <= now]
