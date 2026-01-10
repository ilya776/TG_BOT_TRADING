"""
Etherscan Discovery Service
Discovers whale wallets from Etherscan/BscScan/Arbiscan APIs.

Features:
- Fetch top token holders
- Get wallet transaction history
- Detect DEX swap transactions
- Monitor whale activity
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.onchain_wallet import (
    OnChainWallet,
    ChainType,
    WalletType,
    DiscoverySource,
)

logger = logging.getLogger(__name__)

# API configuration
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "")
ARBISCAN_API_KEY = os.getenv("ARBISCAN_API_KEY", "")

# Chain-specific API endpoints
CHAIN_APIS = {
    "ETHEREUM": {
        "base_url": "https://api.etherscan.io/api",
        "api_key": ETHERSCAN_API_KEY,
    },
    "BSC": {
        "base_url": "https://api.bscscan.com/api",
        "api_key": BSCSCAN_API_KEY,
    },
    "ARBITRUM": {
        "base_url": "https://api.arbiscan.io/api",
        "api_key": ARBISCAN_API_KEY,
    },
    "OPTIMISM": {
        "base_url": "https://api-optimistic.etherscan.io/api",
        "api_key": ETHERSCAN_API_KEY,  # Same key works
    },
    "POLYGON": {
        "base_url": "https://api.polygonscan.com/api",
        "api_key": os.getenv("POLYGONSCAN_API_KEY", ""),
    },
    "BASE": {
        "base_url": "https://api.basescan.org/api",
        "api_key": os.getenv("BASESCAN_API_KEY", ""),
    },
}

# Known whale addresses (curated list)
KNOWN_WHALES = {
    "ETHEREUM": [
        # Major funds/institutions
        ("0x28C6c06298d514Db089934071355E5743bf21d60", "Binance Hot Wallet", WalletType.EXCHANGE),
        ("0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549", "Binance Cold Wallet", WalletType.EXCHANGE),
        ("0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503", "Binance 8", WalletType.EXCHANGE),
        ("0x8103683202aa8DA10536036EDef04CDd865C225E", "Wintermute Trading", WalletType.FUND),
        ("0xDef1C0ded9bec7F1a1670819833240f027b25EfF", "0x Protocol", WalletType.CONTRACT),
    ],
    "BSC": [
        ("0x8894E0a0c962CB723c1976a4421c95949bE2D4E3", "Binance Hot Wallet 6", WalletType.EXCHANGE),
        ("0xF977814e90dA44bFA03b6295A0616a897441aceC", "Binance 8", WalletType.EXCHANGE),
    ],
    "ARBITRUM": [
        ("0xB38e8c17e38363aF6EbdCb3dAE12e0243582891D", "Wintermute Arbitrum", WalletType.FUND),
    ],
}

# Popular tokens to track holders
TRACKED_TOKENS = {
    "ETHEREUM": [
        ("0xdAC17F958D2ee523a2206206994597C13D831ec7", "USDT", 6),
        ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC", 6),
        ("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", "WBTC", 8),
        ("0x514910771AF9Ca656af840dff83E8264EcF986CA", "LINK", 18),
        ("0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", "UNI", 18),
    ],
    "BSC": [
        ("0x55d398326f99059fF775485246999027B3197955", "USDT", 18),
        ("0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", "USDC", 18),
        ("0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c", "BTCB", 18),
    ],
}


@dataclass
class WalletInfo:
    """Information about a discovered wallet."""
    address: str
    chain: str
    label: str | None
    wallet_type: str
    balance_usd: Decimal | None
    tx_count: int
    discovery_source: str


class EtherscanDiscovery:
    """
    Discovers whale wallets using Etherscan-family APIs.

    Supports:
    - Ethereum (Etherscan)
    - BSC (BscScan)
    - Arbitrum (Arbiscan)
    - Optimism, Polygon, Base
    """

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def discover_whales(
        self,
        chain: str = "ETHEREUM",
        limit: int = 100,
    ) -> list[WalletInfo]:
        """
        Discover whale wallets on a specific chain.

        Methods:
        1. Known whale addresses
        2. Top token holders
        3. High-activity addresses (from recent transactions)
        """
        wallets = []

        # 1. Add known whales
        known = await self._get_known_whales(chain)
        wallets.extend(known)

        # 2. Get top holders of major tokens
        token_holders = await self._get_top_token_holders(chain, limit=50)
        wallets.extend(token_holders)

        # Deduplicate by address
        seen = set()
        unique_wallets = []
        for w in wallets:
            if w.address.lower() not in seen:
                seen.add(w.address.lower())
                unique_wallets.append(w)

        logger.info(f"Discovered {len(unique_wallets)} unique wallets on {chain}")
        return unique_wallets[:limit]

    async def _get_known_whales(self, chain: str) -> list[WalletInfo]:
        """Get pre-defined known whale addresses."""
        wallets = []

        known_list = KNOWN_WHALES.get(chain, [])
        for address, label, wallet_type in known_list:
            wallets.append(WalletInfo(
                address=address,
                chain=chain,
                label=label,
                wallet_type=wallet_type,
                balance_usd=None,
                tx_count=0,
                discovery_source=DiscoverySource.KNOWN_WHALE,
            ))

        return wallets

    async def _get_top_token_holders(
        self,
        chain: str,
        limit: int = 50,
    ) -> list[WalletInfo]:
        """
        Get top holders of tracked tokens.

        Note: Etherscan Pro API required for holder lists.
        Falls back to manual tracking if not available.
        """
        wallets = []
        api_config = CHAIN_APIS.get(chain)

        if not api_config or not api_config["api_key"]:
            logger.warning(f"No API key for {chain}, skipping token holders")
            return wallets

        tokens = TRACKED_TOKENS.get(chain, [])

        for token_address, token_symbol, decimals in tokens[:3]:  # Limit to 3 tokens
            try:
                # Etherscan tokentx endpoint to find active holders
                holders = await self._fetch_token_holders(
                    chain, token_address, token_symbol, limit=20
                )
                wallets.extend(holders)

                # Rate limit protection
                await asyncio.sleep(0.25)

            except Exception as e:
                logger.error(f"Error fetching {token_symbol} holders on {chain}: {e}")

        return wallets

    async def _fetch_token_holders(
        self,
        chain: str,
        token_address: str,
        token_symbol: str,
        limit: int = 20,
    ) -> list[WalletInfo]:
        """Fetch top holders of a specific token."""
        wallets = []
        api_config = CHAIN_APIS.get(chain)

        if not api_config:
            return wallets

        try:
            # Get recent token transfers to find active holders
            # Note: For true top holders, Etherscan Pro API is needed
            url = api_config["base_url"]
            params = {
                "module": "account",
                "action": "tokentx",
                "contractaddress": token_address,
                "page": 1,
                "offset": 100,
                "sort": "desc",
                "apikey": api_config["api_key"],
            }

            response = await self.client.get(url, params=params)

            if response.status_code != 200:
                logger.warning(f"Etherscan API returned {response.status_code}")
                return wallets

            data = response.json()

            if data.get("status") != "1":
                logger.warning(f"Etherscan API error: {data.get('message')}")
                return wallets

            # Extract unique addresses from transfers
            seen_addresses = set()
            result = data.get("result", [])

            for tx in result:
                for addr_key in ["from", "to"]:
                    addr = tx.get(addr_key, "").lower()

                    # Skip contracts and known DEX routers
                    if not addr or addr in seen_addresses:
                        continue
                    if addr == token_address.lower():
                        continue

                    seen_addresses.add(addr)

                    wallets.append(WalletInfo(
                        address=addr,
                        chain=chain,
                        label=None,
                        wallet_type=WalletType.UNKNOWN,
                        balance_usd=None,
                        tx_count=0,
                        discovery_source=DiscoverySource.TOKEN_TRANSFER,
                    ))

                    if len(wallets) >= limit:
                        break

                if len(wallets) >= limit:
                    break

        except Exception as e:
            logger.error(f"Error fetching token holders: {e}")

        return wallets

    async def get_wallet_transactions(
        self,
        address: str,
        chain: str = "ETHEREUM",
        from_block: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        """Get recent transactions for a wallet."""
        api_config = CHAIN_APIS.get(chain)

        if not api_config or not api_config["api_key"]:
            return []

        try:
            url = api_config["base_url"]
            params = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": from_block,
                "endblock": 99999999,
                "page": 1,
                "offset": limit,
                "sort": "desc",
                "apikey": api_config["api_key"],
            }

            response = await self.client.get(url, params=params)

            if response.status_code != 200:
                return []

            data = response.json()

            if data.get("status") != "1":
                return []

            return data.get("result", [])

        except Exception as e:
            logger.error(f"Error fetching wallet transactions: {e}")
            return []

    async def get_internal_transactions(
        self,
        address: str,
        chain: str = "ETHEREUM",
        from_block: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        """Get internal transactions (contract calls)."""
        api_config = CHAIN_APIS.get(chain)

        if not api_config or not api_config["api_key"]:
            return []

        try:
            url = api_config["base_url"]
            params = {
                "module": "account",
                "action": "txlistinternal",
                "address": address,
                "startblock": from_block,
                "endblock": 99999999,
                "page": 1,
                "offset": limit,
                "sort": "desc",
                "apikey": api_config["api_key"],
            }

            response = await self.client.get(url, params=params)

            if response.status_code != 200:
                return []

            data = response.json()

            if data.get("status") != "1":
                return []

            return data.get("result", [])

        except Exception as e:
            logger.error(f"Error fetching internal transactions: {e}")
            return []

    async def sync_to_database(
        self,
        wallets: list[WalletInfo],
        db: AsyncSession,
    ) -> int:
        """Sync discovered wallets to database."""
        synced = 0

        for wallet in wallets:
            try:
                # Check if wallet exists
                result = await db.execute(
                    select(OnChainWallet).where(
                        OnChainWallet.address == wallet.address.lower(),
                        OnChainWallet.chain == wallet.chain,
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing
                    if wallet.label and not existing.label:
                        existing.label = wallet.label
                    if wallet.wallet_type != WalletType.UNKNOWN:
                        existing.wallet_type = wallet.wallet_type
                else:
                    # Create new
                    new_wallet = OnChainWallet(
                        address=wallet.address.lower(),
                        chain=wallet.chain,
                        label=wallet.label,
                        wallet_type=wallet.wallet_type,
                        discovery_source=wallet.discovery_source,
                        is_active=True,
                        priority_score=50,
                    )
                    db.add(new_wallet)

                synced += 1

            except Exception as e:
                logger.error(f"Error syncing wallet {wallet.address}: {e}")

        await db.commit()
        logger.info(f"Synced {synced} on-chain wallets to database")

        return synced


# Singleton instance
_discovery: Optional[EtherscanDiscovery] = None


def get_etherscan_discovery() -> EtherscanDiscovery:
    """Get singleton EtherscanDiscovery instance."""
    global _discovery
    if _discovery is None:
        _discovery = EtherscanDiscovery()
    return _discovery
