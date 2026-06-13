"""Tests for the memory layer.

Tests cover memory storage, retrieval, governance filtering, influence tracking,
provenance search, temporal search, relevance scoring, and trace visibility.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from memory.episodic import EpisodicMemoryStore
from memory.influence import InfluenceMapper
from memory.retrieval import RetrievalEngine
from memory.store import MemoryPersistence
from models.memory import EpisodicMemory, MemoryInfluence, ProvenanceRecord


# ============================================================================
# EpisodicMemoryStore
# ============================================================================

class TestEpisodicMemoryStore:
    """Tests for EpisodicMemoryStore."""

    @pytest.fixture
    def store(self, mock_db: MagicMock) -> EpisodicMemoryStore:
        """Return an EpisodicMemoryStore with a mock DB."""
        return EpisodicMemoryStore(mock_db)

    @pytest.fixture
    def sample_memory(self) -> EpisodicMemory:
        """Return a sample EpisodicMemory."""
        return EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="Paris is the capital of France.",
            provenance=ProvenanceRecord(
                source_schema="inference",
                creator_component="GovernedInferenceExecutor",
            ),
            confidence=0.95,
        )

    @pytest.mark.asyncio
    async def test_store_memory(self, store: EpisodicMemoryStore, sample_memory: EpisodicMemory) -> None:
        """store() stores a memory with generated ID."""
        result = await store.store(sample_memory)

        assert result is not None
        assert isinstance(result.memory_id, UUID)
        store.db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_memory_generates_id(self, store: EpisodicMemoryStore) -> None:
        """store() auto-generates memory_id if not present."""
        memory = EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="Test content",
            provenance=ProvenanceRecord(
                source_schema="test",
                creator_component="Test",
            ),
            confidence=0.8,
        )
        assert memory.memory_id is not None  # Pydantic auto-generates

        result = await store.store(memory)
        assert result is not None
        assert isinstance(result.memory_id, UUID)

    @pytest.mark.asyncio
    async def test_retrieve_memories(self, store: EpisodicMemoryStore, mock_db: MagicMock) -> None:
        """retrieve() performs text search and returns results."""
        session_id = uuid4()

        # Mock DB returns rows
        mock_db.fetch.return_value = [
            {
                "memory_id": str(uuid4()),
                "session_id": str(session_id),
                "episode_type": "inference",
                "content": "Paris is the capital of France.",
                "provenance": '{}',
                "governance_influences": ["uncertainty_management"],
                "confidence": 0.95,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "retrieval_count": 0,
                "last_accessed": None,
            }
        ]

        result = await store.retrieve(session_id, "Paris", limit=5)

        assert isinstance(result, list)
        mock_db.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id(self, store: EpisodicMemoryStore, mock_db: MagicMock) -> None:
        """get_by_id() retrieves a specific memory by ID."""
        memory_id = uuid4()
        mock_db.fetchrow.return_value = {
            "memory_id": str(memory_id),
            "session_id": str(uuid4()),
            "episode_type": "inference",
            "content": "Test memory content",
            "provenance": '{}',
            "governance_influences": [],
            "confidence": 0.8,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "retrieval_count": 1,
            "last_accessed": datetime.now(timezone.utc).isoformat(),
        }

        result = await store.get_by_id(memory_id)

        assert result is not None
        mock_db.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, store: EpisodicMemoryStore, mock_db: MagicMock) -> None:
        """get_by_id() returns None when memory not found."""
        mock_db.fetchrow.return_value = None

        result = await store.get_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_memories(self, store: EpisodicMemoryStore, mock_db: MagicMock) -> None:
        """get_session_memories() returns all memories for a session."""
        session_id = uuid4()
        mock_db.fetch.return_value = [
            {
                "memory_id": str(uuid4()),
                "session_id": str(session_id),
                "episode_type": "inference",
                "content": "Memory 1",
                "provenance": '{}',
                "governance_influences": [],
                "confidence": 0.8,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "retrieval_count": 0,
                "last_accessed": None,
            },
            {
                "memory_id": str(uuid4()),
                "session_id": str(session_id),
                "episode_type": "reflection",
                "content": "Memory 2",
                "provenance": '{}',
                "governance_influences": [],
                "confidence": 0.6,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "retrieval_count": 1,
                "last_accessed": datetime.now(timezone.utc).isoformat(),
            },
        ]

        result = await store.get_session_memories(session_id)

        assert isinstance(result, list)
        assert len(result) == 2
        mock_db.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_influence(self, store: EpisodicMemoryStore, mock_db: MagicMock) -> None:
        """record_influence() records a memory influence."""
        await store.record_influence(
            memory_id=uuid4(),
            inference_id=uuid4(),
            influence_type="retrieval",
            strength=0.8,
        )

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_influence_invalid_strength(self, store: EpisodicMemoryStore) -> None:
        """record_influence() rejects invalid strength values."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            await store.record_influence(
                memory_id=uuid4(),
                inference_id=uuid4(),
                influence_type="retrieval",
                strength=1.5,
            )


