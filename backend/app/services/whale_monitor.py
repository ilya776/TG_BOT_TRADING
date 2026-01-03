"""
Whale Monitor Service
Monitors on-chain transactions from whale wallets and generates trading signals
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import AsyncWeb3
from web3.providers import WebsocketProviderV2

from app.config import get_settings
from app.database import get_db_context
from app.models.signal import SignalAction, SignalConfidence, SignalStatus, WhaleSignal
from app.models.whale import Whale, WhaleChain
from app.services.dex_parsers.uniswap import UniswapParser
from app.services.dex_parsers.pancakeswap import PancakeSwapParser
from app.services.dex_parsers.sushiswap import SushiSwapParser

settings = get_settings()
logger = logging.getLogger(__name__)

# Minimum transaction size to consider (in USD)
MIN_SIGNAL_SIZE_USD = Decimal("10000")

# Token to CEX symbol mapping
TOKEN_TO_CEX_SYMBOL = {
    "PEPE": "PEPEUSDT",
    "SHIB": "SHIBUSDT",
    "ARB": "ARBUSDT",
    "OP": "OPUSDT",
    "MATIC": "MATICUSDT",
    "LINK": "LINKUSDT",
    "UNI": "UNIUSDT",
    "AAVE": "AAVEUSDT",
    "CRV": "CRVUSDT",
    "MKR": "MKRUSDT",
    "SNX": "SNXUSDT",
    "COMP": "COMPUSDT",
    "SUSHI": "SUSHIUSDT",
    "1INCH": "1INCHUSDT",
    "LDO": "LDOUSDT",
    "APE": "APEUSDT",
    "DYDX": "DYDXUSDT",
    "GMX": "GMXUSDT",
    "BLUR": "BLURUSDT",
    "WLD": "WLDUSDT",
}


@dataclass
class MonitoredWallet:
    """A wallet being monitored."""

    id: int
    address: str
    name: str
    chain: WhaleChain


class WhaleMonitor:
    """
    Monitors whale wallet transactions on DEXes and generates trading signals.

    Uses WebSocket connections to blockchain nodes for real-time monitoring.
    """

    def __init__(self):
        self.eth_web3: AsyncWeb3 | None = None
        self.bsc_web3: AsyncWeb3 | None = None
        self.redis: redis.Redis | None = None

        self._running = False
        self._monitored_wallets: dict[str, MonitoredWallet] = {}
        self._signal_handlers: list[Callable] = []

        # Parsers
        self._eth_uniswap_parser: UniswapParser | None = None
        self._eth_sushi_parser: SushiSwapParser | None = None
        self._bsc_pancake_parser: PancakeSwapParser | None = None
        self._bsc_sushi_parser: SushiSwapParser | None = None

    async def initialize(self) -> None:
        """Initialize connections and load monitored wallets."""
        logger.info("Initializing Whale Monitor...")

        # Connect to Ethereum
        if settings.eth_rpc_ws_url:
            try:
                self.eth_web3 = AsyncWeb3(
                    WebsocketProviderV2(settings.eth_rpc_ws_url)
                )
                logger.info("Connected to Ethereum WebSocket")
            except Exception as e:
                logger.warning(f"Failed to connect to Ethereum WS: {e}")
                # Fall back to HTTP
                self.eth_web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(settings.eth_rpc_url))

        # Connect to BSC
        if settings.bsc_rpc_ws_url:
            try:
                self.bsc_web3 = AsyncWeb3(
                    WebsocketProviderV2(settings.bsc_rpc_ws_url)
                )
                logger.info("Connected to BSC WebSocket")
            except Exception as e:
                logger.warning(f"Failed to connect to BSC WS: {e}")
                self.bsc_web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(settings.bsc_rpc_url))

        # Connect to Redis
        self.redis = redis.from_url(settings.redis_url)

        # Initialize parsers
        if self.eth_web3:
            self._eth_uniswap_parser = UniswapParser(self.eth_web3)
            self._eth_sushi_parser = SushiSwapParser(self.eth_web3, chain="ethereum")

        if self.bsc_web3:
            self._bsc_pancake_parser = PancakeSwapParser(self.bsc_web3)
            self._bsc_sushi_parser = SushiSwapParser(self.bsc_web3, chain="bsc")

        # Load monitored wallets from database
        await self._load_monitored_wallets()

        logger.info(f"Monitoring {len(self._monitored_wallets)} whale wallets")

    async def _load_monitored_wallets(self) -> None:
        """Load active whale wallets from database."""
        async with get_db_context() as db:
            result = await db.execute(
                select(Whale).where(Whale.is_active == True)
            )
            whales = result.scalars().all()

            for whale in whales:
                self._monitored_wallets[whale.wallet_address.lower()] = MonitoredWallet(
                    id=whale.id,
                    address=whale.wallet_address.lower(),
                    name=whale.name,
                    chain=whale.chain,
                )

    async def close(self) -> None:
        """Close connections."""
        self._running = False
        if self.redis:
            await self.redis.close()

    def add_signal_handler(self, handler: Callable) -> None:
        """Add a handler to be called when a signal is detected."""
        self._signal_handlers.append(handler)

    async def start_monitoring(self) -> None:
        """Start monitoring whale wallets."""
        self._running = True
        logger.info("Starting whale monitoring...")

        # Start monitoring tasks for each chain
        tasks = []

        if self.eth_web3:
            tasks.append(asyncio.create_task(self._monitor_chain(WhaleChain.ETHEREUM)))

        if self.bsc_web3:
            tasks.append(asyncio.create_task(self._monitor_chain(WhaleChain.BSC)))

        # Run all monitoring tasks
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _monitor_chain(self, chain: WhaleChain) -> None:
        """Monitor transactions on a specific chain."""
        web3 = self.eth_web3 if chain == WhaleChain.ETHEREUM else self.bsc_web3
        if not web3:
            return

        logger.info(f"Starting {chain.value} chain monitoring...")

        while self._running:
            try:
                # Get pending transactions from mempool
                # Note: This requires a node with mempool access (e.g., Alchemy)
                await self._poll_pending_transactions(chain, web3)
                await asyncio.sleep(settings.whale_monitor_interval_seconds)

            except Exception as e:
                logger.error(f"Error monitoring {chain.value}: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def _poll_pending_transactions(
        self,
        chain: WhaleChain,
        web3: AsyncWeb3,
    ) -> None:
        """Poll for pending transactions from monitored wallets."""
        # Get wallets for this chain
        chain_wallets = [
            w for w in self._monitored_wallets.values()
            if w.chain == chain
        ]

        if not chain_wallets:
            return

        # Check latest block for whale transactions
        try:
            block = await web3.eth.get_block("latest", full_transactions=True)

            for tx in block.get("transactions", []):
                sender = tx.get("from", "").lower()

                if sender in self._monitored_wallets:
                    await self._process_transaction(chain, tx)

        except Exception as e:
            logger.error(f"Error getting block: {e}")

    async def _process_transaction(
        self,
        chain: WhaleChain,
        tx: dict[str, Any],
    ) -> None:
        """Process a transaction from a monitored wallet."""
        sender = tx.get("from", "").lower()
        wallet = self._monitored_wallets.get(sender)

        if not wallet:
            return

        # Parse the transaction using appropriate parser
        swap_info = await self._parse_swap(chain, tx)

        if not swap_info:
            return  # Not a swap transaction

        # Check minimum size
        if swap_info.amount_usd < MIN_SIGNAL_SIZE_USD:
            return

        # Check if token is available on CEX
        cex_symbol = self._get_cex_symbol(swap_info.token_out if swap_info.action == "BUY" else swap_info.token_in)

        # Determine confidence based on whale history and trade size
        confidence = self._calculate_confidence(wallet, swap_info)

        # Create signal
        signal = await self._create_signal(
            whale_id=wallet.id,
            tx=tx,
            chain=chain,
            swap_info=swap_info,
            cex_symbol=cex_symbol,
            confidence=confidence,
        )

        if signal:
            # Notify handlers
            for handler in self._signal_handlers:
                try:
                    await handler(signal)
                except Exception as e:
                    logger.error(f"Signal handler error: {e}")

            # Publish to Redis for real-time updates
            await self._publish_signal(signal)

    async def _parse_swap(
        self,
        chain: WhaleChain,
        tx: dict[str, Any],
    ) -> Any | None:
        """Parse a transaction using the appropriate DEX parser."""
        if chain == WhaleChain.ETHEREUM:
            # Try Uniswap first
            if self._eth_uniswap_parser:
                result = self._eth_uniswap_parser.parse_transaction(tx)
                if result:
                    return result

            # Try SushiSwap
            if self._eth_sushi_parser:
                result = self._eth_sushi_parser.parse_transaction(tx)
                if result:
                    return result

        elif chain == WhaleChain.BSC:
            # Try PancakeSwap first
            if self._bsc_pancake_parser:
                result = self._bsc_pancake_parser.parse_transaction(tx)
                if result:
                    return result

            # Try SushiSwap
            if self._bsc_sushi_parser:
                result = self._bsc_sushi_parser.parse_transaction(tx)
                if result:
                    return result

        return None

    def _get_cex_symbol(self, token: str) -> str | None:
        """Get CEX trading symbol for a token."""
        token = token.upper()
        return TOKEN_TO_CEX_SYMBOL.get(token)

    def _calculate_confidence(
        self,
        wallet: MonitoredWallet,
        swap_info: Any,
    ) -> SignalConfidence:
        """Calculate signal confidence based on various factors."""
        score = Decimal("50")

        # Size-based scoring
        if swap_info.amount_usd >= Decimal("100000"):
            score += Decimal("30")
        elif swap_info.amount_usd >= Decimal("50000"):
            score += Decimal("20")
        elif swap_info.amount_usd >= Decimal("25000"):
            score += Decimal("10")

        # TODO: Add whale historical performance scoring
        # This would require loading whale stats and adjusting score

        if score >= Decimal("80"):
            return SignalConfidence.VERY_HIGH
        elif score >= Decimal("65"):
            return SignalConfidence.HIGH
        elif score >= Decimal("50"):
            return SignalConfidence.MEDIUM
        else:
            return SignalConfidence.LOW

    async def _create_signal(
        self,
        whale_id: int,
        tx: dict[str, Any],
        chain: WhaleChain,
        swap_info: Any,
        cex_symbol: str | None,
        confidence: SignalConfidence,
    ) -> WhaleSignal | None:
        """Create and store a whale signal."""
        async with get_db_context() as db:
            # Check if signal already exists (by tx hash)
            tx_hash = tx.get("hash", "").hex() if hasattr(tx.get("hash", ""), "hex") else str(tx.get("hash", ""))

            existing = await db.execute(
                select(WhaleSignal).where(WhaleSignal.tx_hash == tx_hash)
            )
            if existing.scalar_one_or_none():
                return None  # Already processed

            signal = WhaleSignal(
                whale_id=whale_id,
                tx_hash=tx_hash,
                block_number=tx.get("blockNumber", 0),
                chain=chain.value,
                action=SignalAction.BUY if swap_info.action == "BUY" else SignalAction.SELL,
                dex=swap_info.dex,
                token_in=swap_info.token_in,
                token_in_address=swap_info.token_in_address,
                token_in_amount=swap_info.token_in_amount,
                token_out=swap_info.token_out,
                token_out_address=swap_info.token_out_address,
                token_out_amount=swap_info.token_out_amount,
                amount_usd=swap_info.amount_usd,
                cex_symbol=cex_symbol,
                cex_available=cex_symbol is not None,
                confidence=confidence,
                confidence_score=Decimal("75") if confidence == SignalConfidence.HIGH else Decimal("50"),
                status=SignalStatus.PENDING,
                gas_price_gwei=Decimal(str(tx.get("gasPrice", 0))) / Decimal("1e9"),
                gas_used=tx.get("gas"),
                raw_data=json.dumps({
                    "from": tx.get("from", ""),
                    "to": tx.get("to", ""),
                    "value": str(tx.get("value", 0)),
                }),
            )

            db.add(signal)
            await db.commit()
            await db.refresh(signal)

            logger.info(
                f"New signal: Whale #{whale_id} {swap_info.action} {swap_info.token_out} "
                f"for ${swap_info.amount_usd:.2f} on {swap_info.dex}"
            )

            return signal

    async def _publish_signal(self, signal: WhaleSignal) -> None:
        """Publish signal to Redis for real-time subscribers."""
        if not self.redis:
            return

        try:
            signal_data = {
                "id": signal.id,
                "whale_id": signal.whale_id,
                "action": signal.action.value,
                "token_out": signal.token_out,
                "amount_usd": str(signal.amount_usd),
                "cex_symbol": signal.cex_symbol,
                "confidence": signal.confidence.value,
                "dex": signal.dex,
            }

            await self.redis.publish(
                "whale_signals",
                json.dumps(signal_data),
            )
        except Exception as e:
            logger.error(f"Failed to publish signal: {e}")


# Entry point for running as standalone service
async def main():
    """Main entry point for whale monitor service."""
    monitor = WhaleMonitor()
    await monitor.initialize()

    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("Shutting down whale monitor...")
    finally:
        await monitor.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
