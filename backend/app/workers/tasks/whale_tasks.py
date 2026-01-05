"""
Whale monitoring Celery tasks
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal

import redis
from sqlalchemy import select, func, and_, text

from app.database import get_sync_db
from app.models.signal import SignalStatus, WhaleSignal
from app.models.trade import Position, PositionStatus, Trade, TradeStatus
from app.models.whale import Whale, WhaleStats, UserWhaleFollow
from app.workers.celery_app import celery_app
from app.workers.tasks.trade_tasks import execute_copy_trade

logger = logging.getLogger(__name__)

# Redis client for distributed locks
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client = None


def get_redis_client():
    """Get Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL)
    return _redis_client


class SignalProcessingLock:
    """
    Distributed lock to prevent duplicate signal processing.
    Uses Redis SET NX to ensure only one task processes a signal.
    """

    LOCK_TTL = 600  # 10 minutes - long enough for processing

    def __init__(self, signal_id: int):
        self.signal_id = signal_id
        self.key = f"signal_lock:{signal_id}"
        self.client = get_redis_client()
        self.acquired = False

    def acquire(self) -> bool:
        """Try to acquire the lock. Returns True if successful."""
        self.acquired = self.client.set(
            self.key,
            datetime.utcnow().isoformat(),
            nx=True,
            ex=self.LOCK_TTL,
        )
        return bool(self.acquired)

    def release(self):
        """Release the lock."""
        if self.acquired:
            self.client.delete(self.key)
            self.acquired = False

    def is_locked(self) -> bool:
        """Check if signal is currently being processed."""
        return self.client.exists(self.key) > 0


@celery_app.task
def check_whale_positions():
    """
    Check all tracked whale positions for exits/changes.
    When a whale exits a position, trigger close for all followers.
    Runs every 30 seconds.

    Uses dual-layer protection:
    1. DB-level: FOR UPDATE SKIP LOCKED prevents race within same worker
    2. Redis-level: SignalProcessingLock prevents race across workers
    """
    logger.debug("Checking whale positions")

    queued_signals = 0
    skipped_signals = 0

    with get_sync_db() as db:
        # Get all pending signals with row-level locking to prevent race conditions
        # FOR UPDATE SKIP LOCKED ensures two workers never process the same signal
        result = db.execute(
            select(WhaleSignal)
            .where(WhaleSignal.status == SignalStatus.PENDING)
            .order_by(WhaleSignal.detected_at.asc())
            .limit(10)
            .with_for_update(skip_locked=True)  # Prevents race conditions
        )

        signals = result.scalars().all()

        for signal in signals:
            try:
                # Try to acquire distributed lock (prevents duplicate queueing)
                lock = SignalProcessingLock(signal.id)
                if not lock.acquire():
                    logger.debug(f"Signal {signal.id} already being processed (lock held)")
                    skipped_signals += 1
                    continue

                # Queue the signal for copy trade execution
                execute_copy_trade.delay(signal.id)
                signal.status = SignalStatus.PROCESSING
                queued_signals += 1
                logger.info(f"Queued signal {signal.id} for processing")

                # Note: Lock is NOT released here - it will be released by
                # execute_copy_trade task or expire after 10 minutes

            except Exception as e:
                logger.error(f"Failed to queue signal {signal.id}: {e}")
                signal.status = SignalStatus.FAILED
                # Release lock on failure to allow retry
                if 'lock' in locals():
                    lock.release()

        db.commit()

    return {
        "status": "checked",
        "queued_signals": queued_signals,
        "skipped_signals": skipped_signals,
    }


