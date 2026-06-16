"""
Isolated orchestrator MVP demo (SAFE: no network, no LLM, no audio, no backend wiring).

Run:
    python runtime/orchestrator/demo.py

Shows the manual flow: ManualPlanner -> Router (Safety + Approval gates) -> Worker.run
-> Merger. A read-only Research task runs automatically; a Docs task (WRITE) runs only
because it is explicitly approved. Re-run without the approval to see it BLOCKED.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # add runtime/

from orchestrator.engine import Orchestrator
from orchestrator.models import TaskSpec
from orchestrator.registry import WorkerRegistry
from orchestrator.workers.docs_worker import DocsWorker
from orchestrator.workers.research_worker import ResearchWorker


def build() -> Orchestrator:
    docs, research = DocsWorker(), ResearchWorker()
    reg = WorkerRegistry()
    reg.register(docs.spec)
    reg.register(research.spec)
    workers = {docs.spec.name: docs, research.spec.name: research}
    return Orchestrator(reg, workers)


def main() -> int:
    orch = build()
    tasks = [
        TaskSpec(id="t1", worker="research", intent="research a topic",
                 inputs={"query": "best multilingual TTS"}),
        TaskSpec(id="t2", worker="docs", intent="write a summary doc",
                 inputs={"title": "tts_summary"}, deps=["t1"], needs_approval=True),
    ]
    print("== run WITH approval for t2 ==")
    run = orch.run_manual("demo: research then document", tasks, approvals={"t2"})
    print(f"run {run.id} status={run.status.value}")
    for tid, env in run.results.items():
        print(f"  {tid}: {env.status.value}  {env.result or env.error}")

    print("\n== run WITHOUT approval for t2 (expect t2 BLOCKED) ==")
    orch2 = build()
    run2 = orch2.run_manual("demo: no approval", tasks)
    print(f"run {run2.id} status={run2.status.value}")
    for tid, env in run2.results.items():
        print(f"  {tid}: {env.status.value}  {env.result or env.error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
