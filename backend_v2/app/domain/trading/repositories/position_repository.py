"""PositionRepository Port - interface для persistence position entities."""

from abc import ABC, abstractmethod
from typing import Optional

from ..entities import Position
from ..value_objects import PositionStatus


class PositionRepository(ABC):
    """Abstract interface для position persistence.

    Example (Domain uses):
        >>> # Use case
        >>> positions = await position_repo.get_open_positions_for_user(user_id)
        >>> for position in positions:
        ...     if position.should_trigger_stop_loss(current_price):
        ...         position.close(current_price, exit_trade_id)
        ...         await position_repo.save(position)
    """

    @abstractmethod
    async def save(self, position: Position) -> None:
        """Save або update position.

        Args:
            position: Position entity to save.
        """
        pass

    @abstractmethod
    async def get_by_id(self, position_id: int) -> Optional[Position]:
        """Get position by ID.

        Args:
            position_id: Position ID.

        Returns:
            Position entity або None.
        """
        pass

    @abstractmethod
    async def get_open_positions_for_user(self, user_id: int) -> list[Position]:
        """Get all OPEN positions для користувача.

        Args:
            user_id: User ID.

        Returns:
            List of OPEN positions.

        Note:
            Використовується для portfolio display.
        """
        pass

    @abstractmethod
    async def get_positions_with_stop_loss(self) -> list[Position]:
        """Get all OPEN positions з встановленим stop-loss.

        Returns:
            List of positions for SL monitoring.

        Note:
            Використовується monitoring worker для перевірки SL triggers.
        """
        pass

    @abstractmethod
    async def get_positions_with_take_profit(self) -> list[Position]:
        """Get all OPEN positions з встановленим take-profit.

        Returns:
            List of positions for TP monitoring.

        Note:
            Використовується monitoring worker для перевірки TP triggers.
        """
        pass

    @abstractmethod
    async def get_position_by_symbol_and_user(
        self, user_id: int, symbol: str, status: PositionStatus = PositionStatus.OPEN
    ) -> Optional[Position]:
        """Get position для користувача по symbol.

        Args:
            user_id: User ID.
            symbol: Trading pair.
            status: Position status (default OPEN).

        Returns:
            Position або None.

        Note:
            Зазвичай користувач має max 1 OPEN position per symbol.
        """
        pass

    @abstractmethod
    async def count_open_positions_for_user(self, user_id: int) -> int:
        """Count скільки відкритих позицій у користувача.

        Args:
            user_id: User ID.

        Returns:
            Number of open positions.

        Note:
            Використовується для position limit enforcement.
        """
        pass
