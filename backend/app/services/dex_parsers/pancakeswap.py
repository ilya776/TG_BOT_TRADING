"""
PancakeSwap V2/V3 Transaction Parser
Parses swap transactions from PancakeSwap routers on BSC
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from web3 import Web3
from eth_abi import decode

# PancakeSwap Router addresses (BSC)
PANCAKE_V2_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
PANCAKE_V3_ROUTER = "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4"

# BSC common tokens
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
BUSD = "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"
USDT_BSC = "0x55d398326f99059fF775485246999027B3197955"

# Method signatures (same as Uniswap V2)
SWAP_SIGNATURES = {
    "0x7ff36ab5": "swapExactETHForTokens",
    "0x18cbafe5": "swapExactTokensForETH",
    "0x38ed1739": "swapExactTokensForTokens",
    "0x8803dbee": "swapTokensForExactTokens",
    "0xfb3bdb41": "swapETHForExactTokens",
    "0x4a25d94a": "swapTokensForExactETH",
    # PancakeSwap specific
    "0x5c11d795": "swapExactTokensForTokensSupportingFeeOnTransferTokens",
    "0xb6f9de95": "swapExactETHForTokensSupportingFeeOnTransferTokens",
    "0x791ac947": "swapExactTokensForETHSupportingFeeOnTransferTokens",
}


@dataclass
class SwapInfo:
    """Parsed swap transaction information."""

    dex: str
    action: str
    token_in: str
    token_in_address: str
    token_in_amount: Decimal
    token_out: str
    token_out_address: str
    token_out_amount: Decimal
    amount_usd: Decimal
    router_address: str
    method: str


class PancakeSwapParser:
    """Parser for PancakeSwap V2 and V3 transactions on BSC."""

    def __init__(self, web3: Web3, token_prices: dict[str, Decimal] | None = None):
        """
        Initialize the parser.

        Args:
            web3: Web3 instance connected to BSC
            token_prices: Optional dict of token address -> USD price
        """
        self.web3 = web3
        self.token_prices = token_prices or {}

        # Token symbol cache
        self._token_symbols: dict[str, str] = {
            WBNB.lower(): "WBNB",
            BUSD.lower(): "BUSD",
            USDT_BSC.lower(): "USDT",
        }

    def is_pancakeswap_transaction(self, tx: dict[str, Any]) -> bool:
        """Check if a transaction is a PancakeSwap swap."""
        to_address = tx.get("to", "").lower()
        input_data = tx.get("input", "")

        routers = [
            PANCAKE_V2_ROUTER.lower(),
            PANCAKE_V3_ROUTER.lower(),
        ]

        if to_address not in routers:
            return False

        if len(input_data) < 10:
            return False

        method_sig = input_data[:10]
        return method_sig in SWAP_SIGNATURES

    def parse_transaction(self, tx: dict[str, Any]) -> SwapInfo | None:
        """
        Parse a PancakeSwap transaction.

        Args:
            tx: Transaction data from web3

        Returns:
            SwapInfo if successfully parsed, None otherwise
        """
        if not self.is_pancakeswap_transaction(tx):
            return None

        input_data = tx.get("input", "")
        method_sig = input_data[:10]
        method_name = SWAP_SIGNATURES.get(method_sig, "unknown")

        to_address = tx.get("to", "").lower()
        value = tx.get("value", 0)

        try:
            # ETH -> Tokens (BNB -> Tokens on BSC)
            if method_name in ["swapExactETHForTokens", "swapExactETHForTokensSupportingFeeOnTransferTokens"]:
                decoded = decode(
                    ["uint256", "address[]", "address", "uint256"],
                    bytes.fromhex(input_data[10:]),
                )
                amount_out_min = decoded[0]
                path = decoded[1]

                return SwapInfo(
                    dex="pancakeswap_v2",
                    action="BUY",
                    token_in="BNB",
                    token_in_address=WBNB,
                    token_in_amount=Decimal(str(value)) / Decimal("1e18"),
                    token_out=self._get_token_symbol(path[-1]),
                    token_out_address=path[-1],
                    token_out_amount=Decimal(str(amount_out_min)) / Decimal("1e18"),
                    amount_usd=self._calculate_usd_value("BNB", Decimal(str(value)) / Decimal("1e18")),
                    router_address=to_address,
                    method=method_name,
                )

            # Tokens -> ETH (Tokens -> BNB on BSC)
            elif method_name in ["swapExactTokensForETH", "swapExactTokensForETHSupportingFeeOnTransferTokens"]:
                decoded = decode(
                    ["uint256", "uint256", "address[]", "address", "uint256"],
                    bytes.fromhex(input_data[10:]),
                )
                amount_in = decoded[0]
                path = decoded[2]

                token_in_addr = path[0]
                decimals = self._get_token_decimals(token_in_addr)
                amount_in_decimal = Decimal(str(amount_in)) / Decimal(f"1e{decimals}")

                return SwapInfo(
                    dex="pancakeswap_v2",
                    action="SELL",
                    token_in=self._get_token_symbol(token_in_addr),
                    token_in_address=token_in_addr,
                    token_in_amount=amount_in_decimal,
                    token_out="BNB",
                    token_out_address=WBNB,
                    token_out_amount=Decimal(str(decoded[1])) / Decimal("1e18"),
                    amount_usd=self._calculate_usd_value(token_in_addr, amount_in_decimal),
                    router_address=to_address,
                    method=method_name,
                )

            # Tokens -> Tokens
            elif method_name in ["swapExactTokensForTokens", "swapExactTokensForTokensSupportingFeeOnTransferTokens"]:
                decoded = decode(
                    ["uint256", "uint256", "address[]", "address", "uint256"],
                    bytes.fromhex(input_data[10:]),
                )
                amount_in = decoded[0]
                path = decoded[2]

                token_in_addr = path[0]
                token_out_addr = path[-1]

                decimals_in = self._get_token_decimals(token_in_addr)
                decimals_out = self._get_token_decimals(token_out_addr)

                amount_in_decimal = Decimal(str(amount_in)) / Decimal(f"1e{decimals_in}")

                action = "BUY" if self._is_stablecoin(token_in_addr) else "SELL"

                return SwapInfo(
                    dex="pancakeswap_v2",
                    action=action,
                    token_in=self._get_token_symbol(token_in_addr),
                    token_in_address=token_in_addr,
                    token_in_amount=amount_in_decimal,
                    token_out=self._get_token_symbol(token_out_addr),
                    token_out_address=token_out_addr,
                    token_out_amount=Decimal(str(decoded[1])) / Decimal(f"1e{decimals_out}"),
                    amount_usd=self._calculate_usd_value(token_in_addr, amount_in_decimal),
                    router_address=to_address,
                    method=method_name,
                )

        except Exception:
            pass

        return None

    def _get_token_symbol(self, address: str) -> str:
        """Get token symbol from address."""
        address = address.lower()
        if address in self._token_symbols:
            return self._token_symbols[address]

        try:
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(address),
                abi=[{"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"}],
            )
            symbol = contract.functions.symbol().call()
            self._token_symbols[address] = symbol
            return symbol
        except Exception:
            return address[:8] + "..."

    def _get_token_decimals(self, address: str) -> int:
        """Get token decimals from address."""
        address = address.lower()

        # Known tokens with non-18 decimals
        if address == USDT_BSC.lower():
            return 18  # USDT on BSC is 18 decimals unlike Ethereum

        try:
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(address),
                abi=[{"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"}],
            )
            return contract.functions.decimals().call()
        except Exception:
            return 18

    def _is_stablecoin(self, address: str) -> bool:
        """Check if address is a stablecoin."""
        address = address.lower()
        stablecoins = [BUSD.lower(), USDT_BSC.lower()]
        return address in stablecoins

    def _calculate_usd_value(self, token: str, amount: Decimal) -> Decimal:
        """Calculate USD value of a token amount."""
        if token.upper() in ["BNB", "WBNB"]:
            bnb_price = self.token_prices.get(WBNB.lower(), Decimal("300"))
            return amount * bnb_price
        elif self._is_stablecoin(token):
            return amount
        else:
            price = self.token_prices.get(token.lower(), Decimal("0"))
            return amount * price
