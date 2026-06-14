from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .executor import AgentExecutor
from .models import RuntimeCommand, RuntimeEvent, RuntimeResult

EventHandler = Callable[[RuntimeEvent], Awaitable[None]]


BLOCKED_PATTERNS = [
    "rm -rf",
    "del /f",
    "format ",
    "shutdown",
    "reboot",
    "docker compose down",
    "docker rm",
    "sudo ",
    "powershell",
    "cmd.exe",
]


class RuntimeBus:
    def __init__(self, executor: AgentExecutor | None = None) -> None:
        self.executor = executor or AgentExecutor()
        self.results: dict[str, RuntimeResult] = {}
        self.events: list[RuntimeEvent] = []
        self.handlers: list[EventHandler] = []
        self.pending = 0
        self.running = 0
        self.completed = 0

    def on_event(self, handler: EventHandler) -> None:
        self.handlers.append(handler)

    def off_event(self, handler: EventHandler) -> None:
        if handler in self.handlers:
            self.handlers.remove(handler)

    async def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)
        for handler in list(self.handlers):
            try:
                await handler(event)
            except Exception:
                pass

    def get_status(self) -> dict[str, Any]:
        return {
            "state": "operational",
            "queue": {
                "pending": self.pending,
                "running": self.running,
                "completed": self.completed,
            },
            "active_sessions": 0,
        }

    def get_result(self, command_id: str) -> RuntimeResult | None:
        return self.results.get(command_id)

    def check_governance(self, text: str) -> dict[str, Any]:
        lowered = text.lower()
        for pattern in BLOCKED_PATTERNS:
            if pattern in lowered:
                return {
                    "decision": "block",
                    "allowed": False,
                    "reason": f"Blocked action detected: {pattern}",
                }
        return {
            "decision": "allow",
            "allowed": True,
            "reason": "Safe conversational command",
        }

    async def submit(self, command: RuntimeCommand) -> RuntimeResult:
        await self.emit(RuntimeEvent(
            command_id=command.command_id,
            session_id=command.session_id,
            type="command_received",
            payload={"source": command.source},
        ))

        governance = self.check_governance(command.text)

        if not governance["allowed"]:
            result = RuntimeResult(
                command_id=command.command_id,
                status="blocked",
                response_text=governance["reason"],
                governance_decision=governance,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            self.results[command.command_id] = result
            await self.emit(RuntimeEvent(
                command_id=command.command_id,
                session_id=command.session_id,
                type="governance_blocked",
                payload=governance,
            ))
            return result

        self.running += 1
        try:
            await self.emit(RuntimeEvent(
                command_id=command.command_id,
                session_id=command.session_id,
                type="model_call_started",
                payload={"model": self.executor.model},
            ))

            # pass source so the executor can apply the voice-mode profile (Phase 3)
            exec_context = {**(command.metadata or {}), "source": command.source}
            response_text = await self.executor.execute(command.text, context=exec_context)

            result = RuntimeResult(
                command_id=command.command_id,
                status="completed",
                response_text=response_text,
                governance_decision=governance,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

            await self.emit(RuntimeEvent(
                command_id=command.command_id,
                session_id=command.session_id,
                type="command_completed",
                payload={"status": "completed"},
            ))

        except Exception as exc:
            result = RuntimeResult(
                command_id=command.command_id,
                status="failed",
                response_text=f"Runtime execution failed: {exc}",
                governance_decision=governance,
                errors=[str(exc)],
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            await self.emit(RuntimeEvent(
                command_id=command.command_id,
                session_id=command.session_id,
                type="command_failed",
                payload={"error": str(exc)},
            ))
        finally:
            self.running = max(0, self.running - 1)
            self.completed += 1

        self.results[command.command_id] = result
        return result
