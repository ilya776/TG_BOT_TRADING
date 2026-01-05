"""
Balance API Routes
"""

import json
import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.user import ExchangeName, UserAPIKey, UserExchangeBalance
from app.services.exchanges import get_exchange_executor
from app.utils.encryption import get_encryption_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/balance", tags=["balance"])


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
    """Manually sync balance for a specific exchange."""
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

    # Decrypt credentials
    encryption = get_encryption_manager()
    decrypted_key = encryption.decrypt(api_key.api_key_encrypted)
    decrypted_secret = encryption.decrypt(api_key.api_secret_encrypted)
    decrypted_passphrase = None
    if api_key.passphrase_encrypted:
        decrypted_passphrase = encryption.decrypt(api_key.passphrase_encrypted)

    # Initialize exchange executor
    try:
        executor = get_exchange_executor(
            exchange_name=exchange_enum.value.lower(),
            api_key=decrypted_key,
            api_secret=decrypted_secret,
            passphrase=decrypted_passphrase,
            testnet=api_key.is_testnet,
        )
        await executor.initialize()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to {exchange}: {str(e)}"
        )

    try:
        # Fetch spot balances
        spot_balances = await executor.get_account_balance()
        spot_assets = []
        spot_total = Decimal("0")
        spot_available = Decimal("0")

        # Stablecoins that are already in USDT equivalent
        stablecoins = ("USDT", "BUSD", "USDC", "TUSD", "FDUSD", "USD")

        for balance in spot_balances:
            value_usdt = Decimal("0")
            price_usdt = Decimal("1")

            if balance.total > 0:
                if balance.asset in stablecoins:
                    # Stablecoins are 1:1 with USD
                    value_usdt = balance.total
                else:
                    # Convert other assets to USDT using current price
                    try:
                        price = await executor.get_ticker_price(f"{balance.asset}USDT")
                        if price:
                            price_usdt = Decimal(str(price))
                            value_usdt = balance.total * price_usdt
                    except Exception:
                        # Try BUSD pair as fallback
                        try:
                            price = await executor.get_ticker_price(f"{balance.asset}BUSD")
                            if price:
                                price_usdt = Decimal(str(price))
                                value_usdt = balance.total * price_usdt
                        except Exception:
                            logger.debug(f"Could not convert {balance.asset} to USDT")

            spot_total += value_usdt
            spot_available += balance.free * price_usdt

            if value_usdt > Decimal("0.01"):  # Filter dust
                spot_assets.append({
                    "symbol": balance.asset,
                    "quantity": str(balance.total),
                    "value_usdt": str(value_usdt),
                })

        # Try to fetch futures balances
        futures_total = Decimal("0")
        futures_available = Decimal("0")
        futures_pnl = Decimal("0")
        futures_assets = []
        futures_error = None

        try:
            futures_balances = await executor.get_futures_balance()
            for balance in futures_balances:
                value_usdt = Decimal(str(balance.get("balance", 0)))
                futures_total += value_usdt
                futures_available += Decimal(str(balance.get("available", 0)))
                futures_pnl += Decimal(str(balance.get("unrealized_pnl", 0)))

                if value_usdt > Decimal("0.01"):
                    futures_assets.append({
                        "symbol": balance.get("asset", "USDT"),
                        "quantity": str(balance.get("balance", 0)),
                        "value_usdt": str(value_usdt),
                    })
        except Exception as e:
            futures_error = str(e)
            logger.warning(f"Failed to get futures balance for {exchange}: {e}")

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

        # Update balance record
        balance.spot_total_usdt = spot_total
        balance.spot_available_usdt = spot_available
        balance.futures_total_usdt = futures_total
        balance.futures_available_usdt = futures_available
        balance.futures_unrealized_pnl = futures_pnl
        balance.spot_assets = json.dumps(spot_assets)
        balance.futures_assets = json.dumps(futures_assets)
        balance.is_connected = True
        balance.synced_at = datetime.utcnow()
        balance.last_sync_error = futures_error

        # Also update user's total balance
        all_balances = await db.execute(
            select(UserExchangeBalance).where(
                UserExchangeBalance.user_id == current_user.id
            )
        )
        total = sum(b.total_usdt for b in all_balances.scalars().all())
        current_user.total_balance = total
        current_user.available_balance = total  # Simplified

        await db.commit()
        await db.refresh(balance)

        return {
            "status": "success",
            "exchange": exchange,
            "spot_total": str(spot_total),
            "futures_total": str(futures_total),
            "synced_at": balance.synced_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Balance sync failed for {exchange}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync balance: {str(e)}"
        )
    finally:
        await executor.close()
