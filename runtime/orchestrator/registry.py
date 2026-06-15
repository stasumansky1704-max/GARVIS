"""Worker registry (INERT SCAFFOLDING)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import SafetyClass


@dataclass
class WorkerSpec:
    name: str
    capabilities: list[str]
    tool_permissions: list[str] = field(default_factory=list)   # least-privilege allowlist
    safety_class: SafetyClass = SafetyClass.READ
    cost_class: str = "cheap"
    description: str = ""


class WorkerRegistry:
    """In-memory registry. Planner only plans with registered capabilities."""

    def __init__(self) -> None:
        self._workers: dict[str, WorkerSpec] = {}

    def register(self, spec: WorkerSpec) -> None:
        self._workers[spec.name] = spec

    def get(self, name: str) -> WorkerSpec | None:
        return self._workers.get(name)

    def capabilities(self) -> dict[str, list[str]]:
        return {n: w.capabilities for n, w in self._workers.items()}

    def __len__(self) -> int:
        return len(self._workers)
