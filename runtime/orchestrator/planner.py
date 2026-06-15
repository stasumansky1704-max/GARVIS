"""Planner agent (INERT SCAFFOLDING). Real impl: Ollama + strict JSON schema."""
from __future__ import annotations

from .models import Plan
from .registry import WorkerRegistry


class Planner:
    """Turns a goal + available capabilities + memory into a task graph (Plan)."""

    def __init__(self, registry: WorkerRegistry) -> None:
        self.registry = registry

    def plan(self, run_id: str, goal: str, memory: dict | None = None) -> Plan:
        # Real impl (T7): prompt Ollama with goal + self.registry.capabilities() +
        # retrieved memory, parse strict JSON into TaskSpec[], validate, repair.
        raise NotImplementedError("Planner.plan: implement per docs/GARVIS_NEXT_30_TASKS.md T7")