# ============================================================================
# RetrievalEngine
# ============================================================================

class TestRetrievalEngine:
    """Tests for RetrievalEngine."""

    @pytest.fixture
    def retrieval(self, mock_db: MagicMock) -> RetrievalEngine:
        """Return a RetrievalEngine with a mock DB."""
        return RetrievalEngine(mock_db)

    @pytest.mark.asyncio
    async def test_search(self, retrieval: RetrievalEngine, mock_db: MagicMock) -> None:
        """search() performs text search with relevance scoring."""
        session_id = uuid4()
        mock_db.fetch.return_value = []

        result = await retrieval.search("test query", session_id)

        assert isinstance(result, list)
        mock_db.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_by_provenance(self, retrieval: RetrievalEngine, mock_db: MagicMock) -> None:
        """search_by_provenance() filters by source schema."""
        session_id = uuid4()
        mock_db.fetch.return_value = []

        result = await retrieval.search_by_provenance(session_id, "uncertainty_management")

        assert isinstance(result, list)
        mock_db.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_by_temporal(self, retrieval: RetrievalEngine, mock_db: MagicMock) -> None:
        """search_by_temporal() searches within a time range."""
        session_id = uuid4()
        mock_db.fetch.return_value = []

        start = datetime.now(timezone.utc) - timedelta(hours=1)
        end = datetime.now(timezone.utc)
        result = await retrieval.search_by_temporal(session_id, start, end)

        assert isinstance(result, list)
        mock_db.fetch.assert_called_once()

    def test_relevance_scoring(self, retrieval: RetrievalEngine) -> None:
        """score_relevance() returns a score between 0 and 1."""
        memory = EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="Paris is the capital of France and a beautiful city.",
            provenance=ProvenanceRecord(source_schema="test", creator_component="test"),
            confidence=0.9,
            retrieval_count=5,
        )

        score = retrieval.score_relevance(memory, "Paris France capital")

        assert 0.0 <= score <= 1.0, f"Score {score} out of range [0, 1]"

    def test_relevance_scoring_exact_phrase_boost(self, retrieval: RetrievalEngine) -> None:
        """score_relevance() boosts score for exact phrase match."""
        memory = EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="The exact phrase appears here.",
            provenance=ProvenanceRecord(source_schema="test", creator_component="test"),
            confidence=0.5,
        )

        score = retrieval.score_relevance(memory, "exact phrase")
        assert score > 0.3, f"Expected phrase boost, got {score}"

    def test_relevance_scoring_empty_query(self, retrieval: RetrievalEngine) -> None:
        """score_relevance() handles empty query gracefully."""
        memory = EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="Some content here.",
            provenance=ProvenanceRecord(source_schema="test", creator_component="test"),
            confidence=0.5,
        )

        score = retrieval.score_relevance(memory, "")
        assert 0.0 <= score <= 1.0


