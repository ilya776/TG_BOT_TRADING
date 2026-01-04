"""
Trade-related Celery tasks
"""
import asyncio
import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.database import get_sync_db
from app.models.signal import SignalStatus, WhaleSignal
from app.models.trade import Position, PositionStatus, Trade, TradeStatus
from app.models.user import User, UserAPIKey, UserSettings
from app.models.whale import UserWhaleFollow
from app.services.exchanges import get_exchange_executor
from app.services.copy_trade_engine import process_signal_async
from app.utils.encryption import get_encryption_manager
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run async code in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, max_retries=3)
def execute_copy_trade(self, signal_id: int):
    """
    Execute copy trades for all followers of a whale signal.

    Args:
        signal_id: Whale signal ID to process
    """
    try:
        logger.info(f"Processing signal {signal_id} for copy trading")

        # Run the async copy trade engine
        results = run_async(process_signal_async(signal_id))

        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        logger.info(f"Signal {signal_id}: {successful} successful, {failed} failed trades")

        return {
            "status": "completed",
            "signal_id": signal_id,
            "successful_trades": successful,
            "failed_trades": failed,
        }

    except Exception as exc:
        logger.error(f"Trade execution failed for signal {signal_id}: {exc}")
        raise self.retry(exc=exc, countdown=5)


@celery_app.task
def sync_all_user_balances():
    """Sync balances for all users with connected exchanges."""
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

                # Fetch balance asynchronously
                async def fetch_and_update():
                    await executor.initialize()
                    try:
                        balances = await executor.get_account_balance()

                        # Calculate total USDT equivalent
                        total_usdt = Decimal("0")
                        for bal in balances:
                            if bal.asset == "USDT":
                                total_usdt += bal.total
                            elif bal.asset == "BUSD":
                                total_usdt += bal.total
                            # For other assets, you'd need price feeds

                        return total_usdt
                    finally:
                        await executor.close()

                balance = run_async(fetch_and_update())

                # Update user balance
                user.balance = balance
                user.available_balance = balance
                synced_count += 1

                logger.debug(f"Synced balance for user {user.id}: {balance} USDT")

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

    Args:
        user_id: User's database ID
        position_id: Position to close
        reason: Reason for closing (manual, stop_loss, take_profit, whale_exit)
    """
    logger.info(f"Closing position {position_id} for user {user_id}")

    encryption = get_encryption_manager()

    try:
        with get_sync_db() as db:
            # Get position with user and API key
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
            )

            row = result.first()
            if not row:
                return {"status": "error", "message": "Position not found or already closed"}

            position, user, api_key = row

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

                    return order_result
                finally:
                    await executor.close()

            order_result = run_async(close_on_exchange())

            # Update position
            from datetime import datetime

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

            # Update user balance
            user.available_balance += exit_value

            db.commit()

            logger.info(
                f"Position {position_id} closed: {order_result.filled_quantity} "
                f"at {order_result.avg_fill_price}, PnL: {position.realized_pnl}"
            )

            return {
                "status": "success",
                "position_id": position_id,
                "exit_price": str(order_result.avg_fill_price),
                "realized_pnl": str(position.realized_pnl),
            }

    except Exception as exc:
        logger.error(f"Failed to close position {position_id}: {exc}")
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
