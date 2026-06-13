"""GARVIS — Project Governance System (Phase 12)

Per-project governance contexts, operational memory, and context isolation.

Each project has:
- Its own governance scope (inherits global + project-specific constraints)
- Its own memory space (isolated from other projects)
- Its own operational state
- Full context isolation — no cross-project data leakage

Exports:
    ProjectGovernance: Governance system scoped to a specific project
    ProjectContext: Isolated context for a single project
    ProjectMemory: Memory store scoped to a single project
    ProjectRegistry: Registry of all project contexts with lifecycle management
"""

from projects.governance import ProjectGovernance
from projects.context import ProjectContext, ContextManager
from projects.memory import ProjectMemory
from projects.registry import ProjectRegistry

__all__ = [
    "ProjectGovernance",
    "ProjectContext",
    "ProjectMemory",
    "ProjectRegistry",
    "ContextManager",
]
