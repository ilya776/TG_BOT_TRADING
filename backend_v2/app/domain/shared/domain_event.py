"""Base DomainEvent class for event-driven architecture.

DomainEvent - щось важливе що сталось в domain, про що треба повідомити інші частини системи.
Events дозволяють decoupling: domain logic не знає хто і як обробляє events.
"""

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent(ABC):
    """Base class for all domain events.

    DomainEvent репрезентує факт що щось сталося в domain.
    Events іменуються в минулому часі (TradeExecuted, PositionClosed).

    Характеристики:
    - **Immutable**: Events не змінюються після створення
    - **Past tense naming**: TradeExecuted, not ExecuteTrade
    - **Rich with data**: Містить всю інформацію про те що сталось
    - **Timestamped**: Коли подія сталась
    - **Unique**: Кожна подія має унікальний ID

    Example:
        >>> @dataclass(frozen=True)
        ... class TradeExecutedEvent(DomainEvent):
        ...     trade_id: int
        ...     user_id: int
        ...     symbol: str
        ...     quantity: Decimal
        ...     price: Decimal

        >>> event = TradeExecutedEvent(
        ...     trade_id=123,
        ...     user_id=456,
        ...     symbol="BTCUSDT",
        ...     quantity=Decimal("0.1"),
        ...     price=Decimal("50000")
        ... )

        >>> # Event handler може підписатись на цю подію
        >>> event_bus.subscribe(TradeExecutedEvent, send_notification_handler)

    Why events?
        1. **Decoupling**: Trade execution не знає про notifications
        2. **Extensibility**: Легко додати нові handlers без зміни domain logic
        3. **Audit trail**: Події = історія всього що відбувалось
        4. **Event sourcing**: Можна відновити стан з історії подій
    """

    event_id: UUID = field(default_factory=uuid4, init=False)
    """Унікальний ID події (auto-generated)."""

    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc), init=False
    )
    """Час коли подія сталась (auto-generated, UTC)."""

    @property
    def event_name(self) -> str:
        """Get human-readable event name.

        Returns:
            Event class name (e.g., "TradeExecutedEvent").
        """
        return self.__class__.__name__

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            String like "TradeExecutedEvent(event_id=..., occurred_at=...)".
        """
        return f"{self.event_name}(event_id={self.event_id}, occurred_at={self.occurred_at})"
