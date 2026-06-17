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
