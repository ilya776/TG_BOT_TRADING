"""
Smart Position Sizing Service

Provides multiple strategies for calculating trade sizes:
1. FIXED - Fixed USD amount per trade
2. PERCENT_BALANCE - Percentage of available balance
3. KELLY - Kelly Criterion based on trader's win rate

Usage:
    sizer = SmartPositionSizer()
    size_usd = await sizer.calculate_size(
        user=user,
        whale=whale,
        signal=signal,
        follow=follow,
    )
"""

import logging
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SizingStrategy(str, Enum):
    """Position sizing strategy options."""
    FIXED = "FIXED"                    # Fixed USD amount
    PERCENT_BALANCE = "PERCENT_BALANCE"  # Percentage of balance
    KELLY = "KELLY"                    # Kelly Criterion


# Default configuration
DEFAULT_STRATEGY = SizingStrategy.FIXED
DEFAULT_FIXED_SIZE = Decimal("10.0")  # $10 default
DEFAULT_PERCENT = Decimal("3.0")       # 3% of balance
DEFAULT_KELLY_FRACTION = Decimal("0.5")  # Half Kelly for safety

# Safety bounds
MIN_TRADE_SIZE_USD = Decimal("5.0")    # Minimum $5
MAX_TRADE_SIZE_USD = Decimal("10000.0")  # Maximum $10,000
MIN_PERCENT = Decimal("0.5")            # 0.5% minimum
MAX_PERCENT = Decimal("25.0")           # 25% maximum
MIN_KELLY_FRACTION = Decimal("0.1")     # 10% of Kelly
MAX_KELLY_FRACTION = Decimal("1.0")     # Full Kelly


