"""WhaleFollowRepository Port - interface для getting whale followers.

Це PORT в Hexagonal Architecture (domain визначає interface).
Infrastructure layer має implement цей interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class WhaleFollow:
    """DTO для whale follower.

    Represents a user following a whale with auto-copy settings.
    """

    user_id: int
    whale_id: int
    auto_copy_enabled: bool
    copy_trade_size_usdt: Decimal
    max_leverage: int
    exchange_name: str


class WhaleFollowRepository(ABC):
    """Abstract interface для whale follow persistence.

    Infrastructure layer implements цей interface з SQLAlchemy.
    Domain layer uses цей interface (Dependency Inversion).

    Example (Infrastructure implements):
        >>> class SQLAlchemyWhaleFollowRepository(WhaleFollowRepository):
        ...     async def get_active_followers(self, whale_id: int) -> list[WhaleFollow]:
        ...         # Query DB for followers with auto_copy_enabled=True
        ...         models = await self.session.execute(
        ...             select(UserWhaleFollowModel)
        ...             .where(whale_id=whale_id, auto_copy_enabled=True)
        ...         )
        ...         return [self.mapper.to_dto(model) for model in models]

    Example (Domain uses):
        >>> # Handler не знає про SQLAlchemy
        >>> followers = await whale_follow_repo.get_active_followers(whale_id)
        >>> for follower in followers:
        ...     await execute_copy_trade(follower.user_id, signal)
    """

    @abstractmethod
    async def get_active_followers(self, whale_id: int) -> list[WhaleFollow]:
        """Get all active followers of a whale.

        Args:
            whale_id: Whale ID.

        Returns:
            List of WhaleFollow DTOs with auto_copy_enabled=True.

        Note:
            Використовується ProcessSignalHandler для copying trades.
        """
        pass

    @abstractmethod
    async def is_following(self, user_id: int, whale_id: int) -> bool:
        """Check if user is following whale.

        Args:
            user_id: User ID.
            whale_id: Whale ID.

        Returns:
            True якщо user follows whale, False otherwise.
        """
        pass

    @abstractmethod
    async def get_follow_settings(
        self, user_id: int, whale_id: int
    ) -> WhaleFollow | None:
        """Get follow settings for user-whale pair.

        Args:
            user_id: User ID.
            whale_id: Whale ID.

        Returns:
            WhaleFollow DTO або None якщо user не follows whale.
        """
        pass
