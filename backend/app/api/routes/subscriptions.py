"""
Subscription API Routes
"""

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.config import SUBSCRIPTION_TIERS
from app.models.subscription import (
    Payment,
    PaymentMethod,
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.models.user import SubscriptionTier

router = APIRouter()


# Pydantic schemas
class TierInfo(BaseModel):
    name: str
    price_monthly: int
    whales_limit: int
    auto_copy: bool
    commission_rate: float
    futures_enabled: bool
    max_positions: int
    features: list[str]


class SubscriptionResponse(BaseModel):
    tier: str
    status: str
    price_monthly: Decimal
    current_period_start: datetime | None
    current_period_end: datetime | None
    auto_renew: bool
    cancelled_at: datetime | None

    class Config:
        from_attributes = True


class UpgradeRequest(BaseModel):
    tier: SubscriptionTier
    payment_method: PaymentMethod


class PaymentResponse(BaseModel):
    id: int
    amount: Decimal
    currency: str
    payment_method: str
    status: str
    description: str | None
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


@router.get("/tiers", response_model=list[TierInfo])
async def list_subscription_tiers() -> list[TierInfo]:
    """List all available subscription tiers."""
    return [
        TierInfo(
            name=tier_name,
            price_monthly=config["price_monthly"],
            whales_limit=config["whales_limit"],
            auto_copy=config["auto_copy"],
            commission_rate=config["commission_rate"],
            futures_enabled=config["futures_enabled"],
            max_positions=config["max_positions"],
            features=config["features"],
        )
        for tier_name, config in SUBSCRIPTION_TIERS.items()
    ]


@router.get("/current", response_model=SubscriptionResponse | None)
async def get_current_subscription(
    current_user: CurrentUser,
    db: DbSession,
) -> Subscription | None:
    """Get user's current subscription."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    return result.scalar_one_or_none()


@router.post("/upgrade", response_model=SubscriptionResponse)
async def upgrade_subscription(
    request: UpgradeRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> Subscription:
    """Upgrade or change subscription tier."""
    if request.tier == SubscriptionTier.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upgrade to FREE tier. Use /cancel instead.",
        )

    tier_config = SUBSCRIPTION_TIERS.get(request.tier.value)
    if not tier_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription tier",
        )

    # Get or create subscription
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()

    now = datetime.utcnow()
    period_end = now + timedelta(days=30)

    if not subscription:
        subscription = Subscription(
            user_id=current_user.id,
            tier=request.tier,
            status=SubscriptionStatus.ACTIVE,
            price_monthly=Decimal(str(tier_config["price_monthly"])),
            current_period_start=now,
            current_period_end=period_end,
            payment_method=request.payment_method,
        )
        db.add(subscription)
    else:
        subscription.tier = request.tier
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.price_monthly = Decimal(str(tier_config["price_monthly"]))
        subscription.current_period_start = now
        subscription.current_period_end = period_end
        subscription.payment_method = request.payment_method
        subscription.cancelled_at = None

    # Create payment record
    payment = Payment(
        subscription_id=subscription.id,
        user_id=current_user.id,
        amount=Decimal(str(tier_config["price_monthly"])),
        currency="USD",
        payment_method=request.payment_method,
        status=PaymentStatus.PENDING,
        description=f"Subscription upgrade to {request.tier.value}",
        period_start=now,
        period_end=period_end,
    )
    db.add(payment)

    # Update user's subscription tier
    current_user.subscription_tier = request.tier
    current_user.subscription_expires_at = period_end

    await db.commit()
    await db.refresh(subscription)

    # TODO: Process payment via Telegram Stars or Crypto
    # For now, auto-complete payment for demo
    payment.status = PaymentStatus.COMPLETED
    payment.completed_at = now
    await db.commit()

    return subscription


@router.post("/cancel")
async def cancel_subscription(
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Cancel subscription (will remain active until period end)."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )

    subscription.status = SubscriptionStatus.CANCELLED
    subscription.cancelled_at = datetime.utcnow()
    subscription.auto_renew = False

    await db.commit()

    return {
        "message": "Subscription cancelled",
        "active_until": subscription.current_period_end,
    }


@router.get("/payments", response_model=list[PaymentResponse])
async def list_payments(
    current_user: CurrentUser,
    db: DbSession,
) -> list[Payment]:
    """List user's payment history."""
    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
    )
    return list(result.scalars().all())
