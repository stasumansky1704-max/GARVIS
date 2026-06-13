"""
Memory Persistence Layer

Database persistence helpers for episodic memories.
Provides CRUD operations with soft-delete only (GARVIS preserves audit trail).
"""

from __future__ import annotations

import logging
from uuid import UUID

from database.connection import DatabaseConnection
from database.queries import Queries
from models.memory import EpisodicMemory

logger = logging.getLogger(__name__)


class MemoryPersistence:
    """Persistence layer for episodic memories.

    All writes are durable. Deletions are soft only —
    GARVIS preserves the complete audit trail and never
    permanently removes memory records.
    """

    def __init__(self, db: DatabaseConnection) -> None:
        self.db = db

    async def insert(self, memory: EpisodicMemory) -> EpisodicMemory:
        """Insert a new episodic memory into the database.

        Args:
            memory: The memory to persist. If memory_id is not set,
                    a new UUID will be generated.

        Returns:
            The persisted memory with generated fields populated.
        """
        from datetime import datetime, timezone
        from uuid import uuid4

        if not memory.memory_id:
            memory.memory_id = uuid4()
            logger.debug("Generated memory_id: %s", memory.memory_id)

        if memory.timestamp is None:
            memory.timestamp = datetime.now(timezone.utc)

        logger.info(
            "Persisting memory: id=%s, session=%s, type=%s",
            memory.memory_id,
            memory.session_id,
            memory.episode_type,
        )

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
            logger.debug("Memory persisted: %s", memory.memory_id)
        except Exception as exc:
            logger.error("Failed to persist memory %s: %s", memory.memory_id, exc)
            raise

        return memory

    async def update_access(self, memory_id: UUID) -> None:
        """Update retrieval_count and last_accessed for a memory.

        Args:
            memory_id: The memory to update.
        """
        logger.debug("Updating access metadata for memory: %s", memory_id)

        try:
            await self.db.execute(
                Queries.MEMORY_UPDATE_ACCESS, str(memory_id)
            )
        except Exception as exc:
            logger.error(
                "Failed to update access for memory %s: %s", memory_id, exc
            )
            raise

    async def delete(self, memory_id: UUID) -> None:
        """Soft-delete a memory.

        GARVIS never permanently deletes memories. Instead, the
        episode_type is prefixed with 'deleted_' and the content
        is replaced with '[deleted]'. The audit trail is preserved.

        Args:
            memory_id: The memory to soft-delete.
        """
        logger.info("Soft-deleting memory: %s", memory_id)

        try:
            await self.db.execute(
                Queries.MEMORY_SOFT_DELETE, str(memory_id)
            )
            logger.debug("Memory soft-deleted: %s", memory_id)
        except Exception as exc:
            logger.error("Failed to soft-delete memory %s: %s", memory_id, exc)
            raise

    async def query_by_session(
        self,
        session_id: UUID,
    ) -> list[EpisodicMemory]:
        """Query all memories for a session.

        Args:
            session_id: Session UUID to query.

        Returns:
            List of EpisodicMemory, ordered by creation time (newest first).
        """
        logger.debug("Querying memories by session: %s", session_id)

        try:
            rows = await self.db.fetch(
                Queries.MEMORY_GET_BY_SESSION, str(session_id)
            )
        except Exception as exc:
            logger.error(
                "Failed to query session memories for %s: %s",
                session_id,
                exc,
            )
            raise

        memories = [EpisodicMemory.from_db_row(dict(row)) for row in rows]

        logger.debug(
            "Found %d memories for session %s", len(memories), session_id
        )
        return memories

    async def query_by_type(
        self,
        session_id: UUID,
        episode_type: str,
    ) -> list[EpisodicMemory]:
        """Query memories filtered by episode type.

        Args:
            session_id: Session UUID to query.
            episode_type: Episode type to filter by (e.g., 'inference').

        Returns:
            List of matching EpisodicMemory, ordered by creation time.
        """
        logger.debug(
            "Querying memories by type: session=%s, type=%s",
            session_id,
            episode_type,
        )

        try:
            rows = await self.db.fetch(
                Queries.MEMORY_GET_BY_TYPE,
                str(session_id),
                episode_type,
            )
        except Exception as exc:
            logger.error(
                "Failed to query memories by type for session %s: %s",
                session_id,
                exc,
            )
            raise

        memories = [EpisodicMemory.from_db_row(dict(row)) for row in rows]

        logger.debug(
            "Found %d memories of type %s for session %s",
            len(memories),
            episode_type,
            session_id,
        )
        return memories

    async def text_search(
        self,
        session_id: UUID,
        query_text: str,
    ) -> list[EpisodicMemory]:
        """Search memories using ILIKE text matching.

        Args:
            session_id: Session UUID to scope the search.
            query_text: Text pattern to search for in memory content.

        Returns:
            List of matching EpisodicMemory, ordered by creation time.
        """
        search_pattern = f"%{query_text}%"

        logger.debug(
            "Text searching memories: session=%s, query=%r",
            session_id,
            query_text,
        )

        try:
            rows = await self.db.fetch(
                Queries.MEMORY_SEARCH_TEXT,
                str(session_id),
                search_pattern,
                100,  # Default limit for persistence layer
            )
        except Exception as exc:
            logger.error(
                "Text search failed for session %s: %s", session_id, exc
            )
            raise

        memories = [EpisodicMemory.from_db_row(dict(row)) for row in rows]

        logger.debug(
            "Text search found %d memories for session %s",
            len(memories),
            session_id,
        )
        return memories
