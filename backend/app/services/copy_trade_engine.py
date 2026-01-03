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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.exchanges import get_exchange_executor
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

    async def process_signal(self, signal: WhaleSignal) -> list[CopyTradeResult]:
        """
        Process a whale signal and execute copy trades.

        Args:
            signal: The whale signal to process

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

        # Get all users following this whale with auto-copy enabled
        followers = await self._get_auto_copy_followers(signal.whale_id)

        if not followers:
            logger.info(f"No auto-copy followers for whale {signal.whale_id}")
            signal.status = SignalStatus.PROCESSED
            await self.db.commit()
            return results

        logger.info(f"Processing signal {signal.id} for {len(followers)} followers")

        # Process each follower
        for follow, user, settings in followers:
            try:
                result = await self._execute_copy_trade(
                    signal=signal,
                    follow=follow,
                    user=user,
                    settings=settings,
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

    async def _execute_copy_trade(
        self,
        signal: WhaleSignal,
        follow: UserWhaleFollow,
        user: User,
        settings: UserSettings | None,
    ) -> CopyTradeResult:
        """Execute a copy trade for a single user."""
        # Determine trade size
        trade_size_usdt = await self._calculate_trade_size(
            follow=follow,
            user=user,
            settings=settings,
            signal=signal,
        )

        if trade_size_usdt <= 0:
            return CopyTradeResult(
                success=False,
                error="Calculated trade size is zero or negative",
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

        # Initialize exchange executor
        try:
            executor = get_exchange_executor(
                exchange_name=exchange.value.lower(),
                api_key=decrypted_key,
                api_secret=decrypted_secret,
                passphrase=decrypted_passphrase,
                testnet=api_key.is_testnet,
            )
            await executor.initialize()

        except Exception as e:
            return CopyTradeResult(
                success=False,
                error=f"Failed to initialize exchange: {e}",
            )

        try:
            # Get current price to calculate quantity
            current_price = await executor.get_ticker_price(signal.cex_symbol)
            if not current_price:
                return CopyTradeResult(
                    success=False,
                    error="Could not get current price",
                )

            quantity = trade_size_usdt / current_price

            # Execute the trade
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

            # Create trade record
            trade = Trade(
                user_id=user.id,
                signal_id=signal.id,
                whale_id=signal.whale_id,
                is_copy_trade=True,
                exchange=exchange.value,
                exchange_order_id=order_result.order_id,
                symbol=signal.cex_symbol,
                trade_type=TradeType.FUTURES if is_futures else TradeType.SPOT,
                side=TradeSide.BUY if signal.action.value == "BUY" else TradeSide.SELL,
                order_type=OrderType.MARKET,
                quantity=quantity,
                filled_quantity=order_result.filled_quantity,
                executed_price=order_result.avg_fill_price,
                trade_value_usdt=trade_size_usdt,
                leverage=leverage if is_futures else None,
                fee_amount=order_result.fee,
                fee_currency=order_result.fee_currency,
                status=TradeStatus.FILLED if order_result.is_filled else TradeStatus.PARTIALLY_FILLED,
                executed_at=datetime.utcnow(),
            )
            self.db.add(trade)

            # Create or update position
            position = await self._create_or_update_position(
                trade=trade,
                user=user,
                signal=signal,
                order_result=order_result,
                is_futures=is_futures,
                leverage=leverage,
            )

            # Update user's balance
            user.available_balance -= trade_size_usdt

            # Update follow statistics
            follow.trades_copied += 1

            await self.db.commit()
            await self.db.refresh(trade)
            await self.db.refresh(position)

            logger.info(
                f"Copy trade executed for user {user.id}: "
                f"{signal.action.value} {quantity} {signal.cex_symbol} at {order_result.avg_fill_price}"
            )

            return CopyTradeResult(
                success=True,
                trade_id=trade.id,
                position_id=position.id,
                details={
                    "symbol": signal.cex_symbol,
                    "side": signal.action.value,
                    "quantity": str(quantity),
                    "price": str(order_result.avg_fill_price),
                    "value_usdt": str(trade_size_usdt),
                    "warnings": risk_check.warnings,
                },
            )

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return CopyTradeResult(
                success=False,
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
    ) -> Decimal:
        """Calculate trade size for a copy trade."""
        # Priority:
        # 1. Follow-specific trade size
        # 2. Follow-specific percentage of balance
        # 3. User's default trade size
        # 4. Default fallback

        if follow.trade_size_usdt:
            return follow.trade_size_usdt

        if follow.trade_size_percent:
            return user.available_balance * (follow.trade_size_percent / Decimal("100"))

        if settings and settings.default_trade_size_usdt:
            return settings.default_trade_size_usdt

        # Default: 1% of balance
        return user.available_balance * Decimal("0.01")

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
        # Check for existing open position
        existing = await self.db.execute(
            select(Position).where(
                Position.user_id == user.id,
                Position.symbol == signal.cex_symbol,
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


async def process_signal_async(signal_id: int) -> list[CopyTradeResult]:
    """
    Process a signal asynchronously (for use with Celery).

    Args:
        signal_id: ID of the signal to process

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

        if signal.status != SignalStatus.PENDING:
            logger.info(f"Signal {signal_id} already processed")
            return []

        engine = CopyTradeEngine(db)
        return await engine.process_signal(signal)
