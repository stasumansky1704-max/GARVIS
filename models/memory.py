"""
Memory Pydantic models for GARVIS.

Defines episodic memory storage, provenance tracking, and memory influence
recording. Every memory in GARVIS carries full provenance and governance
context.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProvenanceRecord(BaseModel):
    """Full provenance tracking for traceability.

    Every artifact in GARVIS -- memories, inferences, decisions -- carries a
    provenance record that establishes its origin, governance context, and
    lineage. This enables complete post-hoc traceability.
    """

    source_schema: str = Field(
        default="unknown",
        description=(
            "Identifier of the governance schema that governed the creation "
            "of this artifact"
        ),
    )
    source_policy: str | None = Field(
        default=None,
        description=(
            "Identifier of the specific policy within the source schema. "
            "None if not governed by a specific policy."
        ),
    )
    inference_id: UUID | None = Field(
        default=None,
        description=(
            "Identifier of the inference request that produced this artifact. "
            "None if not produced by inference."
        ),
    )
    creator_component: str = Field(
        default="unknown",
        description=(
            "Name of the runtime component that created this artifact, "
            "e.g. 'EpisodicMemoryStore', 'GovernedInferenceExecutor'"
        ),
    )
    creation_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the artifact was created",
    )
    parent_memory_id: UUID | None = Field(
        default=None,
        description=(
            "Identifier of the parent memory if this artifact was derived "
            "from another memory. None for original memories."
        ),
    )


class EpisodicMemory(BaseModel):
    """A stored cognitive episode with full provenance.

    Episodic memories are the primary unit of memory in GARVIS. Each memory
    records a cognitive episode -- an inference, reflection, retrieval, or audit
    event -- with complete provenance and governance context.
    """

    memory_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this memory",
    )
    session_id: UUID = Field(
        description="Identifier of the session this memory belongs to",
    )
    episode_type: str = Field(
        description=(
            "Type of cognitive episode: inference, reflection, retrieval, or audit"
        ),
    )
    content: str = Field(
        description="The textual content of the memory episode",
    )
    provenance: ProvenanceRecord = Field(
        description="Full provenance record for this memory",
    )
    governance_influences: list[str] = Field(
        default_factory=list,
        description=(
            "List of governance schema identifiers that influenced the "
            "creation of this memory"
        ),
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Confidence score in the range [0.0, 1.0], governed by the "
            "uncertainty_management schema"
        ),
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the memory was created",
    )
    retrieval_count: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of times this memory has been retrieved. Incremented "
            "on each retrieval."
        ),
    )
    last_accessed: datetime | None = Field(
        default=None,
        description=(
            "UTC timestamp of the most recent retrieval. None if the memory "
            "has never been accessed."
        ),
    )

    def mark_accessed(self) -> None:
        """Increment retrieval count and update last access timestamp.

        Called whenever this memory is retrieved from the store.
        """
        self.retrieval_count += 1
        self.last_accessed = datetime.now(timezone.utc)

    # --- DB deserialization ---

    @classmethod
    def from_db_row(cls, row: dict) -> "EpisodicMemory":
        """Create an EpisodicMemory instance from a database row dict.

        Handles JSONB fields that may come back as dicts or strings.
        """
        import json
        from uuid import UUID

        provenance_raw = row.get("provenance", "{}")
        if isinstance(provenance_raw, str):
            provenance_raw = json.loads(provenance_raw)

        influences_raw = row.get("governance_influences", [])
        if isinstance(influences_raw, str):
            influences_raw = json.loads(influences_raw)

        return cls(
            memory_id=UUID(row["memory_id"]) if isinstance(row["memory_id"], str) else row["memory_id"],
            session_id=UUID(row["session_id"]) if isinstance(row["session_id"], str) else row["session_id"],
            episode_type=row["episode_type"],
            content=row["content"],
            provenance=ProvenanceRecord(**provenance_raw),
            governance_influences=list(influences_raw) if influences_raw else [],
            confidence=row["confidence"],
            timestamp=row.get("created_at", datetime.now(timezone.utc)),
            retrieval_count=row.get("retrieval_count", 0),
            last_accessed=row.get("last_accessed"),
        )


class MemoryInfluence(BaseModel):
    """Tracks how a memory influenced reasoning.

    Memory influences are recorded whenever a retrieved memory affects an
    inference. This provides the traceability link between memory and
    reasoning -- every memory that contributed to a response is visible.
    """

    influence_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this influence record",
    )
    memory_id: UUID = Field(
        description="Identifier of the memory that influenced reasoning",
    )
    target_inference_id: UUID = Field(
        description="Identifier of the inference request that was influenced",
    )
    influence_type: str = Field(
        description=(
            "Type of influence: retrieval, context, constraint, or warning"
        ),
    )
    strength: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Strength of the influence in the range [0.0, 1.0]. Higher "
            "values indicate stronger influence on the reasoning."
        ),
    )
    trace_visible: bool = Field(
        default=True,
        description=(
            "Whether this influence is visible in the cognition trace. "
            "Always True in GARVIS -- no hidden memory influence."
        ),
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the influence was recorded",
    )


__all__ = [
    "ProvenanceRecord",
    "EpisodicMemory",
    "MemoryInfluence",
]
