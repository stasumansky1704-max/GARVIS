"""
Planner agents.

- ManualPlanner: WORKING MVP. Builds a Plan from explicitly provided TaskSpecs and
  validates that every referenced worker is registered. No LLM, no network — safe and
  deterministic, suitable for the isolated manual orchestration flow.
- Planner: FUTURE (T7) — LLM-driven planning via Ollama. Still a stub.
"""
from __future__ import annotations

from .models import Plan, TaskSpec
from .registry import WorkerRegistry


class ManualPlanner:
    """Deterministic planner: validate + assemble a Plan from caller-supplied tasks."""

    def __init__(self, registry: WorkerRegistry) -> None:
        self.registry = registry

    def plan(self, run_id: str, goal: str, tasks: list[TaskSpec]) -> Plan:
        ids = {t.id for t in tasks}
        for t in tasks:
            if self.registry.get(t.worker) is None:
                raise ValueError(f"unknown worker in plan: {t.worker!r} (task {t.id})")
            for d in t.deps:
                if d not in ids:
                    raise ValueError(f"task {t.id} depends on unknown task {d!r}")
        return Plan(run_id=run_id, goal=goal, tasks=list(tasks))


class Planner:
    """FUTURE (T7): goal -> task graph via Ollama + strict JSON schema. Not implemented."""

    def __init__(self, registry: WorkerRegistry) -> None:
        self.registry = registry

    def plan(self, run_id: str, goal: str, memory: dict | None = None) -> Plan:
        raise NotImplementedError("Planner.plan (LLM): implement per docs/GARVIS_NEXT_30_TASKS.md T7")
