"""Pydantic schemas for Trading API requests/responses."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================


class ExecuteCopyTradeRequest(BaseModel):
    """Request schema для виконання copy trade.

    Example:
        {
            "signal_id": 100,
            "exchange_name": "binance",
            "symbol": "BTCUSDT",
            "side": "buy",
            "trade_type": "spot",
            "size_usdt": 1000.00,
            "leverage": 1,
            "stop_loss_percentage": 5.0,
            "take_profit_percentage": 10.0
        }
    """

    signal_id: int = Field(..., description="Signal ID to copy", gt=0)
    exchange_name: str = Field(
        ..., description="Exchange name (binance, bybit, bitget)"
    )
    symbol: str = Field(..., description="Trading pair (e.g., BTCUSDT)")
    side: str = Field(..., description="Trade side: buy or sell")
    trade_type: str = Field(..., description="Trade type: spot or futures")
    size_usdt: Decimal = Field(
        ..., description="Position size in USDT", gt=0, decimal_places=2
    )
    leverage: int = Field(
        default=1, description="Leverage (1-125)", ge=1, le=125
    )
    stop_loss_percentage: Decimal | None = Field(
        default=None, description="Stop loss percentage (optional)", ge=0, le=100
    )
    take_profit_percentage: Decimal | None = Field(
        default=None,
        description="Take profit percentage (optional)",
        ge=0,
        le=1000,
    )

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        """Validate trade side."""
        if v.lower() not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        return v.lower()

    @field_validator("trade_type")
    @classmethod
    def validate_trade_type(cls, v: str) -> str:
        """Validate trade type."""
        if v.lower() not in ("spot", "futures"):
            raise ValueError("trade_type must be 'spot' or 'futures'")
        return v.lower()

    @field_validator("exchange_name")
    @classmethod
    def validate_exchange(cls, v: str) -> str:
        """Validate exchange name."""
        if v.lower() not in ("binance", "bybit", "bitget", "okx"):
            raise ValueError(
                "exchange_name must be one of: binance, bybit, bitget, okx"
            )
        return v.lower()

    model_config = {"json_schema_extra": {"example": {
        "signal_id": 100,
        "exchange_name": "binance",
        "symbol": "BTCUSDT",
        "side": "buy",
        "trade_type": "spot",
        "size_usdt": 1000.00,
        "leverage": 1,
        "stop_loss_percentage": 5.0,
        "take_profit_percentage": 10.0,
    }}}


class ClosePositionRequest(BaseModel):
    """Request schema для закриття позиції.

    Example:
        {
            "position_id": 123,
            "exchange_name": "binance"
        }
    """

    position_id: int = Field(..., description="Position ID to close", gt=0)
    exchange_name: str = Field(
        ..., description="Exchange name (binance, bybit, bitget)"
    )

    @field_validator("exchange_name")
    @classmethod
    def validate_exchange(cls, v: str) -> str:
        """Validate exchange name."""
        if v.lower() not in ("binance", "bybit", "bitget", "okx"):
            raise ValueError(
                "exchange_name must be one of: binance, bybit, bitget, okx"
            )
        return v.lower()

    model_config = {"json_schema_extra": {"example": {
        "position_id": 123,
        "exchange_name": "binance",
    }}}


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================


class TradeResponse(BaseModel):
    """Response schema для Trade.

    Відображає результат виконання trade.
    """

    id: int = Field(..., description="Trade ID")
    user_id: int = Field(..., description="User ID")
    signal_id: int | None = Field(None, description="Signal ID (if copy trade)")
    symbol: str = Field(..., description="Trading pair")
    side: str = Field(..., description="Trade side: buy or sell")
    trade_type: str = Field(..., description="Trade type: spot or futures")
    status: str = Field(..., description="Trade status: pending, filled, failed")
    size_usdt: Decimal = Field(..., description="Position size in USDT")
    quantity: Decimal = Field(..., description="Asset quantity")
    leverage: int = Field(..., description="Leverage used")
    executed_price: Decimal | None = Field(
        None, description="Execution price (after fill)"
    )
    executed_quantity: Decimal | None = Field(
        None, description="Executed quantity (after fill)"
    )
    exchange_order_id: str | None = Field(
        None, description="Exchange order ID"
    )
    fee_amount: Decimal | None = Field(None, description="Trading fee")
    created_at: datetime = Field(..., description="Creation timestamp")
    executed_at: datetime | None = Field(None, description="Execution timestamp")
    error_message: str | None = Field(None, description="Error message (if failed)")

    model_config = {"from_attributes": True}


class PositionResponse(BaseModel):
    """Response schema для Position.

    Відображає відкриту або закриту позицію.
    """

    id: int = Field(..., description="Position ID")
    user_id: int = Field(..., description="User ID")
    symbol: str = Field(..., description="Trading pair")
    side: str = Field(..., description="Position side: long or short")
    status: str = Field(..., description="Position status: open, closed, liquidated")
    entry_price: Decimal = Field(..., description="Entry price")
    quantity: Decimal = Field(..., description="Position quantity")
    leverage: int = Field(..., description="Leverage used")
    stop_loss_price: Decimal | None = Field(None, description="Stop loss price")
    take_profit_price: Decimal | None = Field(
        None, description="Take profit price"
    )
    entry_trade_id: int = Field(..., description="Entry trade ID")
    exit_price: Decimal | None = Field(None, description="Exit price (if closed)")
    exit_trade_id: int | None = Field(None, description="Exit trade ID (if closed)")
    unrealized_pnl: Decimal = Field(..., description="Unrealized PnL (for open)")
    realized_pnl: Decimal | None = Field(
        None, description="Realized PnL (after close)"
    )
    opened_at: datetime = Field(..., description="Opening timestamp")
    closed_at: datetime | None = Field(None, description="Closing timestamp")

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    """Response schema для помилок.

    Стандартний формат для всіх API errors.
    """

    error: str = Field(..., description="Error type/code")
    message: str = Field(..., description="Human-readable error message")
    details: dict | None = Field(None, description="Additional error details")

    model_config = {"json_schema_extra": {"example": {
        "error": "ValidationError",
        "message": "Invalid request parameters",
        "details": {"field": "size_usdt", "reason": "Must be greater than 0"},
    }}}


class SuccessResponse(BaseModel):
    """Generic success response.

    Використовується для операцій без специфічного payload.
    """

    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(..., description="Success message")

    model_config = {"json_schema_extra": {"example": {
        "success": True,
        "message": "Position closed successfully",
    }}}