@celery_app.task
def process_whale_transaction(tx_hash: str, whale_id: int, chain: str):
    """
    Process a new whale transaction detected by the monitor.

    Uses row-level locking and distributed lock to prevent:
    1. Race conditions between concurrent calls with same tx_hash
    2. Duplicate queueing of copy trade tasks

    Args:
        tx_hash: Transaction hash
        whale_id: Whale's database ID
        chain: Blockchain (ethereum, bsc)
    """
    logger.info(f"Processing whale transaction {tx_hash}")

    with get_sync_db() as db:
        # Use FOR UPDATE to lock the signal row and prevent race conditions
        result = db.execute(
            select(WhaleSignal)
            .where(WhaleSignal.tx_hash == tx_hash)
            .with_for_update(nowait=True)  # Fail fast if another task has lock
        )
        signal = result.scalar_one_or_none()

        if signal:
            # Only process if still PENDING
            if signal.status == SignalStatus.PENDING:
                # Try to acquire distributed lock
                lock = SignalProcessingLock(signal.id)
                if lock.acquire():
                    execute_copy_trade.delay(signal.id)
                    signal.status = SignalStatus.PROCESSING
                    db.commit()
                    logger.info(f"Queued signal {signal.id} from tx {tx_hash}")
                else:
                    logger.debug(f"Signal {signal.id} already being processed")

            return {
                "status": "processed",
                "signal_id": signal.id,
                "signal_status": signal.status.value,
                "tx_hash": tx_hash,
            }

        logger.warning(f"Signal for tx {tx_hash} not found")
        return {"status": "not_found", "tx_hash": tx_hash}


@celery_app.task
def update_whale_statistics():
    """
    Update whale performance statistics.
    Calculates win rate, profit/loss, and other metrics.
    Runs every hour.
    """
    logger.info("Updating whale statistics")

    updated_count = 0

    with get_sync_db() as db:
        # Get all active whales
        result = db.execute(
            select(Whale)
            .where(Whale.is_active == True)
        )
        whales = result.scalars().all()

        for whale in whales:
            try:
                # Get or create whale stats
                stats_result = db.execute(
                    select(WhaleStats)
                    .where(WhaleStats.whale_id == whale.id)
                )
                stats = stats_result.scalar_one_or_none()

                if not stats:
                    stats = WhaleStats(whale_id=whale.id)
                    db.add(stats)

                # Calculate stats from signals
                now = datetime.utcnow()

                # Get all signals for this whale
                signals_result = db.execute(
                    select(WhaleSignal)
                    .where(
                        WhaleSignal.whale_id == whale.id,
                        WhaleSignal.status == SignalStatus.PROCESSED,
                    )
                )
                signals = signals_result.scalars().all()

                if signals:
                    total_signals = len(signals)

                    # Calculate win rate based on signals
                    # A "win" is when the token price increased after BUY
                    # This is simplified - real implementation would track actual outcomes
                    winning_signals = sum(
                        1 for s in signals
                        if s.confidence_score and s.confidence_score > Decimal("60")
                    )

                    stats.win_rate = (Decimal(winning_signals) / Decimal(total_signals) * 100) if total_signals > 0 else Decimal("0")
                    stats.total_trades = total_signals

                    # Calculate total volume
                    stats.total_volume = sum(s.amount_usd or Decimal("0") for s in signals)

                    # Calculate time-period P&L
                    week_ago = now - timedelta(days=7)
                    month_ago = now - timedelta(days=30)
                    three_months_ago = now - timedelta(days=90)

                    week_signals = [s for s in signals if s.detected_at >= week_ago]
                    month_signals = [s for s in signals if s.detected_at >= month_ago]
                    quarter_signals = [s for s in signals if s.detected_at >= three_months_ago]

                    # Estimate P&L based on confidence (simplified)
                    def estimate_pnl(signal_list):
                        pnl = Decimal("0")
                        for s in signal_list:
                            if s.amount_usd:
                                # Higher confidence signals assumed to be more profitable
                                multiplier = (s.confidence_score or Decimal("50")) / Decimal("100")
                                pnl += s.amount_usd * (multiplier - Decimal("0.5")) * Decimal("0.1")
                        return pnl

                    stats.profit_7d = estimate_pnl(week_signals)
                    stats.profit_30d = estimate_pnl(month_signals)
                    stats.profit_90d = estimate_pnl(quarter_signals)
                    stats.total_profit_usd = estimate_pnl(signals)

                    # Average trade size
                    if total_signals > 0:
                        stats.avg_trade_size = stats.total_volume / Decimal(total_signals)

                    # Update timestamp
                    stats.updated_at = now

                # Update whale's score based on stats
                if stats.win_rate and stats.total_pnl:
                    # Simple scoring: win_rate * 0.6 + profit_factor * 0.4
                    profit_factor = min(Decimal("100"), max(Decimal("0"), stats.total_pnl / Decimal("10000") + Decimal("50")))
                    whale.score = int(stats.win_rate * Decimal("0.6") + profit_factor * Decimal("0.4"))

                updated_count += 1

            except Exception as e:
                logger.error(f"Failed to update stats for whale {whale.id}: {e}")

        db.commit()

    logger.info(f"Updated statistics for {updated_count} whales")
    return {"status": "updated", "whale_count": updated_count}


