"""
User API Routes
"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.api.deps import CurrentUser, DbSession
from app.models.user import (
    ExchangeName,
    TradingMode,
    User,
    UserAPIKey,
    UserSettings,
)
from app.utils.encryption import get_encryption_manager

router = APIRouter()


# Pydantic schemas
class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    total_balance: Decimal
    available_balance: Decimal
    subscription_tier: str
    subscription_expires_at: datetime | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserSettingsResponse(BaseModel):
    trading_mode: str
    preferred_exchange: str
    auto_copy_enabled: bool
    auto_copy_delay_seconds: int
    default_trade_size_usdt: Decimal
    max_trade_size_usdt: Decimal
    stop_loss_percent: Decimal
    take_profit_percent: Decimal | None
    daily_loss_limit_usdt: Decimal
    max_open_positions: int
    default_leverage: int
    max_leverage: int
    notify_whale_alerts: bool
    notify_trade_executed: bool
    notify_position_closed: bool
    notify_stop_loss_hit: bool

    class Config:
        from_attributes = True


class UpdateSettingsRequest(BaseModel):
    trading_mode: TradingMode | None = None
    preferred_exchange: ExchangeName | None = None
    auto_copy_enabled: bool | None = None
    auto_copy_delay_seconds: int | None = Field(None, ge=0, le=60)
    default_trade_size_usdt: Decimal | None = Field(None, gt=0)
    max_trade_size_usdt: Decimal | None = Field(None, gt=0)
    stop_loss_percent: Decimal | None = Field(None, ge=1, le=50)
    take_profit_percent: Decimal | None = Field(None, ge=1, le=500)
    daily_loss_limit_usdt: Decimal | None = Field(None, gt=0)
    max_open_positions: int | None = Field(None, ge=1, le=50)
    default_leverage: int | None = Field(None, ge=1, le=125)
    max_leverage: int | None = Field(None, ge=1, le=125)
    notify_whale_alerts: bool | None = None
    notify_trade_executed: bool | None = None
    notify_position_closed: bool | None = None
    notify_stop_loss_hit: bool | None = None


class APIKeyCreate(BaseModel):
    exchange: ExchangeName
    api_key: str = Field(..., min_length=10)
    api_secret: str = Field(..., min_length=10)
    passphrase: str | None = None  # OKX only
    label: str | None = None
    is_testnet: bool = False
    can_spot_trade: bool = True
    can_futures_trade: bool = False


class APIKeyResponse(BaseModel):
    id: int
    exchange: str
    label: str | None
    is_active: bool
    is_testnet: bool
    can_spot_trade: bool
    can_futures_trade: bool
    created_at: datetime
    last_used_at: datetime | None

    class Config:
        from_attributes = True


class UserStatsResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    total_profit: Decimal
    total_loss: Decimal
    net_pnl: Decimal
    active_positions: int
    whales_followed: int


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: CurrentUser) -> User:
    """Get the current user's profile."""
    return current_user


@router.get("/me/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    current_user: CurrentUser,
    db: DbSession,
) -> UserSettings:
    """Get the current user's settings."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # Create default settings
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return settings


@router.patch("/me/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    request: UpdateSettingsRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> UserSettings:
    """Update the current user's settings."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)

    # Update only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    await db.commit()
    await db.refresh(settings)
    return settings


@router.get("/me/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user: CurrentUser,
    db: DbSession,
) -> list[UserAPIKey]:
    """List all API keys for the current user."""
    result = await db.execute(
        select(UserAPIKey).where(UserAPIKey.user_id == current_user.id)
    )
    return list(result.scalars().all())


@router.post("/me/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def add_api_key(
    request: APIKeyCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> UserAPIKey:
    """Add a new exchange API key."""
    # Check for existing key for this exchange
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == current_user.id,
            UserAPIKey.exchange == request.exchange,
            UserAPIKey.is_active == True,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Active API key for {request.exchange} already exists",
        )

    # Encrypt credentials
    encryption = get_encryption_manager()

    api_key = UserAPIKey(
        user_id=current_user.id,
        exchange=request.exchange,
        api_key_encrypted=encryption.encrypt(request.api_key),
        api_secret_encrypted=encryption.encrypt(request.api_secret),
        passphrase_encrypted=encryption.encrypt(request.passphrase) if request.passphrase else None,
        label=request.label,
        is_testnet=request.is_testnet,
        can_spot_trade=request.can_spot_trade,
        can_futures_trade=request.can_futures_trade,
        can_withdraw=False,  # Never allow withdrawal
    )

    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key


@router.delete("/me/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete an API key."""
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.id == key_id,
            UserAPIKey.user_id == current_user.id,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    await db.delete(api_key)
    await db.commit()


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_user_stats(
    current_user: CurrentUser,
    db: DbSession,
) -> UserStatsResponse:
    """Get trading statistics for the current user."""
    from sqlalchemy import func

    from app.models.trade import Trade, TradeStatus
    from app.models.whale import UserWhaleFollow
    from app.models.trade import Position, PositionStatus

    # Get trade statistics
    trades_query = await db.execute(
        select(
            func.count(Trade.id).label("total"),
            func.sum(
                func.case(
                    (Trade.status == TradeStatus.FILLED, 1),
                    else_=0,
                )
            ).label("filled"),
        ).where(Trade.user_id == current_user.id)
    )
    trades_stats = trades_query.first()

    # Get PnL from positions
    pnl_query = await db.execute(
        select(
            func.sum(
                func.case(
                    (Position.realized_pnl > 0, Position.realized_pnl),
                    else_=Decimal("0"),
                )
            ).label("total_profit"),
            func.sum(
                func.case(
                    (Position.realized_pnl < 0, func.abs(Position.realized_pnl)),
                    else_=Decimal("0"),
                )
            ).label("total_loss"),
            func.sum(
                func.case(
                    (Position.realized_pnl > 0, 1),
                    else_=0,
                )
            ).label("winning"),
            func.sum(
                func.case(
                    (Position.realized_pnl < 0, 1),
                    else_=0,
                )
            ).label("losing"),
        ).where(
            Position.user_id == current_user.id,
            Position.status == PositionStatus.CLOSED,
        )
    )
    pnl_stats = pnl_query.first()

    # Get active positions count
    active_positions_query = await db.execute(
        select(func.count(Position.id)).where(
            Position.user_id == current_user.id,
            Position.status == PositionStatus.OPEN,
        )
    )
    active_positions = active_positions_query.scalar() or 0

    # Get followed whales count
    whales_query = await db.execute(
        select(func.count(UserWhaleFollow.id)).where(
            UserWhaleFollow.user_id == current_user.id
        )
    )
    whales_followed = whales_query.scalar() or 0

    total_profit = pnl_stats.total_profit or Decimal("0")
    total_loss = pnl_stats.total_loss or Decimal("0")
    winning_trades = pnl_stats.winning or 0
    losing_trades = pnl_stats.losing or 0
    total_trades = winning_trades + losing_trades

    win_rate = (
        (Decimal(winning_trades) / Decimal(total_trades) * 100)
        if total_trades > 0
        else Decimal("0")
    )

    return UserStatsResponse(
        total_trades=trades_stats.total or 0,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate.quantize(Decimal("0.01")),
        total_profit=total_profit,
        total_loss=total_loss,
        net_pnl=total_profit - total_loss,
        active_positions=active_positions,
        whales_followed=whales_followed,
    )
