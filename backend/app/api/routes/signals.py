"""
Whale Signals API Routes
"""

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.models.signal import (
    SignalAction,
    SignalConfidence,
    SignalStatus,
    WhaleSignal,
)
from app.models.whale import Whale, WhaleStats, UserWhaleFollow

router = APIRouter()


class WhaleInfoResponse(BaseModel):
    id: int
    name: str
    wallet_address: str
    win_rate: Decimal | None = None
    avatar: str = "🐋"

    class Config:
        from_attributes = True


class SignalResponse(BaseModel):
    id: int
    whale: WhaleInfoResponse
    action: str
    token: str
    token_name: str
    token_address: str | None
    amount_usd: Decimal
    dex: str
    chain: str
    entry_price: Decimal | None
    cex_symbol: str | None
    cex_available: bool
    confidence: str
    confidence_score: Decimal
    tx_hash: str
    status: str
    detected_at: datetime
    auto_copy_in: int = 0  # Seconds until auto-copy (0 if already copied/skipped)

    class Config:
        from_attributes = True


@router.get("", response_model=list[SignalResponse])
async def list_signals(
    db: DbSession,
    current_user: OptionalUser = None,
    whale_id: int | None = None,
    action: SignalAction | None = None,
    status_filter: SignalStatus | None = None,
    confidence: SignalConfidence | None = None,
    hours: int = Query(24, ge=1, le=168),  # Default last 24 hours, max 7 days
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[SignalResponse]:
    """Get recent whale signals. Public endpoint."""
    # Get user's followed whale IDs (if authenticated)
    followed_whales = {}
    if current_user:
        follows_result = await db.execute(
            select(UserWhaleFollow.whale_id, UserWhaleFollow.auto_copy_enabled).where(
                UserWhaleFollow.user_id == current_user.id
            )
        )
        followed_whales = {row[0]: row[1] for row in follows_result.all()}

    if whale_id:
        # Filter by specific whale
        query = select(WhaleSignal).where(WhaleSignal.whale_id == whale_id)
    elif followed_whales:
        # Filter by followed whales
        query = select(WhaleSignal).where(WhaleSignal.whale_id.in_(list(followed_whales.keys())))
    else:
        # Return all public signals
        query = (
            select(WhaleSignal)
            .join(Whale)
            .where(Whale.is_public == True)
        )

    # Time filter
    since = datetime.utcnow() - timedelta(hours=hours)
    query = query.where(WhaleSignal.detected_at >= since)

    # Additional filters
    if action:
        query = query.where(WhaleSignal.action == action)
    if status_filter:
        query = query.where(WhaleSignal.status == status_filter)
    if confidence:
        query = query.where(WhaleSignal.confidence == confidence)

    # Order by most recent first
    query = query.order_by(WhaleSignal.detected_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    signals = result.scalars().all()

    # Build responses with whale info
    responses = []
    for signal in signals:
        # Get whale info
        whale_result = await db.execute(
            select(Whale).where(Whale.id == signal.whale_id)
        )
        whale = whale_result.scalar_one_or_none()

        # Get whale stats for win rate
        stats_result = await db.execute(
            select(WhaleStats.win_rate).where(WhaleStats.whale_id == signal.whale_id)
        )
        win_rate = stats_result.scalar()

        # Calculate auto_copy_in (10 seconds if pending and auto-copy enabled)
        auto_copy_in = 0
        if signal.status == SignalStatus.PENDING:
            if signal.whale_id in followed_whales and followed_whales[signal.whale_id]:
                seconds_since = (datetime.utcnow() - signal.detected_at).total_seconds()
                auto_copy_in = max(0, 10 - int(seconds_since))

        responses.append(
            SignalResponse(
                id=signal.id,
                whale=WhaleInfoResponse(
                    id=whale.id if whale else 0,
                    name=whale.name if whale else "Unknown",
                    wallet_address=whale.wallet_address if whale else "",
                    win_rate=win_rate,
                    avatar="🐋",
                ),
                action=signal.action.value,
                token=signal.token_out,
                token_name=signal.token_out,  # Could map to full name
                token_address=signal.token_out_address,
                amount_usd=signal.amount_usd,
                dex=signal.dex,
                chain=signal.chain,
                entry_price=signal.price_at_signal,
                cex_symbol=signal.cex_symbol,
                cex_available=signal.cex_available,
                confidence=signal.confidence.value,
                confidence_score=signal.confidence_score,
                tx_hash=signal.tx_hash,
                status=signal.status.value,
                detected_at=signal.detected_at,
                auto_copy_in=auto_copy_in,
            )
        )

    return responses


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: int,
    db: DbSession,
    current_user: OptionalUser = None,
) -> SignalResponse:
    """Get a specific signal's details."""
    result = await db.execute(
        select(WhaleSignal).where(WhaleSignal.id == signal_id)
    )
    signal = result.scalar_one_or_none()

    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )

    # Get whale info
    whale_result = await db.execute(
        select(Whale).where(Whale.id == signal.whale_id)
    )
    whale = whale_result.scalar_one_or_none()

    # Get whale stats for win rate
    stats_result = await db.execute(
        select(WhaleStats.win_rate).where(WhaleStats.whale_id == signal.whale_id)
    )
    win_rate = stats_result.scalar()

    return SignalResponse(
        id=signal.id,
        whale=WhaleInfoResponse(
            id=whale.id if whale else 0,
            name=whale.name if whale else "Unknown",
            wallet_address=whale.wallet_address if whale else "",
            win_rate=win_rate,
            avatar="🐋",
        ),
        action=signal.action.value,
        token=signal.token_out,
        token_name=signal.token_out,
        token_address=signal.token_out_address,
        amount_usd=signal.amount_usd,
        dex=signal.dex,
        chain=signal.chain,
        entry_price=signal.price_at_signal,
        cex_symbol=signal.cex_symbol,
        cex_available=signal.cex_available,
        confidence=signal.confidence.value,
        confidence_score=signal.confidence_score,
        tx_hash=signal.tx_hash,
        status=signal.status.value,
        detected_at=signal.detected_at,
        auto_copy_in=0,
    )


@router.post("/{signal_id}/copy", status_code=status.HTTP_202_ACCEPTED)
async def copy_signal(
    signal_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Manually copy a signal trade."""
    result = await db.execute(
        select(WhaleSignal).where(WhaleSignal.id == signal_id)
    )
    signal = result.scalar_one_or_none()

    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )

    if signal.status != SignalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signal already {signal.status.value.lower()}",
        )

    if not signal.cex_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token not available on supported CEX",
        )

    # TODO: Queue trade execution via Celery
    # For now, just mark as processed
    signal.status = SignalStatus.PROCESSED
    signal.processed_at = datetime.utcnow()
    await db.commit()

    return {
        "message": "Trade copy initiated",
        "signal_id": signal_id,
        "symbol": signal.cex_symbol,
    }


@router.post("/{signal_id}/skip", status_code=status.HTTP_200_OK)
async def skip_signal(
    signal_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Skip a signal (don't copy)."""
    result = await db.execute(
        select(WhaleSignal).where(WhaleSignal.id == signal_id)
    )
    signal = result.scalar_one_or_none()

    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )

    if signal.status != SignalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signal already {signal.status.value.lower()}",
        )

    signal.status = SignalStatus.EXPIRED
    signal.processed_at = datetime.utcnow()
    await db.commit()

    return {
        "message": "Signal skipped",
        "signal_id": signal_id,
    }
