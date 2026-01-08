"""
Wallet Manager Service
Handles cross-wallet transfers for trading operations.
Supports auto-transfer from spot to futures when needed.
"""

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


class WalletManager:
    """
    Manages cross-wallet transfers for trading.

    Supported operations:
    - Spot to USD-M Futures
    - Spot to COIN-M Futures
    - Futures back to Spot
    """

    # Transfer type mappings for each exchange
    TRANSFER_TYPES = {
        "binance": {
            "spot_to_usdm": "MAIN_UMFUTURE",
            "spot_to_coinm": "MAIN_CMFUTURE",
            "usdm_to_spot": "UMFUTURE_MAIN",
            "coinm_to_spot": "CMFUTURE_MAIN",
        },
        "okx": {
            # OKX uses unified account - transfer between 6 (funding) and 18 (trading)
            "spot_to_trading": {"from": "6", "to": "18"},
            "trading_to_spot": {"from": "18", "to": "6"},
        },
        "bitget": {
            "spot_to_futures": {"from": "spot", "to": "mix_usdt"},
            "futures_to_spot": {"from": "mix_usdt", "to": "spot"},
        },
    }

    # Default currencies for each wallet type
    DEFAULT_CURRENCIES = {
        "USD-M": "USDT",
        "COIN-M": "BTC",  # Could also be ETH for ETH margined
    }

    def __init__(self, executor: Any):
        """
        Initialize with an exchange executor.

        Args:
            executor: Exchange executor instance (BinanceExecutor, OKXExecutor, etc.)
        """
        self.executor = executor
        self.exchange = executor.name.lower() if hasattr(executor, 'name') else "binance"

    async def get_spot_balance(self, currency: str = "USDT") -> Decimal:
        """
        Get available balance in spot wallet.

        Args:
            currency: Currency to check (default USDT)

        Returns:
            Available balance
        """
        try:
            balances = await self.executor.get_account_balance()
            for balance in balances:
                if balance.asset.upper() == currency.upper():
                    return balance.free
            return Decimal("0")
        except Exception as e:
            logger.error(f"Error getting spot balance: {e}")
            return Decimal("0")

    async def get_futures_balance(
        self,
        currency: str = "USDT",
        futures_type: str = "USD-M",
    ) -> Decimal:
        """
        Get available balance in futures wallet.

        Args:
            currency: Currency to check
            futures_type: "USD-M" or "COIN-M"

        Returns:
            Available balance
        """
        try:
            if hasattr(self.executor, 'get_futures_balance'):
                balances = await self.executor.get_futures_balance(futures_type=futures_type)
                for balance in balances:
                    if balance.asset.upper() == currency.upper():
                        return balance.free
            return Decimal("0")
        except Exception as e:
            logger.error(f"Error getting futures balance: {e}")
            return Decimal("0")

    async def transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: Decimal,
        currency: str = "USDT",
    ) -> bool:
        """
        Transfer funds between wallets.

        Args:
            from_wallet: Source wallet ("spot", "usdm", "coinm")
            to_wallet: Destination wallet ("spot", "usdm", "coinm")
            amount: Amount to transfer
            currency: Currency to transfer

        Returns:
            True if transfer succeeded
        """
        if amount <= Decimal("0"):
            return False

        try:
            transfer_key = f"{from_wallet}_to_{to_wallet}"
            transfer_type = self.TRANSFER_TYPES.get(self.exchange, {}).get(transfer_key)

            if not transfer_type:
                logger.warning(
                    f"No transfer type found for {self.exchange}: {transfer_key}"
                )
                return False

            if self.exchange == "binance":
                return await self._transfer_binance(
                    transfer_type=transfer_type,
                    amount=amount,
                    currency=currency,
                )
            elif self.exchange == "okx":
                return await self._transfer_okx(
                    transfer_config=transfer_type,
                    amount=amount,
                    currency=currency,
                )
            elif self.exchange == "bitget":
                return await self._transfer_bitget(
                    transfer_config=transfer_type,
                    amount=amount,
                    currency=currency,
                )

            return False

        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            return False

    async def _transfer_binance(
        self,
        transfer_type: str,
        amount: Decimal,
        currency: str,
    ) -> bool:
        """Execute Binance universal transfer."""
        try:
            if hasattr(self.executor, 'client') and self.executor.client:
                client = self.executor.client
                result = await client.universal_transfer(
                    type=transfer_type,
                    asset=currency,
                    amount=str(amount),
                )
                logger.info(
                    f"Binance transfer success: {amount} {currency} ({transfer_type})"
                )
                return bool(result.get("tranId"))
            return False
        except Exception as e:
            logger.error(f"Binance transfer failed: {e}")
            return False

    async def _transfer_okx(
        self,
        transfer_config: dict,
        amount: Decimal,
        currency: str,
    ) -> bool:
        """Execute OKX internal transfer."""
        try:
            client = self.executor._ensure_client()
            result = await client.transfer(
                currency,
                str(amount),
                transfer_config["from"],
                transfer_config["to"],
            )
            logger.info(
                f"OKX transfer success: {amount} {currency} "
                f"({transfer_config['from']} -> {transfer_config['to']})"
            )
            return result.get("code") == "0"
        except Exception as e:
            logger.error(f"OKX transfer failed: {e}")
            return False

    async def _transfer_bitget(
        self,
        transfer_config: dict,
        amount: Decimal,
        currency: str,
    ) -> bool:
        """Execute Bitget internal transfer."""
        try:
            client = self.executor._ensure_client()
            result = await client.transfer(
                currency,
                str(amount),
                transfer_config["from"],
                transfer_config["to"],
            )
            logger.info(
                f"Bitget transfer success: {amount} {currency} "
                f"({transfer_config['from']} -> {transfer_config['to']})"
            )
            return result.get("code") == "0"
        except Exception as e:
            logger.error(f"Bitget transfer failed: {e}")
            return False

    async def ensure_futures_balance(
        self,
        required_amount: Decimal,
        currency: str = "USDT",
        futures_type: str = "USD-M",
        buffer_percent: Decimal = Decimal("10"),
    ) -> tuple[bool, str]:
        """
        Ensure futures wallet has sufficient balance.
        Auto-transfers from spot if needed.

        Args:
            required_amount: Amount needed in futures wallet
            currency: Currency to check/transfer
            futures_type: "USD-M" or "COIN-M"
            buffer_percent: Extra buffer to transfer (default 10%)

        Returns:
            Tuple of (success, message)
        """
        # Get current futures balance
        futures_balance = await self.get_futures_balance(currency, futures_type)

        if futures_balance >= required_amount:
            return True, f"Sufficient balance: {futures_balance} {currency}"

        # Calculate shortfall
        shortfall = required_amount - futures_balance
        # Add buffer
        transfer_amount = shortfall * (Decimal("1") + buffer_percent / Decimal("100"))

        # Check spot balance
        spot_balance = await self.get_spot_balance(currency)

        if spot_balance < transfer_amount:
            # Try to transfer what we can
            if spot_balance > Decimal("1"):  # Min 1 unit transfer
                transfer_amount = spot_balance * Decimal("0.95")  # Leave 5% buffer
            else:
                return False, (
                    f"Insufficient total balance. "
                    f"Futures: {futures_balance} {currency}, "
                    f"Spot: {spot_balance} {currency}, "
                    f"Required: {required_amount} {currency}"
                )

        # Determine transfer destination
        to_wallet = "usdm" if futures_type == "USD-M" else "coinm"

        # Execute transfer
        logger.info(
            f"Auto-transferring {transfer_amount} {currency} from spot to {to_wallet}"
        )

        success = await self.transfer(
            from_wallet="spot",
            to_wallet=to_wallet,
            amount=transfer_amount,
            currency=currency,
        )

        if success:
            return True, f"Transferred {transfer_amount} {currency} to {futures_type} wallet"
        else:
            return False, f"Transfer failed: {transfer_amount} {currency}"

    async def withdraw_to_spot(
        self,
        amount: Decimal,
        currency: str = "USDT",
        futures_type: str = "USD-M",
    ) -> bool:
        """
        Withdraw funds from futures wallet back to spot.

        Args:
            amount: Amount to withdraw
            currency: Currency to withdraw
            futures_type: "USD-M" or "COIN-M"

        Returns:
            True if successful
        """
        from_wallet = "usdm" if futures_type == "USD-M" else "coinm"

        return await self.transfer(
            from_wallet=from_wallet,
            to_wallet="spot",
            amount=amount,
            currency=currency,
        )


async def ensure_trading_balance(
    executor: Any,
    required_amount: Decimal,
    is_futures: bool = True,
    futures_type: str = "USD-M",
    currency: str = "USDT",
) -> tuple[bool, str]:
    """
    Convenience function to ensure sufficient trading balance.

    Args:
        executor: Exchange executor instance
        required_amount: Amount needed
        is_futures: Whether trading futures
        futures_type: "USD-M" or "COIN-M"
        currency: Currency needed

    Returns:
        Tuple of (success, message)
    """
    manager = WalletManager(executor)

    if is_futures:
        return await manager.ensure_futures_balance(
            required_amount=required_amount,
            currency=currency,
            futures_type=futures_type,
        )
    else:
        # For spot, just check balance
        spot_balance = await manager.get_spot_balance(currency)
        if spot_balance >= required_amount:
            return True, f"Sufficient spot balance: {spot_balance} {currency}"
        return False, f"Insufficient spot balance: {spot_balance} < {required_amount} {currency}"
