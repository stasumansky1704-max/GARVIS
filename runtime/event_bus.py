"""Async event bus for internal GARVIS communication.

Provides publish/subscribe messaging between runtime components
using asyncio queues for async handlers.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class EventBus:
    """Simple async event bus for internal component communication.

    Features:
        - Async subscribe/unsubscribe with handler registration
        - Async publish that broadcasts to all handlers
        - Sync publish variant for non-async contexts
        - Uses asyncio queues for backpressure-safe delivery

    Example:
        bus = EventBus()
        bus.subscribe("governance.violation", violation_handler)
        await bus.publish("governance.violation", {"schema_id": "..."})
    """

    def __init__(self) -> None:
        self._handlers: dict[
            str, list[Callable[[str, Any], Coroutine[Any, Any, None] | None]]
        ] = defaultdict(list)
        self._queues: dict[str, asyncio.Queue] = {}
        self._dispatch_tasks: set[asyncio.Task] = set()
        self._running: bool = False

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type: str,
        handler: Callable[..., Coroutine[Any, Any, None] | None],
    ) -> None:
        """Register a handler for an event type.

        Args:
            event_type: Event type string (e.g., "state.transition").
            handler: Callable or coroutine that handles the event.
                     For async handlers, should be an async function.
                     For sync handlers, a regular callable.
        """
        self._handlers[event_type].append(handler)
        logger.debug("Handler subscribed to event type: %s", event_type)

    def unsubscribe(
        self,
        event_type: str,
        handler: Callable[..., Coroutine[Any, Any, None] | None],
    ) -> bool:
        """Remove a handler from an event type.

        Args:
            event_type: Event type string.
            handler: The handler to remove.

        Returns:
            True if handler was found and removed.
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug("Handler unsubscribed from event type: %s", event_type)
            return True
        return False

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(self, event_type: str, data: Any) -> int:
        """Publish an event to all subscribed handlers (async).

        Args:
            event_type: Event type string.
            data: Event payload (any JSON-serializable data).

        Returns:
            Number of handlers that received the event.
        """
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            logger.debug("No handlers for event type: %s", event_type)
            return 0

        delivered = 0
        for handler in list(handlers):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_type, data)
                else:
                    handler(event_type, data)
                delivered += 1
            except Exception as exc:
                logger.error(
                    "Event handler error for %s: %s", event_type, exc, exc_info=True
                )

        logger.debug(
            "Published event '%s' to %d/%d handlers",
            event_type,
            delivered,
            len(handlers),
        )
        return delivered

    def publish_sync(self, event_type: str, data: Any) -> int:
        """Publish an event synchronously.

        Schedules the async publish on the current event loop
        if one is running, otherwise executes sync handlers directly.

        Args:
            event_type: Event type string.
            data: Event payload.

        Returns:
            Number of handlers that received the event.
        """
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            return 0

        delivered = 0
        for handler in list(handlers):
            try:
                if asyncio.iscoroutinefunction(handler):
                    # Try to schedule on running loop
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self.publish(event_type, data))
                        delivered += 1
                    except RuntimeError:
                        logger.warning(
                            "Cannot schedule async handler '%s' without running loop",
                            event_type,
                        )
                else:
                    handler(event_type, data)
                    delivered += 1
            except Exception as exc:
                logger.error("Sync event handler error for %s: %s", event_type, exc)

        return delivered

    # ------------------------------------------------------------------
    # Queue-based async delivery (for backpressure handling)
    # ------------------------------------------------------------------

    def subscribe_queued(
        self,
        event_type: str,
        handler: Callable[..., Coroutine[Any, Any, None]],
        max_queue_size: int = 100,
    ) -> None:
        """Subscribe with queue-based delivery for backpressure safety.

        Events are placed in an asyncio queue and consumed by a
        background task. This prevents slow handlers from blocking
        the publisher.

        Args:
            event_type: Event type to subscribe to.
            handler: Async handler function.
            max_queue_size: Maximum queue size before dropping events.
        """
        queue_key = f"{event_type}__{id(handler)}"
        queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._queues[queue_key] = queue

        async def _enqueue_handler(et: str, data: Any) -> None:
            try:
                queue.put_nowait((et, data))
            except asyncio.QueueFull:
                logger.warning(
                    "Event queue full for '%s', dropping event", event_type
                )

        self.subscribe(event_type, _enqueue_handler)

        # Start consumer task
        task = asyncio.create_task(
            self._queue_consumer(queue, handler),
            name=f"event_consumer_{queue_key}",
        )
        self._dispatch_tasks.add(task)
        task.add_done_callback(self._dispatch_tasks.discard)

    async def _queue_consumer(
        self,
        queue: asyncio.Queue,
        handler: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        """Background task that consumes events from a queue."""
        while True:
            try:
                event_type, data = await queue.get()
                await handler(event_type, data)
                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Queue consumer error: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_subscriber_count(self, event_type: str | None = None) -> int:
        """Get the number of subscribers.

        Args:
            event_type: If provided, count for that type only.
                       If None, count all subscribers across all types.

        Returns:
            Number of subscribers.
        """
        if event_type:
            return len(self._handlers.get(event_type, []))
        return sum(len(h) for h in self._handlers.values())

    def clear(self) -> None:
        """Remove all handlers and cancel background tasks."""
        self._handlers.clear()
        self._queues.clear()
        for task in list(self._dispatch_tasks):
            task.cancel()
        self._dispatch_tasks.clear()
        logger.info("Event bus cleared")
