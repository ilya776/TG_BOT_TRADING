"""SQLAlchemyWhaleFollowRepository - implements WhaleFollowRepository port.

Infrastructure implementation of domain WhaleFollowRepository interface.
"""

from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain.whales.repositories import WhaleFollow, WhaleFollowRepository
from app.infrastructure.persistence.sqlalchemy.models.whale_follow_model import (
    UserModel,
    UserWhaleFollowModel,
    WhaleModel,
)


class SQLAlchemyWhaleFollowRepository(WhaleFollowRepository):
    """SQLAlchemy implementation of WhaleFollowRepository.

    Example:
        >>> async with async_session() as session:
        ...     repo = SQLAlchemyWhaleFollowRepository(session)
        ...     followers = await repo.get_active_followers(whale_id=123)
        ...     for follower in followers:
        ...         print(f"User {follower.user_id} copies {follower.copy_trade_size_usdt} USDT")
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def get_active_followers(self, whale_id: int) -> list[WhaleFollow]:
        """Get all active followers of a whale with auto_copy enabled.

        Args:
            whale_id: Whale ID.

        Returns:
            List of WhaleFollow DTOs with copy settings.

        Note:
            Joins user_whale_follows with users to get complete settings.
            Returns only followers with:
            - auto_copy_enabled = True
            - user.copy_trading_enabled = True (global user setting)
        """
        stmt = (
            select(UserWhaleFollowModel)
            .options(joinedload(UserWhaleFollowModel.user))
            .where(
                and_(
                    UserWhaleFollowModel.whale_id == whale_id,
                    UserWhaleFollowModel.auto_copy_enabled == True,
                )
            )
        )

        result = await self._session.execute(stmt)
        follows = result.unique().scalars().all()

        # Map to WhaleFollow DTOs
        whale_follows = []
        for follow in follows:
            user = follow.user

            # Skip if user has copy trading disabled globally
            if not user.copy_trading_enabled:
                continue

            # Determine trade size (follow-specific or default)
            copy_trade_size_usdt = follow.trade_size_usdt
            if copy_trade_size_usdt is None:
                # TODO: Could calculate from trade_size_percent * balance
                # For now, skip followers without explicit size
                continue

            # Determine exchange (follow mode override or user preference)
            exchange_name = user.preferred_exchange.value.lower()

            whale_follow = WhaleFollow(
                user_id=follow.user_id,
                whale_id=follow.whale_id,
                auto_copy_enabled=follow.auto_copy_enabled,
                copy_trade_size_usdt=copy_trade_size_usdt,
                max_leverage=user.max_leverage,
                exchange_name=exchange_name,
            )
            whale_follows.append(whale_follow)

        return whale_follows

    async def is_following(self, user_id: int, whale_id: int) -> bool:
        """Check if user is following whale.

        Args:
            user_id: User ID.
            whale_id: Whale ID.

        Returns:
            True if user follows whale, False otherwise.
        """
        stmt = select(UserWhaleFollowModel.id).where(
            and_(
                UserWhaleFollowModel.user_id == user_id,
                UserWhaleFollowModel.whale_id == whale_id,
            )
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_follow_settings(
        self, user_id: int, whale_id: int
    ) -> WhaleFollow | None:
        """Get follow settings for user-whale pair.

        Args:
            user_id: User ID.
            whale_id: Whale ID.

        Returns:
            WhaleFollow DTO or None if user doesn't follow whale.
        """
        stmt = (
            select(UserWhaleFollowModel)
            .options(joinedload(UserWhaleFollowModel.user))
            .where(
                and_(
                    UserWhaleFollowModel.user_id == user_id,
                    UserWhaleFollowModel.whale_id == whale_id,
                )
            )
        )

        result = await self._session.execute(stmt)
        follow = result.unique().scalar_one_or_none()

        if follow is None:
            return None

        user = follow.user

        return WhaleFollow(
            user_id=follow.user_id,
            whale_id=follow.whale_id,
            auto_copy_enabled=follow.auto_copy_enabled,
            copy_trade_size_usdt=follow.trade_size_usdt or Decimal("0"),
            max_leverage=user.max_leverage,
            exchange_name=user.preferred_exchange.value.lower(),
        )

    async def get_followers_count(self, whale_id: int) -> int:
        """Get count of followers for a whale.

        Args:
            whale_id: Whale ID.

        Returns:
            Number of followers (with auto_copy enabled).
        """
        stmt = (
            select(UserWhaleFollowModel)
            .where(
                and_(
                    UserWhaleFollowModel.whale_id == whale_id,
                    UserWhaleFollowModel.auto_copy_enabled == True,
                )
            )
        )

        result = await self._session.execute(stmt)
        follows = result.scalars().all()
        return len(follows)

    async def increment_trades_copied(
        self, user_id: int, whale_id: int, profit: Decimal = Decimal("0")
    ) -> None:
        """Increment trades_copied counter and add profit.

        Args:
            user_id: User ID.
            whale_id: Whale ID.
            profit: Profit from the trade (can be negative for losses).
        """
        stmt = select(UserWhaleFollowModel).where(
            and_(
                UserWhaleFollowModel.user_id == user_id,
                UserWhaleFollowModel.whale_id == whale_id,
            )
        )

        result = await self._session.execute(stmt)
        follow = result.scalar_one_or_none()

        if follow:
            follow.trades_copied += 1
            follow.total_profit += profit
