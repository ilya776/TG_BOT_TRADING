"""
Risk Manager Service
Manages trading risk and enforces limits
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    SUBSCRIPTION_TIERS,
    MIN_TRADING_BALANCE_USDT,
    MIN_TRADE_SIZE_USDT,
    TRADE_SIZE_BUFFER_PERCENT,
    EXCHANGE_MIN_NOTIONAL,
)
from app.models.trade import Position, PositionStatus, Trade, TradeStatus
from app.models.user import User, UserSettings

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    """Result of a risk check."""

    allowed: bool
    reason: str | None = None
    adjusted_quantity: Decimal | None = None
    warnings: list[str] | None = None


@dataclass
class PositionRisk:
    """Risk metrics for a position."""

    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal
    distance_to_liquidation_percent: Decimal | None
    should_close: bool
    close_reason: str | None


class RiskManager:
    """
    Manages trading risk and enforces limits.

    Responsibilities:
    - Pre-trade risk checks
    - Position sizing
    - Daily loss limits
    - Max position limits
    - Stop-loss monitoring
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_trade_risk(
        self,
        user: User,
        symbol: str,
        trade_size_usdt: Decimal,
        is_futures: bool = False,
        leverage: int = 1,
    ) -> RiskCheckResult:
        """
        Check if a trade is allowed based on risk limits.

        Args:
            user: User placing the trade
            symbol: Trading symbol
            trade_size_usdt: Trade size in USDT
            is_futures: Whether this is a futures trade
            leverage: Leverage for futures trades

        Returns:
            RiskCheckResult with allowed status and any adjustments
        """
        warnings = []

        # Get user settings
        settings = await self._get_user_settings(user.id)
        tier_config = SUBSCRIPTION_TIERS.get(user.subscription_tier.value, {})

        # Check 1: User is active
        if not user.is_active or user.is_banned:
            return RiskCheckResult(
                allowed=False,
                reason="User account is not active",
            )

        # G2: Minimum balance check
        if user.available_balance < Decimal(str(MIN_TRADING_BALANCE_USDT)):
            return RiskCheckResult(
                allowed=False,
                reason=f"Balance ${user.available_balance} below minimum ${MIN_TRADING_BALANCE_USDT}. "
                       f"Please deposit more funds to trade.",
            )

        # G1: Minimum trade size check
        if trade_size_usdt < Decimal(str(MIN_TRADE_SIZE_USDT)):
            return RiskCheckResult(
                allowed=False,
                reason=f"Trade size ${trade_size_usdt} below minimum ${MIN_TRADE_SIZE_USDT}.",
            )

        # Check 2: Futures permission
        if is_futures and not tier_config.get("futures_enabled", False):
            return RiskCheckResult(
                allowed=False,
                reason="Futures trading requires PRO subscription or higher",
            )

        # Check 3: Balance check
        if user.available_balance < trade_size_usdt:
            return RiskCheckResult(
                allowed=False,
                reason=f"Insufficient balance. Available: ${user.available_balance}, Required: ${trade_size_usdt}",
            )

        # Check 4: Max trade size
        if settings and trade_size_usdt > settings.max_trade_size_usdt:
            adjusted = settings.max_trade_size_usdt
            warnings.append(f"Trade size reduced to max limit: ${adjusted}")
            trade_size_usdt = adjusted

        # Check 5: Daily loss limit
        daily_loss = await self._get_daily_loss(user.id)
        if settings and daily_loss >= settings.daily_loss_limit_usdt:
            return RiskCheckResult(
                allowed=False,
                reason=f"Daily loss limit reached (${settings.daily_loss_limit_usdt})",
            )

        # Check remaining daily allowance
        remaining_daily = settings.daily_loss_limit_usdt - daily_loss if settings else Decimal("1000000")
        if trade_size_usdt > remaining_daily:
            adjusted = remaining_daily
            warnings.append(f"Trade size reduced due to daily loss limit: ${adjusted}")
            trade_size_usdt = adjusted

        # Check 6: Max open positions
        open_positions = await self._get_open_positions_count(user.id)
        max_positions = tier_config.get("max_positions", 5)
        if max_positions > 0 and open_positions >= max_positions:
            return RiskCheckResult(
                allowed=False,
                reason=f"Maximum open positions reached ({max_positions})",
            )

        # Check 7: Leverage limits for futures
        if is_futures and settings:
            if leverage > settings.max_leverage:
                warnings.append(f"Leverage reduced to max: {settings.max_leverage}x")
                leverage = settings.max_leverage

        return RiskCheckResult(
            allowed=True,
            adjusted_quantity=trade_size_usdt,
            warnings=warnings if warnings else None,
        )

    async def calculate_position_size(
        self,
        user: User,
        balance: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal | None = None,
        risk_percent: Decimal | None = None,
        leverage: int = 1,
    ) -> Decimal:
        """
        Calculate optimal position size based on risk management.

        Args:
            user: User placing the trade
            balance: Available balance
            entry_price: Entry price
            stop_loss_price: Stop loss price (optional)
            risk_percent: Risk per trade as percentage (optional)
            leverage: Leverage multiplier

        Returns:
            Calculated position size in USDT
        """
        settings = await self._get_user_settings(user.id)

        # Default risk percent if not provided
        if risk_percent is None:
            risk_percent = Decimal("2")  # 2% default risk per trade

        # Use user's default trade size if available
        if settings and settings.default_trade_size_usdt:
            base_size = settings.default_trade_size_usdt
        else:
            base_size = balance * (risk_percent / Decimal("100"))

        # Calculate based on stop loss distance if provided
        if stop_loss_price and entry_price != stop_loss_price:
            stop_distance = abs(entry_price - stop_loss_price) / entry_price
            risk_amount = balance * (risk_percent / Decimal("100"))
            calculated_size = risk_amount / stop_distance
            base_size = min(base_size, calculated_size)

        # Apply leverage
        position_size = base_size * leverage

        # Cap at available balance * leverage
        max_size = balance * leverage
        position_size = min(position_size, max_size)

        # Cap at user's max trade size
        if settings and settings.max_trade_size_usdt:
            position_size = min(position_size, settings.max_trade_size_usdt * leverage)

        return position_size

    async def check_position_risk(
        self,
        position: Position,
        current_price: Decimal,
    ) -> PositionRisk:
        """
        Check risk for an open position.

        Args:
            position: The position to check
            current_price: Current market price

        Returns:
            PositionRisk with metrics and close recommendation
        """
        # Calculate PnL
        if position.is_long:
            pnl_percent = ((current_price - position.entry_price) / position.entry_price) * 100
        else:
            pnl_percent = ((position.entry_price - current_price) / position.entry_price) * 100

        unrealized_pnl = position.entry_value_usdt * (pnl_percent / 100)

        # Check distance to liquidation
        distance_to_liq = None
        if position.liquidation_price and position.liquidation_price > 0:
            if position.is_long:
                distance_to_liq = ((current_price - position.liquidation_price) / current_price) * 100
            else:
                distance_to_liq = ((position.liquidation_price - current_price) / current_price) * 100

        # Determine if position should be closed
        should_close = False
        close_reason = None

        # Check stop loss
        if position.stop_loss_price:
            if position.is_long and current_price <= position.stop_loss_price:
                should_close = True
                close_reason = "Stop loss triggered"
            elif position.is_short and current_price >= position.stop_loss_price:
                should_close = True
                close_reason = "Stop loss triggered"

        # Check take profit
        if position.take_profit_price:
            if position.is_long and current_price >= position.take_profit_price:
                should_close = True
                close_reason = "Take profit triggered"
            elif position.is_short and current_price <= position.take_profit_price:
                should_close = True
                close_reason = "Take profit triggered"

        # Check liquidation risk (close if within 10% of liquidation)
        if distance_to_liq is not None and distance_to_liq <= Decimal("10"):
            should_close = True
            close_reason = f"Approaching liquidation ({distance_to_liq:.1f}% away)"

        # Get user settings for stop loss
        user_result = await self.db.execute(
            select(UserSettings).where(UserSettings.user_id == position.user_id)
        )
        settings = user_result.scalar_one_or_none()

        # Check user's stop loss setting
        if settings and pnl_percent <= -settings.stop_loss_percent:
            should_close = True
            close_reason = f"Stop loss at -{settings.stop_loss_percent}% triggered"

        return PositionRisk(
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_percent=pnl_percent,
            distance_to_liquidation_percent=distance_to_liq,
            should_close=should_close,
            close_reason=close_reason,
        )

    async def get_risk_summary(self, user_id: int) -> dict[str, Any]:
        """
        Get a summary of user's current risk exposure.

        Args:
            user_id: User ID

        Returns:
            Dictionary with risk metrics
        """
        # Get open positions
        positions_result = await self.db.execute(
            select(Position).where(
                Position.user_id == user_id,
                Position.status == PositionStatus.OPEN,
            )
        )
        positions = positions_result.scalars().all()

        total_exposure = sum(p.current_value_usdt or p.entry_value_usdt for p in positions)
        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        total_leverage_exposure = sum(
            (p.current_value_usdt or p.entry_value_usdt) * (p.leverage or 1)
            for p in positions
        )

        # Get daily stats
        daily_loss = await self._get_daily_loss(user_id)
        daily_profit = await self._get_daily_profit(user_id)

        # Get settings
        settings = await self._get_user_settings(user_id)

        daily_limit = settings.daily_loss_limit_usdt if settings else Decimal("1000")
        daily_limit_used_percent = (daily_loss / daily_limit * 100) if daily_limit > 0 else Decimal("0")

        return {
            "open_positions": len(positions),
            "total_exposure_usdt": total_exposure,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_leverage_exposure": total_leverage_exposure,
            "daily_loss": daily_loss,
            "daily_profit": daily_profit,
            "daily_net_pnl": daily_profit - daily_loss,
            "daily_limit_used_percent": daily_limit_used_percent,
            "positions_at_risk": sum(1 for p in positions if p.unrealized_pnl < 0),
        }

    async def _get_user_settings(self, user_id: int) -> UserSettings | None:
        """Get user settings."""
        result = await self.db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _get_daily_loss(self, user_id: int) -> Decimal:
        """Get user's total loss for today."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(func.sum(func.abs(Position.realized_pnl))).where(
                Position.user_id == user_id,
                Position.status == PositionStatus.CLOSED,
                Position.realized_pnl < 0,
                Position.closed_at >= today_start,
            )
        )
        return result.scalar() or Decimal("0")

    async def _get_daily_profit(self, user_id: int) -> Decimal:
        """Get user's total profit for today."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(func.sum(Position.realized_pnl)).where(
                Position.user_id == user_id,
                Position.status == PositionStatus.CLOSED,
                Position.realized_pnl > 0,
                Position.closed_at >= today_start,
            )
        )
        return result.scalar() or Decimal("0")

    async def _get_open_positions_count(self, user_id: int) -> int:
        """Get count of user's open positions."""
        result = await self.db.execute(
            select(func.count(Position.id)).where(
                Position.user_id == user_id,
                Position.status == PositionStatus.OPEN,
            )
        )
        return result.scalar() or 0

    def calculate_safe_trade_size(
        self,
        balance: Decimal,
        leverage: int,
        exchange: str,
        futures_type: str = "USD-M",
        percent_of_balance: Decimal = Decimal("1"),  # Default 1% of balance
    ) -> Decimal:
        """
        G1: Calculate safe trade size respecting exchange minimums.

        Args:
            balance: User's available balance
            leverage: Leverage to use
            exchange: Exchange name (binance, okx, bitget)
            futures_type: "USD-M", "COIN-M", or "SPOT"
            percent_of_balance: Percentage of balance to use (default 1%)

        Returns:
            Safe trade size in USDT (margin, not position value)
        """
        # Get exchange minimum
        exchange_minimums = EXCHANGE_MIN_NOTIONAL.get(exchange.lower(), {})
        min_notional = Decimal(str(exchange_minimums.get(futures_type, MIN_TRADE_SIZE_USDT)))

        # Calculate minimum margin required (notional / leverage)
        min_margin = min_notional / Decimal(leverage)

        # Add buffer for fees and slippage
        buffer = Decimal(str(1 + TRADE_SIZE_BUFFER_PERCENT / 100))
        min_margin_with_buffer = min_margin * buffer

        # User's default size (percent of balance)
        user_size = balance * (percent_of_balance / Decimal("100"))

        # Use larger of: minimum required OR user's percentage
        base_size = max(min_margin_with_buffer, user_size)

        # Cap at 10% of balance for risk management (max single trade)
        max_size = balance * Decimal("0.10")

        # Final size is minimum of calculated and max
        final_size = min(base_size, max_size)

        # Ensure at least minimum trade size
        final_size = max(final_size, Decimal(str(MIN_TRADE_SIZE_USDT)))

        # But never more than available balance
        final_size = min(final_size, balance)

        logger.info(
            f"Smart sizing: balance=${balance}, leverage={leverage}x, "
            f"exchange_min=${min_notional}, user_pct={percent_of_balance}%, "
            f"calculated=${final_size}"
        )

        return final_size

    def get_minimum_trade_size(
        self,
        exchange: str,
        futures_type: str = "USD-M",
        leverage: int = 1,
    ) -> Decimal:
        """
        Get minimum trade size for exchange/market type.

        Args:
            exchange: Exchange name
            futures_type: Market type
            leverage: Leverage (to calculate margin from notional)

        Returns:
            Minimum margin size in USDT
        """
        exchange_minimums = EXCHANGE_MIN_NOTIONAL.get(exchange.lower(), {})
        min_notional = Decimal(str(exchange_minimums.get(futures_type, MIN_TRADE_SIZE_USDT)))

        # For futures, minimum margin = minimum notional / leverage
        min_margin = min_notional / Decimal(leverage) if leverage > 1 else min_notional

        # Add buffer
        buffer = Decimal(str(1 + TRADE_SIZE_BUFFER_PERCENT / 100))
        return min_margin * buffer
