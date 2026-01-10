"""OrderResult value object - результат виконання ордеру на біржі."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.domain.shared import ValueObject


class OrderStatus(str, Enum):
    """Status ордеру на біржі."""

    FILLED = "filled"
    """Ордер повністю виконаний."""

    PARTIALLY_FILLED = "partially_filled"
    """Ордер частково виконаний."""

    REJECTED = "rejected"
    """Ордер відхилений біржею."""

    CANCELLED = "cancelled"
    """Ордер скасований."""


@dataclass(frozen=True)
class OrderResult(ValueObject):
    """Результат виконання ордеру на біржі.

    Це value object який повертається з ExchangePort.execute_* methods.
    Normalize результат з різних бірж до єдиного формату.

    Example:
        >>> # Binance response
        >>> binance_order = {...}  # Raw Binance response
        >>> result = OrderResult(
        ...     order_id="12345",
        ...     status=OrderStatus.FILLED,
        ...     symbol="BTCUSDT",
        ...     filled_quantity=Decimal("0.1"),
        ...     avg_fill_price=Decimal("50000"),
        ...     total_cost=Decimal("5000"),
        ...     fee_amount=Decimal("5"),
        ... )
    """

    order_id: str
    """Унікальний ID ордеру на біржі."""

    status: OrderStatus
    """Status ордеру."""

    symbol: str
    """Trading pair (normalized)."""

    filled_quantity: Decimal
    """Виконана кількість."""

    avg_fill_price: Decimal
    """Середня ціна виконання."""

    total_cost: Decimal
    """Загальна вартість (quantity * price)."""

    fee_amount: Decimal
    """Комісія біржі."""

    fee_currency: str = "USDT"
    """Валюта комісії (default USDT)."""

    def __post_init__(self) -> None:
        """Validate order result."""
        if self.filled_quantity <= Decimal("0"):
            raise ValueError("Filled quantity must be positive")

        if self.avg_fill_price <= Decimal("0"):
            raise ValueError("Average fill price must be positive")

        if self.total_cost <= Decimal("0"):
            raise ValueError("Total cost must be positive")

        if self.fee_amount < Decimal("0"):
            raise ValueError("Fee amount cannot be negative")
