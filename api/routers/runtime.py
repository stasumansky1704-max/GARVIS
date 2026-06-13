from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing_extensions import Literal

logger = logging.getLogger("garvis.api.runtime")
router = APIRouter()

class CommandRequest(BaseModel):
    text: str = Field(..., min_length=1)
    session_id: str = Field(default="default")
    source: Literal["text", "voice", "system", "api"] = Field(default="text")
    project_id: str | None = Field(default=None)
    metadata: dict = Field(default_factory=dict)

_runtime_bus: Any | None = None

def get_runtime_bus() -> Any:
    global _runtime_bus
    if _runtime_bus is None:
        from runtime.execution.bus import RuntimeBus
        from runtime.execution.executor import AgentExecutor
        _runtime_bus = RuntimeBus(executor=AgentExecutor())
    return _runtime_bus

@router.post("/command")
async def runtime_command(request: CommandRequest) -> dict[str, Any]:
    try:
        from runtime.execution.models import RuntimeCommand
        bus = get_runtime_bus()
        command = RuntimeCommand(
            session_id=request.session_id,
            source=request.source,
            text=request.text,
            project_id=request.project_id,
            metadata=request.metadata,
        )
        result = await bus.submit(command)
        return result.model_dump()
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Runtime execution layer not available: {exc}") from exc
    except Exception as exc:
        logger.error("Runtime command failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/status")
async def runtime_status() -> dict[str, Any]:
    try:
        bus = get_runtime_bus()
        status = bus.get_status()
        executor = bus.executor
        ollama_healthy = await executor.health_check()
        return {
            **status,
            "ollama_reachable": ollama_healthy,
            "ollama_host": executor.ollama_host,
            "default_model": executor.model,
            "safety_mode": True,
            "version": "2.1.0-runtime",
        }
    except Exception as exc:
        return {
            "state": "initializing",
            "error": str(exc),
            "queue": {"pending": 0, "running": 0, "completed": 0},
            "active_sessions": 0,
            "ollama_reachable": False,
            "ollama_host": None,
            "default_model": None,
            "safety_mode": True,
            "version": "2.1.0-runtime",
        }

@router.get("/commands/{command_id}")
async def get_command_result(command_id: str) -> dict[str, Any]:
    try:
        bus = get_runtime_bus()
    except ImportError:
        raise HTTPException(status_code=503, detail="Runtime execution layer not deployed") from None
    result = bus.get_result(command_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Command not found")
    return result.model_dump()

@router.get("/events/stream")
async def runtime_events_stream() -> StreamingResponse:
    try:
        bus = get_runtime_bus()
    except ImportError:
        async def unavailable():
            yield f"data: {json.dumps({'type': 'error', 'detail': 'Runtime execution layer not deployed'})}\n\n"
        return StreamingResponse(unavailable(), media_type="text/event-stream")

    event_queue: asyncio.Queue[Any] = asyncio.Queue()

    async def event_handler(event: Any) -> None:
        await event_queue.put(event)

    bus.on_event(event_handler)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event.model_dump())}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            try:
                bus.off_event(event_handler)
            except Exception:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")
