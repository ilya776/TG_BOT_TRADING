"""ClosePosition Command - закрити відкриту position."""

from dataclasses import dataclass

from app.application.shared import Command


@dataclass(frozen=True)
class ClosePositionCommand(Command):
    """Command для закриття position.

    Orchestrates:
    1. Get position з DB
    2. Execute close trade на exchange
    3. Update position to CLOSED
    4. Calculate realized PnL
    5. Publish PositionClosedEvent

    Example:
        >>> command = ClosePositionCommand(
        ...     position_id=123,
        ...     user_id=1,
        ...     exchange_name="binance",
        ... )
        >>> result = await handler.handle(command)
        >>> # Position closed, PnL calculated, event published!
    """

    position_id: int
    """ID position для закриття."""

    user_id: int
    """ID користувача (security check)."""

    exchange_name: str
    """Назва біржі."""
