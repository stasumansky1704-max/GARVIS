"""Worker base contract (INERT SCAFFOLDING). All workers implement run() -> Envelope."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import TaskSpec, Envelope
from ..registry import WorkerSpec


class Worker(ABC):
    """Uniform, permissioned worker. Subclasses declare a WorkerSpec and implement run().
    No worker accesses secrets directly; external/irreversible actions route through the
    Approval + Safety gates (enforced by the router, not here)."""

    spec: WorkerSpec

    @abstractmethod
    def run(self, task: TaskSpec) -> Envelope:
        ...
