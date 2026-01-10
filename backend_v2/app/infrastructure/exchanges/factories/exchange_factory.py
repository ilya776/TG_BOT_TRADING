"""Exchange Factory - creates exchange adapters based on configuration.

Factory Pattern для створення правильного adapter на основі exchange name.
"""

import logging
from enum import Enum
from typing import Any

from app.domain.exchanges.ports import ExchangePort
from app.infrastructure.exchanges.adapters import BinanceAdapter, BitgetAdapter, BybitAdapter

logger = logging.getLogger(__name__)


class ExchangeName(str, Enum):
    """Supported exchanges."""

    BINANCE = "binance"
    BYBIT = "bybit"
    BITGET = "bitget"


class ExchangeFactory:
    """Factory для створення exchange adapters.

    Example:
        >>> factory = ExchangeFactory()
        >>> 
        >>> # Create Binance adapter
        >>> adapter = factory.create_exchange(
        ...     exchange_name="binance",
        ...     api_key="key",
        ...     api_secret="secret",
        ...     testnet=True
        ... )
        >>> 
        >>> # Create Bybit adapter
        >>> adapter = factory.create_exchange(
        ...     exchange_name="bybit",
        ...     api_key="key",
        ...     api_secret="secret",
        ... )
        >>> 
        >>> # Create Bitget adapter (requires passphrase)
        >>> adapter = factory.create_exchange(
        ...     exchange_name="bitget",
        ...     api_key="key",
        ...     api_secret="secret",
        ...     passphrase="pass",
        ... )
    """

    def create_exchange(
        self,
        exchange_name: str,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        enable_rate_limit: bool = True,
        **extra_params: Any,
    ) -> ExchangePort:
        """Create exchange adapter based on name.

        Args:
            exchange_name: Exchange name ("binance", "bybit", "bitget").
            api_key: API key.
            api_secret: API secret.
            testnet: Use testnet (default: False).
            enable_rate_limit: Enable rate limiting (default: True).
            **extra_params: Extra parameters (e.g., passphrase for Bitget).

        Returns:
            Exchange adapter implementing ExchangePort.

        Raises:
            ValueError: If exchange_name not supported.

        Example:
            >>> factory = ExchangeFactory()
            >>> adapter = factory.create_exchange("binance", "key", "secret")
            >>> await adapter.initialize()
        """
        exchange_name = exchange_name.lower()

        logger.info(
            "exchange_factory.creating",
            extra={"exchange": exchange_name, "testnet": testnet},
        )

        if exchange_name == ExchangeName.BINANCE:
            return BinanceAdapter(
                api_key=api_key,
                api_secret=api_secret,
                testnet=testnet,
                enable_rate_limit=enable_rate_limit,
            )

        elif exchange_name == ExchangeName.BYBIT:
            return BybitAdapter(
                api_key=api_key,
                api_secret=api_secret,
                testnet=testnet,
                enable_rate_limit=enable_rate_limit,
            )

        elif exchange_name == ExchangeName.BITGET:
            # Bitget requires passphrase
            passphrase = extra_params.get("passphrase")
            if not passphrase:
                raise ValueError("Bitget requires 'passphrase' parameter")

            return BitgetAdapter(
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase,
                testnet=testnet,
                enable_rate_limit=enable_rate_limit,
            )

        else:
            supported = ", ".join([e.value for e in ExchangeName])
            raise ValueError(
                f"Unsupported exchange: {exchange_name}. Supported exchanges: {supported}"
            )

    def is_supported(self, exchange_name: str) -> bool:
        """Check if exchange is supported.

        Args:
            exchange_name: Exchange name to check.

        Returns:
            True if supported, False otherwise.
        """
        try:
            ExchangeName(exchange_name.lower())
            return True
        except ValueError:
            return False

    def get_supported_exchanges(self) -> list[str]:
        """Get list of supported exchanges.

        Returns:
            List of supported exchange names.
        """
        return [e.value for e in ExchangeName]
