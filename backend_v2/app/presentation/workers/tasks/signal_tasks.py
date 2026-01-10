"""Signal Processing Celery Tasks.

Celery tasks для background processing trading signals.
Ці tasks є тонкою оберткою навколо application layer handlers.

Architecture:
    Celery Task → ProcessSignalHandler → SignalQueue → Repository
                                      → ExecuteCopyTradeHandler

Usage in Celery Beat:
    beat_schedule = {
        'process-signals': {
            'task': 'app.presentation.workers.tasks.signal_tasks.process_signals_batch',
            'schedule': 5.0,  # Every 5 seconds
        },
        'cleanup-signals': {
            'task': 'app.presentation.workers.tasks.signal_tasks.cleanup_expired_signals',
            'schedule': crontab(minute='*/5'),  # Every 5 minutes
        },
    }
"""

import asyncio
import logging
import os
from functools import wraps
from typing import Any

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.signals import ProcessSignalCommand, ProcessSignalHandler
from app.application.trading.handlers import ExecuteCopyTradeHandler
from app.domain.signals.services import SignalQueue
from app.domain.signals.value_objects import SignalPriority
from app.infrastructure.exchanges.factories import ExchangeFactory
from app.infrastructure.messaging import EventBus
from app.infrastructure.persistence.sqlalchemy.unit_of_work import SQLAlchemyUnitOfWork

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/tg_bot_trading"
)

# Engine and session factory (created once per worker)
_engine = None
_session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create async session factory (singleton per worker)."""
    global _engine, _session_factory

    if _session_factory is None:
        _engine = create_async_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _session_factory


def async_task(f):
    """Decorator to run async function in Celery task."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
