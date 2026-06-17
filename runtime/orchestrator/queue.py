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

    def enqueue(self, goal: str, due: str | None = None, priority: int = 3,
                max_retries: int = 2, deps: list | None = None) -> str:
        qid = uuid.uuid4().hex[:10]
        self._append({"id": qid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "goal": goal, "status": "pending", "due": due,
                      "priority": int(priority), "attempts": 0,
                      "max_retries": int(max_retries), "errors": [],
                      "deps": list(deps or [])})
        return qid

    def deps_satisfied(self, item: dict) -> bool:
        """True when all of an item's dependency queue-ids are done."""
        done = {q["id"] for q in self.list() if q.get("status") == "done"}
        return all(d in done for d in (item.get("deps") or []))

    def mark_done(self, qid: str, run_id: str | None = None) -> None:
        self._append({"id": qid, "status": "done", "run_id": run_id,
                      "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})

    def annotate(self, qid: str, **fields) -> None:
        """Attach metadata to a queue item (e.g. original_goal / rewritten_goal). Merged by
        list() (latest event wins), so it persists without mutating prior events."""
        self._append({"id": qid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **fields})

    def rewrites(self) -> list[dict]:
        """Items whose goal was rewritten by self-learning (original -> rewritten)."""
        return [{"id": q["id"], "original": q.get("original_goal"),
                 "rewritten": q.get("rewritten_goal")}
                for q in self.list() if q.get("rewritten_goal")]

    def mark_failed(self, qid: str, error: str) -> dict:
        """Capture a failure; re-queue for retry until max_retries, then mark 'failed'.
        Returns the resulting state {status, attempts, will_retry}."""
        cur = next((q for q in self.list() if q["id"] == qid), None)
        if not cur:
            return {"status": "unknown", "will_retry": False}
        attempts = int(cur.get("attempts", 0)) + 1
        errors = list(cur.get("errors", [])) + [error]
        will_retry = attempts <= int(cur.get("max_retries", 2))
        self._append({"id": qid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "status": "pending" if will_retry else "failed",
                      "attempts": attempts, "errors": errors})
        return {"status": "pending" if will_retry else "failed",
                "attempts": attempts, "will_retry": will_retry}

    def list(self) -> list[dict]:
        latest: dict[str, dict] = {}
        for e in self._events():
            latest[e["id"]] = {**latest.get(e["id"], {}), **e}
        return list(latest.values())

    def pending(self) -> list[dict]:
        return [q for q in self.list() if q.get("status") == "pending"]

    def failed(self) -> list[dict]:
        return [q for q in self.list() if q.get("status") == "failed"]

    def due_now(self) -> list[dict]:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        return [q for q in self.pending()
                if (not q.get("due") or q["due"] <= now) and self.deps_satisfied(q)]

    def prioritized_due(self) -> list[dict]:
        """Due items ordered by priority (1=highest) then due date - the run order."""
        return sorted(self.due_now(),
                      key=lambda q: (q.get("priority", 3), q.get("due") or "9999"))

    def dry_run(self) -> list[dict]:
        """Show what would run now WITHOUT executing anything (safe scheduler foundation)."""
        return [{"id": q["id"], "goal": q["goal"], "priority": q.get("priority", 3),
                 "attempts": q.get("attempts", 0)} for q in self.prioritized_due()]
