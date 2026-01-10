"""Domain Events для Trading bounded context."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.shared import DomainEvent


@dataclass(frozen=True)
class TradeExecutedEvent(DomainEvent):
    """Event: Trade успішно виконаний на біржі.

    Це critical event - означає що funds були витрачені.
    Subscribers можуть:
    - Відправити notification користувачу
    - Оновити статистику
    - Зробити audit log entry
    """

    trade_id: int
    user_id: int
    signal_id: int | None
    symbol: str
    side: str
    executed_price: Decimal
    executed_quantity: Decimal
    fee_amount: Decimal
    exchange_order_id: str


@dataclass(frozen=True)
class TradeFailedEvent(DomainEvent):
    """Event: Trade failed.

    Subscribers можуть:
    - Відправити error notification
    - Записати в error log
    - Trigger retry mechanism (якщо transient error)
    """

    trade_id: int
    user_id: int
    signal_id: int | None
    symbol: str
    error_message: str


@dataclass(frozen=True)
class TradeNeedsReconciliationEvent(DomainEvent):
    """Event: Trade потребує reconciliation.

    Critical event - означає inconsistency між DB та exchange.
    Потребує manual/automated reconciliation.
    """

    trade_id: int
    user_id: int
    exchange_order_id: str | None
    reason: str
