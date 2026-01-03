"""
Uniswap V2/V3 Transaction Parser
Parses swap transactions from Uniswap routers
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from web3 import Web3
from eth_abi import decode

# Uniswap V2 Router address (Ethereum mainnet)
UNISWAP_V2_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"

# Uniswap V3 Router addresses
UNISWAP_V3_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
UNISWAP_V3_ROUTER_2 = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"

# Common token addresses
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"

# Method signatures for swap functions
SWAP_SIGNATURES = {
    # Uniswap V2
    "0x7ff36ab5": "swapExactETHForTokens",
    "0x18cbafe5": "swapExactTokensForETH",
    "0x38ed1739": "swapExactTokensForTokens",
    "0x8803dbee": "swapTokensForExactTokens",
    "0xfb3bdb41": "swapETHForExactTokens",
    "0x4a25d94a": "swapTokensForExactETH",
    # Uniswap V3
    "0x414bf389": "exactInputSingle",
    "0xc04b8d59": "exactInput",
    "0xdb3e2198": "exactOutputSingle",
    "0xf28c0498": "exactOutput",
    # Uniswap V3 Router 2
    "0x04e45aaf": "exactInputSingle",
    "0xb858183f": "exactInput",
}


@dataclass
class SwapInfo:
    """Parsed swap transaction information."""

    dex: str
    action: str  # BUY or SELL
    token_in: str
    token_in_address: str
    token_in_amount: Decimal
    token_out: str
    token_out_address: str
    token_out_amount: Decimal
    amount_usd: Decimal
    router_address: str
    method: str


class UniswapParser:
    """Parser for Uniswap V2 and V3 transactions."""

    def __init__(self, web3: Web3, token_prices: dict[str, Decimal] | None = None):
        """
        Initialize the parser.

        Args:
            web3: Web3 instance for blockchain interaction
            token_prices: Optional dict of token address -> USD price
        """
        self.web3 = web3
        self.token_prices = token_prices or {}

        # Token symbol cache
        self._token_symbols: dict[str, str] = {
            WETH.lower(): "WETH",
            USDT.lower(): "USDT",
            USDC.lower(): "USDC",
        }

    def is_uniswap_transaction(self, tx: dict[str, Any]) -> bool:
        """Check if a transaction is a Uniswap swap."""
        to_address = tx.get("to", "").lower()
        input_data = tx.get("input", "")

        # Check if it's to a Uniswap router
        routers = [
            UNISWAP_V2_ROUTER.lower(),
            UNISWAP_V3_ROUTER.lower(),
            UNISWAP_V3_ROUTER_2.lower(),
        ]

        if to_address not in routers:
            return False

        # Check if method signature is a swap
        if len(input_data) < 10:
            return False

        method_sig = input_data[:10]
        return method_sig in SWAP_SIGNATURES

    def parse_transaction(self, tx: dict[str, Any]) -> SwapInfo | None:
        """
        Parse a Uniswap transaction.

        Args:
            tx: Transaction data from web3

        Returns:
            SwapInfo if successfully parsed, None otherwise
        """
        if not self.is_uniswap_transaction(tx):
            return None

        input_data = tx.get("input", "")
        method_sig = input_data[:10]
        method_name = SWAP_SIGNATURES.get(method_sig, "unknown")

        to_address = tx.get("to", "").lower()

        # Determine DEX version
        if to_address == UNISWAP_V2_ROUTER.lower():
            return self._parse_v2_swap(tx, method_name)
        else:
            return self._parse_v3_swap(tx, method_name)

    def _parse_v2_swap(self, tx: dict[str, Any], method_name: str) -> SwapInfo | None:
        """Parse Uniswap V2 swap transaction."""
        input_data = tx.get("input", "")
        value = tx.get("value", 0)

        try:
            if method_name == "swapExactETHForTokens":
                # (uint amountOutMin, address[] path, address to, uint deadline)
                decoded = decode(
                    ["uint256", "address[]", "address", "uint256"],
                    bytes.fromhex(input_data[10:]),
                )
                amount_out_min = Decimal(str(decoded[0])) / Decimal("1e18")
                path = decoded[1]

                return SwapInfo(
                    dex="uniswap_v2",
                    action="BUY",
                    token_in="ETH",
                    token_in_address=WETH,
                    token_in_amount=Decimal(str(value)) / Decimal("1e18"),
                    token_out=self._get_token_symbol(path[-1]),
                    token_out_address=path[-1],
                    token_out_amount=amount_out_min,
                    amount_usd=self._calculate_usd_value("ETH", Decimal(str(value)) / Decimal("1e18")),
                    router_address=UNISWAP_V2_ROUTER,
                    method=method_name,
                )

            elif method_name == "swapExactTokensForETH":
                # (uint amountIn, uint amountOutMin, address[] path, address to, uint deadline)
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
                    dex="uniswap_v2",
                    action="SELL",
                    token_in=self._get_token_symbol(token_in_addr),
                    token_in_address=token_in_addr,
                    token_in_amount=amount_in_decimal,
                    token_out="ETH",
                    token_out_address=WETH,
                    token_out_amount=Decimal(str(decoded[1])) / Decimal("1e18"),
                    amount_usd=self._calculate_usd_value(token_in_addr, amount_in_decimal),
                    router_address=UNISWAP_V2_ROUTER,
                    method=method_name,
                )

            elif method_name == "swapExactTokensForTokens":
                # (uint amountIn, uint amountOutMin, address[] path, address to, uint deadline)
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

                # Determine action based on token types
                action = "BUY" if self._is_stablecoin(token_in_addr) else "SELL"

                return SwapInfo(
                    dex="uniswap_v2",
                    action=action,
                    token_in=self._get_token_symbol(token_in_addr),
                    token_in_address=token_in_addr,
                    token_in_amount=amount_in_decimal,
                    token_out=self._get_token_symbol(token_out_addr),
                    token_out_address=token_out_addr,
                    token_out_amount=Decimal(str(decoded[1])) / Decimal(f"1e{decimals_out}"),
                    amount_usd=self._calculate_usd_value(token_in_addr, amount_in_decimal),
                    router_address=UNISWAP_V2_ROUTER,
                    method=method_name,
                )

        except Exception:
            pass

        return None

    def _parse_v3_swap(self, tx: dict[str, Any], method_name: str) -> SwapInfo | None:
        """Parse Uniswap V3 swap transaction."""
        input_data = tx.get("input", "")
        value = tx.get("value", 0)
        to_address = tx.get("to", "")

        try:
            if method_name == "exactInputSingle":
                # struct ExactInputSingleParams {
                #     address tokenIn;
                #     address tokenOut;
                #     uint24 fee;
                #     address recipient;
                #     uint256 deadline;
                #     uint256 amountIn;
                #     uint256 amountOutMinimum;
                #     uint160 sqrtPriceLimitX96;
                # }
                decoded = decode(
                    ["address", "address", "uint24", "address", "uint256", "uint256", "uint256", "uint160"],
                    bytes.fromhex(input_data[10:]),
                )

                token_in_addr = decoded[0]
                token_out_addr = decoded[1]
                amount_in = decoded[5]

                decimals_in = self._get_token_decimals(token_in_addr)
                decimals_out = self._get_token_decimals(token_out_addr)

                amount_in_decimal = Decimal(str(amount_in)) / Decimal(f"1e{decimals_in}")

                action = "BUY" if self._is_stablecoin(token_in_addr) else "SELL"

                return SwapInfo(
                    dex="uniswap_v3",
                    action=action,
                    token_in=self._get_token_symbol(token_in_addr),
                    token_in_address=token_in_addr,
                    token_in_amount=amount_in_decimal,
                    token_out=self._get_token_symbol(token_out_addr),
                    token_out_address=token_out_addr,
                    token_out_amount=Decimal(str(decoded[6])) / Decimal(f"1e{decimals_out}"),
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

        # Try to fetch from contract
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

        # Known stablecoins
        if address in [USDT.lower(), USDC.lower()]:
            return 6

        # Most ERC20 tokens use 18 decimals
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
        stablecoins = [USDT.lower(), USDC.lower()]
        return address in stablecoins

    def _calculate_usd_value(self, token: str, amount: Decimal) -> Decimal:
        """Calculate USD value of a token amount."""
        if token.upper() in ["ETH", "WETH"]:
            eth_price = self.token_prices.get(WETH.lower(), Decimal("2000"))
            return amount * eth_price
        elif self._is_stablecoin(token):
            return amount
        else:
            price = self.token_prices.get(token.lower(), Decimal("0"))
            return amount * price