class SmartPositionSizer:
    """
    Smart position sizing calculator with multiple strategies.

    Strategies:
    1. FIXED: Use a fixed USD amount for every trade
       - Simple and predictable
       - Good for beginners or small accounts
       - Doesn't scale with account size

    2. PERCENT_BALANCE: Use a percentage of available balance
       - Scales with account growth
       - More risk when account is large
       - Compounds gains/losses

    3. KELLY: Kelly Criterion based on trader's historical win rate
       - Mathematically optimal for long-term growth
       - Can be aggressive - use fractional Kelly (50%)
       - Requires accurate win rate data

    Kelly Formula:
        kelly% = W - [(1-W) / R]
        where:
        - W = win rate (probability of winning)
        - R = average win / average loss ratio

    Example:
        Win rate = 60%, Win/Loss ratio = 1.5
        kelly% = 0.60 - (0.40 / 1.5) = 0.60 - 0.267 = 0.333 (33.3%)
        With 50% fractional Kelly: 16.65%
    """

    def __init__(self):
        pass

    async def calculate_size(
        self,
        user,  # User model
        whale,  # Whale model
        signal,  # WhaleSignal model
        follow,  # UserWhaleFollow model
        settings=None,  # UserSettings model (optional)
    ) -> Decimal:
        """
        Calculate trade size based on user's sizing strategy.

        Priority for strategy selection:
        1. Per-whale override (follow.sizing_strategy_override)
        2. User global settings (settings.sizing_strategy)
        3. Default (FIXED with $10)

        Args:
            user: User performing the trade
            whale: Whale being copied
            signal: The trading signal
            follow: User's follow settings for this whale
            settings: User's global settings (optional)

        Returns:
            Trade size in USD
        """
        # Determine strategy (follow override > settings > default)
        strategy = self._get_strategy(follow, settings)

        # Calculate size based on strategy
        if strategy == SizingStrategy.FIXED:
            size = self._fixed_size(follow, settings)
        elif strategy == SizingStrategy.PERCENT_BALANCE:
            size = await self._percent_balance_size(user, follow, settings)
        elif strategy == SizingStrategy.KELLY:
            size = await self._kelly_size(user, whale, follow, settings)
        else:
            # Fallback to fixed
            size = DEFAULT_FIXED_SIZE

        # Apply safety bounds
        size = self._apply_bounds(size, user, follow, settings)

        logger.debug(
            f"Position sizing: strategy={strategy.value}, size=${size:.2f}, "
            f"user={user.id}, whale={whale.name}"
        )

        return size

    def _get_strategy(self, follow, settings) -> SizingStrategy:
        """
        Get the sizing strategy to use.

        Priority:
        1. Per-whale override
        2. User global settings
        3. Default
        """
        # Check follow override first
        if follow and hasattr(follow, 'sizing_strategy_override') and follow.sizing_strategy_override:
            try:
                return SizingStrategy(follow.sizing_strategy_override)
            except ValueError:
                pass

        # Check user settings
        if settings and hasattr(settings, 'sizing_strategy') and settings.sizing_strategy:
            try:
                return SizingStrategy(settings.sizing_strategy)
            except ValueError:
                pass

        return DEFAULT_STRATEGY

    def _fixed_size(self, follow, settings) -> Decimal:
        """
        Calculate fixed USD trade size.

        Uses:
        1. Per-whale trade_size override
        2. User global trade_size_usd
        3. Default $10
        """
        # Per-whale override
        if follow and hasattr(follow, 'trade_size') and follow.trade_size:
            return Decimal(str(follow.trade_size))

        # User global setting
        if settings and hasattr(settings, 'trade_size_usd') and settings.trade_size_usd:
            return Decimal(str(settings.trade_size_usd))

        return DEFAULT_FIXED_SIZE

    async def _percent_balance_size(self, user, follow, settings) -> Decimal:
        """
        Calculate trade size as percentage of available balance.

        Uses:
        1. Per-whale trade_size_percent_override
        2. User global trade_size_percent
        3. Default 3%

        Requires available_balance on user's exchange balance.
        """
        # Get percentage
        percent = DEFAULT_PERCENT

        if follow and hasattr(follow, 'trade_size_percent_override') and follow.trade_size_percent_override:
            percent = Decimal(str(follow.trade_size_percent_override))
        elif settings and hasattr(settings, 'trade_size_percent') and settings.trade_size_percent:
            percent = Decimal(str(settings.trade_size_percent))

        # Clamp percent to safe range
        percent = max(MIN_PERCENT, min(MAX_PERCENT, percent))

        # Get available balance
        available_balance = await self._get_available_balance(user)

        if available_balance <= 0:
            logger.warning(f"User {user.id} has no available balance, using minimum size")
            return MIN_TRADE_SIZE_USD

        # Calculate size
        size = available_balance * (percent / Decimal("100"))

        logger.debug(
            f"Percent sizing: {percent}% of ${available_balance:.2f} = ${size:.2f}"
        )

        return size

    async def _kelly_size(self, user, whale, follow, settings) -> Decimal:
        """
        Calculate trade size using Kelly Criterion.

        Formula: kelly% = W - [(1-W) / R]
        where:
        - W = win rate (0.0 - 1.0)
        - R = win/loss ratio

        Uses fractional Kelly (default 50%) for safety.
        Requires whale stats for win_rate and historical performance.
        """
        # Get Kelly fraction
        kelly_fraction = DEFAULT_KELLY_FRACTION

        if follow and hasattr(follow, 'kelly_fraction_override') and follow.kelly_fraction_override:
            kelly_fraction = Decimal(str(follow.kelly_fraction_override))
        elif settings and hasattr(settings, 'kelly_fraction') and settings.kelly_fraction:
            kelly_fraction = Decimal(str(settings.kelly_fraction))

        kelly_fraction = max(MIN_KELLY_FRACTION, min(MAX_KELLY_FRACTION, kelly_fraction))

        # Get whale stats
        win_rate, win_loss_ratio = await self._get_whale_stats(whale)

        # Calculate Kelly percentage
        # kelly% = W - [(1-W) / R]
        if win_loss_ratio <= 0:
            # No edge, use minimum
            logger.warning(f"Whale {whale.name} has no positive edge, using minimum size")
            return MIN_TRADE_SIZE_USD

        kelly_percent = win_rate - ((Decimal("1") - win_rate) / win_loss_ratio)

        # Apply fractional Kelly
        kelly_percent = kelly_percent * kelly_fraction

        # If Kelly is negative or zero, trader has no edge
        if kelly_percent <= 0:
            logger.info(
                f"Kelly criterion suggests no edge for {whale.name} "
                f"(W={win_rate:.2f}, R={win_loss_ratio:.2f})"
            )
            return MIN_TRADE_SIZE_USD

        # Cap at reasonable maximum (25%)
        kelly_percent = min(kelly_percent, Decimal("0.25"))

        # Get available balance
        available_balance = await self._get_available_balance(user)

        if available_balance <= 0:
            return MIN_TRADE_SIZE_USD

        # Calculate size
        size = available_balance * kelly_percent

        logger.debug(
            f"Kelly sizing: W={win_rate:.2f}, R={win_loss_ratio:.2f}, "
            f"Kelly={kelly_percent*100:.1f}%, Size=${size:.2f}"
        )

        return size

    async def _get_available_balance(self, user) -> Decimal:
        """
        Get user's available balance for trading.

        Tries to get from user's exchange balance, falls back to cached value.
        """
        try:
            # Get exchange balance relationship
            if hasattr(user, 'exchange_balances') and user.exchange_balances:
                for balance in user.exchange_balances:
                    if hasattr(balance, 'available_usdt') and balance.available_usdt:
                        return Decimal(str(balance.available_usdt))

            # Fallback: check for cached balance attribute
            if hasattr(user, 'cached_balance') and user.cached_balance:
                return Decimal(str(user.cached_balance))

        except Exception as e:
            logger.warning(f"Error getting available balance for user {user.id}: {e}")

        return Decimal("0")

    async def _get_whale_stats(self, whale) -> tuple[Decimal, Decimal]:
        """
        Get whale's win rate and win/loss ratio for Kelly calculation.

        Returns:
            (win_rate, win_loss_ratio) tuple
        """
        default_win_rate = Decimal("0.55")  # 55% default
        default_ratio = Decimal("1.2")       # 1.2:1 default

        try:
            # Get whale stats relationship
            if hasattr(whale, 'stats') and whale.stats:
                stats = whale.stats

                # Win rate (as decimal 0.0-1.0)
                win_rate = default_win_rate
                if hasattr(stats, 'win_rate') and stats.win_rate:
                    win_rate = Decimal(str(stats.win_rate)) / Decimal("100")
                    win_rate = max(Decimal("0.1"), min(Decimal("0.9"), win_rate))

                # Win/Loss ratio from profit data
                # Estimate from avg_profit_percent if available
                win_loss_ratio = default_ratio
                if hasattr(stats, 'avg_profit_percent') and stats.avg_profit_percent:
                    # Higher avg profit suggests better win/loss ratio
                    avg_profit = Decimal(str(stats.avg_profit_percent))
                    win_loss_ratio = Decimal("1") + (avg_profit / Decimal("10"))
                    win_loss_ratio = max(Decimal("0.5"), min(Decimal("3.0"), win_loss_ratio))

                return win_rate, win_loss_ratio

        except Exception as e:
            logger.warning(f"Error getting whale stats for {whale.name}: {e}")

        return default_win_rate, default_ratio

    def _apply_bounds(self, size: Decimal, user, follow, settings) -> Decimal:
        """
        Apply safety bounds to trade size.

        Checks:
        1. Minimum trade size ($5)
        2. Maximum trade size ($10,000)
        3. Per-whale max_trade_size override
        4. User max_trade_size_usd setting
        """
        # Apply minimum
        size = max(MIN_TRADE_SIZE_USD, size)

        # Check per-whale max
        max_size = MAX_TRADE_SIZE_USD
        if follow and hasattr(follow, 'max_trade_size') and follow.max_trade_size:
            max_size = min(max_size, Decimal(str(follow.max_trade_size)))

        # Check user global max
        if settings and hasattr(settings, 'max_trade_size_usd') and settings.max_trade_size_usd:
            max_size = min(max_size, Decimal(str(settings.max_trade_size_usd)))

        # Apply maximum
        size = min(max_size, size)

        # Round down to 2 decimal places
        size = size.quantize(Decimal("0.01"), rounding=ROUND_DOWN)

        return size


# Singleton instance for convenience
_default_sizer: Optional[SmartPositionSizer] = None


def get_sizer() -> SmartPositionSizer:
    """Get or create default sizer instance."""
    global _default_sizer
    if _default_sizer is None:
        _default_sizer = SmartPositionSizer()
    return _default_sizer


async def calculate_trade_size(user, whale, signal, follow, settings=None) -> Decimal:
    """Convenience function to calculate trade size."""
    sizer = get_sizer()
    return await sizer.calculate_size(user, whale, signal, follow, settings)
