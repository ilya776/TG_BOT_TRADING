"""
SushiSwap Transaction Parser
Parses swap transactions from SushiSwap routers on multiple chains
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from web3 import Web3
from eth_abi import decode

# SushiSwap Router addresses on different chains
SUSHI_ROUTERS = {
    "ethereum": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
    "bsc": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
    "polygon": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
    "arbitrum": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
}

# Wrapped native tokens
WRAPPED_NATIVE = {
    "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "bsc": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    "polygon": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
    "arbitrum": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
}

# Standard Uniswap V2-style method signatures
SWAP_SIGNATURES = {
    "0x7ff36ab5": "swapExactETHForTokens",
    "0x18cbafe5": "swapExactTokensForETH",
    "0x38ed1739": "swapExactTokensForTokens",
    "0x8803dbee": "swapTokensForExactTokens",
    "0xfb3bdb41": "swapETHForExactTokens",
    "0x4a25d94a": "swapTokensForExactETH",
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
    chain: str


class SushiSwapParser:
    """Parser for SushiSwap transactions on multiple chains."""

    def __init__(
        self,
        web3: Web3,
        chain: str = "ethereum",
        token_prices: dict[str, Decimal] | None = None,
    ):
        """
        Initialize the parser.

        Args:
            web3: Web3 instance for the target chain
            chain: Chain name (ethereum, bsc, polygon, arbitrum)
            token_prices: Optional dict of token address -> USD price
        """
        self.web3 = web3
        self.chain = chain.lower()
        self.token_prices = token_prices or {}

        self.router_address = SUSHI_ROUTERS.get(self.chain, "").lower()
        self.wrapped_native = WRAPPED_NATIVE.get(self.chain, "").lower()

        self._token_symbols: dict[str, str] = {}

    def is_sushiswap_transaction(self, tx: dict[str, Any]) -> bool:
        """Check if a transaction is a SushiSwap swap."""
        to_address = tx.get("to", "").lower()
        input_data = tx.get("input", "")

        if to_address != self.router_address:
            return False

        if len(input_data) < 10:
            return False

        method_sig = input_data[:10]
        return method_sig in SWAP_SIGNATURES

    def parse_transaction(self, tx: dict[str, Any]) -> SwapInfo | None:
        """
        Parse a SushiSwap transaction.

        Args:
            tx: Transaction data from web3

        Returns:
            SwapInfo if successfully parsed, None otherwise
        """
        if not self.is_sushiswap_transaction(tx):
            return None

        input_data = tx.get("input", "")
        method_sig = input_data[:10]
        method_name = SWAP_SIGNATURES.get(method_sig, "unknown")
        value = tx.get("value", 0)

        try:
            # ETH -> Tokens
            if method_name == "swapExactETHForTokens":
                decoded = decode(
                    ["uint256", "address[]", "address", "uint256"],
                    bytes.fromhex(input_data[10:]),
                )
                path = decoded[1]

                native_symbol = self._get_native_symbol()
                amount_in = Decimal(str(value)) / Decimal("1e18")

                return SwapInfo(
                    dex="sushiswap",
                    action="BUY",
                    token_in=native_symbol,
                    token_in_address=self.wrapped_native,
                    token_in_amount=amount_in,
                    token_out=self._get_token_symbol(path[-1]),
                    token_out_address=path[-1],
                    token_out_amount=Decimal(str(decoded[0])) / Decimal("1e18"),
                    amount_usd=self._calculate_usd_value(native_symbol, amount_in),
                    router_address=self.router_address,
                    method=method_name,
                    chain=self.chain,
                )

            # Tokens -> ETH
            elif method_name == "swapExactTokensForETH":
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
                    dex="sushiswap",
                    action="SELL",
                    token_in=self._get_token_symbol(token_in_addr),
                    token_in_address=token_in_addr,
                    token_in_amount=amount_in_decimal,
                    token_out=self._get_native_symbol(),
                    token_out_address=self.wrapped_native,
                    token_out_amount=Decimal(str(decoded[1])) / Decimal("1e18"),
                    amount_usd=self._calculate_usd_value(token_in_addr, amount_in_decimal),
                    router_address=self.router_address,
                    method=method_name,
                    chain=self.chain,
                )

            # Tokens -> Tokens
            elif method_name == "swapExactTokensForTokens":
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
                    dex="sushiswap",
                    action=action,
                    token_in=self._get_token_symbol(token_in_addr),
                    token_in_address=token_in_addr,
                    token_in_amount=amount_in_decimal,
                    token_out=self._get_token_symbol(token_out_addr),
                    token_out_address=token_out_addr,
                    token_out_amount=Decimal(str(decoded[1])) / Decimal(f"1e{decimals_out}"),
                    amount_usd=self._calculate_usd_value(token_in_addr, amount_in_decimal),
                    router_address=self.router_address,
                    method=method_name,
                    chain=self.chain,
                )

        except Exception:
            pass

        return None

    def _get_native_symbol(self) -> str:
        """Get native currency symbol for the chain."""
        symbols = {
            "ethereum": "ETH",
            "bsc": "BNB",
            "polygon": "MATIC",
            "arbitrum": "ETH",
        }
        return symbols.get(self.chain, "ETH")

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
        # Common stablecoins across chains
        stablecoins = [
            "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT Ethereum
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC Ethereum
            "0x55d398326f99059ff775485246999027b3197955",  # USDT BSC
            "0xe9e7cea3dedca5984780bafc599bd69add087d56",  # BUSD BSC
            "0xc2132d05d31c914a87c6611c10748aeb04b58e8f",  # USDT Polygon
            "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",  # USDC Polygon
        ]
        return address.lower() in stablecoins

    def _calculate_usd_value(self, token: str, amount: Decimal) -> Decimal:
        """Calculate USD value of a token amount."""
        native_symbol = self._get_native_symbol()
        if token.upper() in [native_symbol, f"W{native_symbol}"]:
            native_price = self.token_prices.get(self.wrapped_native, Decimal("2000"))
            return amount * native_price
        elif self._is_stablecoin(token):
            return amount
        else:
            price = self.token_prices.get(token.lower(), Decimal("0"))
            return amount * price
