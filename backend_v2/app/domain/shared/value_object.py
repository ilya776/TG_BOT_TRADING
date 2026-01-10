"""Base ValueObject class for domain model.

ValueObject - immutable об'єкт, який порівнюється за значенням атрибутів,
а не за ідентичністю. Два VO з однаковими атрибутами - це один і той же об'єкт.
"""

from abc import ABC
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, eq=True)
class ValueObject(ABC):
    """Base class for all domain value objects.

    ValueObject характеристики:
    - **Immutable**: Не можна змінити після створення (frozen=True)
    - **Equality by value**: Порівнюється за значенням атрибутів, не за ID
    - **No identity**: Не має власного ID
    - **Replaceable**: Якщо треба змінити, створюємо новий VO

    Example:
        >>> @dataclass(frozen=True)
        ... class Money(ValueObject):
        ...     amount: Decimal
        ...     currency: str

        >>> money1 = Money(Decimal("100"), "USD")
        >>> money2 = Money(Decimal("100"), "USD")
        >>> money1 == money2  # True (same value)
        >>> money1 is money2  # False (different objects)

        >>> money3 = Money(Decimal("200"), "USD")
        >>> money1 == money3  # False (different value)

    Why frozen?
        Immutability гарантує, що VO не зміниться неочікувано:
        >>> money = Money(Decimal("100"), "USD")
        >>> money.amount = Decimal("200")  # FrozenInstanceError!
    """

    def __post_init__(self) -> None:
        """Hook для валідації після ініціалізації.

        Override цей метод для додавання бізнес-правил валідації.

        Example:
            >>> @dataclass(frozen=True)
            ... class Money(ValueObject):
            ...     amount: Decimal
            ...
            ...     def __post_init__(self):
            ...         if self.amount < 0:
            ...             raise ValueError("Amount cannot be negative")

        Raises:
            ValueError: If validation fails.
        """
        pass


def validate_value_object(condition: bool, message: str) -> None:
    """Helper для валідації в value objects.

    Args:
        condition: Умова яка має бути True.
        message: Повідомлення помилки якщо condition False.

    Raises:
        ValueError: If condition is False.

    Example:
        >>> validate_value_object(amount >= 0, "Amount must be non-negative")
    """
    if not condition:
        raise ValueError(message)
