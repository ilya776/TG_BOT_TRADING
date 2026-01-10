"""SignalQueue - Domain Service для managing signal processing queue.

SignalQueue manages priority-based processing of trading signals.
Це Domain Service (не entity, не value object), бо координує між entities.
"""

import heapq
import logging
from typing import Optional

from ..entities import Signal
from ..repositories import SignalRepository
from ..value_objects import SignalPriority, SignalStatus

logger = logging.getLogger(__name__)


class SignalQueue:
    """Priority queue для signal processing.

    Responsibilities:
    - Pick next signal to process (based on priority)
    - Track processing signals (for timeout detection)
    - Manage signal lifecycle (PENDING → PROCESSING → PROCESSED/FAILED)

    Priority Order:
    1. HIGH priority signals first
    2. MEDIUM priority signals second
    3. LOW priority signals last
    4. Within same priority → older signals first (FIFO)

    Example:
        >>> queue = SignalQueue(signal_repo)
        >>> signal = await queue.pick_next()
        >>> await process_signal(signal)
        >>> await queue.mark_processed(signal.id, trades_executed=5)
    """

    def __init__(self, repository: SignalRepository) -> None:
        """Initialize SignalQueue.

        Args:
            repository: SignalRepository for persistence.
        """
        self._repository = repository

    async def pick_next(self, min_priority: SignalPriority = SignalPriority.LOW) -> Optional[Signal]:
        """Pick next signal from queue to process.

        Args:
            min_priority: Minimum priority to process (default LOW = all signals).

        Returns:
            Next signal to process, або None if queue empty.

        Algorithm:
            1. Get PENDING signals from repository (sorted by priority + time)
            2. Filter out expired signals
            3. Pick first non-expired signal
            4. Mark as PROCESSING
            5. Save and return

        Note:
            This is a READ-MODIFY-WRITE operation (race condition possible).
            Use optimistic locking (version field) to prevent double processing.
        """
        # Get pending signals
        pending = await self._repository.get_pending_signals(
            limit=10,  # Look at top 10 candidates
            min_priority=min_priority,
        )

        if not pending:
            return None

        # Filter expired signals (they will be cleaned up by background job)
        valid_signals = [s for s in pending if not s.is_expired()]

        if not valid_signals:
            logger.warning("signal_queue.no_valid_signals", extra={"pending": len(pending)})
            return None

        # Pick first valid signal (highest priority + oldest)
        signal = valid_signals[0]

        # Mark as PROCESSING
        try:
            signal.start_processing()
            await self._repository.save(signal)

            logger.info(
                "signal_queue.picked",
                extra={
                    "signal_id": signal.id,
                    "symbol": signal.symbol,
                    "priority": signal.priority.value,
                },
            )

            return signal

        except Exception as e:
            logger.error(
                "signal_queue.pick_failed",
                extra={"signal_id": signal.id, "error": str(e)},
            )
            return None

    async def mark_processed(self, signal_id: int, trades_executed: int) -> None:
        """Mark signal as successfully processed.

        Args:
            signal_id: Signal ID.
            trades_executed: Number of trades executed.

        Raises:
            ValueError: If signal not found or not PROCESSING.
        """
        signal = await self._repository.get_by_id(signal_id)
        if signal is None:
            raise ValueError(f"Signal {signal_id} not found")

        signal.mark_processed(trades_executed)
        await self._repository.save(signal)

        logger.info(
            "signal_queue.marked_processed",
            extra={"signal_id": signal_id, "trades_executed": trades_executed},
        )

    async def mark_failed(self, signal_id: int, error_message: str) -> None:
        """Mark signal as failed.

        Args:
            signal_id: Signal ID.
            error_message: Error message.

        Raises:
            ValueError: If signal not found.
        """
        signal = await self._repository.get_by_id(signal_id)
        if signal is None:
            raise ValueError(f"Signal {signal_id} not found")

        signal.mark_failed(error_message)
        await self._repository.save(signal)

        logger.error(
            "signal_queue.marked_failed",
            extra={"signal_id": signal_id, "error": error_message},
        )

    async def get_queue_size(self, priority: SignalPriority | None = None) -> int:
        """Get number of PENDING signals in queue.

        Args:
            priority: Filter by priority (None = all priorities).

        Returns:
            Number of PENDING signals.
        """
        if priority:
            signals = await self._repository.get_pending_signals(
                limit=1000, min_priority=priority
            )
            return len([s for s in signals if s.priority == priority])
        else:
            signals = await self._repository.get_pending_signals(limit=1000)
            return len(signals)

    async def cleanup_expired(self, expiry_seconds: int = 60) -> int:
        """Cleanup expired PENDING signals.

        Args:
            expiry_seconds: Expiry threshold in seconds.

        Returns:
            Number of expired signals cleaned up.

        Note:
            Викликається background job періодично.
        """
        expired = await self._repository.get_expired_pending_signals(expiry_seconds)

        count = 0
        for signal in expired:
            try:
                signal.mark_expired()
                await self._repository.save(signal)
                count += 1
            except Exception as e:
                logger.error(
                    "signal_queue.cleanup_failed",
                    extra={"signal_id": signal.id, "error": str(e)},
                )

        if count > 0:
            logger.info(
                "signal_queue.cleanup_completed",
                extra={"expired_count": count},
            )

        return count
