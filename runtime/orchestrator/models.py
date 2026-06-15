"""Orchestrator data contracts (INERT SCAFFOLDING - stdlib dataclasses only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    DONE = "done"
    BLOCKED = "blocked"
    FAILED = "failed"


class SafetyClass(str, Enum):
    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"
    DANGEROUS = "dangerous"


@dataclass
class TaskSpec:
    """A single planned unit of work routed to a worker."""
    id: str
    worker: str
    intent: str
    inputs: dict[str, Any] = field(default_factory=dict)
    deps: list[str] = field(default_factory=list)
    needs_approval: bool = False
    budget: dict[str, float] = field(default_factory=dict)   # tokens/usd/seconds
    status: Status = Status.PENDING


@dataclass
class Envelope:
    """Uniform worker result envelope."""
    task_id: str
    status: Status
    result: Any = None
    artifacts: list[str] = field(default_factory=list)
    cost: dict[str, float] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class Plan:
    """An ordered/dependency-aware task graph for a goal."""
    run_id: str
    goal: str
    tasks: list[TaskSpec] = field(default_factory=list)


@dataclass
class Run:
    """A top-level orchestration run."""
    id: str
    goal: str
    status: Status = Status.PENDING
    owner: str | None = None
    budget: dict[str, float] = field(default_factory=dict)
    results: dict[str, Envelope] = field(default_factory=dict)
