"""TradeRepository Port - interface для persistence trade entities.

Це PORT в Hexagonal Architecture (domain визначає interface).
Infrastructure layer має implement цей interface.
"""

from abc import ABC, abstractmethod
from typing import Optional

from ..entities import Trade
from ..value_objects import TradeStatus


class TradeRepository(ABC):
    """Abstract interface для trade persistence.

    Infrastructure layer implements цей interface з SQLAlchemy.
    Domain layer uses цей interface (Dependency Inversion).

    Example (Infrastructure implements):
        >>> class SQLAlchemyTradeRepository(TradeRepository):
        ...     async def save(self, trade: Trade) -> None:
        ...         trade_model = self.mapper.to_model(trade)
        ...         self.session.add(trade_model)
        ...
        ...     async def get_by_id(self, trade_id: int) -> Trade | None:
        ...         model = await self.session.get(TradeModel, trade_id)
        ...         return self.mapper.to_entity(model)

    Example (Domain uses):
        >>> # Use case не знає про SQLAlchemy
        >>> trade = await trade_repo.get_by_id(123)
        >>> trade.execute(order_result)
        >>> await trade_repo.save(trade)
    """

    @abstractmethod
    async def save(self, trade: Trade) -> None:
        """Save або update trade.

        Args:
            trade: Trade entity to save.

        Note:
            Якщо trade.id is None, це INSERT.
            Якщо trade.id exists, це UPDATE.
        """
        pass

    @abstractmethod
    async def get_by_id(self, trade_id: int) -> Optional[Trade]:
        """Get trade by ID.

        Args:
            trade_id: Trade ID.

        Returns:
            Trade entity або None якщо не знайдено.
        """
        pass

    @abstractmethod
    async def get_pending_trades_for_user(self, user_id: int) -> list[Trade]:
        """Get all PENDING trades для користувача.

        Args:
            user_id: User ID.

        Returns:
            List of PENDING trades.

        Note:
            Використовується для cleanup orphaned trades.
        """
        pass

    @abstractmethod
    async def get_trades_by_signal(self, signal_id: int) -> list[Trade]:
        """Get all trades для конкретного signal.

        Args:
            signal_id: Signal ID.

        Returns:
            List of trades created from this signal.

        Note:
            Використовується для analytics (скільки users copied signal).
        """
        pass

    @abstractmethod
    async def get_trades_needing_reconciliation(self) -> list[Trade]:
        """Get all trades з status NEEDS_RECONCILIATION.

        Returns:
            List of trades що потребують reconciliation.

        Note:
            Використовується reconciliation worker.
        """
        pass

    @abstractmethod
    async def count_user_trades_today(self, user_id: int) -> int:
        """Count скільки trades користувач зробив сьогодні.

        Args:
            user_id: User ID.

        Returns:
            Number of trades today.

        Note:
            Використовується для rate limiting (max trades per day).
        """
        pass
