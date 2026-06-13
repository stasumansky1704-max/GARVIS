"""Project Context — projects/context.py

Context isolation between projects. Each project has its own:
- Governance scope (inherits global + project-specific constraints)
- Memory space (isolated from other projects)
- Operational state
- Audit trail
- Workflow registry

Contexts are fully isolated — no cross-project data leakage.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from projects.governance import ProjectGovernance
from projects.memory import ProjectMemory

logger = logging.getLogger("garvis.projects.context")


# ---------------------------------------------------------------------------
# ProjectContext — isolated context for a single project
# ---------------------------------------------------------------------------


class ProjectContext:
    """Isolated context for a single project.

    Each project has its own:
    - Governance scope
    - Memory space
    - Operational state
    - Audit trail
    - Workflow registry

    Contexts are fully isolated — no cross-project data leakage.
    """

    def __init__(self, project_id: str, project_config: dict[str, Any]) -> None:
        self.project_id = project_id
        self.name = project_config["name"]
        self.category = project_config.get("category", "uncategorized")
        self.status = project_config.get("status", "planned")
        self.description = project_config.get("description", "")
        self._governance: ProjectGovernance | None = None
        self._memory: ProjectMemory | None = None
        self._state: dict[str, Any] = {}  # Project-specific state
        self._workflows: list[str] = []  # Active workflow IDs
        self._audit_log: list[dict[str, Any]] = []  # Project audit trail
        self._is_active: bool = False
        self._initialized: bool = False
        self._created_at: str = datetime.now(timezone.utc).isoformat()
        self._last_switched_in: str | None = None
        self._last_switched_out: str | None = None

    # ── Lifecycle ─────────────────────────────────────────────────

    async def initialize(self, global_registry: Any) -> None:
        """Initialize project context with governance and memory.

        Args:
            global_registry: The global GovernanceRegistry to inherit from.
        """
        logger.info(
            "ProjectContext.initialize() — project=%s, name=%s",
            self.project_id,
            self.name,
        )

        # Initialize governance (inherits from global)
        self._governance = ProjectGovernance(self.project_id, global_registry)
        self._governance.initialize()

        # Initialize memory store
        self._memory = ProjectMemory(self.project_id)

        self._initialized = True
        logger.info(
            "ProjectContext initialized: project=%s, schemas=%d",
            self.project_id,
            len(self._governance.get_active_schemas()) if self._governance else 0,
        )

    # ── Context Switching ─────────────────────────────────────────

    async def switch_in(self) -> dict[str, Any]:
        """Activate this project context.

        Returns the governance context to apply. Records audit entry.

        Returns:
            Dict with governance context for the activated project.
        """
        self._is_active = True
        self._last_switched_in = datetime.now(timezone.utc).isoformat()

        audit_entry = {
            "timestamp": self._last_switched_in,
            "action": "context_activated",
            "project_id": self.project_id,
            "project_name": self.name,
        }
        self._audit_log.append(audit_entry)

        # Store context activation in project memory
        if self._memory is not None:
            await self._memory.store(
                content=f"Project context activated: {self.name}",
                memory_type="context_switch",
                metadata={"action": "switch_in", "project_id": self.project_id},
            )

        logger.info(
            "Project context activated: project=%s, name=%s",
            self.project_id,
            self.name,
        )

        return {
            "project_id": self.project_id,
            "project_name": self.name,
            "governance_active": self._governance is not None,
            "active_schemas": (
                [s.schema_id for s in self._governance.get_active_schemas()]
                if self._governance else []
            ),
            "project_constraints": (
                [c.constraint_id for c in self._governance.get_project_constraints()]
                if self._governance else []
            ),
        }

    async def switch_out(self) -> None:
        """Deactivate this project context, save state."""
        self._last_switched_out = datetime.now(timezone.utc).isoformat()

        audit_entry = {
            "timestamp": self._last_switched_out,
            "action": "context_deactivated",
            "project_id": self.project_id,
            "project_name": self.name,
        }
        self._audit_log.append(audit_entry)

        # Store context deactivation in project memory
        if self._memory is not None:
            await self._memory.store(
                content=f"Project context deactivated: {self.name}",
                memory_type="context_switch",
                metadata={"action": "switch_out", "project_id": self.project_id},
            )

        self._is_active = False
        logger.info(
            "Project context deactivated: project=%s, name=%s",
            self.project_id,
            self.name,
        )

    # ── State Management ──────────────────────────────────────────

    def set_state(self, key: str, value: Any) -> None:
        """Set a project-specific state value.

        Args:
            key: State key.
            value: State value.
        """
        self._state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a project-specific state value.

        Args:
            key: State key.
            default: Default value if key not found.

        Returns:
            The state value or default.
        """
        return self._state.get(key, default)

    def clear_state(self) -> None:
        """Clear all project-specific state."""
        self._state.clear()

    # ── Workflow Management ───────────────────────────────────────

    def register_workflow(self, workflow_id: str) -> None:
        """Register an active workflow for this project.

        Args:
            workflow_id: The workflow ID to register.
        """
        if workflow_id not in self._workflows:
            self._workflows.append(workflow_id)

    def unregister_workflow(self, workflow_id: str) -> bool:
        """Unregister a workflow from this project.

        Args:
            workflow_id: The workflow ID to unregister.

        Returns:
            True if workflow was removed, False if not found.
        """
        if workflow_id in self._workflows:
            self._workflows.remove(workflow_id)
            return True
        return False

    def get_active_workflows(self) -> list[str]:
        """Get list of active workflow IDs.

        Returns:
            List of active workflow IDs.
        """
        return list(self._workflows)

    # ── Status ────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Get full project context status.

        Returns:
            Dict with comprehensive project status.
        """
        return {
            "project_id": self.project_id,
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "description": self.description,
            "initialized": self._initialized,
            "is_active": self._is_active,
            "created_at": self._created_at,
            "last_switched_in": self._last_switched_in,
            "last_switched_out": self._last_switched_out,
            "governance": (
                self._governance.get_health() if self._governance else None
            ),
            "memory_entries": (
                self._memory.get_statistics() if self._memory else None
            ),
            "state_keys": list(self._state.keys()),
            "active_workflows": list(self._workflows),
            "audit_log_entries": len(self._audit_log),
        }

    def is_active(self) -> bool:
        """Check if project context is currently active.

        Returns:
            True if this project context is the active one.
        """
        return self._is_active

    # ── Property Accessors ────────────────────────────────────────

    @property
    def governance(self) -> ProjectGovernance | None:
        """Access the project's governance system."""
        return self._governance

    @property
    def memory(self) -> ProjectMemory | None:
        """Access the project's memory store."""
        return self._memory

    @property
    def audit_log(self) -> list[dict[str, Any]]:
        """Access the project's audit trail."""
        return list(self._audit_log)

    def __repr__(self) -> str:
        return (
            f"ProjectContext("
            f"project_id='{self.project_id}', "
            f"name='{self.name}', "
            f"active={self._is_active}, "
            f"initialized={self._initialized})"
        )


