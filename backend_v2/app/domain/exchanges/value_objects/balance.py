"""Balance value object - баланс користувача на біржі."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.shared import ValueObject


@dataclass(frozen=True)
class Balance(ValueObject):
    """Баланс користувача на біржі.

    Example:
        >>> balance = Balance(
        ...     asset="USDT",
        ...     free=Decimal("1000"),
        ...     locked=Decimal("100"),
        ... )
        >>> balance.total  # Decimal("1100")
    """

    asset: str
    """Asset name (e.g., "USDT", "BTC")."""

    free: Decimal
    """Available balance (можна використати для trades)."""

    locked: Decimal
    """Locked balance (в активних ордерах)."""

    @property
    def total(self) -> Decimal:
        """Total balance (free + locked)."""
        return self.free + self.locked

    def __post_init__(self) -> None:
        """Validate balance."""
        if self.free < Decimal("0"):
            raise ValueError("Free balance cannot be negative")

        if self.locked < Decimal("0"):
            raise ValueError("Locked balance cannot be negative")
