"""Event Bus - domain events infrastructure.

Event Bus enables event-driven architecture:
- Domain aggregates emit events (TradeExecuted, PositionClosed, etc.)
- Application services subscribe to events
- Decoupling: domain не знає про subscribers
"""

import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable, Type

from app.domain.shared import DomainEvent

logger = logging.getLogger(__name__)

# Event handler signature: async function that takes DomainEvent
EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    """Event Bus для domain events.

    Singleton pattern - один instance на application.

    Example:
        >>> # Subscribe to events
        >>> event_bus = EventBus()
        >>> event_bus.subscribe(TradeExecutedEvent, send_notification_handler)
        >>> event_bus.subscribe(TradeExecutedEvent, update_stats_handler)
        
        >>> # Publish events (зазвичай в application layer після commit)
        >>> events = trade.get_domain_events()
        >>> await event_bus.publish_all(events)
        
        >>> # TradeExecutedEvent → викликає send_notification + update_stats
    """

    def __init__(self) -> None:
        """Initialize event bus."""
        # Map: event_type → list of handlers
        self._subscribers: dict[Type[DomainEvent], list[EventHandler]] = defaultdict(list)
        logger.info("event_bus.initialized")

    def subscribe(
        self, event_type: Type[DomainEvent], handler: EventHandler
    ) -> None:
        """Subscribe handler to event type.

        Args:
            event_type: Type of event (e.g., TradeExecutedEvent).
            handler: Async function to call when event published.

        Example:
            >>> async def send_notification(event: TradeExecutedEvent):
            ...     await telegram.send(f"Trade executed: {event.symbol}")
            
            >>> event_bus.subscribe(TradeExecutedEvent, send_notification)
        """
        self._subscribers[event_type].append(handler)
        logger.info(
            "event_bus.subscription_added",
            extra={
                "event_type": event_type.__name__,
                "handler": handler.__name__,
            },
        )

    def unsubscribe(
        self, event_type: Type[DomainEvent], handler: EventHandler
    ) -> None:
        """Unsubscribe handler from event type.

        Args:
            event_type: Type of event.
            handler: Handler to remove.
        """
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            logger.info(
                "event_bus.subscription_removed",
                extra={
                    "event_type": event_type.__name__,
                    "handler": handler.__name__,
                },
            )

    async def publish(self, event: DomainEvent) -> None:
        """Publish single domain event.

        Викликає всі handlers для цього event type.

        Args:
            event: Domain event to publish.

        Example:
            >>> event = TradeExecutedEvent(trade_id=1, symbol="BTCUSDT", ...)
            >>> await event_bus.publish(event)
            >>> # Викликає всі handlers subscribed на TradeExecutedEvent
        """
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])

        if not handlers:
            logger.debug(
                "event_bus.no_subscribers",
                extra={"event_type": event_type.__name__},
            )
            return

        logger.info(
            "event_bus.publishing",
            extra={
                "event_type": event_type.__name__,
                "handlers_count": len(handlers),
                "event_id": str(event.event_id),
            },
        )

        # Call all handlers
        for handler in handlers:
            try:
                await handler(event)
                logger.debug(
                    "event_bus.handler_success",
                    extra={
                        "event_type": event_type.__name__,
                        "handler": handler.__name__,
                    },
                )
            except Exception as e:
                # Log error but continue with other handlers
                logger.error(
                    "event_bus.handler_failed",
                    extra={
                        "event_type": event_type.__name__,
                        "handler": handler.__name__,
                        "error": str(e),
                    },
                    exc_info=True,
                )

    async def publish_all(self, events: list[DomainEvent]) -> None:
        """Publish multiple domain events.

        Args:
            events: List of domain events to publish.

        Example:
            >>> # Get all events from aggregate
            >>> events = trade.get_domain_events()
            >>> await event_bus.publish_all(events)
        """
        if not events:
            return

        logger.info(
            "event_bus.publishing_batch",
            extra={"events_count": len(events)},
        )

        for event in events:
            await self.publish(event)

    def clear_subscribers(self) -> None:
        """Clear all subscribers (useful for testing)."""
        self._subscribers.clear()
        logger.info("event_bus.cleared")

    def get_subscribers_count(self, event_type: Type[DomainEvent]) -> int:
        """Get number of subscribers for event type.

        Args:
            event_type: Type of event.

        Returns:
            Number of subscribed handlers.
        """
        return len(self._subscribers.get(event_type, []))


# Singleton instance (можна inject як dependency)
_event_bus_instance: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get singleton event bus instance.

    Returns:
        EventBus instance.

    Example:
        >>> event_bus = get_event_bus()
        >>> event_bus.subscribe(TradeExecutedEvent, handler)
    """
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance


def reset_event_bus() -> None:
    """Reset event bus (for testing).

    Creates new instance, clearing all subscribers.
    """
    global _event_bus_instance
    _event_bus_instance = EventBus()
    logger.info("event_bus.reset")
