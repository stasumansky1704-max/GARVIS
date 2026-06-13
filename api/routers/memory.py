"""Memory router for the GARVIS Operator API.

Exposes episodic memories, memory influences, and search capabilities.
All endpoints are read-only.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import (
    get_mock_memories,
    get_mock_influences,
)
from api.models import (
    MemoryListResponse,
    MemorySearchResponse,
    InfluenceListResponse,
)
from models.memory import EpisodicMemory, MemoryInfluence

router = APIRouter()


# ── Memories ──────────────────────────────────────────────────────────────


@router.get("/memories", response_model=MemoryListResponse)
async def list_memories(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    episode_type: str | None = Query(None),
    session_id: UUID | None = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
) -> MemoryListResponse:
    """List episodic memories (paginated, filterable)."""
    memories = get_mock_memories()

    if episode_type:
        memories = [m for m in memories if m.episode_type == episode_type]
    if session_id:
        memories = [m for m in memories if m.session_id == session_id]
    if min_confidence > 0:
        memories = [m for m in memories if m.confidence >= min_confidence]

    total = len(memories)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = memories[start:end]

    return MemoryListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


@router.get("/memories/{memory_id}")
async def get_memory(
    memory_id: UUID,
) -> dict[str, Any]:
    """Get a specific memory by ID with full details."""
    memories = get_mock_memories()
    for m in memories:
        if m.memory_id == memory_id:
            return m.model_dump()
    raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found")


@router.get("/memories/session/{session_id}", response_model=MemoryListResponse)
async def get_session_memories(
    session_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> MemoryListResponse:
    """Get all memories for a specific session."""
    memories = get_mock_memories()
    filtered = [m for m in memories if m.session_id == session_id]

    total = len(filtered)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = filtered[start:end]

    return MemoryListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


@router.get("/memories/search/query", response_model=MemorySearchResponse)
async def search_memories(
    q: str = Query("", description="Search query text"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    episode_type: str | None = Query(None),
) -> MemorySearchResponse:
    """Search memories by content query string."""
    memories = get_mock_memories()

    if q:
        q_lower = q.lower()
        memories = [
            m for m in memories
            if q_lower in m.content.lower()
            or q_lower in m.episode_type.lower()
            or any(q_lower in inf.lower() for inf in m.governance_influences)
        ]

    if episode_type:
        memories = [m for m in memories if m.episode_type == episode_type]

    total = len(memories)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = memories[start:end]

    return MemorySearchResponse(total=total, page=page, per_page=per_page, pages=pages, items=items, query=q)


@router.get("/memories/{memory_id}/influences", response_model=InfluenceListResponse)
async def get_memory_influences(
    memory_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> InfluenceListResponse:
    """Get all influences originating from a specific memory."""
    influences = get_mock_influences()
    filtered = [inf for inf in influences if inf.memory_id == memory_id]

    total = len(filtered)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = filtered[start:end]

    return InfluenceListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


# ── Influences ────────────────────────────────────────────────────────────


@router.get("/influences", response_model=InfluenceListResponse)
async def list_influences(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    influence_type: str | None = Query(None),
) -> InfluenceListResponse:
    """List all memory influences (paginated, filterable by type)."""
    influences = get_mock_influences()

    if influence_type:
        influences = [inf for inf in influences if inf.influence_type == influence_type]

    total = len(influences)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = influences[start:end]

    return InfluenceListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)


@router.get("/influences/session/{session_id}", response_model=InfluenceListResponse)
async def get_session_influences(
    session_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> InfluenceListResponse:
    """Get memory influences for a specific session.

    This looks up memories for the session, then finds all influences
    from those memories.
    """
    memories = get_mock_memories()
    session_memory_ids = {m.memory_id for m in memories if m.session_id == session_id}

    influences = get_mock_influences()
    filtered = [inf for inf in influences if inf.memory_id in session_memory_ids]

    total = len(filtered)
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    items = filtered[start:end]

    return InfluenceListResponse(total=total, page=page, per_page=per_page, pages=pages, items=items)
