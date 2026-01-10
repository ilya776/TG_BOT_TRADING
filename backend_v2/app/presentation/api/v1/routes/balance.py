"""Balance API Routes.

Exchange balance management and synchronization.
"""

import json
import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.infrastructure.encryption import get_encryption_manager
from app.infrastructure.persistence.sqlalchemy.models import (
    ExchangeName,
    User,
    UserAPIKey,
    UserExchangeBalance,
)
from app.presentation.api.deps import CurrentUser, DbSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/balance", tags=["Balance"])


# ============================================================================
# SCHEMAS
# ============================================================================


class AssetBalance(BaseModel):
    symbol: str
    quantity: str
    value_usdt: str


class ExchangeBalanceResponse(BaseModel):
    exchange: str
    connected: bool
    spot_total: str
    spot_available: str
    futures_total: str
    futures_available: str
    futures_unrealized_pnl: str
    spot_assets: list[AssetBalance]
    futures_assets: list[AssetBalance]
    last_sync: str | None
    error: str | None


class AllBalancesResponse(BaseModel):
    total_usdt: str
    available_usdt: str
    exchanges: list[ExchangeBalanceResponse]


# ============================================================================
# ROUTES
# ============================================================================


@router.get("/", response_model=AllBalancesResponse)
async def get_all_balances(
    current_user: CurrentUser,
    db: DbSession,
):
    """Get balances for all connected exchanges."""
    # Get all exchange balances for user
    result = await db.execute(
        select(UserExchangeBalance).where(
            UserExchangeBalance.user_id == current_user.id
        )
    )
    balances = result.scalars().all()

    # Get all API keys to know which exchanges are connected
    keys_result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == current_user.id,
            UserAPIKey.is_active == True,
        )
    )
    api_keys = keys_result.scalars().all()
    connected_exchanges = {key.exchange.value for key in api_keys}

    exchanges = []
    total_usdt = Decimal("0")
    available_usdt = Decimal("0")

    # Build response for each exchange
    for exchange_name in ExchangeName:
        balance = next(
            (b for b in balances if b.exchange == exchange_name),
            None
        )

        if balance:
            spot_assets = []
            futures_assets = []

            if balance.spot_assets:
                try:
                    assets = json.loads(balance.spot_assets)
                    spot_assets = [
                        AssetBalance(
                            symbol=a.get("symbol", ""),
                            quantity=str(a.get("quantity", "0")),
                            value_usdt=str(a.get("value_usdt", "0")),
                        )
                        for a in assets
                    ]
                except json.JSONDecodeError:
                    pass

            if balance.futures_assets:
                try:
                    assets = json.loads(balance.futures_assets)
                    futures_assets = [
                        AssetBalance(
                            symbol=a.get("symbol", ""),
                            quantity=str(a.get("quantity", "0")),
                            value_usdt=str(a.get("value_usdt", "0")),
                        )
                        for a in assets
                    ]
                except json.JSONDecodeError:
                    pass

            exchanges.append(
                ExchangeBalanceResponse(
                    exchange=exchange_name.value,
                    connected=exchange_name.value in connected_exchanges,
                    spot_total=str(balance.spot_total_usdt),
                    spot_available=str(balance.spot_available_usdt),
                    futures_total=str(balance.futures_total_usdt),
                    futures_available=str(balance.futures_available_usdt),
                    futures_unrealized_pnl=str(balance.futures_unrealized_pnl),
                    spot_assets=spot_assets,
                    futures_assets=futures_assets,
                    last_sync=balance.synced_at.isoformat() if balance.synced_at else None,
                    error=balance.last_sync_error,
                )
            )

            total_usdt += balance.total_usdt
            available_usdt += balance.available_usdt
        else:
            exchanges.append(
                ExchangeBalanceResponse(
                    exchange=exchange_name.value,
                    connected=exchange_name.value in connected_exchanges,
                    spot_total="0",
                    spot_available="0",
                    futures_total="0",
                    futures_available="0",
                    futures_unrealized_pnl="0",
                    spot_assets=[],
                    futures_assets=[],
                    last_sync=None,
                    error=None,
                )
            )

    return AllBalancesResponse(
        total_usdt=str(total_usdt),
        available_usdt=str(available_usdt),
        exchanges=exchanges,
    )


@router.post("/{exchange}/sync")
async def sync_exchange_balance(
    exchange: str,
    current_user: CurrentUser,
    db: DbSession,
):
    """Manually sync balance for a specific exchange.

    Note: Full implementation requires exchange adapters from infrastructure layer.
    This is a placeholder that updates the balance record.
    """
    # Validate exchange
    try:
        exchange_enum = ExchangeName(exchange.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid exchange: {exchange}")

    # Get API key for this exchange
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == current_user.id,
            UserAPIKey.exchange == exchange_enum,
            UserAPIKey.is_active == True,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=404,
            detail=f"No active API key found for {exchange}"
        )

    # Get or create balance record
    balance_result = await db.execute(
        select(UserExchangeBalance).where(
            UserExchangeBalance.user_id == current_user.id,
            UserExchangeBalance.exchange == exchange_enum,
        )
    )
    balance = balance_result.scalar_one_or_none()

    if not balance:
        balance = UserExchangeBalance(
            user_id=current_user.id,
            exchange=exchange_enum,
        )
        db.add(balance)

    # TODO: Implement actual balance sync using exchange adapters
    # from app.infrastructure.exchanges import get_exchange_executor
    # encryption = get_encryption_manager()
    # decrypted_key = encryption.decrypt(api_key.api_key_encrypted)
    # decrypted_secret = encryption.decrypt(api_key.api_secret_encrypted)
    # executor = get_exchange_executor(exchange_enum.value.lower(), ...)
    # balances = await executor.get_account_balance()

    # For now, just update the sync timestamp
    balance.synced_at = datetime.utcnow()
    balance.is_connected = True

    await db.commit()
    await db.refresh(balance)

    return {
        "status": "success",
        "exchange": exchange,
        "spot_total": str(balance.spot_total_usdt),
        "futures_total": str(balance.futures_total_usdt),
        "synced_at": balance.synced_at.isoformat(),
        "note": "Balance sync placeholder - implement with exchange adapters",
    }
