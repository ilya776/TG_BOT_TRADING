"""SQLAlchemy implementation of TradeRepository."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.trading.entities import Trade
from app.domain.trading.repositories import TradeRepository as TradeRepositoryPort
from app.domain.trading.value_objects import TradeStatus
from app.infrastructure.persistence.sqlalchemy.mappers import TradeMapper
from app.infrastructure.persistence.sqlalchemy.models import TradeModel


class SQLAlchemyTradeRepository(TradeRepositoryPort):
    """SQLAlchemy implementation of TradeRepository port.

    Використовує:
    - AsyncSession для async DB operations
    - TradeMapper для Domain ↔ ORM conversion
    - SQLAlchemy ORM для queries

    Example:
        >>> async with AsyncSession(engine) as session:
        ...     repo = SQLAlchemyTradeRepository(session)
        ...     trade = await repo.get_by_id(123)
        ...     trade.execute(order_result)
        ...     await repo.save(trade)
        ...     await session.commit()
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session
        self._mapper = TradeMapper()

    async def save(self, trade: Trade) -> None:
        """Save або update trade.

        Args:
            trade: Trade entity to save.

        Note:
            - Якщо trade.id is None → INSERT
            - Якщо trade.id exists → UPDATE з optimistic locking
        """
        if trade.id is None:
            # INSERT: Create new TradeModel
            model = self._mapper.to_model(trade)
            self._session.add(model)
            await self._session.flush()  # Get generated ID
            trade.id = model.id
        else:
            # UPDATE: Merge existing model
            existing_model = await self._session.get(TradeModel, trade.id)
            if existing_model is None:
                raise ValueError(f"Trade {trade.id} not found for update")

            # Update model з entity (increment version for optimistic locking)
            updated_model = self._mapper.update_model_from_entity(
                existing_model, trade
            )
            await self._session.flush()

    async def get_by_id(self, trade_id: int) -> Optional[Trade]:
        """Get trade by ID.

        Args:
            trade_id: Trade ID.

        Returns:
            Trade entity або None.
        """
        model = await self._session.get(TradeModel, trade_id)
        if model is None:
            return None

        return self._mapper.to_entity(model)

    async def get_pending_trades_for_user(self, user_id: int) -> list[Trade]:
        """Get all PENDING trades для користувача.

        Args:
            user_id: User ID.

        Returns:
            List of PENDING trades.
        """
        stmt = (
            select(TradeModel)
            .where(TradeModel.user_id == user_id)
            .where(TradeModel.status == TradeStatus.PENDING.value)
            .order_by(TradeModel.created_at.desc())
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._mapper.to_entity(model) for model in models]

    async def get_trades_by_signal(self, signal_id: int) -> list[Trade]:
        """Get all trades для конкретного signal.

        Args:
            signal_id: Signal ID.

        Returns:
            List of trades created from this signal.
        """
        stmt = (
            select(TradeModel)
            .where(TradeModel.signal_id == signal_id)
            .order_by(TradeModel.created_at.desc())
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._mapper.to_entity(model) for model in models]

    async def get_trades_needing_reconciliation(self) -> list[Trade]:
        """Get all trades з status NEEDS_RECONCILIATION.

        Returns:
            List of trades що потребують reconciliation.
        """
        stmt = (
            select(TradeModel)
            .where(TradeModel.status == TradeStatus.NEEDS_RECONCILIATION.value)
            .order_by(TradeModel.created_at.asc())  # Oldest first
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._mapper.to_entity(model) for model in models]

    async def count_user_trades_today(self, user_id: int) -> int:
        """Count скільки trades користувач зробив сьогодні.

        Args:
            user_id: User ID.

        Returns:
            Number of trades today.
        """
        # Get start of today (UTC)
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        stmt = (
            select(func.count(TradeModel.id))
            .where(TradeModel.user_id == user_id)
            .where(TradeModel.created_at >= today_start)
        )

        result = await self._session.execute(stmt)
        count = result.scalar_one()

        return count
