"""Run store (INERT SCAFFOLDING). Protocol + in-memory impl; real impl = postgres."""
from __future__ import annotations

from typing import Protocol

from .models import Run


class RunStore(Protocol):
    def save(self, run: Run) -> None: ...
    def get(self, run_id: str) -> Run | None: ...


class InMemoryRunStore:
    """Volatile store for tests/scaffolding. Real impl persists to postgres (T12)."""

    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    def save(self, run: Run) -> None:
        self._runs[run.id] = run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)
