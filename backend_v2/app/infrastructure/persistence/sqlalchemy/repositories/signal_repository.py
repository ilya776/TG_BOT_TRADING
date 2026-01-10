"""SQLAlchemySignalRepository - implements SignalRepository port.

Infrastructure implementation of domain SignalRepository interface.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.signals.entities import Signal
from app.domain.signals.repositories import SignalRepository
from app.domain.signals.value_objects import SignalPriority, SignalStatus
from app.infrastructure.persistence.sqlalchemy.mappers.signal_mapper import (
    SignalMapper,
)
from app.infrastructure.persistence.sqlalchemy.models.signal_model import SignalModel


class SQLAlchemySignalRepository(SignalRepository):
    """SQLAlchemy implementation of SignalRepository.

    Example:
        >>> async with async_session() as session:
        ...     repo = SQLAlchemySignalRepository(session)
        ...     signal = Signal.create_whale_signal(...)
        ...     await repo.save(signal)
        ...     await session.commit()
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session
        self._mapper = SignalMapper()

    async def save(self, signal: Signal) -> None:
        """Save або update signal.

        Args:
            signal: Signal entity to save.
        """
        if signal.id is None:
            # INSERT - новий signal
            model = self._mapper.to_model(signal)
            self._session.add(model)
            await self._session.flush()  # Get ID
            signal._id = model.id  # Set ID back to entity
        else:
            # UPDATE - існуючий signal
            model = await self._session.get(SignalModel, signal.id)
            if model is None:
                raise ValueError(f"Signal {signal.id} not found")
            self._mapper.update_model(signal, model)

    async def get_by_id(self, signal_id: int) -> Signal | None:
        """Get signal by ID.

        Args:
            signal_id: Signal ID.

        Returns:
            Signal entity або None.
        """
        model = await self._session.get(SignalModel, signal_id)
        if model is None:
            return None
        return self._mapper.to_entity(model)

    async def get_pending_signals(
        self, limit: int = 100, min_priority: SignalPriority = SignalPriority.LOW
    ) -> list[Signal]:
        """Get PENDING signals sorted by priority.

        Args:
            limit: Maximum number of signals.
            min_priority: Minimum priority filter.

        Returns:
            List of PENDING signals, sorted by priority (HIGH > MEDIUM > LOW) + detected_at.
        """
        # Priority mapping для sorting (lower = higher priority)
        priority_order = {
            SignalPriority.HIGH: 1,
            SignalPriority.MEDIUM: 2,
            SignalPriority.LOW: 3,
        }

        # Build priority filter
        if min_priority == SignalPriority.HIGH:
            priority_filter = SignalModel.priority == "high"
        elif min_priority == SignalPriority.MEDIUM:
            priority_filter = or_(
                SignalModel.priority == "high",
                SignalModel.priority == "medium",
            )
        else:  # LOW = all priorities
            priority_filter = True

        # Query
        stmt = (
            select(SignalModel)
            .where(
                and_(
                    SignalModel.status == "pending",
                    priority_filter,
                )
            )
            .order_by(
                # Sort by priority (HIGH first)
                SignalModel.priority.asc(),
                # Then by detected_at (older first)
                SignalModel.detected_at.asc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._mapper.to_entity(model) for model in models]

    async def get_processing_signals(self) -> list[Signal]:
        """Get all PROCESSING signals.

        Returns:
            List of signals currently being processed.
        """
        stmt = select(SignalModel).where(SignalModel.status == "processing")
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._mapper.to_entity(model) for model in models]

    async def get_expired_pending_signals(
        self, expiry_seconds: int = 60
    ) -> list[Signal]:
        """Get PENDING signals that are expired.

        Args:
            expiry_seconds: Age threshold in seconds.

        Returns:
            List of expired PENDING signals.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=expiry_seconds)

        stmt = (
            select(SignalModel)
            .where(
                and_(
                    SignalModel.status == "pending",
                    SignalModel.detected_at < cutoff_time,
                )
            )
            .order_by(SignalModel.detected_at.asc())
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._mapper.to_entity(model) for model in models]

    async def get_signals_by_whale(
        self, whale_id: int, limit: int = 100
    ) -> list[Signal]:
        """Get all signals від конкретного whale.

        Args:
            whale_id: Whale ID.
            limit: Maximum number of signals.

        Returns:
            List of signals from this whale (newest first).
        """
        stmt = (
            select(SignalModel)
            .where(SignalModel.whale_id == whale_id)
            .order_by(desc(SignalModel.detected_at))
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._mapper.to_entity(model) for model in models]

    async def count_processed_today(self) -> int:
        """Count скільки signals було processed сьогодні.

        Returns:
            Number of PROCESSED signals today.
        """
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        stmt = select(SignalModel).where(
            and_(
                SignalModel.status == "processed",
                SignalModel.processed_at >= today_start,
            )
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return len(models)

    async def get_by_status(
        self, status: SignalStatus, limit: int = 100
    ) -> list[Signal]:
        """Get signals by status.

        Args:
            status: Signal status to filter by.
            limit: Maximum number of signals.

        Returns:
            List of signals with given status.
        """
        stmt = (
            select(SignalModel)
            .where(SignalModel.status == status.value)
            .order_by(desc(SignalModel.detected_at))
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._mapper.to_entity(model) for model in models]
