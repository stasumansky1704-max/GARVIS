"""
Agent capability registry - the reusable building blocks future business agents compose.

Each capability is metadata pointing at an existing, tested core function (research,
proposal, review, planning, memory, learning, autonomy, ...). The registry lets a future
factory enumerate and assemble capabilities WITHOUT reimplementing the core. No business
logic here - just a typed, queryable catalog of what GARVIS can already do.
"""
from __future__ import annotations

from dataclasses import dataclass, field

KINDS = ("research", "proposal", "review", "goal", "workflow", "memory",
         "learning", "planning", "autonomy")


@dataclass
class AgentCapability:
    name: str
    kind: str                       # one of KINDS
    ref: str                        # "module:function" pointer to the core implementation
    description: str = ""
    safety_class: str = "read"      # read | write | external
    tags: list = field(default_factory=list)


class CapabilityRegistry:
    def __init__(self):
        self._caps: dict[str, AgentCapability] = {}

    def register(self, cap: AgentCapability) -> None:
        if cap.kind not in KINDS:
            raise ValueError(f"unknown capability kind {cap.kind!r} (use {KINDS})")
        self._caps[cap.name] = cap

    def get(self, name: str) -> AgentCapability | None:
        return self._caps.get(name)

    def list(self) -> list[AgentCapability]:
        return list(self._caps.values())

    def by_kind(self, kind: str) -> list[AgentCapability]:
        return [c for c in self._caps.values() if c.kind == kind]

    def kinds(self) -> dict:
        out: dict[str, int] = {}
        for c in self._caps.values():
            out[c.kind] = out.get(c.kind, 0) + 1
        return out

    def catalog(self) -> list[dict]:
        return [{"name": c.name, "kind": c.kind, "ref": c.ref,
                 "safety_class": c.safety_class} for c in self.list()]

    def __len__(self) -> int:
        return len(self._caps)


# The core capabilities GARVIS exposes today, as reusable metadata.
_CORE = [
    AgentCapability("research", "research", "workflows:Workflows.research_to_report",
                    "Read-only web research -> ranked findings", "read"),
    AgentCapability("decision_support", "research", "summarize:decision_support",
                    "Findings -> recommendation + confidence + risks", "read"),
    AgentCapability("proposal", "proposal", "generators:change_proposal",
                    "Findings -> ranked change proposal", "read"),
    AgentCapability("draft_pr", "proposal", "workers.github_worker:GitHubDraftPRWorker",
                    "Approval-gated draft PR creation", "external"),
    AgentCapability("review", "review", "brief:review_run",
                    "Record a run review into memory", "write"),
    AgentCapability("auto_review", "review", "brief:auto_review",
                    "Auto-rate recent runs", "write"),
    AgentCapability("goal", "goal", "goals:GoalRegistry",
                    "Goals with priority/deps/blockers", "write"),
    AgentCapability("workflow", "workflow", "workflows:Workflows",
                    "Composed end-to-end flows", "read"),
    AgentCapability("memory_graph", "memory", "memory:MemoryStore",
                    "Graph + lifecycle memory", "write"),
    AgentCapability("learn", "learning", "selflearn:learn",
                    "Write deduped lessons from history", "write"),
    AgentCapability("plan", "planning", "planning:multi_strategy_decompose",
                    "Multi-strategy, centrality-ranked planning", "read"),
    AgentCapability("loop", "autonomy", "autonomy:run_loop",
                    "Bounded, approval-gated scheduled loop", "write"),
    AgentCapability("schedule", "autonomy", "schedule:ScheduleStore",
                    "Persisted recurring schedules", "write"),
]


def build_default_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    for cap in _CORE:
        reg.register(cap)
    return reg