@async_task
async def process_next_signal(
    self,
    min_priority: str = "low",
) -> dict[str, Any]:
    """Process next signal from queue.

    Args:
        min_priority: Minimum priority to process ("high", "medium", "low").

    Returns:
        Dict with processing result.

    Example:
        >>> process_next_signal.delay()  # Process any priority
        >>> process_next_signal.delay(min_priority="high")  # Only high priority
    """
    session_factory = get_session_factory()
    uow = SQLAlchemyUnitOfWork(session_factory)

    try:
        async with uow:
            # Create dependencies
            signal_queue = SignalQueue(uow.signals)
            exchange_factory = ExchangeFactory()
            event_bus = EventBus()

            # Create ExecuteCopyTradeHandler
            trade_handler = ExecuteCopyTradeHandler(
                uow=uow,
                exchange_factory=exchange_factory,
                event_bus=event_bus,
            )

            # Create ProcessSignalHandler
            handler = ProcessSignalHandler(
                uow=uow,
                signal_queue=signal_queue,
                whale_follow_repo=uow.whale_follows,
                trade_handler=trade_handler,
                event_bus=event_bus,
            )

            # Parse priority
            priority_map = {
                "high": SignalPriority.HIGH,
                "medium": SignalPriority.MEDIUM,
                "low": SignalPriority.LOW,
            }
            priority = priority_map.get(min_priority.lower(), SignalPriority.LOW)

            # Execute
            command = ProcessSignalCommand(min_priority=priority)
            result = await handler.handle(command)

            await uow.commit()

            if result is None:
                logger.debug("process_next_signal: No signals in queue")
                return {"status": "idle", "message": "No signals in queue"}

            logger.info(
                "process_next_signal: Completed",
                extra={
                    "signal_id": result.signal_id,
                    "successful_trades": result.successful_trades,
                    "failed_trades": result.failed_trades,
                    "total_volume": str(result.total_volume_usdt),
                },
            )

            return {
                "status": "processed",
                "signal_id": result.signal_id,
                "successful_trades": result.successful_trades,
                "failed_trades": result.failed_trades,
                "total_volume_usdt": str(result.total_volume_usdt),
                "errors": result.errors[:5] if result.errors else [],  # First 5 errors
            }

    except Exception as e:
        logger.error(
            "process_next_signal: Error",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise


@shared_task(bind=True, max_retries=0)
@async_task
async def process_signals_batch(
    self,
    max_signals: int = 10,
    min_priority: str = "low",
) -> dict[str, Any]:
    """Process batch of signals from queue.

    Processes up to max_signals or until queue is empty.
    Useful for Celery Beat periodic scheduling.

    Args:
        max_signals: Maximum signals to process in one batch.
        min_priority: Minimum priority to process.

    Returns:
        Dict with batch processing summary.

    Example (Celery Beat):
        beat_schedule = {
            'process-signals-every-5s': {
                'task': 'process_signals_batch',
                'schedule': 5.0,
                'kwargs': {'max_signals': 10, 'min_priority': 'low'},
            },
        }
    """
    session_factory = get_session_factory()

    processed = 0
    successful = 0
    failed = 0
    errors = []

    for _ in range(max_signals):
        try:
            uow = SQLAlchemyUnitOfWork(session_factory)

            async with uow:
                # Create dependencies
                signal_queue = SignalQueue(uow.signals)
                exchange_factory = ExchangeFactory()
                event_bus = EventBus()

                trade_handler = ExecuteCopyTradeHandler(
                    uow=uow,
                    exchange_factory=exchange_factory,
                    event_bus=event_bus,
                )

                handler = ProcessSignalHandler(
                    uow=uow,
                    signal_queue=signal_queue,
                    whale_follow_repo=uow.whale_follows,
                    trade_handler=trade_handler,
                    event_bus=event_bus,
                )

                priority_map = {
                    "high": SignalPriority.HIGH,
                    "medium": SignalPriority.MEDIUM,
                    "low": SignalPriority.LOW,
                }
                priority = priority_map.get(min_priority.lower(), SignalPriority.LOW)

                command = ProcessSignalCommand(min_priority=priority)
                result = await handler.handle(command)

                await uow.commit()

                if result is None:
                    # Queue empty
                    break

                processed += 1
                successful += result.successful_trades
                failed += result.failed_trades

                if result.errors:
                    errors.extend(result.errors[:3])  # First 3 errors per signal

        except Exception as e:
            logger.error(
                "process_signals_batch: Signal processing failed",
                extra={"error": str(e)},
            )
            errors.append(str(e))
            # Continue with next signal

    logger.info(
        "process_signals_batch: Completed",
        extra={
            "processed": processed,
            "successful_trades": successful,
            "failed_trades": failed,
        },
    )

    return {
        "status": "completed",
        "signals_processed": processed,
        "successful_trades": successful,
        "failed_trades": failed,
        "errors": errors[:10],  # First 10 errors
    }


@shared_task(bind=True, max_retries=0)
@async_task
async def cleanup_expired_signals(
    self,
    expiry_seconds: int = 60,
) -> dict[str, Any]:
    """Cleanup expired signals from queue.

    Marks PENDING signals older than expiry_seconds as EXPIRED.
    Run periodically (every 5 minutes) via Celery Beat.

    Args:
        expiry_seconds: Signals older than this are expired.

    Returns:
        Dict with cleanup summary.

    Example (Celery Beat):
        beat_schedule = {
            'cleanup-expired-signals': {
                'task': 'cleanup_expired_signals',
                'schedule': crontab(minute='*/5'),
            },
        }
    """
    session_factory = get_session_factory()
    uow = SQLAlchemyUnitOfWork(session_factory)

    try:
        async with uow:
            signal_queue = SignalQueue(uow.signals)

            expired_count = await signal_queue.cleanup_expired(
                expiry_seconds=expiry_seconds
            )

            await uow.commit()

            if expired_count > 0:
                logger.warning(
                    "cleanup_expired_signals: Cleaned up expired signals",
                    extra={"expired_count": expired_count},
                )
            else:
                logger.debug("cleanup_expired_signals: No expired signals")

            return {
                "status": "completed",
                "expired_count": expired_count,
            }

    except Exception as e:
        logger.error(
            "cleanup_expired_signals: Error",
            extra={"error": str(e)},
            exc_info=True,
        )
        return {
            "status": "error",
            "error": str(e),
        }


@shared_task(bind=True, max_retries=0)
@async_task
async def get_queue_status(self) -> dict[str, Any]:
    """Get current signal queue status.

    Returns:
        Dict with queue status (counts by priority).

    Example:
        >>> status = get_queue_status.delay().get()
        >>> print(f"High priority: {status['high_priority']}")
    """
    session_factory = get_session_factory()
    uow = SQLAlchemyUnitOfWork(session_factory)

    try:
        async with uow:
            signal_queue = SignalQueue(uow.signals)

            high_count = await signal_queue.get_queue_size(
                priority=SignalPriority.HIGH
            )
            medium_count = await signal_queue.get_queue_size(
                priority=SignalPriority.MEDIUM
            )
            low_count = await signal_queue.get_queue_size(
                priority=SignalPriority.LOW
            )

            return {
                "status": "ok",
                "high_priority": high_count,
                "medium_priority": medium_count,
                "low_priority": low_count,
                "total": high_count + medium_count + low_count,
            }

    except Exception as e:
        logger.error(
            "get_queue_status: Error",
            extra={"error": str(e)},
        )
        return {
            "status": "error",
            "error": str(e),
        }
