"""FastAPI application factory for the GARVIS Operator API.

Governance-Aware Reflective Virtual Intelligence System - Operator Console API.
Provides REST endpoints and WebSocket for real-time observation of the GARVIS runtime.

All endpoints are strictly observational (read-only by default).  State transitions
and schema activation require explicit POST with reason.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import (
    command_center,
    collaboration,
    governance,
    cognition,
    memory,
    traceability,
    audit,
    analytics,
    status,
)
from api.websocket import manager, handle_websocket

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Startup: initialize mock data, start WebSocket broadcast loop.
    Shutdown: clean up broadcast loop.
    """
    # Startup
    logger.info("GARVIS Operator API starting up...")
    from api.dependencies import _init_mock_data
    _init_mock_data()
    await manager.start_broadcast_loop()
    logger.info("GARVIS Operator API ready")

    yield

    # Shutdown
    logger.info("GARVIS Operator API shutting down...")
    await manager.stop_broadcast_loop()


# ── FastAPI app factory ───────────────────────────────────────────────────

app = FastAPI(
    title="GARVIS Operator API",
    description=(
        "**Governance-Aware Reflective Virtual Intelligence System** - "
        "Operator Console API.\n\n"
        "Provides RESTful endpoints and WebSocket for real-time observation "
        "of the GARVIS cognition runtime. All endpoints are strictly "
        "observational - they expose data for operator viewing, never execute "
        "autonomous cognition.\n\n"
        "## Governance Context\n"
        "Every response includes governance context headers.\n"
        "- `X-Governance-Scope`: The governance scope of the endpoint\n"
        "- `X-API-Version`: API version identifier\n"
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to dashboard origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Governance context middleware ─────────────────────────────────────────

@app.middleware("http")
async def governance_context_middleware(request, call_next):
    """Add governance context headers to every response."""
    response = await call_next(request)
    response.headers["X-API-Version"] = "v1"
    response.headers["X-Governance-Aware"] = "true"
    response.headers["X-Observational-Only"] = "true"
    return response


# ── Router inclusion ──────────────────────────────────────────────────────

app.include_router(
    governance.router,
    prefix="/api/v1/governance",
    tags=["governance"],
)
app.include_router(
    cognition.router,
    prefix="/api/v1/cognition",
    tags=["cognition"],
)
app.include_router(
    memory.router,
    prefix="/api/v1/memory",
    tags=["memory"],
)
app.include_router(
    traceability.router,
    prefix="/api/v1/traceability",
    tags=["traceability"],
)
app.include_router(
    audit.router,
    prefix="/api/v1/audit",
    tags=["audit"],
)
app.include_router(
    analytics.router,
    prefix="/api/v1/analytics",
    tags=["analytics"],
)
app.include_router(
    status.router,
    prefix="/api/v1/status",
    tags=["status"],
)
app.include_router(
    command_center.router,
    prefix="/api/v1/command-center",
    tags=["command-center"],
)
app.include_router(
    collaboration.router,
    prefix="/api/v1/collaboration",
    tags=["collaboration"],
)


# ── Root endpoint ─────────────────────────────────────────────────────────

@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """API root — returns basic info and available endpoints."""
    return {
        "name": "GARVIS Operator API",
        "version": "2.0.0",
        "description": "Governance-Aware Reflective Virtual Intelligence System",
        "docs": "/docs",
        "health": "/api/v1/status/health",
        "status": "/api/v1/status/",
        "websocket": "/ws",
    }


# ── WebSocket endpoint ────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket for real-time operator dashboard updates.

    On connect: sends current governance state snapshot.
    Then: streams periodic updates (state changes, audit events, metrics).

    Client messages:
    - `{"type": "ping"}` → receives `{"type": "pong"}`
    - `{"type": "get_state"}` → receives full governance state
    - `{"type": "subscribe", "channel": "all"}` → subscribes to channel
    """
    await handle_websocket(websocket)
