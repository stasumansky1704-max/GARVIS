"""Project Registry — projects/registry.py

Central registry for all project contexts. Manages project lifecycle,
context switching, and cross-project governance coordination.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from projects.context import ContextManager, ProjectContext
from projects.governance import ProjectGovernance
from projects.memory import ProjectMemory
from projects.reasoning import OperationalReasoningEngine, WorkflowDefinition

logger = logging.getLogger("garvis.projects.registry")


# ---------------------------------------------------------------------------
# Project Configuration — the 7 GARVIS projects
# ---------------------------------------------------------------------------

PROJECTS: list[dict[str, str]] = [
    {
        "id": "garvis",
        "name": "GARVIS",
        "status": "active",
        "category": "core",
        "description": "Governance runtime — the core governance-aware system",
    },
    {
        "id": "alphaflow",
        "name": "AlphaFlow",
        "status": "planned",
        "category": "workflow",
        "description": "Workflow engine preparation — structured task automation",
    },
    {
        "id": "nova",
        "name": "NOVA",
        "status": "planned",
        "category": "analytics",
        "description": "Analytics platform preparation — data analysis and insights",
    },
    {
        "id": "teachflow",
        "name": "TeachFlow",
        "status": "planned",
        "category": "education",
        "description": "Education platform preparation — structured learning",
    },
    {
        "id": "bella",
        "name": "Bella & Friends",
        "status": "planned",
        "category": "character",
        "description": "Character system preparation — interactive characters",
    },
    {
        "id": "youtube",
        "name": "YouTube Engine",
        "status": "planned",
        "category": "content",
        "description": "Content engine preparation — video content automation",
    },
    {
        "id": "general",
        "name": "General Ops",
        "status": "active",
        "category": "operations",
        "description": "General operations — monitoring, maintenance, reporting",
    },
]


# ---------------------------------------------------------------------------
# ProjectRegistry — central registry for all project contexts
# ---------------------------------------------------------------------------


class ProjectRegistry:
    """Central registry for all project contexts.

    Manages:
    - Project lifecycle (register, initialize, activate)
    - Context switching between projects
    - Cross-project governance coordination
    - Operational reasoning across projects

    Ensures full context isolation between projects.
    """

    def __init__(self) -> None:
        self._context_manager = ContextManager()
        self._reasoning_engine = OperationalReasoningEngine()
        self._initialized = False
        self._initialization_log: list[dict[str, Any]] = []

    # ── Lifecycle ─────────────────────────────────────────────────

    async def initialize(self, global_registry: Any) -> dict[str, Any]:
        """Initialize all 7 projects with governance and memory.

        Args:
            global_registry: The global GovernanceRegistry.

        Returns:
            Initialization result dict.
        """
        logger.info("ProjectRegistry.initialize() — registering all 7 projects")

        initialized: list[str] = []
        failed: list[str] = []

        for project_config in PROJECTS:
            project_id = project_config["id"]
            try:
                # Register with context manager
                context = self._context_manager.register_project(
                    project_id=project_id,
                    config=project_config,
                )

                # Initialize with governance and memory
                await context.initialize(global_registry)

                initialized.append(project_id)

                logger.debug(
                    "Project initialized: %s (%s)",
                    project_id,
                    project_config["name"],
                )

            except Exception as exc:
                logger.error(
                    "Failed to initialize project '%s': %s",
                    project_id,
                    exc,
                )
                failed.append(project_id)

        self._initialized = True

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "initialized" if not failed else "partial",
            "projects_initialized": len(initialized),
            "projects_failed": len(failed),
            "initialized": initialized,
            "failed": failed,
        }
        self._initialization_log.append(result)

        logger.info(
            "ProjectRegistry initialized: %d projects ready, %d failed",
            len(initialized),
            len(failed),
        )

        return result

    async def shutdown(self) -> dict[str, Any]:
        """Shutdown all projects, save state, deactivate contexts.

        Returns:
            Shutdown result dict.
        """
        logger.info("ProjectRegistry.shutdown() — shutting down all projects")

        # Deactivate current context
        active = self._context_manager.get_active_context()
        if active is not None:
            await active.switch_out()

        shutdown_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "shutdown",
            "projects": self._context_manager.list_project_ids(),
            "active_context_was": active.project_id if active else None,
        }
        self._initialization_log.append(shutdown_record)

        self._initialized = False

        return {
            "status": "shutdown",
            "projects": len(self._context_manager.list_project_ids()),
        }

    # ── Context Switching ─────────────────────────────────────────

    async def activate_project(self, project_id: str) -> ProjectContext:
        """Activate a specific project context.

        Args:
            project_id: The project ID to activate.

        Returns:
            The activated ProjectContext.

        Raises:
            ValueError: If project is not registered.
        """
        logger.info("Activating project: %s", project_id)
        return await self._context_manager.switch_context(project_id)

    async def deactivate_current(self) -> None:
        """Deactivate the currently active project context."""
        active = self._context_manager.get_active_context()
        if active is not None:
            await active.switch_out()
            self._context_manager.clear_active_context()
            logger.info("Deactivated project: %s", active.project_id)

    def get_active_project(self) -> ProjectContext | None:
        """Get the currently active project context.

        Returns:
            Active ProjectContext or None.
        """
        return self._context_manager.get_active_context()

    def get_active_project_id(self) -> str | None:
        """Get the ID of the currently active project.

        Returns:
            Active project ID or None.
        """
        return self._context_manager.get_active_project_id()

    # ── Project Queries ───────────────────────────────────────────

    def get_project(self, project_id: str) -> ProjectContext | None:
        """Get a project context by ID.

        Args:
            project_id: The project ID.

        Returns:
            ProjectContext or None if not found.
        """
        return self._context_manager.get_context(project_id)

    def get_project_governance(self, project_id: str) -> ProjectGovernance | None:
        """Get a project's governance system.

        Args:
            project_id: The project ID.

        Returns:
            ProjectGovernance or None.
        """
        context = self._context_manager.get_context(project_id)
        return context.governance if context else None

    def get_project_memory(self, project_id: str) -> ProjectMemory | None:
        """Get a project's memory store.

        Args:
            project_id: The project ID.

        Returns:
            ProjectMemory or None.
        """
        context = self._context_manager.get_context(project_id)
        return context.memory if context else None

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects with their status.

        Returns:
            List of project status dicts.
        """
        return self._context_manager.list_contexts()

    def list_active_projects(self) -> list[dict[str, Any]]:
        """List projects with 'active' status.

        Returns:
            List of active project status dicts.
        """
        return [
            p for p in self._context_manager.list_contexts()
            if p["status"] == "active"
        ]

    def list_planned_projects(self) -> list[dict[str, Any]]:
        """List projects with 'planned' status.

        Returns:
            List of planned project status dicts.
        """
        return [
            p for p in self._context_manager.list_contexts()
            if p["status"] == "planned"
        ]

    # ── Operational Reasoning ─────────────────────────────────────

    def reason_about_workflow(
        self, workflow: WorkflowDefinition, project_id: str | None = None
    ) -> dict[str, Any]:
        """Analyze a workflow within a project context.

        Args:
            workflow: The workflow to analyze.
            project_id: Optional project ID. Uses active project if not specified.

        Returns:
            Reasoning result dict.

        Raises:
            ValueError: If no project context available.
        """
        context = self._resolve_project_context(project_id)
        if context is None:
            raise ValueError(
                "No project context available. "
                "Activate a project or provide project_id."
            )
        return self._reasoning_engine.reason_about_workflow(workflow, context)

    def assess_risk(
        self, action: str, project_id: str | None = None
    ) -> dict[str, Any]:
        """Assess risk of a proposed action.

        Args:
            action: The action to assess.
            project_id: Optional project ID. Uses active project if not specified.

        Returns:
            Risk assessment dict.

        Raises:
            ValueError: If no project context available.
        """
        context = self._resolve_project_context(project_id)
        if context is None:
            raise ValueError(
                "No project context available. "
                "Activate a project or provide project_id."
            )
        return self._reasoning_engine.assess_risk(action, context)

    def prioritize_actions(
        self, actions: list[str], project_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Prioritize actions by governance compliance and risk.

        Args:
            actions: List of actions to prioritize.
            project_id: Optional project ID. Uses active project if not specified.

        Returns:
            Ranked list of actions.

        Raises:
            ValueError: If no project context available.
        """
        context = self._resolve_project_context(project_id)
        if context is None:
            raise ValueError(
                "No project context available. "
                "Activate a project or provide project_id."
            )
        return self._reasoning_engine.prioritize_actions(actions, context)

    def generate_operational_plan(
        self, objective: str, project_id: str | None = None
    ) -> dict[str, Any]:
        """Generate a bounded operational plan.

        Args:
            objective: The objective to plan for.
            project_id: Optional project ID. Uses active project if not specified.

        Returns:
            Operational plan dict.

        Raises:
            ValueError: If no project context available.
        """
        context = self._resolve_project_context(project_id)
        if context is None:
            raise ValueError(
                "No project context available. "
                "Activate a project or provide project_id."
            )
        return self._reasoning_engine.generate_operational_plan(objective, context)

    def get_reasoning_log(self) -> list[dict[str, Any]]:
        """Get the full operational reasoning log.

        Returns:
            List of all reasoning records.
        """
        return self._reasoning_engine.get_reasoning_log()

    # ── Cross-Project Operations ──────────────────────────────────

    async def cross_project_memory_access(
        self,
        source_project_id: str,
        target_project_id: str,
        operator_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Request cross-project memory access.

        Requires explicit operator action. Creates audit trail.

        Args:
            source_project_id: Project requesting access.
            target_project_id: Project being accessed.
            operator_id: Operator requesting access.
            reason: Reason for access.

        Returns:
            Result dict with access status.
        """
        source_ctx = self._context_manager.get_context(source_project_id)
        if source_ctx is None:
            return {
                "status": "error",
                "reason": f"Source project '{source_project_id}' not found",
            }

        target_ctx = self._context_manager.get_context(target_project_id)
        if target_ctx is None:
            return {
                "status": "error",
                "reason": f"Target project '{target_project_id}' not found",
            }

        # Enforce: cannot access if both are active (context isolation)
        if source_ctx.is_active() and target_ctx.is_active():
            return {
                "status": "error",
                "reason": (
                    "Context isolation violation: "
                    "cannot access cross-project memory while both are active"
                ),
            }

        # Request through source project memory
        if source_ctx.memory is not None:
            result = await source_ctx.memory.request_cross_project_access(
                target_project_id=target_project_id,
                operator_id=operator_id,
                reason=reason,
            )
            return result

        return {
            "status": "error",
            "reason": "Source project has no memory store",
        }

    # ── System Health ─────────────────────────────────────────────

    def get_system_health(self) -> dict[str, Any]:
        """Get health status for the entire project governance system.

        Returns:
            System health dict with per-project metrics.
        """
        project_healths: dict[str, dict[str, Any]] = {}
        for ctx_entry in self._context_manager.list_contexts():
            pid = ctx_entry["project_id"]
            ctx = self._context_manager.get_context(pid)
            if ctx is not None and ctx.governance is not None:
                project_healths[pid] = ctx.governance.get_health()
            else:
                project_healths[pid] = {
                    "project_id": pid,
                    "status": "not_initialized",
                }

        # Calculate aggregate metrics
        all_statuses = [h.get("status", "unknown") for h in project_healths.values()]
        healthy_count = all_statuses.count("healthy")

        return {
            "registry_initialized": self._initialized,
            "total_projects": len(self._context_manager.list_contexts()),
            "active_context": self._context_manager.get_active_project_id(),
            "healthy_projects": healthy_count,
            "project_healths": project_healths,
            "overall_status": (
                "healthy" if healthy_count == len(all_statuses)
                else "degraded" if healthy_count >= len(all_statuses) // 2
                else "critical"
            ),
        }

    def get_switch_history(self) -> list[dict[str, Any]]:
        """Get context switch history.

        Returns:
            List of context switch records.
        """
        return self._context_manager.get_switch_history()

    # ── Internal Helpers ──────────────────────────────────────────

    def _resolve_project_context(
        self, project_id: str | None
    ) -> ProjectContext | None:
        """Resolve a project context from ID or active context.

        Args:
            project_id: Explicit project ID, or None for active context.

        Returns:
            ProjectContext or None.
        """
        if project_id is not None:
            return self._context_manager.get_context(project_id)
        return self._context_manager.get_active_context()

    @property
    def context_manager(self) -> ContextManager:
        """Access the underlying ContextManager."""
        return self._context_manager

    @property
    def reasoning_engine(self) -> OperationalReasoningEngine:
        """Access the underlying OperationalReasoningEngine."""
        return self._reasoning_engine

    def __len__(self) -> int:
        return len(self._context_manager)

    def __contains__(self, project_id: str) -> bool:
        return project_id in self._context_manager

    def __repr__(self) -> str:
        return (
            f"ProjectRegistry("
            f"projects={len(self._context_manager)}, "
            f"initialized={self._initialized})"
        )
