"""Whale API Routes.

Whale listing, following, and copy trading configuration.
"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.infrastructure.persistence.sqlalchemy.models import (
    Whale,
    WhaleChain,
    WhaleRank,
    WhaleStats,
    UserWhaleFollow,
)
from app.presentation.api.deps import CurrentUser, DbSession, OptionalUser

router = APIRouter(prefix="/whales", tags=["Whales"])

# Subscription tier limits
SUBSCRIPTION_TIERS = {
    "FREE": {"whales_limit": 1, "auto_copy": False},
    "PRO": {"whales_limit": 5, "auto_copy": True},
    "ELITE": {"whales_limit": -1, "auto_copy": True},  # -1 = unlimited
}


# ============================================================================
# SCHEMAS
# ============================================================================


class WhaleResponse(BaseModel):
    id: int
    name: str
    wallet_address: str
    chain: str
    description: str | None
    tags: str | None
    rank: str
    score: Decimal
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class WhaleStatsResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    total_volume_usd: Decimal
    total_profit_usd: Decimal
    avg_profit_percent: Decimal
    avg_loss_percent: Decimal
    max_drawdown_percent: Decimal
    avg_holding_hours: Decimal
    trades_per_week: Decimal
    profit_7d: Decimal
    profit_30d: Decimal
    profit_90d: Decimal
    last_trade_at: datetime | None

    class Config:
        from_attributes = True


class WhaleWithStatsResponse(WhaleResponse):
    stats: WhaleStatsResponse | None
    is_following: bool = False
    followers_count: int = 0


class WhaleFollowResponse(BaseModel):
    id: int
    whale_id: int
    whale_name: str
    auto_copy_enabled: bool
    trade_size_usdt: Decimal | None
    trade_size_percent: Decimal | None
    trading_mode_override: str | None
    notify_on_trade: bool
    trades_copied: int
    total_profit: Decimal
    followed_at: datetime

    class Config:
        from_attributes = True


class FollowWhaleRequest(BaseModel):
    auto_copy_enabled: bool = False
    trade_size_usdt: Decimal | None = Field(None, gt=0)
    trade_size_percent: Decimal | None = Field(None, gt=0, le=100)
    trading_mode_override: str | None = None
    notify_on_trade: bool = True


class UpdateFollowRequest(BaseModel):
    auto_copy_enabled: bool | None = None
    trade_size_usdt: Decimal | None = Field(None, gt=0)
    trade_size_percent: Decimal | None = Field(None, gt=0, le=100)
    trading_mode_override: str | None = None
    notify_on_trade: bool | None = None


# ============================================================================
# ROUTES
# ============================================================================


@router.get("", response_model=list[WhaleWithStatsResponse])
async def list_whales(
    db: DbSession,
    current_user: OptionalUser = None,
    chain: WhaleChain | None = None,
    rank: WhaleRank | None = None,
    search: str | None = None,
    sort_by: str = Query("score", enum=["score", "win_rate", "profit_7d", "profit_30d"]),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[WhaleWithStatsResponse]:
    """List available whales with optional filtering. Public endpoint."""
    query = select(Whale).where(Whale.is_active == True, Whale.is_public == True)

    if chain:
        query = query.where(Whale.chain == chain)
    if rank:
        query = query.where(Whale.rank == rank)
    if search:
        query = query.where(
            (Whale.name.ilike(f"%{search}%"))
            | (Whale.wallet_address.ilike(f"%{search}%"))
            | (Whale.tags.ilike(f"%{search}%"))
        )

    # Sorting
    if sort_by == "score":
        query = query.order_by(Whale.score.desc())
    elif sort_by in ["win_rate", "profit_7d", "profit_30d"]:
        query = query.join(WhaleStats).order_by(
            getattr(WhaleStats, sort_by).desc()
        )
    else:
        query = query.order_by(Whale.score.desc())

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    whales = result.scalars().all()

    # Get user's followed whales (if authenticated)
    followed_ids = set()
    if current_user:
        follows_result = await db.execute(
            select(UserWhaleFollow.whale_id).where(
                UserWhaleFollow.user_id == current_user.id
            )
        )
        followed_ids = {row[0] for row in follows_result.all()}

    # Batch load followers count
    whale_ids = [w.id for w in whales]
    followers_query = await db.execute(
        select(
            UserWhaleFollow.whale_id,
            func.count(UserWhaleFollow.id).label("count"),
        )
        .where(UserWhaleFollow.whale_id.in_(whale_ids))
        .group_by(UserWhaleFollow.whale_id)
    )
    followers_counts = {row[0]: row[1] for row in followers_query.all()}

    # Batch load all stats
    stats_result = await db.execute(
        select(WhaleStats).where(WhaleStats.whale_id.in_(whale_ids))
    )
    stats_map = {s.whale_id: s for s in stats_result.scalars().all()}

    # Build response
    responses = []
    for whale in whales:
        stats = stats_map.get(whale.id)

        responses.append(
            WhaleWithStatsResponse(
                id=whale.id,
                name=whale.name,
                wallet_address=whale.wallet_address,
                chain=whale.chain.value,
                description=whale.description,
                tags=whale.tags,
                rank=whale.rank.value,
                score=whale.score,
                is_verified=whale.is_verified,
                created_at=whale.created_at,
                stats=WhaleStatsResponse.model_validate(stats) if stats else None,
                is_following=whale.id in followed_ids,
                followers_count=followers_counts.get(whale.id, 0),
            )
        )

    return responses


@router.get("/leaderboard", response_model=list[WhaleWithStatsResponse])
async def get_whale_leaderboard(
    db: DbSession,
    current_user: OptionalUser = None,
    period: str = Query("7d", enum=["7d", "30d", "90d", "all"]),
    limit: int = Query(10, ge=1, le=50),
) -> list[WhaleWithStatsResponse]:
    """Get top performing whales. Public endpoint."""
    profit_field = {
        "7d": WhaleStats.profit_7d,
        "30d": WhaleStats.profit_30d,
        "90d": WhaleStats.profit_90d,
        "all": WhaleStats.total_profit_usd,
    }[period]

    query = (
        select(Whale)
        .join(WhaleStats)
        .where(Whale.is_active == True, Whale.is_public == True)
        .order_by(profit_field.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    whales = result.scalars().all()

    # Same batch loading as list_whales
    followed_ids = set()
    if current_user:
        follows_result = await db.execute(
            select(UserWhaleFollow.whale_id).where(
                UserWhaleFollow.user_id == current_user.id
            )
        )
        followed_ids = {row[0] for row in follows_result.all()}

    whale_ids = [w.id for w in whales]
    stats_result = await db.execute(
        select(WhaleStats).where(WhaleStats.whale_id.in_(whale_ids))
    )
    stats_map = {s.whale_id: s for s in stats_result.scalars().all()}

    followers_query = await db.execute(
        select(
            UserWhaleFollow.whale_id,
            func.count(UserWhaleFollow.id).label("count"),
        )
        .where(UserWhaleFollow.whale_id.in_(whale_ids))
        .group_by(UserWhaleFollow.whale_id)
    )
    followers_counts = {row[0]: row[1] for row in followers_query.all()}

    responses = []
    for whale in whales:
        stats = stats_map.get(whale.id)
        responses.append(
            WhaleWithStatsResponse(
                id=whale.id,
                name=whale.name,
                wallet_address=whale.wallet_address,
                chain=whale.chain.value,
                description=whale.description,
                tags=whale.tags,
                rank=whale.rank.value,
                score=whale.score,
                is_verified=whale.is_verified,
                created_at=whale.created_at,
                stats=WhaleStatsResponse.model_validate(stats) if stats else None,
                is_following=whale.id in followed_ids,
                followers_count=followers_counts.get(whale.id, 0),
            )
        )

    return responses


@router.get("/me/following", response_model=list[WhaleFollowResponse])
async def get_followed_whales(
    current_user: CurrentUser,
    db: DbSession,
) -> list[WhaleFollowResponse]:
    """Get all whales the user is following."""
    result = await db.execute(
        select(UserWhaleFollow, Whale.name)
        .join(Whale)
        .where(UserWhaleFollow.user_id == current_user.id)
    )
    follows = result.all()

    return [
        WhaleFollowResponse(
            id=follow.id,
            whale_id=follow.whale_id,
            whale_name=whale_name,
            auto_copy_enabled=follow.auto_copy_enabled,
            trade_size_usdt=follow.trade_size_usdt,
            trade_size_percent=follow.trade_size_percent,
            trading_mode_override=follow.trading_mode_override,
            notify_on_trade=follow.notify_on_trade,
            trades_copied=follow.trades_copied,
            total_profit=follow.total_profit,
            followed_at=follow.followed_at,
        )
        for follow, whale_name in follows
    ]


@router.get("/{whale_id}", response_model=WhaleWithStatsResponse)
async def get_whale(
    whale_id: int,
    db: DbSession,
    current_user: OptionalUser = None,
) -> WhaleWithStatsResponse:
    """Get a specific whale's details. Public endpoint."""
    result = await db.execute(select(Whale).where(Whale.id == whale_id))
    whale = result.scalar_one_or_none()

    if not whale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Whale not found",
        )

    # Get stats
    stats_result = await db.execute(
        select(WhaleStats).where(WhaleStats.whale_id == whale_id)
    )
    stats = stats_result.scalar_one_or_none()

    # Check if following
    is_following = False
    if current_user:
        follow_result = await db.execute(
            select(UserWhaleFollow).where(
                UserWhaleFollow.user_id == current_user.id,
                UserWhaleFollow.whale_id == whale_id,
            )
        )
        is_following = follow_result.scalar_one_or_none() is not None

    # Get followers count
    followers_query = await db.execute(
        select(func.count(UserWhaleFollow.id)).where(
            UserWhaleFollow.whale_id == whale_id
        )
    )
    followers_count = followers_query.scalar() or 0

    return WhaleWithStatsResponse(
        id=whale.id,
        name=whale.name,
        wallet_address=whale.wallet_address,
        chain=whale.chain.value,
        description=whale.description,
        tags=whale.tags,
        rank=whale.rank.value,
        score=whale.score,
        is_verified=whale.is_verified,
        created_at=whale.created_at,
        stats=WhaleStatsResponse.model_validate(stats) if stats else None,
        is_following=is_following,
        followers_count=followers_count,
    )


