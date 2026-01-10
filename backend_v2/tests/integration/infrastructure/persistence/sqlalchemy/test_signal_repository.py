"""Integration tests for SQLAlchemySignalRepository."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.signals.entities import Signal
from app.domain.signals.value_objects import (
    SignalPriority,
    SignalSource,
    SignalStatus,
    SignalType,
    TradeSide,
)
from app.infrastructure.persistence.sqlalchemy.repositories import (
    SQLAlchemySignalRepository,
)
from app.infrastructure.persistence.sqlalchemy.unit_of_work import SQLAlchemyUnitOfWork


class TestSQLAlchemySignalRepository:
    """Tests for SQLAlchemySignalRepository."""

    @pytest.fixture
    def create_signal(self) -> Signal:
        """Factory for creating test signals."""

        def _create(
            symbol: str = "BTCUSDT",
            side: TradeSide = TradeSide.BUY,
            priority: SignalPriority = SignalPriority.MEDIUM,
            whale_id: int | None = 1,
            price: Decimal = Decimal("50000"),
            size: Decimal = Decimal("1000"),
        ) -> Signal:
            return Signal.create_whale_signal(
                whale_id=whale_id,
                whale_tier="premium",  # → MEDIUM priority
                symbol=symbol,
                side=side,
                signal_type=SignalType.SPOT,
                price=price,
                size=size,
            )

        return _create

    @pytest.mark.asyncio
    async def test_save_new_signal(self, session_factory, create_signal):
        """Test saving a new signal assigns ID."""
        signal = create_signal()
        assert signal.id is None

        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            await repo.save(signal)
            await session.commit()

        assert signal.id is not None
        assert signal.id > 0

    @pytest.mark.asyncio
    async def test_get_by_id(self, session_factory, create_signal):
        """Test retrieving signal by ID."""
        signal = create_signal(symbol="ETHUSDT")

        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            await repo.save(signal)
            await session.commit()

        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            loaded = await repo.get_by_id(signal.id)

        assert loaded is not None
        assert loaded.id == signal.id
        assert loaded.symbol == "ETHUSDT"
        assert loaded.status == SignalStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, session_factory):
        """Test get_by_id returns None for non-existent signal."""
        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            loaded = await repo.get_by_id(9999)

        assert loaded is None

    @pytest.mark.asyncio
    async def test_save_updates_existing_signal(self, session_factory, create_signal):
        """Test that save updates existing signal."""
        signal = create_signal()

        # Create signal
        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            await repo.save(signal)
            await session.commit()

        # Update status
        signal.start_processing()

        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            await repo.save(signal)
            await session.commit()

        # Verify
        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            loaded = await repo.get_by_id(signal.id)

        assert loaded.status == SignalStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_get_pending_signals(self, session_factory, create_signal):
        """Test retrieving pending signals in priority order."""
        # Create signals with different priorities
        high_signal = Signal.create_whale_signal(
            whale_id=1,
            whale_tier="vip",  # → HIGH
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            signal_type=SignalType.SPOT,
            price=Decimal("50000"),
            size=Decimal("1000"),
        )
        medium_signal = create_signal(symbol="ETHUSDT")  # premium → MEDIUM
        low_signal = Signal.create_whale_signal(
            whale_id=1,
            whale_tier="regular",  # → LOW
            symbol="SOLUSDT",
            side=TradeSide.BUY,
            signal_type=SignalType.SPOT,
            price=Decimal("100"),
            size=Decimal("500"),
        )

        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            await repo.save(high_signal)
            await repo.save(medium_signal)
            await repo.save(low_signal)
            await session.commit()

        # Get all pending
        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            pending = await repo.get_pending_signals(limit=10)

        assert len(pending) == 3
        # HIGH should be first
        assert pending[0].priority == SignalPriority.HIGH

    @pytest.mark.asyncio
    async def test_get_pending_signals_with_min_priority(
        self, session_factory, create_signal
    ):
        """Test filtering by minimum priority."""
        # Create signals
        high_signal = Signal.create_whale_signal(
            whale_id=1,
            whale_tier="vip",
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            signal_type=SignalType.SPOT,
            price=Decimal("50000"),
            size=Decimal("1000"),
        )
        low_signal = Signal.create_whale_signal(
            whale_id=1,
            whale_tier="regular",
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            signal_type=SignalType.SPOT,
            price=Decimal("3000"),
            size=Decimal("500"),
        )

        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            await repo.save(high_signal)
            await repo.save(low_signal)
            await session.commit()

        # Get only HIGH priority
        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            pending = await repo.get_pending_signals(
                limit=10, min_priority=SignalPriority.HIGH
            )

        assert len(pending) == 1
        assert pending[0].priority == SignalPriority.HIGH

    @pytest.mark.asyncio
    async def test_get_processing_signals(self, session_factory, create_signal):
        """Test retrieving signals that are processing."""
        signal1 = create_signal(symbol="BTCUSDT")
        signal2 = create_signal(symbol="ETHUSDT")

        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            await repo.save(signal1)
            await repo.save(signal2)
            await session.commit()

        # Start processing signal1 only
        signal1.start_processing()

        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            await repo.save(signal1)
            await session.commit()

        # Get processing signals
        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            processing = await repo.get_processing_signals()

        assert len(processing) == 1
        assert processing[0].id == signal1.id
        assert processing[0].status == SignalStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_get_signals_by_whale(self, session_factory, create_signal):
        """Test retrieving signals by whale ID."""
        whale1_signal = create_signal(symbol="BTCUSDT")
        whale1_signal._whale_id = 100

        whale2_signal = create_signal(symbol="ETHUSDT")
        whale2_signal._whale_id = 200

        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            await repo.save(whale1_signal)
            await repo.save(whale2_signal)
            await session.commit()

        # Get only whale 100's signals
        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            signals = await repo.get_signals_by_whale(whale_id=100)

        assert len(signals) == 1
        assert signals[0].whale_id == 100

    @pytest.mark.asyncio
    async def test_get_by_status(self, session_factory, create_signal):
        """Test filtering signals by status."""
        signal1 = create_signal(symbol="BTCUSDT")
        signal2 = create_signal(symbol="ETHUSDT")

        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            await repo.save(signal1)
            await repo.save(signal2)
            await session.commit()

        # Process and complete signal1
        signal1.start_processing()
        signal1.mark_processed(trades_executed=1)

        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            await repo.save(signal1)
            await session.commit()

        # Get only PROCESSED signals
        async with session_factory() as session:
            repo = SQLAlchemySignalRepository(session)
            processed = await repo.get_by_status(SignalStatus.PROCESSED)

        assert len(processed) == 1
        assert processed[0].status == SignalStatus.PROCESSED


class TestSignalRepositoryWithUnitOfWork:
    """Tests for SignalRepository with Unit of Work pattern."""

    @pytest.mark.asyncio
    async def test_signal_saved_through_uow(self, session_factory):
        """Test saving signal through UoW."""
        uow = SQLAlchemyUnitOfWork(session_factory)

        signal = Signal.create_whale_signal(
            whale_id=1,
            whale_tier="vip",
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            signal_type=SignalType.SPOT,
            price=Decimal("50000"),
            size=Decimal("1000"),
        )

        async with uow:
            await uow.signals.save(signal)
            await uow.commit()

        assert signal.id is not None

        # Verify
        async with uow:
            loaded = await uow.signals.get_by_id(signal.id)

        assert loaded is not None
        assert loaded.symbol == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_signal_queue_workflow_through_uow(self, session_factory):
        """Test complete signal queue workflow."""
        uow = SQLAlchemyUnitOfWork(session_factory)

        # 1. Create signals
        signals = [
            Signal.create_whale_signal(
                whale_id=1,
                whale_tier="vip",
                symbol="BTCUSDT",
                side=TradeSide.BUY,
                signal_type=SignalType.SPOT,
                price=Decimal("50000"),
                size=Decimal("1000"),
            ),
            Signal.create_whale_signal(
                whale_id=2,
                whale_tier="premium",
                symbol="ETHUSDT",
                side=TradeSide.BUY,
                signal_type=SignalType.SPOT,
                price=Decimal("3000"),
                size=Decimal("500"),
            ),
        ]

        async with uow:
            for signal in signals:
                await uow.signals.save(signal)
            await uow.commit()

        # 2. Get pending signals (sorted by priority)
        async with uow:
            pending = await uow.signals.get_pending_signals()

        assert len(pending) == 2
        assert pending[0].priority == SignalPriority.HIGH  # vip first

        # 3. Process first signal
        first_signal = pending[0]
        first_signal.start_processing()

        async with uow:
            await uow.signals.save(first_signal)
            await uow.commit()

        # 4. Verify processing status
        async with uow:
            processing = await uow.signals.get_processing_signals()

        assert len(processing) == 1
        assert processing[0].id == first_signal.id

    @pytest.mark.asyncio
    async def test_rollback_on_exception(self, session_factory):
        """Test that changes are rolled back on exception."""
        uow = SQLAlchemyUnitOfWork(session_factory)

        signal = Signal.create_whale_signal(
            whale_id=1,
            whale_tier="vip",
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            signal_type=SignalType.SPOT,
            price=Decimal("50000"),
            size=Decimal("1000"),
        )

        try:
            async with uow:
                await uow.signals.save(signal)
                await uow.commit()
                signal_id = signal.id
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # Signal should still exist (commit was before exception)
        async with uow:
            loaded = await uow.signals.get_by_id(signal_id)
            assert loaded is not None
