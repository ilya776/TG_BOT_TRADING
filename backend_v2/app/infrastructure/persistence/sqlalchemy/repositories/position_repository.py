"""SQLAlchemy implementation of PositionRepository."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.trading.entities import Position
from app.domain.trading.repositories import (
    PositionRepository as PositionRepositoryPort,
)
from app.domain.trading.value_objects import PositionStatus
from app.infrastructure.persistence.sqlalchemy.mappers import PositionMapper
from app.infrastructure.persistence.sqlalchemy.models import PositionModel


class SQLAlchemyPositionRepository(PositionRepositoryPort):
    """SQLAlchemy implementation of PositionRepository port.

    Використовує:
    - AsyncSession для async DB operations
    - PositionMapper для Domain ↔ ORM conversion
    - SQLAlchemy ORM для queries

    Example:
        >>> async with AsyncSession(engine) as session:
        ...     repo = SQLAlchemyPositionRepository(session)
        ...     positions = await repo.get_open_positions_for_user(user_id)
        ...     for position in positions:
        ...         if position.should_trigger_stop_loss(current_price):
        ...             position.close(current_price, exit_trade_id)
        ...             await repo.save(position)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session
        self._mapper = PositionMapper()

    async def save(self, position: Position) -> None:
        """Save або update position.

        Args:
            position: Position entity to save.

        Note:
            - Якщо position.id is None → INSERT
            - Якщо position.id exists → UPDATE з optimistic locking
        """
        if position.id is None:
            # INSERT: Create new PositionModel
            model = self._mapper.to_model(position)
            self._session.add(model)
            await self._session.flush()  # Get generated ID
            position.id = model.id
        else:
            # UPDATE: Merge existing model
            existing_model = await self._session.get(PositionModel, position.id)
            if existing_model is None:
                raise ValueError(f"Position {position.id} not found for update")

            # Update model з entity (increment version for optimistic locking)
            updated_model = self._mapper.update_model_from_entity(
                existing_model, position
            )
            await self._session.flush()

    async def get_by_id(self, position_id: int) -> Optional[Position]:
        """Get position by ID.

        Args:
            position_id: Position ID.

        Returns:
            Position entity або None.
        """
        model = await self._session.get(PositionModel, position_id)
        if model is None:
            return None

        return self._mapper.to_entity(model)

    async def get_open_positions_for_user(self, user_id: int) -> list[Position]:
        """Get all OPEN positions для користувача.

        Args:
            user_id: User ID.

        Returns:
            List of OPEN positions.
        """
        stmt = (
            select(PositionModel)
            .where(PositionModel.user_id == user_id)
            .where(PositionModel.status == PositionStatus.OPEN.value)
            .order_by(PositionModel.opened_at.desc())
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._mapper.to_entity(model) for model in models]

    async def get_positions_with_stop_loss(self) -> list[Position]:
        """Get all OPEN positions з встановленим stop-loss.

        Returns:
            List of positions for SL monitoring.
        """
        stmt = (
            select(PositionModel)
            .where(PositionModel.status == PositionStatus.OPEN.value)
            .where(PositionModel.stop_loss_price.isnot(None))
            .order_by(PositionModel.opened_at.asc())
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._mapper.to_entity(model) for model in models]

    async def get_positions_with_take_profit(self) -> list[Position]:
        """Get all OPEN positions з встановленим take-profit.

        Returns:
            List of positions for TP monitoring.
        """
        stmt = (
            select(PositionModel)
            .where(PositionModel.status == PositionStatus.OPEN.value)
            .where(PositionModel.take_profit_price.isnot(None))
            .order_by(PositionModel.opened_at.asc())
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._mapper.to_entity(model) for model in models]

    async def get_position_by_symbol_and_user(
        self,
        user_id: int,
        symbol: str,
        status: PositionStatus = PositionStatus.OPEN,
    ) -> Optional[Position]:
        """Get position для користувача по symbol.

        Args:
            user_id: User ID.
            symbol: Trading pair.
            status: Position status (default OPEN).

        Returns:
            Position або None.
        """
        stmt = (
            select(PositionModel)
            .where(PositionModel.user_id == user_id)
            .where(PositionModel.symbol == symbol)
            .where(PositionModel.status == status.value)
            .limit(1)
        )

        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._mapper.to_entity(model)

    async def count_open_positions_for_user(self, user_id: int) -> int:
        """Count скільки відкритих позицій у користувача.

        Args:
            user_id: User ID.

        Returns:
            Number of open positions.
        """
        from sqlalchemy import func

        stmt = (
            select(func.count(PositionModel.id))
            .where(PositionModel.user_id == user_id)
            .where(PositionModel.status == PositionStatus.OPEN.value)
        )

        result = await self._session.execute(stmt)
        count = result.scalar_one()

        return count
