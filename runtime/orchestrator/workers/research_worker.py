"""
Research Worker - READ-ONLY, no side effects.

Receives a research task and returns STRUCTURED findings:
    {"query","findings":[...],"sources":[...],"summary","mock":bool}

MVP is MOCK (no network, no file writes, no repo changes, no PRs). The structured
output shape is the real contract, so swapping in a real backend later requires no
change to the Router/Merger.

Real implementation path (NEXT tasks, separate PRs):
  - Web: Browser Use or a Playwright/MCP web tool (read-only fetch + extract).
  - Summarize: local Ollama (no external write).
  - Keep safety_class=READ; never write files / open PRs / mutate state.
"""
from __future__ import annotations

import os

from .base import Worker
from ..models import TaskSpec, Envelope, Status, SafetyClass
from ..registry import WorkerSpec

# MOCK by default. A real adapter sets GARVIS_RESEARCH_MOCK=0 AND wires a read-only tool.
RESEARCH_MOCK = os.getenv("GARVIS_RESEARCH_MOCK", "1").strip().lower() in ("1", "true", "yes", "on")


class ResearchWorker(Worker):
    spec = WorkerSpec(
        name="research",
        capabilities=["web_search", "summarize"],
        tool_permissions=["web:read"],          # read-only; no write/external mutation
        safety_class=SafetyClass.READ,          # reads need no approval
        cost_class="cheap",
        description="Read-only web research returning structured findings + citations.",
    )

    def __init__(self, mock: bool = RESEARCH_MOCK) -> None:
        self.mock = mock

    def run(self, task: TaskSpec) -> Envelope:
        query = str(task.inputs.get("query", "")).strip()
        if not query:
            return Envelope(task_id=task.id, status=Status.FAILED,
                            error="research task missing 'query' input")
        if self.mock:
            result = {
                "query": query,
                "findings": [],                 # real adapter fills these (read-only)
                "sources": [],
                "summary": f"(mock) no research performed for: {query}",
                "mock": True,
            }
            return Envelope(task_id=task.id, status=Status.DONE, result=result,
                            logs=["ResearchWorker MOCK: no network, no side effects"])
        # Real path is intentionally not wired here (keeps the sprint side-effect-free).
        return Envelope(task_id=task.id, status=Status.BLOCKED,
                        error="real research backend not configured; set up a read-only "
                              "web tool (Browser Use/MCP) then disable GARVIS_RESEARCH_MOCK",
                        logs=["ResearchWorker: real backend unimplemented (by design)"])
