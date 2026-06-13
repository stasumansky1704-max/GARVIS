"""
Episodic Memory Store

Stores cognitive episodes with full provenance.
All memories are governance-aware and traceable.

Per SPEC section 5.7:
- store(memory) -> stored EpisodicMemory | None
- retrieve(session_id, query, limit, governance_filter) -> list[EpisodicMemory] | None
- get_by_id(memory_id) -> EpisodicMemory | None
- get_session_memories(session_id) -> list[EpisodicMemory]
- record_influence(memory_id, inference_id, influence_type, strength) -> None
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from database.connection import DatabaseConnection
from database.queries import Queries
from governance.middleware import GovernanceMiddleware
from models.memory import EpisodicMemory, MemoryInfluence, ProvenanceRecord

logger = logging.getLogger(__name__)


class EpisodicMemoryStore:
    """Stores cognitive episodes with full provenance.

    All memories are governance-aware and traceable.
    Every storage and retrieval operation passes through governance middleware.
    """

    def __init__(
        self,
        db: DatabaseConnection,
        middleware: GovernanceMiddleware | None = None,
    ) -> None:
        self.db = db
        self.middleware = middleware

    async def store(self, memory: EpisodicMemory) -> EpisodicMemory | None:
        """Store an episodic memory.

        Flow:
        1. Generate memory_id if not present
        2. Pass through governance middleware
        3. Insert into PostgreSQL
        4. Return stored memory with ID and timestamps

        Returns stored memory with ID, or None if governance blocks.
        """
        # Step 1: Ensure memory has an ID and timestamp
        if not memory.memory_id:
            memory.memory_id = uuid4()

        if memory.timestamp is None:
            memory.timestamp = datetime.now(timezone.utc)

        logger.info(
            "Storing episodic memory: id=%s, session=%s, type=%s",
            memory.memory_id,
            memory.session_id,
            memory.episode_type,
        )

        # Step 2: Pass through governance middleware
        if self.middleware is not None and self.middleware.is_active:
            governed_memory = await self.middleware.process_memory_store(memory)
            if governed_memory is None:
                logger.critical(
                    "Governance blocked memory store: memory_id=%s", memory.memory_id
                )
                return None
            memory = governed_memory

        # Step 3: Insert into PostgreSQL
        try:
            await self.db.execute(
                Queries.MEMORY_INSERT,
                str(memory.memory_id),
                str(memory.session_id),
                memory.episode_type,
                memory.content,
                memory.provenance.model_dump_json(),
                memory.governance_influences,
                memory.confidence,
                memory.timestamp,
                memory.retrieval_count,
                memory.last_accessed,
            )
            logger.debug(
                "Episodic memory stored successfully: memory_id=%s", memory.memory_id
            )
        except Exception as exc:
            logger.error(
                "Failed to store episodic memory %s: %s", memory.memory_id, exc
            )
            raise

        return memory

    async def retrieve(
        self,
        session_id: UUID,
        query: str,
        limit: int = 10,
        governance_filter: list[str] | None = None,
    ) -> list[EpisodicMemory] | None:
        """Retrieve memories relevant to query.

        Flow:
        1. Search memories by content similarity (ILIKE text search)
        2. Pass through governance middleware
        3. Apply governance filtering if provided
        4. Update retrieval_count and last_accessed
        5. Return ordered by relevance

        Returns None if governance blocks the retrieval entirely.
        """
        logger.info(
            "Retrieving memories: session=%s, query=%r, limit=%d",
            session_id,
            query,
            limit,
        )

        # Step 1: Text search using ILIKE
        search_pattern = f"%{query}%"
        try:
            rows = await self.db.fetch(
                Queries.MEMORY_SEARCH_TEXT,
                str(session_id),
                search_pattern,
                limit,
            )
        except Exception as exc:
            logger.error(
                "Memory retrieval failed for session %s: %s", session_id, exc
            )
            raise

        memories: list[EpisodicMemory] = []
        for row in rows:
            row_dict = dict(row)
            memory = EpisodicMemory.from_db_row(row_dict)
            memories.append(memory)

        # Step 2: Pass through governance middleware
        if self.middleware is not None and self.middleware.is_active:
            governed_results = await self.middleware.process_memory_retrieval(
                query, session_id, memories
            )
            if governed_results is None:
                logger.critical(
                    "Governance blocked memory retrieval: session=%s", session_id
                )
                return None
            memories = governed_results

        # Step 3: Apply governance schema filtering if provided
        if governance_filter:
            memories = self._apply_governance_filter(memories, governance_filter)

        # Step 4: Update retrieval metadata for each returned memory
        for memory in memories:
            memory.mark_accessed()
            try:
                await self.db.execute(
                    Queries.MEMORY_UPDATE_ACCESS, str(memory.memory_id)
                )
            except Exception as exc:
                logger.warning(
                    "Failed to update access for memory %s: %s",
                    memory.memory_id,
                    exc,
                )

        logger.debug(
            "Retrieved %d memories for session %s", len(memories), session_id
        )
        return memories

    async def get_by_id(self, memory_id: UUID) -> EpisodicMemory | None:
        """Get a specific memory by ID.

        Updates last_accessed timestamp.
        """
        logger.debug("Fetching memory by ID: %s", memory_id)

        try:
            row = await self.db.fetchrow(
                Queries.MEMORY_GET_BY_ID, str(memory_id)
            )
        except Exception as exc:
            logger.error("Failed to fetch memory %s: %s", memory_id, exc)
            raise

        if row is None:
            logger.debug("Memory not found: %s", memory_id)
            return None

        memory = EpisodicMemory.from_db_row(dict(row))

        # Update access metadata
        memory.mark_accessed()
        try:
            await self.db.execute(
                Queries.MEMORY_UPDATE_ACCESS, str(memory.memory_id)
            )
        except Exception as exc:
            logger.warning(
                "Failed to update access for memory %s: %s", memory.memory_id, exc
            )

        return memory

    async def get_session_memories(self, session_id: UUID) -> list[EpisodicMemory]:
        """Get all memories for a session, ordered by creation time (newest first)."""
        logger.debug("Fetching all memories for session: %s", session_id)

        try:
            rows = await self.db.fetch(
                Queries.MEMORY_GET_BY_SESSION, str(session_id)
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch session memories for %s: %s", session_id, exc
            )
            raise

        memories = [EpisodicMemory.from_db_row(dict(row)) for row in rows]

        logger.debug(
            "Fetched %d memories for session %s", len(memories), session_id
        )
        return memories

    async def record_influence(
        self,
        memory_id: UUID,
        inference_id: UUID,
        influence_type: str,
        strength: float,
    ) -> None:
        """Record how a memory influenced an inference.

        All influences in GARVIS are trace_visible=True (enforced invariant).
        """
        if not 0.0 <= strength <= 1.0:
            raise ValueError(f"strength must be between 0.0 and 1.0, got {strength}")

        influence = MemoryInfluence(
            influence_id=uuid4(),
            memory_id=memory_id,
            target_inference_id=inference_id,
            influence_type=influence_type,
            strength=strength,
            trace_visible=True,  # Invariant: all influences are trace-visible
        )

        logger.info(
            "Recording memory influence: memory=%s -> inference=%s, type=%s, strength=%.2f",
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
                "Memory influence recorded: influence_id=%s", influence.influence_id
            )
        except Exception as exc:
            logger.error("Failed to record memory influence: %s", exc)
            raise

    def _apply_governance_filter(
        self,
        memories: list[EpisodicMemory],
        active_schemas: list[str],
    ) -> list[EpisodicMemory]:
        """Filter memories to only include those influenced by active schemas.

        A memory passes the filter if at least one of its governance_influences
        is in the active_schemas list. If a memory has no governance influences,
        it is excluded when filtering is active.
        """
        if not active_schemas:
            return memories

        filtered = []
        for memory in memories:
            # Memory passes if any of its governance influences intersect with active schemas
            if any(
                influence in active_schemas
                for influence in memory.governance_influences
            ):
                filtered.append(memory)

        logger.debug(
            "Governance filter: %d -> %d memories (schemas=%s)",
            len(memories),
            len(filtered),
            active_schemas,
        )
        return filtered
