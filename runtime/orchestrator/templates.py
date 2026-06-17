"""
Factory-ready templates - reusable, pure builders future factories (Viral / Education /
AlphaFlow / Business agents) compose. No UI, no business implementation - only structured
core foundations (dict/str skeletons) backed by the existing tested capabilities.
"""
from __future__ import annotations

from .research_quality import clean_query, extract_terms


def research_template(topic: str, max_tasks: int = 5) -> dict:
    """A research-job spec: cleaned query + suggested subqueries (factory feeds it to research)."""
    from .decompose import decompose_smart
    return {"kind": "research", "topic": topic,
            "query": clean_query(topic), "subqueries": decompose_smart(topic, max_tasks),
            "max_tasks": max_tasks, "read_only": True}


def proposal_template(goal: str, findings=None) -> dict:
    """A proposal skeleton with the standard sections (filled by generators.change_proposal)."""
    return {"kind": "proposal", "goal": goal,
            "sections": ["Executive summary", "Context", "Options considered (ranked)",
                         "Key evidence", "Recommendation", "Risk / next step"],
            "findings": findings or [], "draft_only": True}


def review_template(subject: str) -> dict:
    """A review checklist template (reused by review/auto_review)."""
    return {"kind": "review", "subject": subject,
            "checklist": ["produced signal?", "evidence quality?", "risks flagged?",
                          "matches goal?", "reusable lesson?"],
            "ratings": ["weak", "auto-good", "good", "excellent"]}


def goal_template(objective: str, priority: int = 3) -> dict:
    return {"kind": "goal", "text": objective, "priority": priority,
            "tags": [], "deps": [], "progress": 0}


def workflow_template(name: str, steps: list[str]) -> dict:
    return {"kind": "workflow", "name": name, "steps": list(steps),
            "safe_by_default": True}


def agent_template(name: str, kind: str, capabilities: list[str] | None = None) -> dict:
    """A composable agent spec referencing core capabilities by name (see agents registry)."""
    from .agents import build_default_registry
    reg = build_default_registry()
    caps = capabilities or [c.name for c in reg.by_kind(kind)]
    valid = [c for c in caps if reg.get(c)]
    return {"kind": "agent", "name": name, "agent_kind": kind,
            "capabilities": valid, "unknown_capabilities": [c for c in caps if not reg.get(c)]}


def memory_template(seed: str) -> dict:
    return {"kind": "memory", "layers": ["user", "project", "decision", "rule", "run"],
            "seed_terms": extract_terms(seed), "protected_layer": "rule"}


def learning_template() -> dict:
    return {"kind": "learning",
            "signals": ["empty_results", "weak_plans", "repeat_failures", "blocked",
                        "denials"],
            "outputs": ["rule", "decision"], "feedback": "rewrite_query"}


CORE_TEMPLATES = ("research", "proposal", "review", "goal", "workflow", "agent",
                  "memory", "learning")


def factory_readiness(registry=None) -> dict:
    """Report what's ready for factories: capability coverage by kind + available templates.
    ready=True when every capability kind has at least one registered capability."""
    from .agents import build_default_registry, KINDS
    reg = registry or build_default_registry()
    kinds = reg.kinds()
    missing = [k for k in KINDS if kinds.get(k, 0) == 0]
    return {"capability_kinds": kinds, "missing_kinds": missing,
            "templates": list(CORE_TEMPLATES),
            "capabilities_total": len(reg),
            "ready": not missing}
