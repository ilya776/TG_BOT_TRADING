"""
DEX Swap Detector
Detects and parses DEX swap transactions from on-chain data.

Supported DEXes:
- Uniswap V2/V3
- SushiSwap
- PancakeSwap
- 1inch
- 0x Protocol
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.models.signal import SignalAction

logger = logging.getLogger(__name__)

# Known DEX router addresses by chain
DEX_ROUTERS = {
    "ETHEREUM": {
        # Uniswap
        "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D": ("uniswap_v2", "Uniswap V2 Router"),
        "0xE592427A0AEce92De3Edee1F18E0157C05861564": ("uniswap_v3", "Uniswap V3 Router"),
        "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45": ("uniswap_v3", "Uniswap V3 Router 2"),
        "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD": ("uniswap_universal", "Uniswap Universal Router"),
        # SushiSwap
        "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F": ("sushiswap", "SushiSwap Router"),
        # 1inch
        "0x1111111254fb6c44bAC0beD2854e76F90643097d": ("1inch_v4", "1inch V4 Router"),
        "0x1111111254EEB25477B68fb85Ed929f73A960582": ("1inch_v5", "1inch V5 Router"),
        # 0x
        "0xDef1C0ded9bec7F1a1670819833240f027b25EfF": ("0x", "0x Exchange Proxy"),
        # Curve
        "0x99a58482BD75cbab83b27EC03CA68fF489b5788f": ("curve", "Curve Router"),
    },
    "BSC": {
        # PancakeSwap
        "0x10ED43C718714eb63d5aA57B78B54917a90F6D3A": ("pancakeswap_v2", "PancakeSwap V2 Router"),
        "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4": ("pancakeswap_v3", "PancakeSwap V3 Router"),
        # SushiSwap
        "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506": ("sushiswap", "SushiSwap Router"),
        # 1inch
        "0x1111111254fb6c44bAC0beD2854e76F90643097d": ("1inch", "1inch Router"),
    },
    "ARBITRUM": {
        # Uniswap
        "0xE592427A0AEce92De3Edee1F18E0157C05861564": ("uniswap_v3", "Uniswap V3 Router"),
        "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45": ("uniswap_v3", "Uniswap V3 Router 2"),
        # SushiSwap
        "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506": ("sushiswap", "SushiSwap Router"),
        # Camelot
        "0xc873fEcbd354f5A56E00E710B90EF4201db2448d": ("camelot", "Camelot Router"),
        # GMX
        "0xaBBc5F99639c9B6bCb58544ddf04EFA6802F4064": ("gmx", "GMX Router"),
    },
    "OPTIMISM": {
        "0xE592427A0AEce92De3Edee1F18E0157C05861564": ("uniswap_v3", "Uniswap V3 Router"),
        "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45": ("uniswap_v3", "Uniswap V3 Router 2"),
    },
    "POLYGON": {
        "0xE592427A0AEce92De3Edee1F18E0157C05861564": ("uniswap_v3", "Uniswap V3 Router"),
        "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff": ("quickswap", "QuickSwap Router"),
    },
    "BASE": {
        "0x2626664c2603336E57B271c5C0b26F421741e481": ("uniswap_v3", "Uniswap V3 Router"),
        "0x327Df1E6de05895d2ab08513aaDD9313Fe505d86": ("baseswap", "BaseSwap Router"),
    },
}

# Common token addresses for price lookups
STABLECOINS = {
    "ETHEREUM": {
        "0xdAC17F958D2ee523a2206206994597C13D831ec7": ("USDT", 6),
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": ("USDC", 6),
        "0x6B175474E89094C44Da98b954EescdeCB5Bad": ("DAI", 18),
    },
    "BSC": {
        "0x55d398326f99059fF775485246999027B3197955": ("USDT", 18),
        "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d": ("USDC", 18),
        "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56": ("BUSD", 18),
    },
    "ARBITRUM": {
        "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9": ("USDT", 6),
        "0xaf88d065e77c8cC2239327C5EDb3A432268e5831": ("USDC", 6),
    },
}

# Method signatures for swap detection
SWAP_SIGNATURES = {
    # Uniswap V2
    "0x38ed1739": "swapExactTokensForTokens",
    "0x8803dbee": "swapTokensForExactTokens",
    "0x7ff36ab5": "swapExactETHForTokens",
    "0x4a25d94a": "swapTokensForExactETH",
    "0x18cbafe5": "swapExactTokensForETH",
    "0xfb3bdb41": "swapETHForExactTokens",
    # Uniswap V3
    "0x04e45aaf": "exactInputSingle",
    "0xb858183f": "exactInput",
    "0x5023b4df": "exactOutputSingle",
    "0x09b81346": "exactOutput",
    # 1inch
    "0x7c025200": "swap",
    "0xe449022e": "uniswapV3Swap",
    "0x2e95b6c8": "unoswap",
}


@dataclass
class SwapInfo:
    """Information about a detected DEX swap."""
    tx_hash: str
    block_number: int
    timestamp: datetime
    wallet_address: str
    chain: str

    # DEX info
    dex: str
    dex_name: str

    # Swap details
    token_in: str
    token_in_symbol: str | None
    token_in_amount: Decimal
    token_out: str
    token_out_symbol: str | None
    token_out_amount: Decimal

    # USD values (if available)
    amount_usd: Decimal | None

    # Derived signal info
    action: SignalAction  # BUY or SELL (based on token_out)

    def __repr__(self) -> str:
        return (
            f"<SwapInfo(tx={self.tx_hash[:10]}..., "
            f"{self.token_in_symbol or 'TOKEN'} -> {self.token_out_symbol or 'TOKEN'}, "
            f"${self.amount_usd or '?'})>"
        )


class SwapDetector:
    """
    Detects DEX swaps from transaction data.

    Can process:
    - Raw transactions from Etherscan API
    - Transaction receipts with logs
    - Internal transactions
    """

    def __init__(self):
        # Build reverse lookup for router addresses
        self._router_lookup = {}
        for chain, routers in DEX_ROUTERS.items():
            for addr, (dex_id, dex_name) in routers.items():
                self._router_lookup[addr.lower()] = (chain, dex_id, dex_name)

    def is_dex_router(self, address: str) -> bool:
        """Check if address is a known DEX router."""
        return address.lower() in self._router_lookup

    def get_dex_info(self, address: str) -> tuple[str, str, str] | None:
        """Get DEX info for a router address."""
        return self._router_lookup.get(address.lower())

    def detect_swap_from_tx(
        self,
        tx: dict,
        chain: str,
    ) -> SwapInfo | None:
        """
        Detect if a transaction is a DEX swap.

        Args:
            tx: Transaction data from Etherscan API
            chain: Chain name (ETHEREUM, BSC, etc.)

        Returns:
            SwapInfo if swap detected, None otherwise
        """
        to_address = tx.get("to", "").lower()
        input_data = tx.get("input", "")
        method_sig = input_data[:10] if len(input_data) >= 10 else ""

        # Check if it's a DEX router
        dex_info = self.get_dex_info(to_address)
        if not dex_info:
            return None

        chain_name, dex_id, dex_name = dex_info

        # Check if it's a swap method
        method_name = SWAP_SIGNATURES.get(method_sig)
        if not method_name:
            # Could still be a swap via different method
            # For now, only detect known methods
            return None

        try:
            # Parse basic transaction info
            tx_hash = tx.get("hash", "")
            block_number = int(tx.get("blockNumber", 0))
            timestamp = datetime.fromtimestamp(int(tx.get("timeStamp", 0)))
            wallet_address = tx.get("from", "").lower()

            # For full swap details, we'd need to decode the input data
            # and/or parse event logs. This is a simplified version.

            # Estimate amount from transaction value (for ETH swaps)
            value_wei = int(tx.get("value", 0))
            gas_used = int(tx.get("gasUsed", 0))
            gas_price = int(tx.get("gasPrice", 0))

            # Determine action based on method
            # swapExact*ForTokens = BUY (buying tokens)
            # swapTokensForExact* = SELL (selling tokens)
            if "ForTokens" in method_name or "Input" in method_name:
                action = SignalAction.BUY
            else:
                action = SignalAction.SELL

            # Create swap info (with placeholder values for tokens)
            # Full implementation would decode input data
            swap_info = SwapInfo(
                tx_hash=tx_hash,
                block_number=block_number,
                timestamp=timestamp,
                wallet_address=wallet_address,
                chain=chain,
                dex=dex_id,
                dex_name=dex_name,
                token_in="",  # Would need decoding
                token_in_symbol=None,
                token_in_amount=Decimal(str(value_wei)) / Decimal("1e18") if value_wei else Decimal("0"),
                token_out="",  # Would need decoding
                token_out_symbol=None,
                token_out_amount=Decimal("0"),
                amount_usd=None,  # Would need price lookup
                action=action,
            )

            return swap_info

        except Exception as e:
            logger.error(f"Error detecting swap from tx {tx.get('hash')}: {e}")
            return None

    def detect_swaps_from_transactions(
        self,
        transactions: list[dict],
        chain: str,
    ) -> list[SwapInfo]:
        """Detect all swaps from a list of transactions."""
        swaps = []

        for tx in transactions:
            swap = self.detect_swap_from_tx(tx, chain)
            if swap:
                swaps.append(swap)

        logger.debug(f"Detected {len(swaps)} swaps from {len(transactions)} transactions")
        return swaps

    def is_stablecoin(self, token_address: str, chain: str) -> bool:
        """Check if token is a stablecoin."""
        stables = STABLECOINS.get(chain, {})
        return token_address.lower() in {addr.lower() for addr in stables.keys()}

    def determine_signal_action(
        self,
        swap: SwapInfo,
    ) -> SignalAction:
        """
        Determine if swap is a BUY or SELL signal.

        Logic:
        - Swapping stablecoin -> token = BUY
        - Swapping token -> stablecoin = SELL
        - Swapping ETH -> token = BUY
        - Swapping token -> ETH = SELL
        """
        chain = swap.chain

        # Check if output is stablecoin (SELL signal)
        if swap.token_out and self.is_stablecoin(swap.token_out, chain):
            return SignalAction.SELL

        # Check if input is stablecoin (BUY signal)
        if swap.token_in and self.is_stablecoin(swap.token_in, chain):
            return SignalAction.BUY

        # Default to action from method signature
        return swap.action


# Singleton instance
_detector: Optional[SwapDetector] = None


def get_swap_detector() -> SwapDetector:
    """Get singleton SwapDetector instance."""
    global _detector
    if _detector is None:
        _detector = SwapDetector()
    return _detector
