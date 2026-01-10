"""Base AggregateRoot class for domain model.

AggregateRoot - головний Entity в Aggregate, який контролює доступ до всіх інших entities
всередині aggregate та забезпечує consistency (узгодженість).
"""

from typing import List

from .domain_event import DomainEvent
from .entity import Entity


class AggregateRoot(Entity):
    """Base class for aggregate roots in DDD.

    AggregateRoot - це:
    - **Consistency boundary**: Всередині aggregate consistency завжди підтримується
    - **Transaction boundary**: Aggregate зберігається/завантажується як єдине ціле
    - **Event producer**: Aggregate генерує domain events про зміни

    Правила роботи з Aggregates:
    1. Зовнішній код може тримати reference тільки на root
    2. Aggregate зберігається/завантажується повністю (не частинами)
    3. Зміни в aggregate через методи root (не напряму до внутрішніх entities)
    4. Aggregate маленький (ідеально - 1 entity)

    Example:
        >>> class Trade(AggregateRoot):
        ...     def __init__(self, id, user_id, symbol, size):
        ...         super().__init__(id)
        ...         self.user_id = user_id
        ...         self.symbol = symbol
        ...         self.size = size
        ...         self.status = TradeStatus.PENDING
        ...
        ...     def execute(self, order_result: OrderResult):
        ...         # Business logic
        ...         if self.status != TradeStatus.PENDING:
        ...             raise InvalidStateError("Trade already executed")
        ...
        ...         self.status = TradeStatus.FILLED
        ...         self.executed_price = order_result.price
        ...
        ...         # Emit domain event
        ...         self.add_domain_event(
        ...             TradeExecutedEvent(
        ...                 trade_id=self.id,
        ...                 price=order_result.price
        ...             )
        ...         )

        >>> # Usage
        >>> trade = Trade(...)
        >>> trade.execute(order_result)
        >>> events = trade.get_domain_events()  # [TradeExecutedEvent(...)]

    Why AggregateRoot?
        - **Consistency**: Всі бізнес-правила в одному місці
        - **Encapsulation**: Зовнішній код не може зламати aggregate
        - **Events**: Aggregate повідомляє про зміни через events
        - **Transaction**: DB операція = save/load aggregate
    """

    def __init__(self, id: int | None = None) -> None:
        """Initialize aggregate root.

        Args:
            id: Unique identifier. None для нових aggregates.
        """
        super().__init__(id)
        self._domain_events: List[DomainEvent] = []

    def add_domain_event(self, event: DomainEvent) -> None:
        """Add domain event to pending events list.

        Events додаються в aggregate але не публікуються одразу.
        Вони будуть опубліковані після successful commit в DB.

        Args:
            event: Domain event to add.

        Example:
            >>> trade.add_domain_event(TradeExecutedEvent(...))
            >>> # Event буде опублікований після db.commit()
        """
        self._domain_events.append(event)

    def get_domain_events(self) -> List[DomainEvent]:
        """Get all pending domain events.

        Returns:
            List of domain events that occurred during this transaction.

        Note:
            Events typically published by infrastructure layer after DB commit.
        """
        return self._domain_events.copy()

    def clear_domain_events(self) -> None:
        """Clear all pending domain events.

        Викликається після того як events були опубліковані,
        щоб вони не публікувались повторно.

        Example:
            >>> events = aggregate.get_domain_events()
            >>> await event_bus.publish_all(events)
            >>> aggregate.clear_domain_events()
        """
        self._domain_events.clear()

    @property
    def has_domain_events(self) -> bool:
        """Check if aggregate has pending domain events.

        Returns:
            True if there are unpublished events, False otherwise.
        """
        return len(self._domain_events) > 0
