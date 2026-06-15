"""
Research Worker (MVP DRY-RUN) - safe, read-only, no network.

Capability: web search + summarize. In the inert MVP it performs NO network call and
returns a structured "would research" envelope, so the pipeline can be exercised safely.
Real impl (NEXT_30 T14) uses Browser Use / an MCP web tool, read-only.
"""
from __future__ import annotations

from .base import Worker
from ..models import TaskSpec, Envelope, Status, SafetyClass
from ..registry import WorkerSpec


class ResearchWorker(Worker):
    spec = WorkerSpec(
        name="research",
        capabilities=["web_search", "summarize"],
        tool_permissions=["web:read"],          # read-only
        safety_class=SafetyClass.READ,          # no approval needed for reads
        cost_class="cheap",
        description="Read-only web research + summary with citations.",
    )

    def run(self, task: TaskSpec) -> Envelope:
        query = task.inputs.get("query", "")
        return Envelope(
            task_id=task.id,
            status=Status.DONE,
            result={"action": "would_research", "query": query,
                    "note": "network disabled in inert MVP"},
            logs=["ResearchWorker dry-run: no network call (inert MVP)"],
        )
