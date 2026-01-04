"""
Whale monitoring Celery tasks
"""
import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, func, and_

from app.database import get_sync_db
from app.models.signal import SignalStatus, WhaleSignal
from app.models.trade import Position, PositionStatus, Trade, TradeStatus
from app.models.whale import Whale, WhaleStats, UserWhaleFollow
from app.workers.celery_app import celery_app
from app.workers.tasks.trade_tasks import execute_copy_trade

logger = logging.getLogger(__name__)


@celery_app.task
def check_whale_positions():
    """
    Check all tracked whale positions for exits/changes.
    When a whale exits a position, trigger close for all followers.
    Runs every 30 seconds.
    """
    logger.debug("Checking whale positions")

    # This task monitors on-chain whale positions
    # When a whale sells/exits, it triggers followers to exit too

    closed_signals = 0

    with get_sync_db() as db:
        # Get all pending signals that haven't been processed yet
        result = db.execute(
            select(WhaleSignal)
            .where(WhaleSignal.status == SignalStatus.PENDING)
            .order_by(WhaleSignal.created_at.asc())
            .limit(10)  # Process in batches
        )

        signals = result.scalars().all()

        for signal in signals:
            try:
                # Queue the signal for copy trade execution
                execute_copy_trade.delay(signal.id)
                signal.status = SignalStatus.PROCESSING
                closed_signals += 1
                logger.info(f"Queued signal {signal.id} for processing")

            except Exception as e:
                logger.error(f"Failed to queue signal {signal.id}: {e}")
                signal.status = SignalStatus.FAILED

        db.commit()

    return {"status": "checked", "queued_signals": closed_signals}


@celery_app.task
def process_whale_transaction(tx_hash: str, whale_id: int, chain: str):
    """
    Process a new whale transaction detected by the monitor.

    Args:
        tx_hash: Transaction hash
        whale_id: Whale's database ID
        chain: Blockchain (ethereum, bsc)
    """
    logger.info(f"Processing whale transaction {tx_hash}")

    # This is called by the whale monitor when it detects a new transaction
    # The whale monitor has already parsed the transaction and created a signal

    with get_sync_db() as db:
        # Check if signal already exists
        result = db.execute(
            select(WhaleSignal)
            .where(WhaleSignal.tx_hash == tx_hash)
        )
        signal = result.scalar_one_or_none()

        if signal:
            # Queue for copy trade execution if pending
            if signal.status == SignalStatus.PENDING:
                execute_copy_trade.delay(signal.id)
                signal.status = SignalStatus.PROCESSING
                db.commit()

            return {
                "status": "processed",
                "signal_id": signal.id,
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

                    week_signals = [s for s in signals if s.created_at >= week_ago]
                    month_signals = [s for s in signals if s.created_at >= month_ago]
                    quarter_signals = [s for s in signals if s.created_at >= three_months_ago]

                    # Estimate P&L based on confidence (simplified)
                    def estimate_pnl(signal_list):
                        pnl = Decimal("0")
                        for s in signal_list:
                            if s.amount_usd:
                                # Higher confidence signals assumed to be more profitable
                                multiplier = (s.confidence_score or Decimal("50")) / Decimal("100")
                                pnl += s.amount_usd * (multiplier - Decimal("0.5")) * Decimal("0.1")
                        return pnl

                    stats.pnl_7d = estimate_pnl(week_signals)
                    stats.pnl_30d = estimate_pnl(month_signals)
                    stats.pnl_90d = estimate_pnl(quarter_signals)
                    stats.total_pnl = estimate_pnl(signals)

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
        # Get follower counts
        result = db.execute(
            select(
                UserWhaleFollow.whale_id,
                func.count(UserWhaleFollow.id).label("follower_count")
            )
            .where(UserWhaleFollow.is_active == True)
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
                WhaleSignal.created_at < cutoff,
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