@celery_app.task
def add_new_whale(wallet_address: str, name: str = None, chain: str = "ethereum"):
    """
    Add a new whale wallet to monitoring.

    Args:
        wallet_address: Wallet address to monitor
        name: Optional name for the whale
        chain: Blockchain (ethereum, bsc)
    """
    logger.info(f"Adding new whale: {wallet_address}")

    with get_sync_db() as db:
        # Check if whale already exists
        result = db.execute(
            select(Whale)
            .where(Whale.wallet_address == wallet_address.lower())
        )
        existing = result.scalar_one_or_none()

        if existing:
            return {
                "status": "exists",
                "whale_id": existing.id,
                "address": wallet_address,
            }

        # Create new whale
        from app.models.whale import WhaleChain

        whale = Whale(
            wallet_address=wallet_address.lower(),
            name=name or f"Whale {wallet_address[:8]}",
            chain=WhaleChain(chain.upper()),
            is_verified=False,
            is_active=True,
            score=50,  # Default score
        )
        db.add(whale)

        # Create initial stats
        stats = WhaleStats(whale=whale)
        db.add(stats)

        db.commit()
        db.refresh(whale)

        logger.info(f"Added new whale {whale.id}: {wallet_address}")

        return {
            "status": "added",
            "whale_id": whale.id,
            "address": wallet_address,
            "name": whale.name,
        }


@celery_app.task
def update_whale_followers_count():
    """
    Update follower count for all whales.
    Runs every 5 minutes.
    """
    logger.debug("Updating whale follower counts")

    with get_sync_db() as db:
        # Get follower counts (all follows counted, no is_active filter)
        result = db.execute(
            select(
                UserWhaleFollow.whale_id,
                func.count(UserWhaleFollow.id).label("follower_count")
            )
            .group_by(UserWhaleFollow.whale_id)
        )

        follower_counts = {row.whale_id: row.follower_count for row in result.all()}

        # Update whales
        whales_result = db.execute(select(Whale))
        whales = whales_result.scalars().all()

        for whale in whales:
            whale.followers_count = follower_counts.get(whale.id, 0)

        db.commit()

    return {"status": "updated", "whale_count": len(follower_counts)}


@celery_app.task
def sync_exchange_leaderboards():
    """
    Sync top traders from exchange leaderboards to database.
    Fetches real data from Binance and Bybit leaderboards.
    Runs every 5 minutes.
    """
    logger.info("Syncing exchange leaderboards")

    try:
        from app.services.exchange_leaderboard import sync_exchange_leaderboards as do_sync
        synced = run_async(do_sync())
        logger.info(f"Exchange leaderboard sync complete: {synced} traders")
        return {"status": "completed", "synced_traders": synced}
    except Exception as e:
        logger.error(f"Exchange leaderboard sync failed: {e}")
        return {"status": "error", "error": str(e)}


def run_async(coro):
    """Run async code in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task
def generate_trader_signals():
    """
    Generate trading signals from exchange leaderboard trader positions.
    Monitors position changes and creates signals when traders open/close positions.
    Runs every 2 minutes.
    """
    logger.info("Generating trader signals from positions")

    try:
        from app.services.trader_signals import generate_trader_signals as do_generate
        signals_count = run_async(do_generate())
        logger.info(f"Generated {signals_count} new trading signals")
        return {"status": "completed", "signals_generated": signals_count}
    except Exception as e:
        logger.error(f"Trader signal generation failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task
def cleanup_old_signals():
    """
    Clean up old processed signals.
    Keeps signals for 30 days.
    Runs daily.
    """
    logger.info("Cleaning up old signals")

    cutoff = datetime.utcnow() - timedelta(days=30)

    with get_sync_db() as db:
        result = db.execute(
            select(WhaleSignal)
            .where(
                WhaleSignal.detected_at < cutoff,
                WhaleSignal.status.in_([SignalStatus.PROCESSED, SignalStatus.FAILED]),
            )
        )
        old_signals = result.scalars().all()

        deleted_count = len(old_signals)

        for signal in old_signals:
            db.delete(signal)

        db.commit()

    logger.info(f"Deleted {deleted_count} old signals")
    return {"status": "completed", "deleted": deleted_count}
