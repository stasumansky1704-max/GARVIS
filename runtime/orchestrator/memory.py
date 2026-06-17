"""
Memory system - lightweight, file-backed (JSONL), no database.

Layers: user, project, decision, rule, run. Supports add/get/list/search/compress and
planner_context() which feeds relevant memory into planning (rules + user always; plus
decisions and goal-relevant items). Run memory is derived from completed runs so the
planner learns from history. Gitignored storage.
"""
from __future__ import annotations

import json
import os
import time
import uuid

LAYERS = ("user", "project", "decision", "rule", "run")
_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_runs", "memory.jsonl")


def _tokens(s: str) -> set[str]:
    return {t for t in "".join(c.lower() if c.isalnum() else " " for c in s).split() if len(t) > 2}


class MemoryStore:
    def __init__(self, path: str | None = None):
        self.path = path or _DEFAULT
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def add(self, layer: str, text: str, tags=None, meta=None, confidence: float = 1.0) -> str:
        if layer not in LAYERS:
            raise ValueError(f"unknown memory layer {layer!r} (use {LAYERS})")
        rec = {"id": uuid.uuid4().hex[:12], "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "layer": layer, "text": text, "tags": list(tags or []),
               "meta": meta or {}, "confidence": float(confidence)}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec["id"]

    def all(self) -> list[dict]:
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

    def list(self, layer: str | None = None) -> list[dict]:
        return [r for r in self.all() if layer is None or r["layer"] == layer]

    def get(self, mid: str) -> dict | None:
        for r in self.all():
            if r["id"] == mid:
                return r
        return None

    def search(self, query: str, layer: str | None = None, limit: int = 10) -> list[dict]:
        q = _tokens(query)
        scored = []
        for r in self.list(layer):
            score = len(q & _tokens(r["text"] + " " + " ".join(r.get("tags", []))))
            if score:
                scored.append((score, r))
        scored.sort(key=lambda x: (-x[0], x[1]["ts"]))
        return [r for _, r in scored[:limit]]

    def compress(self) -> int:
        """Dedup identical (layer,text); keep highest confidence. Returns removed count."""
        seen: dict[tuple, dict] = {}
        for r in self.all():
            key = (r["layer"], r["text"].strip())
            if key not in seen or r["confidence"] > seen[key]["confidence"]:
                seen[key] = r
        kept = list(seen.values())
        removed = len(self.all()) - len(kept)
        with open(self.path, "w", encoding="utf-8") as f:
            for r in kept:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return removed

    def planner_context(self, goal: str, limit: int = 8) -> dict:
        return {
            "rules": [r["text"] for r in self.list("rule")],
            "user": [r["text"] for r in self.list("user")],
            "decisions": [r["text"] for r in self.list("decision")][:limit],
            "relevant": [r["text"] for r in self.search(goal, limit=limit)],
        }


def record_run(mem: MemoryStore, run) -> str:
    """Write a run-layer memory derived from a completed run (feedback loop)."""
    status = getattr(run.status, "value", str(run.status))
    summary = ""
    for env in run.results.values():
        if isinstance(env.result, dict) and env.result.get("summary"):
            summary = env.result["summary"]
            break
    text = f"run {run.id}: goal='{run.goal}' -> {status}. {summary}"[:500]
    return mem.add("run", text, tags=["run", status], meta={"run_id": run.id, "goal": run.goal})
