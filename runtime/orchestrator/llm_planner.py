"""
LLM Planner adapter (ISOLATED). Ollama-compatible; produces Plans ONLY; never executes.

- Calls Ollama /api/generate with format=json, asking for a task graph using only the
  registered worker capabilities.
- Validates the structured output (types + worker exists + dep references) before
  building a Plan.
- Graceful fallback: on ANY error (no Ollama, bad JSON, invalid plan), returns an empty
  Plan, or delegates to ManualPlanner when caller-supplied fallback_tasks are given.
- NEVER runs tools/actions - it only returns a Plan. Execution is the Router's job.

Nothing in api/ or runtime/execution/ imports this; it is inert until explicitly wired.
`_call_ollama` is isolated so tests can monkeypatch it (no network in tests).
"""
from __future__ import annotations

import json
import os
import urllib.request

from .models import Plan, TaskSpec
from .planner import ManualPlanner
from .registry import WorkerRegistry

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("GARVIS_PLANNER_MODEL", "llama3.1")
PLANNER_TIMEOUT_S = int(os.getenv("GARVIS_PLANNER_TIMEOUT", "60"))

SYSTEM_PROMPT = (
    "You are GARVIS's task planner. Given a goal and the list of available workers, "
    "output ONLY strict JSON of the form: "
    '{"tasks":[{"id":"t1","worker":"<one of the listed worker names>",'
    '"intent":"short description","inputs":{},"deps":[],"needs_approval":false}]}. '
    "Use only worker names from the provided list. Keep ids unique. deps must reference "
    "earlier task ids. Do not include any prose, only the JSON object."
)


class LLMPlanner:
    """Ollama-backed planner. Returns Plan only; never executes actions."""

    def __init__(self, registry: WorkerRegistry, model: str = OLLAMA_MODEL,
                 host: str = OLLAMA_HOST) -> None:
        self.registry = registry
        self.model = model
        self.host = host
        self.fallback = ManualPlanner(registry)

    # --- prompt + transport (transport isolated for testing) ---
    def _build_prompt(self, goal: str, memory: dict | None) -> str:
        caps = self.registry.capabilities()
        parts = [f"Goal: {goal}", f"Available workers: {json.dumps(caps)}"]
        if memory:
            parts.append(f"Relevant context: {json.dumps(memory)[:2000]}")
        parts.append("Return only the JSON task graph.")
        return "\n".join(parts)

    def _call_ollama(self, system: str, prompt: str) -> str:
        body = json.dumps({"model": self.model, "system": system, "prompt": prompt,
                           "stream": False, "format": "json"}).encode("utf-8")
        req = urllib.request.Request(self.host + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=PLANNER_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8")).get("response", "")

    # --- validation ---
    def _parse_and_validate(self, run_id: str, goal: str, raw: str) -> Plan:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("planner output is not a JSON object")
        tasks_raw = data.get("tasks")
        if not isinstance(tasks_raw, list) or not tasks_raw:
            raise ValueError("planner output has no 'tasks' list")
        ids: set[str] = set()
        tasks: list[TaskSpec] = []
        for t in tasks_raw:
            if not isinstance(t, dict):
                raise ValueError("task is not an object")
            tid = str(t["id"])
            worker = str(t["worker"])
            if self.registry.get(worker) is None:
                raise ValueError(f"unknown worker {worker!r}")
            inputs = t.get("inputs", {}) or {}
            if not isinstance(inputs, dict):
                raise ValueError("task.inputs must be an object")
            deps = [str(d) for d in (t.get("deps", []) or [])]
            tasks.append(TaskSpec(id=tid, worker=worker, intent=str(t.get("intent", "")),
                                  inputs=inputs, deps=deps,
                                  needs_approval=bool(t.get("needs_approval", False))))
            ids.add(tid)
        for t in tasks:                                   # deps must reference known ids
            for d in t.deps:
                if d not in ids:
                    raise ValueError(f"task {t.id} depends on unknown task {d!r}")
        return Plan(run_id=run_id, goal=goal, tasks=tasks)

    # --- public API: returns a Plan, never raises ---
    def plan(self, run_id: str, goal: str, memory: dict | None = None,
             fallback_tasks: list[TaskSpec] | None = None) -> Plan:
        try:
            raw = self._call_ollama(SYSTEM_PROMPT, self._build_prompt(goal, memory))
            return self._parse_and_validate(run_id, goal, raw)
        except Exception:
            # graceful: ManualPlanner with caller tasks if provided, else empty no-op plan
            if fallback_tasks:
                try:
                    return self.fallback.plan(run_id, goal, fallback_tasks)
                except Exception:
                    pass
            return Plan(run_id=run_id, goal=goal, tasks=[])
