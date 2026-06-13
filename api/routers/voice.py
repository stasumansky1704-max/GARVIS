from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.routers.runtime import get_runtime_bus

logger = logging.getLogger("garvis.api.voice")
router = APIRouter()

class VoiceTextTestRequest(BaseModel):
    text: str = Field(..., min_length=1)
    session_id: str = Field(default="voice-sim-test")
    metadata: dict = Field(default_factory=dict)

class VoiceStatusResponse(BaseModel):
    stt_available: bool = False
    tts_available: bool = False
    wake_word_available: bool = False
    runtime_bridge_available: bool = True
    note: str = "Voice pipeline is skeleton. Only text simulation is active."

@router.post("/text-test")
async def voice_text_test(request: VoiceTextTestRequest) -> dict[str, Any]:
    try:
        from runtime.execution.models import RuntimeCommand
        bus = get_runtime_bus()
        command = RuntimeCommand(
            session_id=request.session_id,
            source="voice",
            text=request.text,
            metadata=request.metadata,
        )
        result = await bus.submit(command)
        return result.model_dump()
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Runtime execution layer not available: {exc}") from exc
    except Exception as exc:
        logger.error("Voice text test failed: %s", exc, exc_info=True)
        return {
            "command_id": "",
            "status": "failed",
            "response_text": f"Voice text test failed: {exc}",
            "errors": [str(exc)],
        }

@router.get("/status")
async def voice_status() -> VoiceStatusResponse:
    return VoiceStatusResponse()
