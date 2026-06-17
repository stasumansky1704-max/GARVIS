"""
Run history - simple, durable JSONL storage of completed orchestrator runs.

Each record: {id, timestamp, goal, status, tasks:[{id,worker,intent,status}],
              result_summary, approvals}. Append-on-save; retrievable by id or listed.
No database, no backend wiring. Default path is a gitignored artifacts dir.
"""
from __future__ import annotations

import json
import os
import time

from .models import Run, Status

_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_runs", "history.jsonl")


def run_to_record(run: Run, approvals: set[str] | None = None) -> dict:
    tasks = []
    summary = ""
    for tid, env in run.results.items():
        tasks.append({"id": tid, "status": getattr(env.status, "value", str(env.status)),
                      "error": env.error})
        if isinstance(env.result, dict) and env.result.get("summary"):
            summary = env.result["summary"]
    return {
        "id": run.id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "goal": run.goal,
        "status": getattr(run.status, "value", str(run.status)),
        "tasks": tasks,
        "result_summary": summary,
        "approvals": sorted(approvals or []),
    }


class RunHistory:
    def __init__(self, path: str | None = None):
        self.path = path or _DEFAULT
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def save(self, record: dict) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def list(self) -> list[dict]:
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

    def get(self, run_id: str) -> dict | None:
        # last record wins if an id repeats
        found = None
        for rec in self.list():
            if rec.get("id") == run_id:
                found = rec
        return found

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Find runs whose goal/summary contains all query terms (case-insensitive)."""
        terms = [t for t in query.lower().split() if t]
        out = []
        for r in self.list():
            hay = (r.get("goal", "") + " " + r.get("result_summary", "")).lower()
            if all(t in hay for t in terms):
                out.append(r)
        return out[-limit:]

    def filter(self, status: str) -> list[dict]:
        """Runs with a given status (done/failed/blocked/...)."""
        return [r for r in self.list() if r.get("status") == status]

    def stats(self) -> dict:
        """Aggregate run stats: totals by status + success rate."""
        runs = self.list()
        by: dict[str, int] = {}
        for r in runs:
            by[r.get("status", "?")] = by.get(r.get("status", "?"), 0) + 1
        total = len(runs)
        return {"total": total, "by_status": by,
                "success_rate": round(by.get("done", 0) / total, 3) if total else 0.0}