@router.post("/{whale_id}/follow", response_model=WhaleFollowResponse, status_code=status.HTTP_201_CREATED)
async def follow_whale(
    whale_id: int,
    request: FollowWhaleRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> WhaleFollowResponse:
    """Follow a whale to copy their trades."""
    # Check whale exists
    whale_result = await db.execute(select(Whale).where(Whale.id == whale_id))
    whale = whale_result.scalar_one_or_none()

    if not whale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Whale not found",
        )

    # Check if already following
    existing = await db.execute(
        select(UserWhaleFollow).where(
            UserWhaleFollow.user_id == current_user.id,
            UserWhaleFollow.whale_id == whale_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already following this whale",
        )

    # Check whale limit based on subscription
    tier_config = SUBSCRIPTION_TIERS.get(current_user.subscription_tier.value, {})
    whale_limit = tier_config.get("whales_limit", 1)

    if whale_limit > 0:  # -1 means unlimited
        follows_count = await db.execute(
            select(func.count(UserWhaleFollow.id)).where(
                UserWhaleFollow.user_id == current_user.id
            )
        )
        current_count = follows_count.scalar() or 0

        if current_count >= whale_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Whale limit reached ({whale_limit}). Upgrade subscription for more.",
            )

    # Check auto-copy permission
    if request.auto_copy_enabled and not tier_config.get("auto_copy", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auto-copy requires PRO subscription or higher",
        )

    follow = UserWhaleFollow(
        user_id=current_user.id,
        whale_id=whale_id,
        auto_copy_enabled=request.auto_copy_enabled,
        trade_size_usdt=request.trade_size_usdt,
        trade_size_percent=request.trade_size_percent,
        trading_mode_override=request.trading_mode_override,
        notify_on_trade=request.notify_on_trade,
    )

    db.add(follow)
    await db.commit()
    await db.refresh(follow)

    return WhaleFollowResponse(
        id=follow.id,
        whale_id=whale.id,
        whale_name=whale.name,
        auto_copy_enabled=follow.auto_copy_enabled,
        trade_size_usdt=follow.trade_size_usdt,
        trade_size_percent=follow.trade_size_percent,
        trading_mode_override=follow.trading_mode_override,
        notify_on_trade=follow.notify_on_trade,
        trades_copied=follow.trades_copied,
        total_profit=follow.total_profit,
        followed_at=follow.followed_at,
    )