# ============================================================================
# InfluenceMapper
# ============================================================================

class TestInfluenceMapper:
    """Tests for InfluenceMapper."""

    @pytest.fixture
    def mapper(self, mock_db: MagicMock) -> InfluenceMapper:
        """Return an InfluenceMapper with a mock DB."""
        return InfluenceMapper(mock_db)

    @pytest.mark.asyncio
    async def test_map_influence(self, mapper: InfluenceMapper, mock_db: MagicMock) -> None:
        """map_influence() records a new influence relationship."""
        result = await mapper.map_influence(
            memory_id=uuid4(),
            inference_id=uuid4(),
            influence_type="retrieval",
            strength=0.8,
        )

        assert isinstance(result, MemoryInfluence)
        assert result.trace_visible is True
        assert result.strength == 0.8
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_map_influence_invalid_type(self, mapper: InfluenceMapper) -> None:
        """map_influence() rejects invalid influence type."""
        with pytest.raises(ValueError, match="Invalid influence_type"):
            await mapper.map_influence(
                memory_id=uuid4(),
                inference_id=uuid4(),
                influence_type="invalid_type",
                strength=0.5,
            )

    @pytest.mark.asyncio
    async def test_map_influence_invalid_strength(self, mapper: InfluenceMapper) -> None:
        """map_influence() rejects strength out of bounds."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            await mapper.map_influence(
                memory_id=uuid4(),
                inference_id=uuid4(),
                influence_type="retrieval",
                strength=-0.1,
            )

    @pytest.mark.asyncio
    async def test_get_influences_on_inference(self, mapper: InfluenceMapper, mock_db: MagicMock) -> None:
        """get_influences_on_inference() returns influences for an inference."""
        inference_id = uuid4()
        mock_db.fetch.return_value = []

        result = await mapper.get_influences_on_inference(inference_id)

        assert isinstance(result, list)
        mock_db.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_influences_from_memory(self, mapper: InfluenceMapper, mock_db: MagicMock) -> None:
        """get_influences_from_memory() returns influences from a memory."""
        memory_id = uuid4()
        mock_db.fetch.return_value = []

        result = await mapper.get_influences_from_memory(memory_id)

        assert isinstance(result, list)
        mock_db.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_influence_graph(self, mapper: InfluenceMapper, mock_db: MagicMock) -> None:
        """get_influence_graph() builds a graph of influences."""
        session_id = uuid4()
        mock_db.fetch.return_value = []

        result = await mapper.get_influence_graph(session_id)

        assert "nodes" in result
        assert "edges" in result
        assert result["session_id"] == str(session_id)

    def test_verify_trace_visibility_pass(self, mapper: InfluenceMapper) -> None:
        """verify_trace_visibility() returns True for trace-visible influence."""
        influence = MemoryInfluence(
            memory_id=uuid4(),
            target_inference_id=uuid4(),
            influence_type="retrieval",
            strength=0.5,
            trace_visible=True,
        )
        assert mapper.verify_trace_visibility(influence) is True

    def test_verify_trace_visibility_fail(self, mapper: InfluenceMapper) -> None:
        """verify_trace_visibility() raises RuntimeError for non-trace-visible influence."""
        influence = MemoryInfluence(
            memory_id=uuid4(),
            target_inference_id=uuid4(),
            influence_type="retrieval",
            strength=0.5,
            trace_visible=False,
        )
        with pytest.raises(RuntimeError, match="Non-trace-visible"):
            mapper.verify_trace_visibility(influence)


# ============================================================================
# MemoryPersistence
# ============================================================================

class TestMemoryPersistence:
    """Tests for MemoryPersistence layer."""

    @pytest.fixture
    def persistence(self, mock_db: MagicMock) -> MemoryPersistence:
        """Return a MemoryPersistence instance with a mock DB."""
        return MemoryPersistence(mock_db)

    @pytest.mark.asyncio
    async def test_insert(self, persistence: MemoryPersistence, mock_db: MagicMock) -> None:
        """insert() persists a memory to the database."""
        memory = EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="Test content",
            provenance=ProvenanceRecord(source_schema="test", creator_component="test"),
            confidence=0.8,
        )

        result = await persistence.insert(memory)

        assert result is not None
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_soft(self, persistence: MemoryPersistence, mock_db: MagicMock) -> None:
        """delete() performs a soft delete."""
        memory_id = uuid4()

        await persistence.delete(memory_id)

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_search(self, persistence: MemoryPersistence, mock_db: MagicMock) -> None:
        """text_search() searches by content pattern."""
        session_id = uuid4()
        mock_db.fetch.return_value = []

        result = await persistence.text_search(session_id, "test")

        assert isinstance(result, list)
        mock_db.fetch.assert_called_once()


# ============================================================================
# Governance Filtering
# ============================================================================

class TestGovernanceFiltering:
    """Tests for governance schema filtering in memory operations."""

    def test_apply_governance_filter_basic(self, mock_db: MagicMock) -> None:
        """Governance filtering includes memories influenced by active schemas."""
        retrieval = RetrievalEngine(mock_db)

        mem1 = EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="Memory with schema A",
            provenance=ProvenanceRecord(source_schema="test", creator_component="test"),
            confidence=0.8,
            governance_influences=["schema_a", "schema_b"],
        )
        mem2 = EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="Memory with schema C",
            provenance=ProvenanceRecord(source_schema="test", creator_component="test"),
            confidence=0.8,
            governance_influences=["schema_c"],
        )

        result = retrieval.apply_governance_filter([mem1, mem2], ["schema_a"])

        assert len(result) == 1
        assert result[0].memory_id == mem1.memory_id

    def test_apply_governance_filter_empty_schemas(self, mock_db: MagicMock) -> None:
        """Governance filtering with empty schema list returns all memories."""
        retrieval = RetrievalEngine(mock_db)

        mem1 = EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="Test",
            provenance=ProvenanceRecord(source_schema="test", creator_component="test"),
            confidence=0.8,
            governance_influences=["schema_a"],
        )

        result = retrieval.apply_governance_filter([mem1], [])
        assert len(result) == 1

    def test_apply_governance_filter_no_match(self, mock_db: MagicMock) -> None:
        """Governance filtering with no matching schemas returns empty list."""
        retrieval = RetrievalEngine(mock_db)

        mem1 = EpisodicMemory(
            session_id=uuid4(),
            episode_type="inference",
            content="Test",
            provenance=ProvenanceRecord(source_schema="test", creator_component="test"),
            confidence=0.8,
            governance_influences=["schema_a"],
        )

        result = retrieval.apply_governance_filter([mem1], ["schema_z"])
        assert len(result) == 0


# ============================================================================
# Trace Visibility Enforcement
# ============================================================================

class TestTraceVisibility:
    """Tests for the trace visibility invariant."""

    def test_trace_visible_always_true(self) -> None:
        """MemoryInfluence trace_visible defaults to True."""
        influence = MemoryInfluence(
            memory_id=uuid4(),
            target_inference_id=uuid4(),
            influence_type="retrieval",
            strength=0.5,
        )
        assert influence.trace_visible is True

    def test_trace_visible_cannot_be_false_at_creation(self) -> None:
        """MemoryInfluence can be created with trace_visible=False but verify catches it."""
        influence = MemoryInfluence(
            memory_id=uuid4(),
            target_inference_id=uuid4(),
            influence_type="retrieval",
            strength=0.5,
            trace_visible=False,
        )
        # Creation succeeds but verify_trace_visibility catches it
        from memory.influence import InfluenceMapper
        mapper = InfluenceMapper(MagicMock())
        with pytest.raises(RuntimeError):
            mapper.verify_trace_visibility(influence)
