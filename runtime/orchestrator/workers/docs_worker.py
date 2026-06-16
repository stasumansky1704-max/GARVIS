"""
Docs Worker (INERT SCAFFOLDING) - the lowest-risk first worker (NEXT_30 T13).

Capability: generate/update repo docs and deliver via branch + DRAFT PR. Chosen first
because it exercises the full pipeline (Planner -> Router -> gates -> worker -> Merger)
with minimal blast radius. Real impl uses an LLM + repo file tools + the GitHub worker.
"""
from __future__ import annotations

from .base import Worker
from ..models import TaskSpec, Envelope, SafetyClass
from ..registry import WorkerSpec


class DocsWorker(Worker):
    spec = WorkerSpec(
        name="docs",
        capabilities=["write_docs", "update_docs"],
        tool_permissions=["repo:read", "repo:write", "pulls:write_draft"],
        safety_class=SafetyClass.WRITE,        # -> Approval Gate before any write
        cost_class="cheap",
        description="Generate/update repo docs; deliver via branch + draft PR.",
    )

    def run(self, task: TaskSpec) -> Envelope:
        # MVP DRY-RUN: describe the write without performing any external action (no file
        # write, no PR). Real impl (T13) writes to a branch + opens a DRAFT PR via the
        # GitHub worker; never main, never merge.
        from ..models import Status
        title = task.inputs.get("title", "untitled")
        return Envelope(
            task_id=task.id,
            status=Status.DONE,
            result={"action": "would_write_doc", "title": title,
                    "delivery": "branch + DRAFT PR"},
            artifacts=[f"docs/{title}.md (planned)"],
            logs=["DocsWorker dry-run: no file written, no PR opened (inert MVP)"],
        )
