"""WebSocket handler for real-time GARVIS operator updates.

Manages client connections and broadcasts runtime state changes,
audit events, and governance updates to connected dashboard clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from api.dependencies import (
    get_mock_schemas,
    get_mock_active_schema_ids,
    get_audit_events as get_mock_audit_events,
    get_mock_violations,
    get_uptime_seconds,
)

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time operator updates.

    On connect: sends current governance state snapshot.
    Then: periodically broadcasts state changes, audit events, and metrics.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._broadcast_task: asyncio.Task | None = None
        self._seq = 0

    # ── Connection management ─────────────────────────────────────────────

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and send initial state."""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WebSocket client connected. Total: %d", len(self._connections))

        # Send initial governance state
        await self._send_initial_state(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("WebSocket client disconnected. Total: %d", len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        if not self._connections:
            return

        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []

        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)

    async def send_personal(self, message: dict[str, Any], websocket: WebSocket) -> None:
        """Send a message to a specific client."""
        try:
            await websocket.send_text(json.dumps(message, default=str))
        except Exception:
            await self.disconnect(websocket)

    # ── Initial state ─────────────────────────────────────────────────────

    async def _send_initial_state(self, websocket: WebSocket) -> None:
        """Send the current governance state snapshot to a new client."""
        schemas = get_mock_schemas()
        active_ids = get_mock_active_schema_ids()
        events = get_mock_audit_events()
        violations = get_mock_violations()

        state = {
            "type": "governance_state",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "schemas_total": len(schemas),
                "schemas_active": len(active_ids),
                "active_schema_ids": sorted(active_ids),
                "schema_list": [
                    {
                        "schema_id": s.schema_id,
                        "name": s.name,
                        "version": s.version,
                        "category": s.category,
                        "active": s.schema_id in active_ids,
                        "policies": len(s.policies),
                        "constraints": len(s.constraints),
                    }
                    for s in schemas
                ],
                "recent_events": [
                    {
                        "event_type": e.event_type,
                        "severity": e.severity,
                        "component": e.component,
                        "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, "isoformat") else str(e.timestamp),
                    }
                    for e in events[-5:]  # Last 5 events
                ],
                "violations_recent": [
                    {
                        "schema_id": v.schema_id,
                        "policy_id": v.policy_id,
                        "severity": v.severity,
                        "description": v.description,
                    }
                    for v in violations[-3:]  # Last 3 violations
                ],
            },
        }
        await self.send_personal(state, websocket)

    # ── Periodic broadcast ────────────────────────────────────────────────

    async def start_broadcast_loop(self) -> None:
        """Start the periodic state broadcast background task."""
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(
                self._broadcast_loop(), name="ws_broadcast_loop"
            )
            logger.debug("WebSocket broadcast loop started")

    async def stop_broadcast_loop(self) -> None:
        """Stop the broadcast loop."""
        if self._broadcast_task and not self._broadcast_task.done():
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

    async def _broadcast_loop(self) -> None:
        """Periodically broadcast updates to all connected clients."""
        while True:
            try:
                await asyncio.sleep(10)  # Broadcast every 10 seconds

                if not self._connections:
                    continue

                self._seq += 1
                uptime = get_uptime_seconds()

                # Build heartbeat / metrics update
                message = {
                    "type": "heartbeat",
                    "seq": self._seq,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "uptime_seconds": uptime,
                        "current_state": "cognition_active",
                        "active_connections": len(self._connections),
                    },
                }
                await self.broadcast(message)

                # Every 3rd broadcast, send a synthetic event
                if self._seq % 3 == 0:
                    synthetic = self._generate_synthetic_update()
                    await self.broadcast(synthetic)

            except asyncio.CancelledError:
                logger.debug("WebSocket broadcast loop cancelled")
                break
            except Exception as exc:
                logger.error("WebSocket broadcast error: %s", exc)

    def _generate_synthetic_update(self) -> dict[str, Any]:
        """Generate a synthetic runtime update for demo purposes."""
        import random

        update_types = ["inference_complete", "governance_check", "memory_access", "state_change"]
        update_type = random.choice(update_types)

        if update_type == "inference_complete":
            return {
                "type": "inference_complete",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "model": "llama3.1",
                    "prompt_length": random.randint(50, 500),
                    "response_length": random.randint(100, 1000),
                    "inference_time_ms": random.randint(500, 3000),
                    "passed_validation": random.random() > 0.1,
                },
            }
        elif update_type == "governance_check":
            schemas = get_mock_schemas()
            schema = random.choice(schemas)
            policy = random.choice(schema.policies) if schema.policies else None
            passed = random.random() > 0.2
            return {
                "type": "governance_check",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "schema_id": schema.schema_id,
                    "policy_id": policy.policy_id if policy else "unknown",
                    "passed": passed,
                    "severity": policy.severity if policy else "info",
                },
            }
        elif update_type == "memory_access":
            return {
                "type": "memory_access",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "access_type": random.choice(["retrieval", "store", "update"]),
                    "memories_accessed": random.randint(1, 5),
                    "retrieval_time_ms": random.randint(5, 50),
                },
            }
        else:  # state_change
            return {
                "type": "state_change",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "from_state": "cognition_active",
                    "to_state": "cognition_active",
                    "trigger": "periodic_heartbeat",
                    "governance_check": True,
                },
            }


# Global connection manager instance
manager = ConnectionManager()


# ── WebSocket endpoint handler ────────────────────────────────────────────


async def handle_websocket(websocket: WebSocket) -> None:
    """Handle a WebSocket connection lifecycle."""
    await manager.connect(websocket)

    try:
        while True:
            # Receive client messages (ping/pong, subscription changes, etc.)
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_type = message.get("type", "unknown")

                if msg_type == "ping":
                    await manager.send_personal(
                        {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()},
                        websocket,
                    )
                elif msg_type == "subscribe":
                    channel = message.get("channel", "all")
                    await manager.send_personal(
                        {"type": "subscribed", "channel": channel},
                        websocket,
                    )
                elif msg_type == "get_state":
                    await manager._send_initial_state(websocket)
                else:
                    await manager.send_personal(
                        {"type": "error", "message": f"Unknown message type: {msg_type}"},
                        websocket,
                    )

            except json.JSONDecodeError:
                await manager.send_personal(
                    {"type": "error", "message": "Invalid JSON"},
                    websocket,
                )

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
        await manager.disconnect(websocket)
