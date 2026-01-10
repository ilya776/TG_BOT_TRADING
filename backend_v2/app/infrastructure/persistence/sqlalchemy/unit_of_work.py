"""SQLAlchemy Unit of Work implementation."""

import logging
from types import TracebackType
from typing import Callable, Optional, Type

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.shared import UnitOfWork
from app.domain.signals.repositories import SignalRepository
from app.domain.trading.repositories import PositionRepository, TradeRepository
from app.domain.whales.repositories import WhaleFollowRepository
from app.infrastructure.persistence.sqlalchemy.repositories import (
    SQLAlchemyPositionRepository,
    SQLAlchemySignalRepository,
    SQLAlchemyTradeRepository,
    SQLAlchemyWhaleFollowRepository,
)

logger = logging.getLogger(__name__)


class SQLAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of Unit of Work pattern.

    Відповідальності:
    - Керування SQLAlchemy async session
    - Transaction management (commit/rollback)
    - Automatic rollback при exceptions
    - Lazy initialization of repositories

    Example:
        >>> session_factory = async_sessionmaker(engine, ...)
        >>> uow = SQLAlchemyUnitOfWork(session_factory)
        >>>
        >>> async with uow:
        ...     trade = await uow.trades.get_by_id(123)
        ...     trade.execute(order_result)
        ...     await uow.trades.save(trade)
        ...
        ...     position = Position.create_from_trade(trade)
        ...     await uow.positions.save(position)
        ...
        ...     await uow.commit()  # Single commit!

    Why SQLAlchemy Unit of Work:
        - **Single Session**: All repositories share same session
        - **Single Transaction**: All changes in one atomic transaction
        - **Auto Rollback**: Exception → automatic rollback
        - **Resource Management**: Session cleanup guaranteed
    """

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Initialize Unit of Work.

        Args:
            session_factory: SQLAlchemy async session factory.
        """
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None

        # Repository instances (lazy initialized)
        self._trades: Optional[TradeRepository] = None
        self._positions: Optional[PositionRepository] = None
        self._signals: Optional[SignalRepository] = None
        self._whale_follows: Optional[WhaleFollowRepository] = None

    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        """Enter async context manager.

        Creates new SQLAlchemy session and starts transaction.

        Returns:
            Self (UnitOfWork instance).
        """
        # Create new session
        self._session = self._session_factory()

        # Start transaction (SQLAlchemy 2.0+ auto-begins)
        logger.debug("unit_of_work.started")

        return self

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
            - Якщо exc_type не None → rollback
            - Завжди закриває session (cleanup)
        """
        try:
            if exc_type is not None:
                # Exception occurred - rollback transaction
                await self.rollback()
                logger.warning(
                    "unit_of_work.rolled_back",
                    extra={"exception_type": exc_type.__name__},
                )
        finally:
            # Always close session (cleanup)
            if self._session:
                await self._session.close()
                self._session = None
                self._trades = None  # Clear repository references
                self._positions = None
                self._signals = None
                self._whale_follows = None

            logger.debug("unit_of_work.closed")

    async def commit(self) -> None:
        """Commit transaction.

        Зберігає всі зміни з всіх repositories в DB.

        Raises:
            Exception: If commit failed (DB error, constraint violation, etc.).
        """
        if self._session is None:
            raise RuntimeError("Unit of Work not started (use async with)")

        try:
            await self._session.commit()
            logger.debug("unit_of_work.committed")
        except Exception as e:
            logger.error(
                "unit_of_work.commit_failed", extra={"error": str(e)}
            )
            await self.rollback()
            raise

    async def rollback(self) -> None:
        """Rollback transaction.

        Відміняє всі зміни з repositories.
        """
        if self._session is None:
            raise RuntimeError("Unit of Work not started (use async with)")

        await self._session.rollback()
        logger.debug("unit_of_work.rolled_back")

    @property
    def trades(self) -> TradeRepository:
        """Get TradeRepository instance.

        Returns:
            TradeRepository (SQLAlchemy implementation).

        Note:
            Lazy initialization - створюється тільки коли потрібно.
        """
        if self._session is None:
            raise RuntimeError("Unit of Work not started (use async with)")

        if self._trades is None:
            self._trades = SQLAlchemyTradeRepository(self._session)

        return self._trades

    @property
    def positions(self) -> PositionRepository:
        """Get PositionRepository instance.

        Returns:
            PositionRepository (SQLAlchemy implementation).

        Note:
            Lazy initialization - створюється тільки коли потрібно.
        """
        if self._session is None:
            raise RuntimeError("Unit of Work not started (use async with)")

        if self._positions is None:
            self._positions = SQLAlchemyPositionRepository(self._session)

        return self._positions

    @property
    def signals(self) -> SignalRepository:
        """Get SignalRepository instance.

        Returns:
            SignalRepository (SQLAlchemy implementation).

        Note:
            Lazy initialization - створюється тільки коли потрібно.
        """
        if self._session is None:
            raise RuntimeError("Unit of Work not started (use async with)")

        if self._signals is None:
            self._signals = SQLAlchemySignalRepository(self._session)

        return self._signals

    @property
    def whale_follows(self) -> WhaleFollowRepository:
        """Get WhaleFollowRepository instance.

        Returns:
            WhaleFollowRepository (SQLAlchemy implementation).

        Note:
            Lazy initialization - створюється тільки коли потрібно.
        """
        if self._session is None:
            raise RuntimeError("Unit of Work not started (use async with)")

        if self._whale_follows is None:
            self._whale_follows = SQLAlchemyWhaleFollowRepository(self._session)

        return self._whale_follows


# Factory function для dependency injection
def create_unit_of_work(
    session_factory: async_sessionmaker[AsyncSession],
) -> SQLAlchemyUnitOfWork:
    """Factory для створення Unit of Work.

    Args:
        session_factory: SQLAlchemy async session factory.

    Returns:
        SQLAlchemyUnitOfWork instance.

    Example:
        >>> from sqlalchemy.ext.asyncio import create_async_engine
        >>> engine = create_async_engine("postgresql+asyncpg://...")
        >>> session_factory = async_sessionmaker(engine, expire_on_commit=False)
        >>> uow = create_unit_of_work(session_factory)
    """
    return SQLAlchemyUnitOfWork(session_factory)