# ---------------------------------------------------------------------------
# ContextManager — manages all project contexts
# ---------------------------------------------------------------------------


class ContextManager:
    """Manages all project contexts.

    Ensures:
    - Only one context active at a time
    - Clean context switching
    - No cross-context data leakage
    - Governance context updated on switch
    """

    def __init__(self) -> None:
        self._contexts: dict[str, ProjectContext] = {}
        self._active_context: ProjectContext | None = None
        self._switch_history: list[dict[str, Any]] = []

    # ── Project Registration ──────────────────────────────────────

    def register_project(
        self, project_id: str, config: dict[str, Any]
    ) -> ProjectContext:
        """Register a new project context.

        Args:
            project_id: Unique project identifier.
            config: Project configuration dict with name, category, status.

        Returns:
            The registered ProjectContext.

        Raises:
            ValueError: If project_id is already registered.
        """
        if project_id in self._contexts:
            raise ValueError(
                f"Project '{project_id}' is already registered. "
                f"Use get_context() to access it."
            )

        context = ProjectContext(project_id, config)
        self._contexts[project_id] = context

        logger.info(
            "Project registered: project_id=%s, name=%s, category=%s",
            project_id,
            config.get("name", "unknown"),
            config.get("category", "uncategorized"),
        )

        return context

    # ── Context Switching ─────────────────────────────────────────

    async def switch_context(self, project_id: str) -> ProjectContext:
        """Switch to a different project context.

        Saves current context state, loads new context, updates governance.
        Ensures only one context is active at a time.

        Args:
            project_id: The project ID to switch to.

        Returns:
            The newly activated ProjectContext.

        Raises:
            ValueError: If project_id is not registered.
        """
        if project_id not in self._contexts:
            raise ValueError(
                f"Project '{project_id}' is not registered. "
                f"Available: {list(self._contexts.keys())}"
            )

        target_context = self._contexts[project_id]

        # If already active, no-op
        if self._active_context is not None and self._active_context.project_id == project_id:
            logger.debug(
                "Project '%s' is already active, no switch needed",
                project_id,
            )
            return target_context

        # Switch out current context
        if self._active_context is not None:
            await self._active_context.switch_out()
            logger.debug(
                "Switched out context: %s",
                self._active_context.project_id,
            )

        # Switch in new context
        self._active_context = target_context
        governance_context = await target_context.switch_in()

        # Record switch history
        switch_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
            "project_name": target_context.name,
            "governance_context": governance_context,
        }
        self._switch_history.append(switch_record)

        logger.info(
            "Context switched to: project=%s, name=%s, schemas=%d",
            project_id,
            target_context.name,
            len(governance_context.get("active_schemas", [])),
        )

        return target_context

    # ── Queries ───────────────────────────────────────────────────

    def get_active_context(self) -> ProjectContext | None:
        """Get currently active project context.

        Returns:
            The active ProjectContext or None if no context is active.
        """
        return self._active_context

    def get_active_project_id(self) -> str | None:
        """Get the ID of the currently active project.

        Returns:
            Active project ID or None.
        """
        return self._active_context.project_id if self._active_context else None

    def clear_active_context(self) -> None:
        """Clear the active context reference.

        Used when the active context is deactivated externally.
        Does NOT call switch_out — that must be done separately.
        """
        self._active_context = None

    def get_context(self, project_id: str) -> ProjectContext | None:
        """Get a specific project context by ID.

        Args:
            project_id: The project ID to look up.

        Returns:
            The ProjectContext or None if not registered.
        """
        return self._contexts.get(project_id)

    def list_contexts(self) -> list[dict[str, Any]]:
        """List all project contexts with status.

        Returns:
            List of status dicts for all registered projects.
        """
        return [
            {
                "project_id": ctx.project_id,
                "name": ctx.name,
                "category": ctx.category,
                "status": ctx.status,
                "is_active": ctx.is_active(),
                "initialized": ctx._initialized,
            }
            for ctx in self._contexts.values()
        ]

    def list_project_ids(self) -> list[str]:
        """List all registered project IDs.

        Returns:
            List of registered project IDs.
        """
        return list(self._contexts.keys())

    def get_switch_history(self) -> list[dict[str, Any]]:
        """Get context switch history.

        Returns:
            List of switch history records.
        """
        return list(self._switch_history)

    def __len__(self) -> int:
        return len(self._contexts)

    def __contains__(self, project_id: str) -> bool:
        return project_id in self._contexts

    def __repr__(self) -> str:
        active = (
            self._active_context.project_id
            if self._active_context else "None"
        )
        return (
            f"ContextManager("
            f"projects={len(self._contexts)}, "
            f"active='{active}')"
        )
