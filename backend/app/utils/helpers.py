"""
General utility helper functions
"""

import re
import secrets
import string
from decimal import Decimal
from typing import Any


def generate_random_string(length: int = 32) -> str:
    """
    Generate a random alphanumeric string.

    Args:
        length: Length of the string to generate

    Returns:
        Random string
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def is_valid_eth_address(address: str) -> bool:
    """
    Validate an Ethereum address format.

    Args:
        address: Address to validate

    Returns:
        True if valid Ethereum address format
    """
    if not address:
        return False
    # Check basic format: 0x followed by 40 hex characters
    pattern = r"^0x[a-fA-F0-9]{40}$"
    return bool(re.match(pattern, address))


def normalize_symbol(symbol: str, exchange: str = "binance") -> str:
    """
    Normalize a trading symbol for a specific exchange.

    Args:
        symbol: Original symbol (e.g., "ETH/USDT", "ETHUSDT")
        exchange: Target exchange name

    Returns:
        Normalized symbol for the exchange
    """
    # Remove common separators
    symbol = symbol.upper().replace("/", "").replace("-", "").replace("_", "")

    # Add USDT if not present and symbol seems incomplete
    if not any(
        symbol.endswith(quote) for quote in ["USDT", "BUSD", "USDC", "BTC", "ETH"]
    ):
        symbol = f"{symbol}USDT"

    # Exchange-specific formatting
    if exchange.lower() == "okx":
        # OKX uses hyphen format: BTC-USDT
        base = symbol[:-4] if symbol.endswith(("USDT", "BUSD", "USDC")) else symbol[:-3]
        quote = symbol[len(base) :]
        return f"{base}-{quote}"
    elif exchange.lower() == "bybit":
        # Bybit uses plain format: BTCUSDT
        return symbol

    # Binance and default: plain format
    return symbol


def calculate_pnl_percent(
    entry_price: Decimal | float,
    current_price: Decimal | float,
    is_long: bool = True,
) -> Decimal:
    """
    Calculate PnL percentage.

    Args:
        entry_price: Entry price
        current_price: Current/exit price
        is_long: True for long position, False for short

    Returns:
        PnL percentage as Decimal
    """
    entry = Decimal(str(entry_price))
    current = Decimal(str(current_price))

    if entry == 0:
        return Decimal("0")

    if is_long:
        pnl_percent = ((current - entry) / entry) * 100
    else:
        pnl_percent = ((entry - current) / entry) * 100

    return pnl_percent.quantize(Decimal("0.01"))


def calculate_position_size(
    balance: Decimal,
    risk_percent: Decimal,
    entry_price: Decimal,
    stop_loss_price: Decimal | None = None,
    leverage: int = 1,
) -> Decimal:
    """
    Calculate position size based on risk management.

    Args:
        balance: Available balance in USDT
        risk_percent: Maximum risk per trade (percentage)
        entry_price: Entry price
        stop_loss_price: Stop loss price (optional)
        leverage: Leverage multiplier

    Returns:
        Position size in quote currency
    """
    risk_amount = balance * (risk_percent / Decimal("100"))

    if stop_loss_price and entry_price != stop_loss_price:
        # Calculate based on stop loss distance
        stop_distance_percent = abs(entry_price - stop_loss_price) / entry_price
        position_value = risk_amount / stop_distance_percent
    else:
        # Default: use risk amount directly
        position_value = risk_amount

    # Apply leverage
    position_value = position_value * leverage

    # Cap at available balance * leverage
    max_position = balance * leverage
    return min(position_value, max_position)


def format_currency(
    amount: Decimal | float,
    currency: str = "USDT",
    decimals: int = 2,
) -> str:
    """
    Format a currency amount for display.

    Args:
        amount: Amount to format
        currency: Currency symbol
        decimals: Number of decimal places

    Returns:
        Formatted string
    """
    amount = Decimal(str(amount))
    formatted = f"{amount:,.{decimals}f}"

    if currency.upper() in ["USD", "USDT", "USDC", "BUSD"]:
        return f"${formatted}"
    elif currency.upper() == "BTC":
        return f"{formatted} BTC"
    elif currency.upper() == "ETH":
        return f"{formatted} ETH"
    else:
        return f"{formatted} {currency}"


def truncate_address(address: str, chars: int = 6) -> str:
    """
    Truncate an Ethereum address for display.

    Args:
        address: Full address
        chars: Number of characters to show at start/end

    Returns:
        Truncated address (e.g., "0x1234...5678")
    """
    if not address or len(address) < chars * 2 + 4:
        return address
    return f"{address[:chars + 2]}...{address[-chars:]}"


def safe_divide(
    numerator: Decimal | float,
    denominator: Decimal | float,
    default: Decimal | float = 0,
) -> Decimal:
    """
    Safely divide two numbers, returning default if denominator is 0.

    Args:
        numerator: Number to divide
        denominator: Number to divide by
        default: Value to return if denominator is 0

    Returns:
        Result of division or default
    """
    num = Decimal(str(numerator))
    denom = Decimal(str(denominator))

    if denom == 0:
        return Decimal(str(default))

    return num / denom


def dict_to_query_string(params: dict[str, Any]) -> str:
    """
    Convert a dictionary to a URL query string.

    Args:
        params: Dictionary of parameters

    Returns:
        Query string (without leading ?)
    """
    parts = []
    for key, value in sorted(params.items()):
        if value is not None:
            parts.append(f"{key}={value}")
    return "&".join(parts)


def parse_trading_pair(symbol: str) -> tuple[str, str]:
    """
    Parse a trading pair symbol into base and quote currencies.

    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT", "BTC/USDT", "BTC-USDT")

    Returns:
        Tuple of (base, quote) currencies
    """
    # Remove separators
    symbol = symbol.upper().replace("/", "").replace("-", "").replace("_", "")

    # Common quote currencies
    quotes = ["USDT", "BUSD", "USDC", "TUSD", "BTC", "ETH", "BNB"]

    for quote in quotes:
        if symbol.endswith(quote):
            base = symbol[: -len(quote)]
            return (base, quote)

    # If no known quote found, assume last 4 chars are quote
    return (symbol[:-4], symbol[-4:])
