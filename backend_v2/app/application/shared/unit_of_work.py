"""Unit of Work pattern - manages transactions.

UnitOfWork забезпечує:
- Atomic operations (all or nothing)
- Transaction boundary
- Single commit per use case
"""

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Optional, Type


class UnitOfWork(ABC):
    """Abstract Unit of Work interface.

    UnitOfWork pattern:
    - **Atomic**: Всі зміни в одній транзакції
    - **Consistent**: Commit тільки якщо все успішно
    - **Isolated**: Транзакції ізольовані одна від одної
    - **Context Manager**: Use with async context manager

    Example (Infrastructure implements):
        >>> class SQLAlchemyUnitOfWork(UnitOfWork):
        ...     def __init__(self, session_factory):
        ...         self.session_factory = session_factory
        ...
        ...     async def __aenter__(self):
        ...         self.session = self.session_factory()
        ...         return self
        ...
        ...     async def __aexit__(self, *args):
        ...         await self.session.close()
        ...
        ...     async def commit(self):
        ...         await self.session.commit()
        ...
        ...     async def rollback(self):
        ...         await self.session.rollback()
        ...
        ...     @property
        ...     def trades(self) -> TradeRepository:
        ...         return SQLAlchemyTradeRepository(self.session)

    Example (Use case uses):
        >>> async with uow:
        ...     trade = await uow.trades.get_by_id(123)
        ...     trade.execute(order_result)
        ...     await uow.trades.save(trade)
        ...
        ...     position = Position.create_from_trade(trade)
        ...     await uow.positions.save(position)
        ...
        ...     await uow.commit()  # Single commit for entire operation

    Why Unit of Work?
        - **Consistency**: Either all changes succeed or all fail
        - **Performance**: Single commit замість багатьох
        - **Simplicity**: Infrastructure handles transaction management
    """

    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork":
        """Enter async context manager.

        Returns:
            Self (UnitOfWork instance).
        """
        pass

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit async context manager.

        Args:
            exc_type: Exception type if exception occurred.
            exc_val: Exception value.
            exc_tb: Exception traceback.

        Note:
            Якщо exc_type не None, має викликати rollback().
        """
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit transaction.

        Raises:
            Exception: If commit failed.
        """
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback transaction.

        Note:
            Використовується коли exception в use case.
        """
        pass
