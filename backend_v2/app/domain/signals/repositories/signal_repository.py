"""SignalRepository Port - interface для persistence signal entities.

Це PORT в Hexagonal Architecture (domain визначає interface).
Infrastructure layer має implement цей interface.
"""

from abc import ABC, abstractmethod
from typing import Optional

from ..entities import Signal
from ..value_objects import SignalPriority, SignalStatus


class SignalRepository(ABC):
    """Abstract interface для signal persistence.

    Infrastructure layer implements цей interface з SQLAlchemy або Redis.
    Domain layer uses цей interface (Dependency Inversion).

    Example (Infrastructure implements):
        >>> class SQLAlchemySignalRepository(SignalRepository):
        ...     async def save(self, signal: Signal) -> None:
        ...         signal_model = self.mapper.to_model(signal)
        ...         self.session.add(signal_model)
        ...
        ...     async def get_by_id(self, signal_id: int) -> Signal | None:
        ...         model = await self.session.get(SignalModel, signal_id)
        ...         return self.mapper.to_entity(model)

    Example (Domain uses):
        >>> # Use case не знає про SQLAlchemy
        >>> signal = await signal_repo.get_by_id(123)
        >>> signal.start_processing()
        >>> await signal_repo.save(signal)
    """

    @abstractmethod
    async def save(self, signal: Signal) -> None:
        """Save або update signal.

        Args:
            signal: Signal entity to save.

        Note:
            Якщо signal.id is None, це INSERT.
            Якщо signal.id exists, це UPDATE.
        """
        pass

    @abstractmethod
    async def get_by_id(self, signal_id: int) -> Optional[Signal]:
        """Get signal by ID.

        Args:
            signal_id: Signal ID.

        Returns:
            Signal entity або None якщо не знайдено.
        """
        pass

    @abstractmethod
    async def get_pending_signals(
        self, limit: int = 100, min_priority: SignalPriority = SignalPriority.LOW
    ) -> list[Signal]:
        """Get PENDING signals sorted by priority.

        Args:
            limit: Maximum number of signals to return.
            min_priority: Minimum priority (HIGH, MEDIUM, or LOW).

        Returns:
            List of PENDING signals, sorted by:
            1. Priority (HIGH > MEDIUM > LOW)
            2. Detected time (older first)

        Note:
            Використовується SignalQueue для picking next signals to process.
        """
        pass

    @abstractmethod
    async def get_processing_signals(self) -> list[Signal]:
        """Get all PROCESSING signals.

        Returns:
            List of signals currently being processed.

        Note:
            Використовується для моніторингу та timeout detection.
        """
        pass

    @abstractmethod
    async def get_expired_pending_signals(
        self, expiry_seconds: int = 60
    ) -> list[Signal]:
        """Get PENDING signals that are expired.

        Args:
            expiry_seconds: Age threshold in seconds.

        Returns:
            List of expired PENDING signals (older than threshold).

        Note:
            Використовується cleanup worker для marking expired signals.
        """
        pass

    @abstractmethod
    async def get_signals_by_whale(
        self, whale_id: int, limit: int = 100
    ) -> list[Signal]:
        """Get all signals від конкретного whale.

        Args:
            whale_id: Whale ID.
            limit: Maximum number of signals.

        Returns:
            List of signals from this whale (newest first).

        Note:
            Використовується для whale analytics (signal frequency, success rate).
        """
        pass

    @abstractmethod
    async def count_processed_today(self) -> int:
        """Count скільки signals було processed сьогодні.

        Returns:
            Number of PROCESSED signals today.

        Note:
            Використовується для daily metrics.
        """
        pass

    @abstractmethod
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
        pass
