"""
Sharing Validator Service
Detects and manages whale position sharing status.

Key logic:
- Bitget traders ALWAYS share positions (100% public)
- Binance traders can disable sharing (~40-60% do)
- OKX traders mostly share (~70%)
- 3+ consecutive empty responses = likely SHARING_DISABLED
"""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.whale import Whale

if TYPE_CHECKING:
    from app.services.trader_signals import TraderPosition

logger = logging.getLogger(__name__)


# Exchanges that ALWAYS share positions (no closed status possible)
ALWAYS_PUBLIC_EXCHANGES = {"BITGET"}

# Number of consecutive empty checks before marking as SHARING_DISABLED
# With 1s polling interval, 1000 checks = ~17 minutes of continuous empty
# responses. This prevents false-disabling traders who simply have no
# open positions temporarily (which is normal trading behavior).
EMPTY_CHECKS_THRESHOLD = 1000

# Hours before re-checking a disabled whale
RECHECK_INTERVAL_HOURS = 24


class SharingValidator:
    """
    Validates and manages whale position sharing status.

    This service solves the "closed status" problem where 40-60% of
    Binance traders have position sharing disabled, causing us to
    receive empty position lists and generate zero signals.

    Detection logic:
    1. If exchange is BITGET -> always ACTIVE (100% public)
    2. If rate limit error -> RATE_LIMITED (temporary)
    3. If positions found -> ACTIVE (reset counter)
    4. If 3+ consecutive empty -> SHARING_DISABLED
    """

    async def check_and_update_status(
        self,
        whale: Whale,
        positions: list["TraderPosition"],
        fetch_error: Exception | None = None,
    ) -> str:
        """
        Check whale's sharing status based on fetch result.

        Args:
            whale: The whale being checked
            positions: List of positions returned (empty = might be disabled OR no positions)
            fetch_error: Any exception from fetch (rate limit, sharing disabled, network, etc.)

        Returns:
            Updated status as string: "ACTIVE", "SHARING_DISABLED", "RATE_LIMITED"
        """
        now = datetime.utcnow()
        whale.last_position_check = now

        # Handle explicit sharing disabled exception
        if fetch_error:
            from app.services.trader_signals import SharingDisabledException

            error_str = str(fetch_error).lower()

            # Check for explicit sharing disabled
            if isinstance(fetch_error, SharingDisabledException) or "sharing disabled" in error_str:
                logger.warning(f"Whale {whale.id} ({whale.name}) CONFIRMED sharing disabled")
                whale.data_status = "SHARING_DISABLED"
                whale.sharing_disabled_at = now
                whale.sharing_recheck_at = now + timedelta(hours=RECHECK_INTERVAL_HOURS)
                whale.consecutive_empty_checks = 0
                return "SHARING_DISABLED"

            # Handle rate limit
            if "429" in error_str or "rate" in error_str:
                logger.warning(f"Whale {whale.id} ({whale.name}) rate limited")
                whale.data_status = "RATE_LIMITED"
                return "RATE_LIMITED"

        # Bitget ALWAYS shares - empty means no open positions
        if whale.exchange in ALWAYS_PUBLIC_EXCHANGES:
            whale.consecutive_empty_checks = 0
            whale.data_status = "ACTIVE"
            if positions:
                whale.last_position_found = now
            return "ACTIVE"

        # Has positions = definitely active
        if positions:
            whale.consecutive_empty_checks = 0
            whale.last_position_found = now
            whale.data_status = "ACTIVE"
            whale.sharing_disabled_at = None
            return "ACTIVE"

        # Empty positions - increment counter
        # BUT ONLY if we didn't have a fetch error (which would be ambiguous)
        if fetch_error is None:
            whale.consecutive_empty_checks += 1
        else:
            logger.debug(f"Whale {whale.id} skipping empty check due to fetch error")

        # Check if threshold reached
        if whale.consecutive_empty_checks >= EMPTY_CHECKS_THRESHOLD:
            if whale.data_status != "SHARING_DISABLED":
                logger.warning(
                    f"Whale {whale.id} ({whale.name}) marked SHARING_DISABLED "
                    f"after {whale.consecutive_empty_checks} consecutive empty checks. "
                    f"This might be FALSE POSITIVE if trader has no positions."
                )
                whale.sharing_disabled_at = now
                whale.sharing_recheck_at = now + timedelta(hours=RECHECK_INTERVAL_HOURS)
            whale.data_status = "SHARING_DISABLED"
            return "SHARING_DISABLED"

        # Not enough evidence yet - keep as active
        return "ACTIVE"

    async def get_whales_for_revalidation(
        self,
        db: AsyncSession,
        limit: int = 50,
    ) -> list[Whale]:
        """
        Get whales that are due for sharing status re-check.

        These are whales marked as SHARING_DISABLED whose
        sharing_recheck_at time has passed.

        Args:
            db: Database session
            limit: Maximum whales to return

        Returns:
            List of whales to re-check
        """
        now = datetime.utcnow()

        result = await db.execute(
            select(Whale)
            .where(Whale.data_status == "SHARING_DISABLED")
            .where(Whale.sharing_recheck_at <= now)
            .where(Whale.is_active == True)
            .order_by(Whale.sharing_recheck_at)
            .limit(limit)
        )

        return list(result.scalars().all())

    async def reset_for_revalidation(
        self,
        whale: Whale,
    ) -> None:
        """
        Reset whale's counters for re-validation attempt.

        Call this before re-checking a SHARING_DISABLED whale
        to give it a fresh start.
        """
        whale.consecutive_empty_checks = 0
        whale.data_status = "ACTIVE"
        # Schedule next recheck further out
        whale.sharing_recheck_at = datetime.utcnow() + timedelta(
            hours=RECHECK_INTERVAL_HOURS * 2
        )
        logger.debug(
            f"Whale {whale.id} ({whale.name}) reset for re-validation"
        )

    async def mark_rate_limited(
        self,
        whale: Whale,
        cooldown_seconds: int = 60,
    ) -> None:
        """Mark whale as temporarily rate limited."""
        whale.data_status = "RATE_LIMITED"
        whale.sharing_recheck_at = datetime.utcnow() + timedelta(
            seconds=cooldown_seconds
        )

    async def clear_rate_limit(
        self,
        whale: Whale,
    ) -> None:
        """Clear rate limit status."""
        if whale.data_status == "RATE_LIMITED":
            whale.data_status = "ACTIVE"
            whale.sharing_recheck_at = None

    async def get_active_whales_for_polling(
        self,
        db: AsyncSession,
        exchange: str | None = None,
        limit: int = 100,
    ) -> list[Whale]:
        """
        Get whales that should be polled for positions.

        Excludes:
        - SHARING_DISABLED whales (unless due for recheck)
        - INACTIVE whales
        - RATE_LIMITED whales (unless cooldown passed)

        Args:
            db: Database session
            exchange: Filter by specific exchange (optional)
            limit: Maximum whales to return

        Returns:
            List of whales ready for polling, ordered by priority
        """
        now = datetime.utcnow()

        query = (
            select(Whale)
            .where(Whale.is_active == True)
            .where(
                # Active whales
                (Whale.data_status == "ACTIVE") |
                # Rate limited but cooldown passed
                (
                    (Whale.data_status == "RATE_LIMITED") &
                    (Whale.sharing_recheck_at <= now)
                )
            )
            .order_by(Whale.priority_score.desc())
            .limit(limit)
        )

        if exchange:
            query = query.where(Whale.exchange == exchange)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_sharing_statistics(
        self,
        db: AsyncSession,
    ) -> dict:
        """
        Get statistics about sharing status across exchanges.

        Returns dict with counts per exchange and status.
        """
        from sqlalchemy import func

        # Get counts by exchange and status
        result = await db.execute(
            select(
                Whale.exchange,
                Whale.data_status,
                func.count(Whale.id).label('count')
            )
            .where(Whale.is_active == True)
            .group_by(Whale.exchange, Whale.data_status)
        )

        stats = {}
        for row in result:
            exchange = row.exchange or "UNKNOWN"
            if exchange not in stats:
                stats[exchange] = {
                    "total": 0,
                    "active": 0,
                    "sharing_disabled": 0,
                    "rate_limited": 0,
                    "inactive": 0,
                }
            stats[exchange]["total"] += row.count
            # data_status is VARCHAR, so it's already a string
            status_key = (row.data_status or "ACTIVE").lower()
            if status_key in stats[exchange]:
                stats[exchange][status_key] = row.count

        # Calculate percentages
        for exchange, data in stats.items():
            total = data["total"]
            if total > 0:
                data["active_percent"] = round(data["active"] / total * 100, 1)
                data["disabled_percent"] = round(
                    data["sharing_disabled"] / total * 100, 1
                )

        return stats


# Singleton instance
_validator: SharingValidator | None = None


def get_sharing_validator() -> SharingValidator:
    """Get singleton SharingValidator instance."""
    global _validator
    if _validator is None:
        _validator = SharingValidator()
    return _validator