@router.patch("/{whale_id}/follow", response_model=WhaleFollowResponse)
async def update_follow(
    whale_id: int,
    request: UpdateFollowRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> WhaleFollowResponse:
    """Update follow settings for a whale."""
    result = await db.execute(
        select(UserWhaleFollow).where(
            UserWhaleFollow.user_id == current_user.id,
            UserWhaleFollow.whale_id == whale_id,
        )
    )
    follow = result.scalar_one_or_none()

    if not follow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not following this whale",
        )

    # Check auto-copy permission if enabling
    if request.auto_copy_enabled:
        tier_config = SUBSCRIPTION_TIERS.get(current_user.subscription_tier.value, {})
        if not tier_config.get("auto_copy", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Auto-copy requires PRO subscription or higher",
            )

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(follow, field, value)

    await db.commit()
    await db.refresh(follow)

    # Get whale name
    whale_result = await db.execute(
        select(Whale.name).where(Whale.id == whale_id)
    )
    whale_name = whale_result.scalar()

    return WhaleFollowResponse(
        id=follow.id,
        whale_id=follow.whale_id,
        whale_name=whale_name,
        auto_copy_enabled=follow.auto_copy_enabled,
        trade_size_usdt=follow.trade_size_usdt,
        trade_size_percent=follow.trade_size_percent,
        trading_mode_override=follow.trading_mode_override,
        notify_on_trade=follow.notify_on_trade,
        trades_copied=follow.trades_copied,
        total_profit=follow.total_profit,
        followed_at=follow.followed_at,
    )


@router.delete("/{whale_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_whale(
    whale_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Unfollow a whale."""
    result = await db.execute(
        select(UserWhaleFollow).where(
            UserWhaleFollow.user_id == current_user.id,
            UserWhaleFollow.whale_id == whale_id,
        )
    )
    follow = result.scalar_one_or_none()

    if not follow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not following this whale",
        )

    await db.delete(follow)
    await db.commit()
