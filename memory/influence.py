"""
Memory Influence Mapper

Tracks how memories influence reasoning in GARVIS.
Every memory influence is trace-visible — no hidden influences allowed.

Provides:
- map_influence: Record a new influence relationship
- get_influences_on_inference: All influences for a given inference
- get_influences_from_memory: All influences from a given memory
- get_influence_graph: Full influence graph for a session
- verify_trace_visibility: Enforce the trace_visible invariant
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from database.connection import DatabaseConnection
from database.queries import Queries
from models.memory import EpisodicMemory, MemoryInfluence

logger = logging.getLogger(__name__)


class InfluenceMapper:
    """Maps and tracks memory influence on reasoning.

    In GARVIS, every memory influence on reasoning MUST be trace-visible.
    This is an invariant enforced by verify_trace_visibility().
    """

    # Influence types supported by the system
    VALID_INFLUENCE_TYPES: set[str] = {
        "retrieval",
        "context",
        "constraint",
        "warning",
    }

    def __init__(self, db: DatabaseConnection) -> None:
        self.db = db

    async def map_influence(
        self,
        memory_id: UUID,
        inference_id: UUID,
        influence_type: str,
        strength: float,
    ) -> MemoryInfluence:
        """Record how a memory influenced an inference.

        Args:
            memory_id: The influencing memory
            inference_id: The target inference
            influence_type: Type of influence (retrieval/context/constraint/warning)
            strength: Influence strength 0.0-1.0

        Returns:
            The recorded MemoryInfluence

        Raises:
            ValueError: If influence_type is invalid or strength out of range
        """
        if influence_type not in self.VALID_INFLUENCE_TYPES:
            raise ValueError(
                f"Invalid influence_type '{influence_type}'. "
                f"Must be one of: {self.VALID_INFLUENCE_TYPES}"
            )

        if not 0.0 <= strength <= 1.0:
            raise ValueError(f"strength must be between 0.0 and 1.0, got {strength}")

        influence = MemoryInfluence(
            influence_id=uuid4(),
            memory_id=memory_id,
            target_inference_id=inference_id,
            influence_type=influence_type,
            strength=strength,
            trace_visible=True,  # Invariant: always trace-visible
        )

        # Enforce trace visibility invariant before persistence
        if not self.verify_trace_visibility(influence):
            raise RuntimeError(
                "CRITICAL: Attempted to create non-trace-visible influence. "
                "This violates GARVIS governance invariants."
            )

        logger.info(
            "Mapping influence: memory=%s -> inference=%s, type=%s, strength=%.2f",
            memory_id,
            inference_id,
            influence_type,
            strength,
        )

        try:
            await self.db.execute(
                Queries.INFLUENCE_INSERT,
                str(influence.influence_id),
                str(influence.memory_id),
                str(influence.target_inference_id),
                influence.influence_type,
                influence.strength,
                influence.trace_visible,
                influence.timestamp,
            )
            logger.debug(
                "Influence recorded: influence_id=%s", influence.influence_id
            )
        except Exception as exc:
            logger.error("Failed to record influence: %s", exc)
            raise

        return influence

    async def get_influences_on_inference(
        self,
        inference_id: UUID,
    ) -> list[MemoryInfluence]:
        """Get all memory influences on a specific inference.

        Returns:
            List of MemoryInfluence, ordered by creation time (newest first).
        """
        logger.debug("Fetching influences on inference: %s", inference_id)

        try:
            rows = await self.db.fetch(
                Queries.INFLUENCE_GET_BY_INFERENCE, str(inference_id)
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch influences for inference %s: %s",
                inference_id,
                exc,
            )
            raise

        influences = [MemoryInfluence.from_db_row(dict(row)) for row in rows]

        logger.debug(
            "Found %d influences on inference %s", len(influences), inference_id
        )
        return influences

    async def get_influences_from_memory(
        self,
        memory_id: UUID,
    ) -> list[MemoryInfluence]:
        """Get all influences recorded from a specific memory.

        Returns:
            List of MemoryInfluence, ordered by creation time (newest first).
        """
        logger.debug("Fetching influences from memory: %s", memory_id)

        try:
            rows = await self.db.fetch(
                Queries.INFLUENCE_GET_BY_MEMORY, str(memory_id)
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch influences from memory %s: %s", memory_id, exc
            )
            raise

        influences = [MemoryInfluence.from_db_row(dict(row)) for row in rows]

        logger.debug(
            "Found %d influences from memory %s", len(influences), memory_id
        )
        return influences

    async def get_influence_graph(
        self,
        session_id: UUID,
    ) -> dict:
        """Build an influence graph for a session.

        Returns:
            Dict with:
                - nodes: dict of node_id -> {type, data}
                - edges: list of {from, to, type, strength}
                - session_id: the session UUID
        """
        logger.debug("Building influence graph for session: %s", session_id)

        try:
            rows = await self.db.fetch(
                Queries.INFLUENCE_GET_BY_SESSION, str(session_id)
            )
        except Exception as exc:
            logger.error(
                "Failed to build influence graph for session %s: %s",
                session_id,
                exc,
            )
            raise

        influences = [MemoryInfluence.from_db_row(dict(row)) for row in rows]

        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        for inf in influences:
            memory_node = f"memory:{inf.memory_id}"
            inference_node = f"inference:{inf.target_inference_id}"

            if memory_node not in nodes:
                nodes[memory_node] = {
                    "type": "memory",
                    "id": str(inf.memory_id),
                }
            if inference_node not in nodes:
                nodes[inference_node] = {
                    "type": "inference",
                    "id": str(inf.target_inference_id),
                }

            edges.append({
                "from": memory_node,
                "to": inference_node,
                "type": inf.influence_type,
                "strength": inf.strength,
                "trace_visible": inf.trace_visible,
            })

        graph = {
            "session_id": str(session_id),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

        logger.debug(
            "Influence graph built: %d nodes, %d edges",
            len(nodes),
            len(edges),
        )
        return graph

    def verify_trace_visibility(self, influence: MemoryInfluence) -> bool:
        """Verify that an influence is trace-visible.

        In GARVIS, ALL influences MUST be trace_visible=True.
        This is an absolute invariant. No exceptions.

        Returns:
            True if the influence is trace-visible.

        Raises:
            RuntimeError: If trace_visible is False (this is a critical violation).
        """
        if not influence.trace_visible:
            logger.critical(
                "GOVERNANCE VIOLATION: Non-trace-visible influence detected. "
                "memory=%s, inference=%s, type=%s, strength=%.2f",
                influence.memory_id,
                influence.target_inference_id,
                influence.influence_type,
                influence.strength,
            )
            raise RuntimeError(
                "Critical governance violation: Non-trace-visible influence "
                f"memory={influence.memory_id} -> inference={influence.target_inference_id}. "
                "All influences in GARVIS must be trace_visible=True."
            )
        return True
