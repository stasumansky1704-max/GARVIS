"""Project Memory — projects/memory.py

Memory store scoped to a single project. All memories are tagged with
their project ID. Retrieval is scoped to the active project.
Cross-project memory access requires explicit operator action.

Uses in-memory storage (use DB in production).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger("garvis.projects.memory")


# ---------------------------------------------------------------------------
# ProjectMemory — memory store scoped to a single project
# ---------------------------------------------------------------------------


class ProjectMemory:
    """Memory store scoped to a single project.

    All memories are tagged with their project ID.
    Retrieval is scoped to the active project.
    Cross-project memory access requires explicit operator action.

    Uses in-memory store (use DB in production).
    """

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self._memories: list[dict[str, Any]] = []
        self._next_id: int = 1

    # ── Storage ───────────────────────────────────────────────────

    async def store(
        self, content: str, memory_type: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Store a memory scoped to this project.

        Args:
            content: The memory content.
            memory_type: Type of memory (e.g., 'context_switch', 'decision', 'workflow').
            metadata: Optional metadata dict.

        Returns:
            Stored memory record dict.
        """
        memory_id = f"{self.project_id}_{self._next_id:06d}"
        self._next_id += 1

        entry = {
            "memory_id": memory_id,
            "project_id": self.project_id,
            "content": content,
            "memory_type": memory_type,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "retrieval_count": 0,
            "last_accessed": None,
        }

        self._memories.append(entry)

        logger.debug(
            "Memory stored: project=%s, type=%s, id=%s",
            self.project_id,
            memory_type,
            memory_id,
        )

        return dict(entry)

    # ── Retrieval ─────────────────────────────────────────────────

    async def retrieve(
        self, query: str | None = None, limit: int = 10, memory_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve memories scoped to this project.

        Args:
            query: Optional text query to filter memories (substring match).
            limit: Maximum number of memories to return.
            memory_type: Optional filter by memory type.

        Returns:
            List of matching memory records, most recent first.
        """
        results: list[dict[str, Any]] = []

        # Iterate in reverse (most recent first)
        for entry in reversed(self._memories):
            # Memory type filter
            if memory_type is not None and entry["memory_type"] != memory_type:
                continue

            # Text query filter
            if query is not None and query.lower() not in entry["content"].lower():
                continue

            # Update access metadata
            entry["retrieval_count"] += 1
            entry["last_accessed"] = datetime.now(timezone.utc).isoformat()

            results.append(dict(entry))

            if len(results) >= limit:
                break

        logger.debug(
            "Memory retrieved: project=%s, query=%s, found=%d",
            self.project_id,
            query,
            len(results),
        )

        return results

    async def get_by_id(self, memory_id: str) -> dict[str, Any] | None:
        """Get a specific memory by ID.

        Args:
            memory_id: The memory ID to look up.

        Returns:
            Memory record dict or None if not found.
        """
        for entry in self._memories:
            if entry["memory_id"] == memory_id:
                entry["retrieval_count"] += 1
                entry["last_accessed"] = datetime.now(timezone.utc).isoformat()
                return dict(entry)
        return None

    # ── Specialized Queries ───────────────────────────────────────

    async def get_workflow_history(self) -> list[dict[str, Any]]:
        """Get workflow execution history for this project.

        Returns:
            List of workflow-related memory records.
        """
        return [
            dict(entry) for entry in self._memories
            if entry["memory_type"] in ("workflow", "workflow_execution", "workflow_step")
        ]

    async def get_decision_ancestry(self) -> list[dict[str, Any]]:
        """Get decision lineage for this project.

        Returns:
            List of decision-related memory records, oldest first.
        """
        return [
            dict(entry) for entry in self._memories
            if entry["memory_type"] in ("decision", "governance_decision", "context_switch")
        ]

    async def get_governance_continuity(self) -> list[dict[str, Any]]:
        """Get governance continuity record for this project.

        Returns:
            List of governance-related memory records.
        """
        return [
            dict(entry) for entry in self._memories
            if entry["memory_type"] in (
                "governance_check", "constraint_change", "violation",
                "context_switch",
            )
        ]

    # ── Cross-Project Access (requires explicit operator action) ──

    async def request_cross_project_access(
        self,
        target_project_id: str,
        operator_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Request access to another project's memories.

        Cross-project memory access requires explicit operator action.
        This creates an audit record but does NOT grant access —
        the ContextManager must approve.

        Args:
            target_project_id: The project to access memories from.
            operator_id: The operator requesting access.
            reason: Reason for cross-project access.

        Returns:
            Result dict with request status.
        """
        if not operator_id:
            return {
                "status": "error",
                "reason": "operator_id required for cross-project access",
            }

        if not reason:
            return {
                "status": "error",
                "reason": "reason required for cross-project access",
            }

        # Create audit record
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "cross_project_access_requested",
            "operator_id": operator_id,
            "source_project": self.project_id,
            "target_project": target_project_id,
            "reason": reason,
            "status": "pending_approval",
        }

        # Store the request itself in memory
        await self.store(
            content=f"Cross-project access requested: {self.project_id} -> {target_project_id}",
            memory_type="cross_project_request",
            metadata=audit_entry,
        )

        logger.info(
            "Cross-project access requested: %s -> %s by operator=%s",
            self.project_id,
            target_project_id,
            operator_id,
        )

        return {
            "status": "pending_approval",
            "source_project": self.project_id,
            "target_project": target_project_id,
            "operator_id": operator_id,
            "reason": reason,
            "note": (
                "Cross-project access requires explicit ContextManager approval. "
                "Access is NOT granted automatically."
            ),
        }

    # ── Statistics ────────────────────────────────────────────────

    def get_statistics(self) -> dict[str, Any]:
        """Get memory statistics for this project.

        Returns:
            Dict with memory statistics.
        """
        type_counts: dict[str, int] = {}
        for entry in self._memories:
            mt = entry["memory_type"]
            type_counts[mt] = type_counts.get(mt, 0) + 1

        total_retrievals = sum(
            entry["retrieval_count"] for entry in self._memories
        )

        return {
            "project_id": self.project_id,
            "total_memories": len(self._memories),
            "by_type": type_counts,
            "total_retrievals": total_retrievals,
            "memory_types": list(type_counts.keys()),
        }

    def get_all_memories(self) -> list[dict[str, Any]]:
        """Get all memories (for testing/debugging).

        Returns:
            List of all memory records.
        """
        return [dict(entry) for entry in self._memories]

    def __len__(self) -> int:
        return len(self._memories)

    def __repr__(self) -> str:
        return (
            f"ProjectMemory("
            f"project_id='{self.project_id}', "
            f"entries={len(self._memories)})"
        )
