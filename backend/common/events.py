"""In-process async event bus for cross-module communication."""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Coroutine[Any, Any, None]]


@dataclass
class Event:
    name: str
    payload: dict = field(default_factory=dict)


class EventBus:
    """Simple in-process async event bus.

    Usage:
        bus = EventBus()
        bus.on("match_created", handle_new_match)
        bus.emit(Event("match_created", {"match_id": ..., "user_id": ...}))
    """

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = {}

    def on(self, event_name: str, handler: EventHandler) -> None:
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)

    def emit(self, event: Event) -> None:
        """Fire all handlers for this event as background tasks."""
        handlers = self._handlers.get(event.name, [])
        for handler in handlers:
            try:
                asyncio.create_task(handler(event))
            except Exception as e:
                logger.error(f"Event handler error for {event.name}: {e}")


# Global singleton
event_bus = EventBus()
