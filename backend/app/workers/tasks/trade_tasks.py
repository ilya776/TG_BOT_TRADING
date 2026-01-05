"""
Trade-related Celery tasks
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Any

import redis
from sqlalchemy import select, and_

from app.database import get_sync_db
from app.models.signal import SignalStatus, WhaleSignal
from app.models.trade import Position, PositionStatus, Trade, TradeStatus
from app.models.user import User, UserAPIKey, UserSettings
from app.models.whale import UserWhaleFollow
from app.services.exchanges import get_exchange_executor, CircuitOpenError
from app.services.copy_trade_engine import process_signal_async
from app.utils.encryption import get_encryption_manager
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Redis client for idempotency checks
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client = None


def get_redis_client():
    """Get Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL)
    return _redis_client


class IdempotencyLock:
    """
    Redis-based idempotency lock to prevent duplicate task execution.

    Two-phase protection:
    1. Processing lock (short TTL) - prevents concurrent execution
    2. Completion marker (long TTL) - prevents re-execution of completed tasks

    Usage:
        with IdempotencyLock("trade", signal_id, user_id) as lock:
            if lock.already_completed:
                return {"status": "already_completed"}
            if not lock.acquired:
                return {"status": "already_processing"}
            # ... do work ...
            lock.mark_completed()  # Call on success
    """

    PROCESSING_TTL = 300  # 5 minutes for processing lock
    COMPLETED_TTL = 86400  # 24 hours for completion marker

    def __init__(self, prefix: str, *args, ttl_seconds: int = None):
        """
        Args:
            prefix: Lock name prefix (e.g., "trade", "close_position")
            *args: Components to create unique lock key
            ttl_seconds: Processing lock TTL (default 5 minutes)
        """
        key_parts = [str(a) for a in args if a is not None]
        base_key = f"idempotency:{prefix}:{':'.join(key_parts)}"
        self.processing_key = f"{base_key}:processing"
        self.completed_key = f"{base_key}:completed"
        self.ttl = ttl_seconds or self.PROCESSING_TTL
        self.acquired = False
        self.already_completed = False
        self.client = get_redis_client()

    def __enter__(self):
        # First check if already completed (prevents re-execution)
        if self.client.exists(self.completed_key):
            self.already_completed = True
            logger.info(f"Task already completed: {self.completed_key}")
            return self

        # Try to acquire processing lock using SET NX
        self.acquired = self.client.set(
            self.processing_key,
            datetime.utcnow().isoformat(),
            nx=True,
            ex=self.ttl,
        )
        if not self.acquired:
            logger.warning(f"Task already processing: {self.processing_key}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Only release processing lock on failure (allows retry)
        # On success, mark_completed() should have been called
        if exc_type is not None and self.acquired:
            # Exception occurred - release lock for retry
            self.client.delete(self.processing_key)
            logger.info(f"Released lock due to exception: {self.processing_key}")
        return False  # Don't suppress exceptions

    def mark_completed(self, result_data: dict = None):
        """
        Mark task as successfully completed.
        Call this after successful execution to prevent re-runs.
        """
        if self.acquired:
            # Set completion marker with long TTL
            completion_data = {
                "completed_at": datetime.utcnow().isoformat(),
                "result": str(result_data)[:500] if result_data else None,
            }
            self.client.setex(
                self.completed_key,
                self.COMPLETED_TTL,
                json.dumps(completion_data),
            )
            # Remove processing lock
            self.client.delete(self.processing_key)
            logger.info(f"Task marked completed: {self.completed_key}")

    def release(self):
        """Explicitly release the lock without marking complete (for retryable failures)."""
        if self.acquired:
            self.client.delete(self.processing_key)
            self.acquired = False


def run_async(coro):
    """Run async code in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, max_retries=3)
def execute_copy_trade(
    self,
    signal_id: int,
    user_id: int | None = None,
    size_usdt: float | None = None,
    exchange: str | None = None,
):
    """
    Execute copy trades for a whale signal.

    This task uses idempotency locks to prevent duplicate execution:
    - For auto-copy (user_id=None): Lock on signal_id only
    - For manual copy: Lock on signal_id + user_id

    Args:
        signal_id: Whale signal ID to process
        user_id: Optional specific user ID (for manual copy)
        size_usdt: Optional trade size override in USDT
        exchange: Optional exchange override (BINANCE, BYBIT, OKX)
    """
    # Create idempotency lock to prevent duplicate execution
    # Lock key: "trade:signal_id:user_id" or "trade:signal_id:auto" for auto-copy
    lock_suffix = user_id if user_id else "auto"

    with IdempotencyLock("trade", signal_id, lock_suffix, ttl_seconds=300) as lock:
        # Phase 1: Check if already completed (prevents re-execution)
        if lock.already_completed:
            logger.info(
                f"Trade for signal {signal_id} (user={user_id}) already completed"
            )
            return {
                "status": "already_completed",
                "signal_id": signal_id,
                "user_id": user_id,
            }

        # Phase 2: Check if another task is processing
        if not lock.acquired:
            logger.warning(
                f"Skipping duplicate trade execution for signal {signal_id} "
                f"(user={user_id}) - already in progress"
            )
            return {
                "status": "skipped",
                "reason": "duplicate_execution",
                "signal_id": signal_id,
                "user_id": user_id,
            }

        try:
            logger.info(
                f"Processing signal {signal_id} for copy trading "
                f"(user={user_id}, size={size_usdt}, exchange={exchange})"
            )

            # Double-check signal status in database before proceeding
            with get_sync_db() as db:
                signal_result = db.execute(
                    select(WhaleSignal.status).where(WhaleSignal.id == signal_id)
                )
                signal_status = signal_result.scalar_one_or_none()

                if signal_status and signal_status == SignalStatus.PROCESSED:
                    logger.info(f"Signal {signal_id} already processed, skipping")
                    # Mark as completed to prevent future retries
                    lock.mark_completed({"reason": "already_processed_in_db"})
                    return {
                        "status": "skipped",
                        "reason": "already_processed",
                        "signal_id": signal_id,
                    }

            # Run the async copy trade engine with optional overrides
            results = run_async(
                process_signal_async(
                    signal_id,
                    user_id=user_id,
                    size_usdt_override=Decimal(str(size_usdt)) if size_usdt else None,
                    exchange_override=exchange,
                )
            )

            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful

            logger.info(f"Signal {signal_id}: {successful} successful, {failed} failed trades")

            result = {
                "status": "completed",
                "signal_id": signal_id,
                "successful_trades": successful,
                "failed_trades": failed,
                "user_id": user_id,
                "size_usdt": size_usdt,
                "exchange": exchange,
            }

            # Mark as completed - prevents any re-execution for 24h
            lock.mark_completed(result)

            return result

        except Exception as exc:
            logger.error(f"Trade execution failed for signal {signal_id}: {exc}")
            # Lock will be released on exit via __exit__, allowing retry
            raise self.retry(exc=exc, countdown=5)


@celery_app.task
def sync_all_user_balances():
    """
    Sync balances for all users with connected exchanges.

    Calculates:
    - total_balance: Total portfolio value on exchange
    - available_balance: total_balance - locked_in_positions - pending_trades
    """
    logger.info("Starting balance sync for all users")

    synced_count = 0
    error_count = 0
    encryption = get_encryption_manager()

    with get_sync_db() as db:
        # Get all active users with API keys
        result = db.execute(
            select(User, UserAPIKey)
            .join(UserAPIKey, User.id == UserAPIKey.user_id)
            .where(
                User.is_active == True,
                UserAPIKey.is_active == True,
            )
        )

        user_keys = result.all()

        for user, api_key in user_keys:
            try:
                # Decrypt credentials
                decrypted_key = encryption.decrypt(api_key.api_key_encrypted)
                decrypted_secret = encryption.decrypt(api_key.api_secret_encrypted)
                decrypted_passphrase = None
                if api_key.passphrase_encrypted:
                    decrypted_passphrase = encryption.decrypt(api_key.passphrase_encrypted)

                # Get exchange executor
                executor = get_exchange_executor(
                    exchange_name=api_key.exchange.lower(),
                    api_key=decrypted_key,
                    api_secret=decrypted_secret,
                    passphrase=decrypted_passphrase,
                    testnet=api_key.is_testnet,
                )

                # Fetch balance asynchronously (both SPOT and FUTURES)
                async def fetch_and_update():
                    await executor.initialize()
                    try:
                        total_usdt = Decimal("0")
                        stablecoins = ("USDT", "BUSD", "USDC", "TUSD", "FDUSD", "USD")

                        # Get SPOT balances (all assets)
                        try:
                            spot_balances = await executor.get_account_balance()
                            logger.info(f"User spot balances: {[(b.asset, float(b.total)) for b in spot_balances if b.total > 0]}")
                            for bal in spot_balances:
                                if bal.total > 0:
                                    if bal.asset in stablecoins:
                                        total_usdt += bal.total
                                    else:
                                        # Convert other assets to USDT using current price
                                        try:
                                            price = await executor.get_ticker_price(f"{bal.asset}USDT")
                                            if price:
                                                total_usdt += bal.total * price
                                                logger.debug(f"Converted {bal.total} {bal.asset} = {bal.total * price} USDT")
                                        except Exception:
                                            # Try with BUSD pair as fallback
                                            try:
                                                price = await executor.get_ticker_price(f"{bal.asset}BUSD")
                                                if price:
                                                    total_usdt += bal.total * price
                                            except Exception:
                                                logger.debug(f"Could not convert {bal.asset} to USDT")
                        except Exception as e:
                            logger.warning(f"Failed to get spot balance: {e}")

                        # Get FUTURES balances (usually in USDT)
                        try:
                            futures_balances = await executor.get_futures_balance()
                            for bal in futures_balances:
                                if bal.total > 0:
                                    if bal.asset in stablecoins:
                                        total_usdt += bal.total
                                    else:
                                        try:
                                            price = await executor.get_ticker_price(f"{bal.asset}USDT")
                                            if price:
                                                total_usdt += bal.total * price
                                        except Exception:
                                            pass
                        except Exception as e:
                            logger.warning(f"Failed to get futures balance: {e}")

                        return total_usdt
                    finally:
                        await executor.close()

                exchange_balance = run_async(fetch_and_update())

                # Calculate locked funds: open positions + pending/executing trades
                # Open positions (funds committed to active trades)
                from sqlalchemy import func as sql_func
                open_positions_result = db.execute(
                    select(sql_func.coalesce(sql_func.sum(Position.entry_value_usdt), Decimal("0")))
                    .where(
                        Position.user_id == user.id,
                        Position.status == PositionStatus.OPEN,
                    )
                )
                locked_in_positions = open_positions_result.scalar() or Decimal("0")

                # Pending/executing trades (balance already reserved but not yet in position)
                pending_trades_result = db.execute(
                    select(sql_func.coalesce(sql_func.sum(Trade.trade_value_usdt), Decimal("0")))
                    .where(
                        Trade.user_id == user.id,
                        Trade.status.in_([TradeStatus.PENDING, TradeStatus.EXECUTING]),
                    )
                )
                locked_in_pending = pending_trades_result.scalar() or Decimal("0")

                # Calculate available balance
                # Note: Exchange balance already reflects what's on the exchange
                # We track available_balance separately to prevent double-spending
                total_locked = locked_in_positions + locked_in_pending

                # Update balances
                user.total_balance = exchange_balance
                # Available = exchange balance minus what's already committed
                # But since we reserve balance in 2-phase commit, we need to be careful
                # available_balance should reflect what can be used for NEW trades
                user.available_balance = max(exchange_balance - total_locked, Decimal("0"))

                synced_count += 1

                logger.info(
                    f"Synced balance for user {user.id}: "
                    f"total={exchange_balance} USDT, "
                    f"locked={total_locked} USDT (positions={locked_in_positions}, pending={locked_in_pending}), "
                    f"available={user.available_balance} USDT"
                )

            except Exception as e:
                logger.error(f"Failed to sync balance for user {user.id}: {e}")
                error_count += 1

        db.commit()

    logger.info(f"Balance sync completed: {synced_count} synced, {error_count} errors")
    return {
        "status": "completed",
        "synced": synced_count,
        "errors": error_count,
    }


@celery_app.task(bind=True, max_retries=3)
def close_position(self, user_id: int, position_id: int, reason: str = "manual"):
    """
    Close an open position for a user.

    Uses idempotency lock to prevent duplicate close attempts
    (e.g., from concurrent SL/TP triggers or manual close + auto-close race).

    Args:
        user_id: User's database ID
        position_id: Position to close
        reason: Reason for closing (manual, stop_loss, take_profit, whale_exit)
    """
    # Idempotency lock: prevent duplicate close on same position
    with IdempotencyLock("close_position", position_id, ttl_seconds=120) as lock:
        # Phase 1: Check if position was already closed by previous task
        if lock.already_completed:
            logger.info(f"Position {position_id} already closed previously")
            return {"status": "already_closed", "position_id": position_id}

        # Phase 2: Check if another task is actively closing this position
        if not lock.acquired:
            logger.warning(
                f"Skipping duplicate position close for {position_id} - already in progress"
            )
            return {"status": "skipped", "reason": "already_closing", "position_id": position_id}

        logger.info(f"Closing position {position_id} for user {user_id}")

        encryption = get_encryption_manager()

        try:
            with get_sync_db() as db:
                # ATOMIC CLOSE: Lock position row to prevent race conditions
                # Two concurrent close attempts will be serialized via FOR UPDATE
                # First one succeeds, second one sees status=CLOSED and returns early
                result = db.execute(
                    select(Position, User, UserAPIKey)
                    .join(User, Position.user_id == User.id)
                    .join(UserAPIKey, and_(
                        UserAPIKey.user_id == User.id,
                        UserAPIKey.exchange == Position.exchange,
                    ))
                    .where(
                        Position.id == position_id,
                        Position.user_id == user_id,
                        Position.status == PositionStatus.OPEN,
                    )
                    .with_for_update(of=Position)  # Lock only position row
                )

                row = result.first()
                if not row:
                    # Position doesn't exist, is closed, or user mismatch
                    # Mark as completed to prevent retries
                    lock.mark_completed({"reason": "position_not_found_or_closed"})
                    return {"status": "error", "message": "Position not found or already closed"}

                position, user, api_key = row

                # Double-check status after acquiring lock (defensive)
                if position.status != PositionStatus.OPEN:
                    lock.mark_completed({"reason": "position_already_closed_after_lock"})
                    return {"status": "error", "message": "Position already closed"}

                # Decrypt credentials
                decrypted_key = encryption.decrypt(api_key.api_key_encrypted)
                decrypted_secret = encryption.decrypt(api_key.api_secret_encrypted)
                decrypted_passphrase = None
                if api_key.passphrase_encrypted:
                    decrypted_passphrase = encryption.decrypt(api_key.passphrase_encrypted)

                # Get exchange executor with circuit breaker protection
                try:
                    executor = get_exchange_executor(
                        exchange_name=api_key.exchange.lower(),
                        api_key=decrypted_key,
                        api_secret=decrypted_secret,
                        passphrase=decrypted_passphrase,
                        testnet=api_key.is_testnet,
                    )
                except CircuitOpenError as e:
                    logger.warning(f"Circuit breaker open for {api_key.exchange}: {e}")
                    return {
                        "status": "circuit_open",
                        "message": f"Exchange temporarily unavailable. Retry in {e.time_remaining:.0f}s",
                        "position_id": position_id,
                    }

                async def close_on_exchange():
                    await executor.initialize()
                    try:
                        from app.services.exchanges.base import PositionSide

                        # Determine position side
                        side = PositionSide.LONG if position.side.value == "BUY" else PositionSide.SHORT

                        if position.position_type.value == "FUTURES":
                            # Close futures position
                            order_result = await executor.futures_close_position(
                                symbol=position.symbol,
                                position_side=side,
                                quantity=position.remaining_quantity,
                            )
                        else:
                            # Close spot position by selling
                            order_result = await executor.spot_market_sell(
                                symbol=position.symbol,
                                quantity=position.remaining_quantity,
                            )

                        # Record success for circuit breaker
                        executor.record_success()
                        return order_result
                    except Exception as exc:
                        # Record failure for circuit breaker
                        executor.record_failure(exc)
                        raise
                    finally:
                        await executor.close()

                order_result = run_async(close_on_exchange())

                # Update position
                position.status = PositionStatus.CLOSED
                position.exit_price = order_result.avg_fill_price
                position.exit_value_usdt = position.remaining_quantity * order_result.avg_fill_price
                position.closed_at = datetime.utcnow()
                position.close_reason = reason

                # Calculate realized PnL
                entry_value = position.entry_price * position.quantity
                exit_value = order_result.avg_fill_price * order_result.filled_quantity

                if position.side.value == "BUY":
                    position.realized_pnl = exit_value - entry_value
                else:
                    position.realized_pnl = entry_value - exit_value

                # Create closing trade record
                from app.models.trade import Trade, TradeSide, OrderType, TradeType

                closing_trade = Trade(
                    user_id=user_id,
                    whale_id=position.whale_id,
                    is_copy_trade=False,
                    exchange=position.exchange,
                    exchange_order_id=order_result.order_id,
                    symbol=position.symbol,
                    trade_type=TradeType(position.position_type.value),
                    side=TradeSide.SELL if position.side.value == "BUY" else TradeSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=order_result.filled_quantity,
                    filled_quantity=order_result.filled_quantity,
                    executed_price=order_result.avg_fill_price,
                    trade_value_usdt=exit_value,
                    fee_amount=order_result.fee,
                    fee_currency=order_result.fee_currency,
                    status=TradeStatus.FILLED,
                    executed_at=datetime.utcnow(),
                )
                db.add(closing_trade)

                # Update user balance (subtract fees from profit)
                fee_amount = order_result.fee or Decimal("0")
                user.available_balance += exit_value - fee_amount

                db.commit()

                logger.info(
                    f"Position {position_id} closed: {order_result.filled_quantity} "
                    f"at {order_result.avg_fill_price}, PnL: {position.realized_pnl}"
                )

                result = {
                    "status": "success",
                    "position_id": position_id,
                    "exit_price": str(order_result.avg_fill_price),
                    "realized_pnl": str(position.realized_pnl),
                    "reason": reason,
                }

                # Mark as completed - prevents re-closing for 24h
                lock.mark_completed(result)

                return result

        except Exception as exc:
            logger.error(f"Failed to close position {position_id}: {exc}")
            # Lock released on exit, allowing retry
            raise self.retry(exc=exc, countdown=5)


@celery_app.task
def monitor_positions():
    """
    Monitor all open positions for stop-loss and take-profit.
    Runs every 30 seconds.
    """
    logger.debug("Monitoring open positions")

    closed_count = 0

    with get_sync_db() as db:
        # Get all open positions with stop-loss or take-profit set
        result = db.execute(
            select(Position)
            .where(
                Position.status == PositionStatus.OPEN,
                (Position.stop_loss_price.isnot(None)) | (Position.take_profit_price.isnot(None)),
            )
        )

        positions = result.scalars().all()

        for position in positions:
            try:
                # Get current price
                current_price = position.current_price

                # Check stop-loss
                if position.stop_loss_price:
                    if position.side.value == "BUY":  # Long position
                        if current_price <= position.stop_loss_price:
                            close_position.delay(position.user_id, position.id, "stop_loss")
                            closed_count += 1
                            continue
                    else:  # Short position
                        if current_price >= position.stop_loss_price:
                            close_position.delay(position.user_id, position.id, "stop_loss")
                            closed_count += 1
                            continue

                # Check take-profit
                if position.take_profit_price:
                    if position.side.value == "BUY":  # Long position
                        if current_price >= position.take_profit_price:
                            close_position.delay(position.user_id, position.id, "take_profit")
                            closed_count += 1
                            continue
                    else:  # Short position
                        if current_price <= position.take_profit_price:
                            close_position.delay(position.user_id, position.id, "take_profit")
                            closed_count += 1
                            continue

            except Exception as e:
                logger.error(f"Error monitoring position {position.id}: {e}")

    if closed_count > 0:
        logger.info(f"Triggered {closed_count} position closes")

    return {"status": "completed", "triggered_closes": closed_count}


@celery_app.task
def update_position_prices():
    """
    Update current prices for all open positions.
    Runs every 10 seconds.
    """
    logger.debug("Updating position prices")

    # Group positions by exchange and symbol to minimize API calls
    with get_sync_db() as db:
        result = db.execute(
            select(Position)
            .where(Position.status == PositionStatus.OPEN)
        )

        positions = result.scalars().all()

        if not positions:
            return {"status": "completed", "updated": 0}

        # Group by exchange
        by_exchange: dict[str, list[Position]] = {}
        for pos in positions:
            if pos.exchange not in by_exchange:
                by_exchange[pos.exchange] = []
            by_exchange[pos.exchange].append(pos)

        updated_count = 0

        for exchange_name, exchange_positions in by_exchange.items():
            try:
                # Get first user's API key for this exchange (for public price data)
                api_key_result = db.execute(
                    select(UserAPIKey)
                    .where(
                        UserAPIKey.exchange == exchange_name,
                        UserAPIKey.is_active == True,
                    )
                    .limit(1)
                )
                api_key = api_key_result.scalar_one_or_none()

                if not api_key:
                    continue

                encryption = get_encryption_manager()
                decrypted_key = encryption.decrypt(api_key.api_key_encrypted)
                decrypted_secret = encryption.decrypt(api_key.api_secret_encrypted)

                executor = get_exchange_executor(
                    exchange_name=exchange_name.lower(),
                    api_key=decrypted_key,
                    api_secret=decrypted_secret,
                    testnet=api_key.is_testnet,
                )

                async def update_prices():
                    await executor.initialize()
                    try:
                        updated = 0
                        # Get unique symbols
                        symbols = set(p.symbol for p in exchange_positions)

                        for symbol in symbols:
                            try:
                                price = await executor.get_ticker_price(symbol)
                                if price:
                                    for pos in exchange_positions:
                                        if pos.symbol == symbol:
                                            pos.current_price = price
                                            pos.current_value_usdt = pos.remaining_quantity * price

                                            # Calculate unrealized PnL
                                            if pos.side.value == "BUY":
                                                pos.unrealized_pnl = (price - pos.entry_price) * pos.remaining_quantity
                                            else:
                                                pos.unrealized_pnl = (pos.entry_price - price) * pos.remaining_quantity

                                            updated += 1
                            except Exception as e:
                                logger.error(f"Failed to get price for {symbol}: {e}")

                        return updated
                    finally:
                        await executor.close()

                updated_count += run_async(update_prices())

            except Exception as e:
                logger.error(f"Failed to update prices for {exchange_name}: {e}")

        db.commit()

    return {"status": "completed", "updated": updated_count}
