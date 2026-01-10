"""
Adaptive Polling Scheduler
Dynamically schedules whale position polling based on priority tiers.

Tiers:
- CRITICAL (15s): Followed whales with recent activity
- HIGH (30s): Bitget traders (always public), high-score whales
- NORMAL (60s): Most active whales
- LOW (5min): Low activity, low score whales
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.whale import Whale, UserWhaleFollow

logger = logging.getLogger(__name__)


class PollingTier(str, Enum):
    """Polling frequency tiers."""
    CRITICAL = "critical"  # 15s - followed + recent activity
    HIGH = "high"          # 30s - Bitget, high-score
    NORMAL = "normal"      # 60s - most whales
    LOW = "low"            # 300s - low activity


# Tier configuration - ULTRA LOW-LATENCY POLLING
# Critical tier: Small batch (10) + fast polling (2s) = ~100ms detection
TIER_CONFIG = {
    PollingTier.CRITICAL: {
        "interval_seconds": 2,
        "max_whales": 10,  # Small batch for fast iteration
        "description": "Followed whales - ULTRA FAST",
    },
    PollingTier.HIGH: {
        "interval_seconds": 5,
        "max_whales": 50,  # Reduced to prevent DB exhaustion
        "description": "Bitget (always public) and high-score whales",
    },
    PollingTier.NORMAL: {
        "interval_seconds": 15,
        "max_whales": 100,
        "description": "Standard active whales",
    },
    PollingTier.LOW: {
        "interval_seconds": 60,
        "max_whales": 200,
        "description": "Low activity whales",
    },
}


class AdaptivePollingScheduler:
    """
    Schedules whale polling with adaptive priority-based tiers.

    Assigns whales to tiers based on:
    - Whether they're being followed by users
    - Exchange (Bitget = higher priority - always public)
    - Recent signal activity
    - Overall score
    """

    async def get_whales_for_tier(
        self,
        db: AsyncSession,
        tier: PollingTier,
    ) -> list[Whale]:
        """
        Get whales that should be polled in this tier.

        Args:
            db: Database session
            tier: Polling tier

        Returns:
            List of whales to poll
        """
        config = TIER_CONFIG[tier]
        limit = config["max_whales"]

        if tier == PollingTier.CRITICAL:
            return await self._get_critical_whales(db, limit)
        elif tier == PollingTier.HIGH:
            return await self._get_high_priority_whales(db, limit)
        elif tier == PollingTier.NORMAL:
            return await self._get_normal_whales(db, limit)
        else:  # LOW
            return await self._get_low_priority_whales(db, limit)

    async def _get_critical_whales(
        self,
        db: AsyncSession,
        limit: int,
    ) -> list[Whale]:
        """
        CRITICAL tier: Followed whales with recent activity.

        Criteria:
        - Being followed by users with notify_on_trade=True
        - Has had signals in the last hour
        - ACTIVE data status
        """
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        result = await db.execute(
            select(Whale)
            .join(UserWhaleFollow, Whale.id == UserWhaleFollow.whale_id)
            .where(
                Whale.is_active == True,
                Whale.data_status == "ACTIVE",
                UserWhaleFollow.notify_on_trade == True,
                # Prefer whales with recent positions
                or_(
                    Whale.last_position_found >= one_hour_ago,
                    Whale.last_position_found.is_(None),  # Never checked
                )
            )
            .distinct()
            .order_by(
                Whale.last_position_found.desc().nulls_last(),
                Whale.priority_score.desc(),
            )
            .limit(limit)
        )

        return list(result.scalars().all())

    async def _get_high_priority_whales(
        self,
        db: AsyncSession,
        limit: int,
    ) -> list[Whale]:
        """
        HIGH tier: Bitget traders and high-score whales.

        Criteria:
        - Exchange = BITGET (always public positions)
        - OR priority_score >= 70
        - ACTIVE data status
        - Not in CRITICAL tier (not followed)
        """
        # Get IDs of followed whales (to exclude)
        followed_result = await db.execute(
            select(UserWhaleFollow.whale_id)
            .where(UserWhaleFollow.notify_on_trade == True)
            .distinct()
        )
        followed_ids = {row[0] for row in followed_result}

        result = await db.execute(
            select(Whale)
            .where(
                Whale.is_active == True,
                Whale.data_status == "ACTIVE",
                or_(
                    Whale.exchange == "BITGET",  # Bitget always public
                    Whale.priority_score >= 70,
                ),
                # Exclude followed whales (they're in CRITICAL tier)
                ~Whale.id.in_(followed_ids) if followed_ids else True,
            )
            .order_by(
                # Bitget first (always public)
                (Whale.exchange == "BITGET").desc(),
                Whale.priority_score.desc(),
            )
            .limit(limit)
        )

        return list(result.scalars().all())

    async def _get_normal_whales(
        self,
        db: AsyncSession,
        limit: int,
    ) -> list[Whale]:
        """
        NORMAL tier: Standard active whales.

        Criteria:
        - priority_score between 40 and 70
        - ACTIVE data status
        - Not in CRITICAL or HIGH tiers
        """
        # Get IDs of followed whales
        followed_result = await db.execute(
            select(UserWhaleFollow.whale_id)
            .where(UserWhaleFollow.notify_on_trade == True)
            .distinct()
        )
        followed_ids = {row[0] for row in followed_result}

        result = await db.execute(
            select(Whale)
            .where(
                Whale.is_active == True,
                Whale.data_status == "ACTIVE",
                Whale.priority_score >= 40,
                Whale.priority_score < 70,
                Whale.exchange != "BITGET",  # Bitget in HIGH tier
                ~Whale.id.in_(followed_ids) if followed_ids else True,
            )
            .order_by(Whale.priority_score.desc())
            .limit(limit)
        )

        return list(result.scalars().all())

    async def _get_low_priority_whales(
        self,
        db: AsyncSession,
        limit: int,
    ) -> list[Whale]:
        """
        LOW tier: Low activity, low score whales.

        Criteria:
        - priority_score < 40
        - ACTIVE data status
        - Not in other tiers
        """
        followed_result = await db.execute(
            select(UserWhaleFollow.whale_id)
            .where(UserWhaleFollow.notify_on_trade == True)
            .distinct()
        )
        followed_ids = {row[0] for row in followed_result}

        result = await db.execute(
            select(Whale)
            .where(
                Whale.is_active == True,
                Whale.data_status == "ACTIVE",
                Whale.priority_score < 40,
                ~Whale.id.in_(followed_ids) if followed_ids else True,
            )
            .order_by(Whale.priority_score.desc())
            .limit(limit)
        )

        return list(result.scalars().all())

    async def recalculate_whale_priorities(
        self,
        db: AsyncSession,
    ) -> int:
        """
        Recalculate priority scores for all whales.

        Factors:
        - Exchange (Bitget = +30, OKX = +20, Binance = 0)
        - Number of followers (more = higher)
        - Recent activity (traded recently = higher)
        - Signal success rate
        - ROI score

        Returns number of whales updated.
        """
        result = await db.execute(
            select(Whale)
            .where(Whale.is_active == True)
        )
        whales = list(result.scalars().all())

        updated = 0
        for whale in whales:
            new_score = await self._calculate_priority_score(db, whale)

            if whale.priority_score != new_score:
                whale.priority_score = new_score
                updated += 1

        await db.commit()
        logger.info(f"Recalculated priorities for {updated} whales")

        return updated

    async def _calculate_priority_score(
        self,
        db: AsyncSession,
        whale: Whale,
    ) -> int:
        """Calculate priority score for a whale."""
        score = 50  # Base score

        # Exchange bonus (Bitget always public)
        if whale.exchange == "BITGET":
            score += 30
        elif whale.exchange == "OKX":
            score += 20
        elif whale.exchange == "BYBIT":
            score += 10
        # Binance = no bonus (40-60% closed)

        # Follower count bonus
        follower_count = await db.scalar(
            select(func.count(UserWhaleFollow.id))
            .where(UserWhaleFollow.whale_id == whale.id)
        )
        if follower_count:
            if follower_count >= 10:
                score += 15
            elif follower_count >= 5:
                score += 10
            elif follower_count >= 1:
                score += 5

        # Recent activity bonus
        if whale.last_position_found:
            hours_since = (datetime.utcnow() - whale.last_position_found).total_seconds() / 3600
            if hours_since < 1:
                score += 15
            elif hours_since < 6:
                score += 10
            elif hours_since < 24:
                score += 5

        # ROI score bonus (whale.score is 0-100 based on ROI)
        if whale.score:
            score += int(float(whale.score) * 0.1)  # Up to +10

        # Cap at 100
        return min(100, max(1, score))

    async def get_tier_statistics(
        self,
        db: AsyncSession,
    ) -> dict:
        """Get statistics about whale distribution across tiers."""
        stats = {}

        for tier in PollingTier:
            whales = await self.get_whales_for_tier(db, tier)
            config = TIER_CONFIG[tier]

            # Count by exchange
            exchange_counts = {}
            for w in whales:
                ex = w.exchange or "UNKNOWN"
                exchange_counts[ex] = exchange_counts.get(ex, 0) + 1

            stats[tier.value] = {
                "count": len(whales),
                "max": config["max_whales"],
                "interval_seconds": config["interval_seconds"],
                "by_exchange": exchange_counts,
            }

        return stats


# Singleton instance
_scheduler: Optional[AdaptivePollingScheduler] = None


def get_polling_scheduler() -> AdaptivePollingScheduler:
    """Get singleton AdaptivePollingScheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AdaptivePollingScheduler()
    return _scheduler
