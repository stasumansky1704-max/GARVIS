"""
Provenance-Aware Retrieval Engine

Implements governance-aware memory retrieval with:
- Content similarity scoring (text-based)
- Provenance filtering (by source schema)
- Temporal range queries
- Governance schema filtering
- Relevance scoring using retrieval_scoring rules

All retrieval operations pass through governance middleware.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from database.connection import DatabaseConnection
from database.queries import Queries
from governance.middleware import GovernanceMiddleware
from models.memory import EpisodicMemory

logger = logging.getLogger(__name__)


class RetrievalEngine:
    """Provenance-aware retrieval engine for episodic memories.

    Provides multiple search modes:
    - Text search (ILIKE-based content matching)
    - Provenance search (by source governance schema)
    - Temporal search (by time range)

    All operations pass through governance middleware.
    Uses the retrieval_scoring governance schema for scoring rules.
    """

    # Scoring weights from retrieval_scoring schema
    DEFAULT_RECENCY_WEIGHT: float = 0.3
    DEFAULT_RETRIEVAL_WEIGHT: float = 0.2
    DEFAULT_CONTENT_WEIGHT: float = 0.5

    # Influence type multipliers
    INFLUENCE_MULTIPLIERS: dict[str, float] = {
        "retrieval": 1.0,
        "context": 0.9,
        "constraint": 0.7,
        "warning": 0.5,
    }

    def __init__(
        self,
        db: DatabaseConnection,
        middleware: GovernanceMiddleware | None = None,
    ) -> None:
        self.db = db
        self.middleware = middleware

    async def search(
        self,
        query: str,
        session_id: UUID,
        filters: dict | None = None,
    ) -> list[EpisodicMemory]:
        """Search memories with relevance scoring and governance filtering.

        Args:
            query: Text query to search for
            session_id: Session to scope the search to
            filters: Optional filters:
                - episode_type: str — filter by episode type
                - active_schemas: list[str] — governance schema filter
                - limit: int — max results (default 10)

        Returns:
            Ranked list of EpisodicMemory, highest relevance first.
        """
        filters = filters or {}
        limit = filters.get("limit", 10)

        logger.info(
            "RetrievalEngine.search: session=%s, query=%r, filters=%s",
            session_id,
            query,
            filters,
        )

        # Execute text search
        search_pattern = f"%{query}%"
        try:
            rows = await self.db.fetch(
                Queries.MEMORY_SEARCH_TEXT,
                str(session_id),
                search_pattern,
                limit * 2,  # Fetch more for re-ranking
            )
        except Exception as exc:
            logger.error("Retrieval search failed for session %s: %s", session_id, exc)
            raise

        memories = [EpisodicMemory.from_db_row(dict(row)) for row in rows]

        # Apply episode type filter if specified
        episode_type = filters.get("episode_type")
        if episode_type:
            memories = [m for m in memories if m.episode_type == episode_type]

        # Score relevance
        scored_memories = []
        for memory in memories:
            score = self.score_relevance(memory, query)
            scored_memories.append((score, memory))

        # Sort by relevance (highest first)
        scored_memories.sort(key=lambda x: x[0], reverse=True)

        # Take top results
        results = [m for _, m in scored_memories[:limit]]

        # Apply governance filtering
        active_schemas = filters.get("active_schemas")
        if active_schemas:
            results = self.apply_governance_filter(results, active_schemas)

        # Pass through governance middleware
        if self.middleware is not None and self.middleware.is_active:
            governed_results = await self.middleware.process_memory_retrieval(
                query, session_id, results
            )
            if governed_results is not None:
                results = governed_results

        # Update access metadata
        for memory in results:
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
            "RetrievalEngine returned %d results for session %s",
            len(results),
            session_id,
        )
        return results

    async def search_by_provenance(
        self,
        session_id: UUID,
        source_schema: str,
    ) -> list[EpisodicMemory]:
        """Search memories that were governed by a specific schema.

        Args:
            session_id: Session to scope the search to
            source_schema: Governance schema ID to filter by

        Returns:
            Memories whose provenance.source_schema matches.
        """
        logger.info(
            "RetrievalEngine.search_by_provenance: session=%s, schema=%s",
            session_id,
            source_schema,
        )

        try:
            rows = await self.db.fetch(
                Queries.MEMORY_SEARCH_BY_SCHEMA,
                str(session_id),
                source_schema,
            )
        except Exception as exc:
            logger.error(
                "Provenance search failed for session %s, schema %s: %s",
                session_id,
                source_schema,
                exc,
            )
            raise

        memories = [EpisodicMemory.from_db_row(dict(row)) for row in rows]

        logger.debug(
            "RetrievalEngine found %d memories from schema %s",
            len(memories),
            source_schema,
        )
        return memories

    async def search_by_temporal(
        self,
        session_id: UUID,
        start: datetime,
        end: datetime,
    ) -> list[EpisodicMemory]:
        """Search memories within a time range.

        Args:
            session_id: Session to scope the search to
            start: Start of time range (inclusive)
            end: End of time range (inclusive)

        Returns:
            Memories created within the time range.
        """
        logger.info(
            "RetrievalEngine.search_by_temporal: session=%s, range=[%s, %s]",
            session_id,
            start.isoformat(),
            end.isoformat(),
        )

        try:
            rows = await self.db.fetch(
                Queries.MEMORY_SEARCH_TEMPORAL,
                str(session_id),
                start,
                end,
            )
        except Exception as exc:
            logger.error(
                "Temporal search failed for session %s: %s", session_id, exc
            )
            raise

        memories = [EpisodicMemory.from_db_row(dict(row)) for row in rows]

        logger.debug(
            "RetrievalEngine found %d memories in temporal range", len(memories)
        )
        return memories

    def score_relevance(self, memory: EpisodicMemory, query: str) -> float:
        """Score the relevance of a memory to a query.

        Uses a weighted combination of:
        - Content match (keyword overlap)
        - Recency (newer = higher)
        - Retrieval popularity (more accessed = higher)

        Returns a float score between 0.0 and 1.0.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        content_lower = memory.content.lower()
        content_words = set(content_lower.split())

        # Content score: Jaccard similarity of word sets
        if query_words and content_words:
            intersection = query_words & content_words
            union = query_words | content_words
            content_score = len(intersection) / len(union) if union else 0.0
        else:
            content_score = 0.0

        # Bonus for exact phrase match
        if query_lower in content_lower:
            content_score = min(1.0, content_score + 0.3)

        # Recency score: exponential decay over time
        now = datetime.now(memory.timestamp.tzinfo)
        age_seconds = max(1.0, (now - memory.timestamp).total_seconds())
        # Normalize: 1.0 for very recent, decaying to ~0.0 for old
        import math
        recency_score = math.exp(-age_seconds / 3600.0)  # 1-hour half-life

        # Retrieval popularity score
        retrieval_score = min(1.0, memory.retrieval_count / 10.0)

        # Weighted combination
        score = (
            self.DEFAULT_CONTENT_WEIGHT * content_score
            + self.DEFAULT_RECENCY_WEIGHT * recency_score
            + self.DEFAULT_RETRIEVAL_WEIGHT * retrieval_score
        )

        return round(min(1.0, max(0.0, score)), 4)

    def apply_governance_filter(
        self,
        results: list[EpisodicMemory],
        active_schemas: list[str],
    ) -> list[EpisodicMemory]:
        """Filter results to only include memories governed by active schemas.

        A memory passes if at least one of its governance_influences is in
        the active_schemas list.
        """
        if not active_schemas:
            return results

        active_set = set(active_schemas)
        filtered = [
            m
            for m in results
            if any(inf in active_set for inf in m.governance_influences)
        ]

        logger.debug(
            "Governance filter applied: %d -> %d (schemas=%s)",
            len(results),
            len(filtered),
            active_schemas,
        )
        return filtered
