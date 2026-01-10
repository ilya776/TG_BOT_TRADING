"""
Copy Trade Engine
Executes copy trades based on whale signals
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError

from app.config import SUBSCRIPTION_TIERS
from app.database import get_db_context
from app.models.signal import SignalStatus, WhaleSignal
from app.models.trade import (
    OrderType,
    Position,
    PositionStatus,
    Trade,
    TradeSide,
    TradeStatus,
    TradeType,
)
from app.models.user import User, UserAPIKey, UserSettings
from app.models.whale import UserWhaleFollow
from app.services.exchanges import get_exchange_executor, CircuitOpenError
from app.services.risk_manager import RiskManager
from app.utils.encryption import get_encryption_manager

logger = logging.getLogger(__name__)


@dataclass
class CopyTradeResult:
    """Result of a copy trade execution."""

    success: bool
    trade_id: int | None = None
    position_id: int | None = None
    error: str | None = None
    details: dict[str, Any] | None = None


class CopyTradeEngine:
    """
    Executes copy trades based on whale signals.

    Workflow:
    1. Receive signal from whale monitor
    2. Find all users following this whale with auto-copy enabled
    3. For each user:
       - Check risk limits
       - Calculate position size
       - Execute trade on their preferred exchange
       - Create trade/position records
       - Send notification
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.encryption = get_encryption_manager()

    async def process_signal(
        self,
        signal: WhaleSignal,
        user_id: int | None = None,
        size_usdt_override: Decimal | None = None,
        exchange_override: str | None = None,
    ) -> list[CopyTradeResult]:
        """
        Process a whale signal and execute copy trades.

        Args:
            signal: The whale signal to process
            user_id: Optional specific user ID (for manual copy)
            size_usdt_override: Optional trade size override
            exchange_override: Optional exchange override (BINANCE, BYBIT, OKX)

        Returns:
            List of CopyTradeResult for each user
        """
        results = []

        # Check if signal is valid for copy trading
        if not signal.cex_available or not signal.cex_symbol:
            logger.info(f"Signal {signal.id} not available on CEX, skipping")
            signal.status = SignalStatus.PROCESSED
            await self.db.commit()
            return results

        # If specific user_id provided (manual copy), process only that user
        if user_id:
            followers = await self._get_specific_user_for_copy(user_id, signal.whale_id)
        else:
            # Get all users following this whale with auto-copy enabled
            followers = await self._get_auto_copy_followers(signal.whale_id)

        if not followers:
            logger.info(f"No followers to process for whale {signal.whale_id}")
            signal.status = SignalStatus.PROCESSED
            await self.db.commit()
            return results

        logger.info(f"Processing signal {signal.id} for {len(followers)} followers (is_close={signal.is_close})")

        # Process each follower
        for follow, user, settings in followers:
            try:
                # Handle close signals differently - close existing positions instead of opening new ones
                if signal.is_close:
                    result = await self._handle_close_signal(
                        signal=signal,
                        user=user,
                    )
                    results.append(result)
                    continue

                # Apply overrides if provided
                effective_size = size_usdt_override or None
                effective_exchange = exchange_override or None

                result = await self._execute_copy_trade(
                    signal=signal,
                    follow=follow,
                    user=user,
                    settings=settings,
                    size_usdt_override=effective_size,
                    exchange_override=effective_exchange,
                )
                results.append(result)

            except Exception as e:
                logger.error(f"Error executing copy trade for user {user.id}: {e}")
                results.append(CopyTradeResult(
                    success=False,
                    error=str(e),
                ))

        # Mark signal as processed
        signal.status = SignalStatus.PROCESSED
        signal.processed_at = datetime.utcnow()
        await self.db.commit()

        return results

    async def _get_auto_copy_followers(
        self,
        whale_id: int,
    ) -> list[tuple[UserWhaleFollow, User, UserSettings | None]]:
        """Get all users with auto-copy enabled for a whale."""
        result = await self.db.execute(
            select(UserWhaleFollow, User, UserSettings)
            .join(User, UserWhaleFollow.user_id == User.id)
            .outerjoin(UserSettings, User.id == UserSettings.user_id)
            .where(
                UserWhaleFollow.whale_id == whale_id,
                UserWhaleFollow.auto_copy_enabled == True,
                User.is_active == True,
                User.is_banned == False,
            )
        )
        return list(result.all())

    async def _get_specific_user_for_copy(
        self,
        user_id: int,
        whale_id: int,
    ) -> list[tuple[UserWhaleFollow, User, UserSettings | None]]:
        """Get a specific user for manual copy (regardless of auto_copy setting)."""
        result = await self.db.execute(
            select(UserWhaleFollow, User, UserSettings)
            .join(User, UserWhaleFollow.user_id == User.id)
            .outerjoin(UserSettings, User.id == UserSettings.user_id)
            .where(
                UserWhaleFollow.user_id == user_id,
                UserWhaleFollow.whale_id == whale_id,
                User.is_active == True,
                User.is_banned == False,
            )
        )
        followers = list(result.all())

        # If user is not following this whale, still allow manual copy
        if not followers:
            user_result = await self.db.execute(
                select(User, UserSettings)
                .outerjoin(UserSettings, User.id == UserSettings.user_id)
                .where(
                    User.id == user_id,
                    User.is_active == True,
                    User.is_banned == False,
                )
            )
            user_data = user_result.first()
            if user_data:
                user, settings = user_data
                # Create a dummy follow object for manual copy
                dummy_follow = UserWhaleFollow(
                    user_id=user_id,
                    whale_id=whale_id,
                    auto_copy_enabled=False,
                )
                return [(dummy_follow, user, settings)]

        return followers

    async def _handle_close_signal(
        self,
        signal: WhaleSignal,
        user: User,
    ) -> CopyTradeResult:
        """
        Handle a close signal by closing user's existing position from this whale.

        When a whale closes their position, we need to close the follower's
        corresponding position instead of opening a new one.
        """
        try:
            # Find user's open position from this whale on this symbol
            result = await self.db.execute(
                select(Position).where(
                    Position.user_id == user.id,
                    Position.whale_id == signal.whale_id,
                    Position.symbol == signal.cex_symbol,
                    Position.status == PositionStatus.OPEN,
                )
            )
            position = result.scalar_one_or_none()

            if not position:
                logger.info(
                    f"No open position found for user {user.id} on {signal.cex_symbol} "
                    f"from whale {signal.whale_id} - nothing to close"
                )
                return CopyTradeResult(
                    success=True,
                    error=None,
                    details={"reason": "no_position_to_close"},
                )

            # Import here to avoid circular dependency
            from app.workers.tasks.trade_tasks import close_position

            # Queue the close position task
            close_position.delay(user.id, position.id, "whale_exit")

            logger.info(
                f"WHALE_EXIT: Queued close_position for user {user.id}, position {position.id} "
                f"(whale {signal.whale_id} exited {signal.cex_symbol})"
            )

            return CopyTradeResult(
                success=True,
                position_id=position.id,
                details={
                    "action": "close_queued",
                    "symbol": signal.cex_symbol,
                    "reason": "whale_exit",
                },
            )

        except Exception as e:
            logger.error(f"Error handling close signal for user {user.id}: {e}")
            return CopyTradeResult(
                success=False,
                error=f"Failed to close position: {e}",
            )

    async def _execute_copy_trade(
        self,
        signal: WhaleSignal,
        follow: UserWhaleFollow,
        user: User,
        settings: UserSettings | None,
        size_usdt_override: Decimal | None = None,
        exchange_override: str | None = None,
    ) -> CopyTradeResult:
        """Execute a copy trade for a single user."""
        # Determine trade size (use override if provided)
        if size_usdt_override:
            trade_size_usdt = size_usdt_override
        else:
            trade_size_usdt = await self._calculate_trade_size(
                follow=follow,
                user=user,
                settings=settings,
                signal=signal,
            )

        # Check if trade size could be calculated
        if trade_size_usdt is None:
            return CopyTradeResult(
                success=False,
                error="No trade size configured. Please set trade_size_usdt, trade_size_percent, or default_trade_size_usdt in Settings.",
            )

        if trade_size_usdt <= 0:
            return CopyTradeResult(
                success=False,
                error=f"Trade size too small: ${trade_size_usdt}. Minimum exchange requirements not met.",
            )

        # Determine trading mode
        is_futures = self._should_use_futures(follow, settings, user)
        leverage = settings.default_leverage if settings and is_futures else 1

        # Risk check
        risk_manager = RiskManager(self.db)
        risk_check = await risk_manager.check_trade_risk(
            user=user,
            symbol=signal.cex_symbol,
            trade_size_usdt=trade_size_usdt,
            is_futures=is_futures,
            leverage=leverage,
        )

        if not risk_check.allowed:
            return CopyTradeResult(
                success=False,
                error=risk_check.reason,
            )

        # Use adjusted quantity if provided
        if risk_check.adjusted_quantity:
            trade_size_usdt = risk_check.adjusted_quantity

        # Get user's API key for preferred exchange
        exchange = settings.preferred_exchange if settings else "BINANCE"
        api_key = await self._get_user_api_key(user.id, exchange.value)

        if not api_key:
            return CopyTradeResult(
                success=False,
                error=f"No API key found for {exchange.value}",
            )

        # Decrypt API credentials
        decrypted_key = self.encryption.decrypt(api_key.api_key_encrypted)
        decrypted_secret = self.encryption.decrypt(api_key.api_secret_encrypted)
        decrypted_passphrase = None
        if api_key.passphrase_encrypted:
            decrypted_passphrase = self.encryption.decrypt(api_key.passphrase_encrypted)

        # Initialize exchange executor with circuit breaker protection
        try:
            executor = get_exchange_executor(
                exchange_name=exchange.value.lower(),
                api_key=decrypted_key,
                api_secret=decrypted_secret,
                passphrase=decrypted_passphrase,
                testnet=api_key.is_testnet,
            )
            await executor.initialize()

        except CircuitOpenError as e:
            # Exchange is temporarily unavailable due to circuit breaker
            logger.warning(f"Circuit breaker open for {exchange.value}: {e}")
            return CopyTradeResult(
                success=False,
                error=f"Exchange {exchange.value} temporarily unavailable. Retry in {e.time_remaining:.0f}s",
            )
        except Exception as e:
            return CopyTradeResult(
                success=False,
                error=f"Failed to initialize exchange: {e}",
            )

        # === CRITICAL: 2-PHASE COMMIT PATTERN ===
        # To prevent orphaned trades and ensure recoverability:
        #
        # PHASE 1 (Reserve): Lock user → Create PENDING trade → Reserve balance → COMMIT
        # EXCHANGE CALL: Execute on exchange (if crash here, PENDING trade exists for reconciliation)
        # PHASE 2 (Confirm/Rollback): Update trade to FILLED/FAILED → Update position → COMMIT
        #
        # Benefits:
        # - If crash before Phase 1 commit: Nothing saved, clean state
        # - If crash after Phase 1 but before exchange: PENDING trade can be cancelled
        # - If crash after exchange but before Phase 2: PENDING trade can be reconciled with exchange
        # - If crash after Phase 2: Fully consistent state

        trade = None
        order_result = None

        try:
            # ============================================
            # PHASE 1: RESERVE (Atomic reservation)
            # ============================================
            # Lock user row and wait if necessary (serializes concurrent trades)
            locked_user_result = await self.db.execute(
                select(User)
                .where(User.id == user.id)
                .with_for_update()  # Wait for lock instead of failing
            )
            locked_user = locked_user_result.scalar_one_or_none()

            if not locked_user:
                return CopyTradeResult(success=False, error="User not found")

            if locked_user.available_balance < trade_size_usdt:
                return CopyTradeResult(
                    success=False,
                    error=f"Insufficient balance: {locked_user.available_balance} < {trade_size_usdt}",
                )

            # Normalize symbol: OKX/Bybit use BTCUSDTSWAPUSDT, Binance uses BTCUSDT
            normalized_symbol = signal.cex_symbol
            if "SWAP" in normalized_symbol:
                # Remove "SWAP" and dedupe "USDT": BTCUSDTSWAPUSDT -> BTCUSDT
                normalized_symbol = normalized_symbol.replace("SWAP", "").replace("USDTUSDT", "USDT")

            # Get current price for quantity calculation
            current_price = await executor.get_ticker_price(normalized_symbol)
            if not current_price:
                logger.warning(
                    f"Could not get price for {normalized_symbol} (original: {signal.cex_symbol})"
                )
                return CopyTradeResult(success=False, error=f"Could not get current price for {normalized_symbol}")

            quantity = trade_size_usdt / current_price

            # Create PENDING trade record (reservation)
            trade = Trade(
                user_id=user.id,
                signal_id=signal.id,
                whale_id=signal.whale_id,
                is_copy_trade=True,
                exchange=exchange.value,
                exchange_order_id=None,  # Will be set after exchange call
                symbol=normalized_symbol,  # Use normalized symbol
                trade_type=TradeType.FUTURES if is_futures else TradeType.SPOT,
                side=TradeSide.BUY if signal.action.value == "BUY" else TradeSide.SELL,
                order_type=OrderType.MARKET,
                quantity=quantity,
                filled_quantity=Decimal("0"),
                executed_price=None,
                trade_value_usdt=trade_size_usdt,
                leverage=leverage if is_futures else None,
                status=TradeStatus.PENDING,  # Will be updated after exchange call
            )
            self.db.add(trade)

            # Reserve balance (deduct from available)
            locked_user.available_balance -= trade_size_usdt

            # COMMIT PHASE 1 - reservation is now durable
            await self.db.commit()
            await self.db.refresh(trade)

            logger.info(
                f"Phase 1 complete: Trade {trade.id} reserved for user {user.id}, "
                f"{trade_size_usdt} USDT reserved"
            )

            # ============================================
            # EXCHANGE CALL (Between phases - recoverable)
            # ============================================
            try:
                # Update trade status to EXECUTING
                trade.status = TradeStatus.EXECUTING
                await self.db.commit()

                if signal.action.value == "BUY":
                    if is_futures:
                        order_result = await executor.futures_market_long(
                            symbol=signal.cex_symbol,
                            quantity=quantity,
                        )
                    else:
                        order_result = await executor.spot_market_buy(
                            symbol=signal.cex_symbol,
                            quantity=quantity,
                        )
                else:  # SELL
                    if is_futures:
                        order_result = await executor.futures_market_short(
                            symbol=signal.cex_symbol,
                            quantity=quantity,
                        )
                    else:
                        order_result = await executor.spot_market_sell(
                            symbol=signal.cex_symbol,
                            quantity=quantity,
                        )

                # Record success for circuit breaker
                executor.record_success()

            except Exception as exchange_error:
                # Record failure for circuit breaker (may open circuit after threshold)
                executor.record_failure(exchange_error)

                # Exchange call failed - rollback the reservation
                logger.error(f"Exchange call failed for trade {trade.id}: {exchange_error}")
                trade.status = TradeStatus.FAILED
                trade.error_message = str(exchange_error)[:500]
                # Restore reserved balance
                locked_user_result = await self.db.execute(
                    select(User).where(User.id == user.id).with_for_update()
                )
                user_to_restore = locked_user_result.scalar_one()
                user_to_restore.available_balance += trade_size_usdt
                await self.db.commit()

                return CopyTradeResult(
                    success=False,
                    trade_id=trade.id,
                    error=f"Exchange error: {exchange_error}",
                )

            # ============================================
            # PHASE 2: CONFIRM (Finalize successful trade)
            # ============================================
            # Update trade with exchange results
            trade.exchange_order_id = order_result.order_id
            trade.filled_quantity = order_result.filled_quantity
            trade.executed_price = order_result.avg_fill_price
            trade.fee_amount = order_result.fee
            trade.fee_currency = order_result.fee_currency
            trade.status = TradeStatus.FILLED if order_result.is_filled else TradeStatus.PARTIALLY_FILLED
            trade.executed_at = datetime.utcnow()

            # Create or update position
            position = await self._create_or_update_position(
                trade=trade,
                user=locked_user,
                signal=signal,
                order_result=order_result,
                is_futures=is_futures,
                leverage=leverage,
            )

            # Update follow statistics
            follow.trades_copied += 1

            # COMMIT PHASE 2 - trade is now complete
            await self.db.commit()
            await self.db.refresh(trade)
            await self.db.refresh(position)

            logger.info(
                f"Phase 2 complete: Trade {trade.id} filled for user {user.id}: "
                f"{signal.action.value} {order_result.filled_quantity} {signal.cex_symbol} "
                f"at {order_result.avg_fill_price}"
            )

            # Send trade execution notification
            try:
                if settings and settings.notify_trade_executed:
                    from app.workers.tasks.notification_tasks import send_trade_notification
                    from app.models.whale import Whale

                    whale_result = await self.db.execute(
                        select(Whale).where(Whale.id == signal.whale_id)
                    )
                    whale = whale_result.scalar_one_or_none()

                    send_trade_notification.delay(
                        user_id=user.id,
                        trade_data={
                            "symbol": signal.cex_symbol,
                            "side": signal.action.value,
                            "quantity": float(order_result.filled_quantity),
                            "price": float(order_result.avg_fill_price),
                            "value_usdt": float(trade_size_usdt),
                            "status": "FILLED",
                            "whale_name": whale.name if whale else "",
                        }
                    )
                    logger.info(f"Sent trade notification to user {user.id} for trade {trade.id}")
            except Exception as notif_error:
                logger.error(f"Failed to send trade notification: {notif_error}")

            return CopyTradeResult(
                success=True,
                trade_id=trade.id,
                position_id=position.id,
                details={
                    "symbol": signal.cex_symbol,
                    "side": signal.action.value,
                    "quantity": str(order_result.filled_quantity),
                    "price": str(order_result.avg_fill_price),
                    "value_usdt": str(trade_size_usdt),
                    "warnings": risk_check.warnings,
                },
            )

        except Exception as e:
            logger.error(f"Unexpected error in copy trade: {e}")

            # If we have a trade record, mark it for reconciliation
            if trade and trade.id:
                try:
                    # Use fresh session to avoid transaction issues
                    async with get_db_context() as recovery_db:
                        recovery_result = await recovery_db.execute(
                            select(Trade).where(Trade.id == trade.id)
                        )
                        recovery_trade = recovery_result.scalar_one_or_none()
                        if recovery_trade and recovery_trade.status in (
                            TradeStatus.PENDING, TradeStatus.EXECUTING
                        ):
                            recovery_trade.status = TradeStatus.NEEDS_RECONCILIATION
                            recovery_trade.error_message = f"Unexpected error: {str(e)[:400]}"
                            await recovery_db.commit()
                            logger.warning(f"Trade {trade.id} marked for reconciliation")
                except Exception as recovery_error:
                    logger.critical(f"Failed to mark trade for reconciliation: {recovery_error}")

            return CopyTradeResult(
                success=False,
                trade_id=trade.id if trade else None,
                error=str(e),
            )

        finally:
            await executor.close()

    async def _calculate_trade_size(
        self,
        follow: UserWhaleFollow,
        user: User,
        settings: UserSettings | None,
        signal: WhaleSignal,
    ) -> Decimal | None:
        """
        Calculate trade size for a copy trade.

        Returns None if no trade size is configured - DO NOT use arbitrary defaults!
        This is people's money - explicit configuration required.

        Priority:
        1. Follow-specific trade size (fixed USDT)
        2. Follow-specific percentage of balance
        3. User's default trade size from settings
        """
        calculated_size = None

        # 1. Check follow-specific fixed size
        if follow.trade_size_usdt:
            calculated_size = follow.trade_size_usdt

        # 2. Check follow-specific percentage
        elif follow.trade_size_percent:
            calculated_size = user.available_balance * (follow.trade_size_percent / Decimal("100"))

        # 3. Check user's default trade size
        elif settings and settings.default_trade_size_usdt:
            calculated_size = settings.default_trade_size_usdt

        # NO DEFAULT FALLBACK - require explicit configuration!
        if calculated_size is None:
            return None

        # Validate against max_trade_size from settings
        if settings and settings.max_trade_size_usdt:
            calculated_size = min(calculated_size, settings.max_trade_size_usdt)

        # Never exceed available balance
        calculated_size = min(calculated_size, user.available_balance)

        return calculated_size

    def _should_use_futures(
        self,
        follow: UserWhaleFollow,
        settings: UserSettings | None,
        user: User,
    ) -> bool:
        """Determine if futures should be used for the trade."""
        # Check subscription tier
        tier_config = SUBSCRIPTION_TIERS.get(user.subscription_tier.value, {})
        if not tier_config.get("futures_enabled", False):
            return False

        # Check follow-specific override
        if follow.trading_mode_override:
            return follow.trading_mode_override == "FUTURES"

        # Check user settings
        if settings:
            return settings.trading_mode.value in ("FUTURES", "MIXED")

        return False

    async def _get_user_api_key(
        self,
        user_id: int,
        exchange: str,
    ) -> UserAPIKey | None:
        """Get user's API key for an exchange."""
        result = await self.db.execute(
            select(UserAPIKey).where(
                UserAPIKey.user_id == user_id,
                UserAPIKey.exchange == exchange,
                UserAPIKey.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def _create_or_update_position(
        self,
        trade: Trade,
        user: User,
        signal: WhaleSignal,
        order_result: Any,
        is_futures: bool,
        leverage: int,
    ) -> Position:
        """Create a new position or update existing one."""
        # Check for existing open position FROM THE SAME WHALE
        # This prevents merging positions from different whales on the same symbol
        existing = await self.db.execute(
            select(Position).where(
                Position.user_id == user.id,
                Position.symbol == signal.cex_symbol,
                Position.whale_id == signal.whale_id,  # Only merge positions from same whale
                Position.status == PositionStatus.OPEN,
            )
        )
        position = existing.scalar_one_or_none()

        if position:
            # Update existing position
            # Calculate new average entry price
            total_value = (position.entry_price * position.quantity) + (
                order_result.avg_fill_price * order_result.filled_quantity
            )
            new_quantity = position.quantity + order_result.filled_quantity
            position.entry_price = total_value / new_quantity
            position.quantity = new_quantity
            position.remaining_quantity = new_quantity
            position.current_price = order_result.avg_fill_price
            position.entry_value_usdt += trade.trade_value_usdt
            position.current_value_usdt = new_quantity * order_result.avg_fill_price

        else:
            # Create new position
            position = Position(
                user_id=user.id,
                whale_id=signal.whale_id,
                entry_trade_id=trade.id,
                exchange=trade.exchange,
                symbol=signal.cex_symbol,
                position_type=TradeType.FUTURES if is_futures else TradeType.SPOT,
                side=trade.side,
                quantity=order_result.filled_quantity,
                remaining_quantity=order_result.filled_quantity,
                entry_price=order_result.avg_fill_price,
                current_price=order_result.avg_fill_price,
                entry_value_usdt=trade.trade_value_usdt,
                current_value_usdt=trade.trade_value_usdt,
                leverage=leverage if is_futures else None,
                status=PositionStatus.OPEN,
            )
            self.db.add(position)

        return position


async def process_signal_async(
    signal_id: int,
    user_id: int | None = None,
    size_usdt_override: Decimal | None = None,
    exchange_override: str | None = None,
) -> list[CopyTradeResult]:
    """
    Process a signal asynchronously (for use with Celery).

    Args:
        signal_id: ID of the signal to process
        user_id: Optional specific user ID (for manual copy)
        size_usdt_override: Optional trade size override
        exchange_override: Optional exchange override (BINANCE, BYBIT, OKX)

    Returns:
        List of copy trade results
    """
    async with get_db_context() as db:
        # Get the signal
        result = await db.execute(
            select(WhaleSignal).where(WhaleSignal.id == signal_id)
        )
        signal = result.scalar_one_or_none()

        if not signal:
            logger.error(f"Signal {signal_id} not found")
            return []

        # Accept both PENDING and PROCESSING signals
        # PROCESSING is set by check_whale_positions before this task runs
        if signal.status not in (SignalStatus.PENDING, SignalStatus.PROCESSING):
            logger.info(f"Signal {signal_id} already processed (status: {signal.status})")
            return []

        engine = CopyTradeEngine(db)
        return await engine.process_signal(
            signal,
            user_id=user_id,
            size_usdt_override=size_usdt_override,
            exchange_override=exchange_override,
        )
