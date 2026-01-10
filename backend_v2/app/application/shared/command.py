"""Base Command class для CQRS pattern.

Command - запит на зміну стану системи (write operation).
Commands мають side effects (змінюють дані).
"""

from abc import ABC
from dataclasses import dataclass


@dataclass(frozen=True)
class Command(ABC):
    """Base class для всіх commands.

    Command характеристики:
    - **Immutable**: frozen=True запобігає змінам
    - **Intent**: Чітко виражає намір (ExecuteCopyTradeCommand, ClosePositionCommand)
    - **Verb-based naming**: ExecuteTrade, ClosePosition (не Trade, Position)
    - **No business logic**: Тільки data, logic в Handler

    Example:
        >>> @dataclass(frozen=True)
        ... class ExecuteCopyTradeCommand(Command):
        ...     signal_id: int
        ...     user_id: int | None = None
        ...     size_usdt_override: Decimal | None = None

        >>> command = ExecuteCopyTradeCommand(signal_id=123, user_id=456)
        >>> result = await handler.handle(command)

    Why Commands?
        - **Explicit intent**: Код читається як business process
        - **Validation**: Можна validate command перед execution
        - **Audit trail**: Log all commands = повна історія операцій
        - **Testability**: Easy to test handlers with simple command objects
    """

    pass
