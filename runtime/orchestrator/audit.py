"""
Audit log - append-only JSONL of orchestrator events (gitignored).

Events: run_started, task_started, task_completed, task_blocked, run_completed.
Each record: {ts, kind, ...data}. No secrets are written.
"""
from __future__ import annotations

import json
import os
import time


class AuditLog:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def event(self, kind: str, **data) -> dict:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, **data}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

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

    def query(self, kind: str, limit: int = 50) -> list[dict]:
        """All events of a given kind (most recent last)."""
        return [e for e in self.list() if e.get("kind") == kind][-limit:]

    def summary(self) -> dict:
        """Counts per event kind + total - a quick audit overview."""
        counts: dict[str, int] = {}
        for e in self.list():
            counts[e.get("kind", "?")] = counts.get(e.get("kind", "?"), 0) + 1
        return {"total": sum(counts.values()), "by_kind": counts}
