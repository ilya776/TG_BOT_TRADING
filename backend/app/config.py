"""
Application Configuration
Loads settings from environment variables with validation
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "WhaleCopyTrading"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = Field(..., min_length=32)

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/whale_copy_trading"
    )
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Telegram
    telegram_bot_token: str = Field(...)
    telegram_webhook_url: str | None = None
    telegram_webapp_url: str | None = None

    # Security: Disable desktop auth in production (no cryptographic verification)
    disable_desktop_auth: bool = False

    # Encryption
    encryption_key: str = Field(..., min_length=32)

    # Binance
    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    binance_testnet: bool = True

    # OKX
    okx_api_key: str | None = None
    okx_api_secret: str | None = None
    okx_passphrase: str | None = None
    okx_testnet: bool = True

    # Bybit
    bybit_api_key: str | None = None
    bybit_api_secret: str | None = None
    bybit_testnet: bool = True

    # Blockchain / Web3
    eth_rpc_url: str = "https://eth-mainnet.g.alchemy.com/v2/demo"
    eth_rpc_ws_url: str | None = None
    bsc_rpc_url: str = "https://bsc-dataseed.binance.org/"
    bsc_rpc_ws_url: str | None = None

    # Subscription & Payments
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None

    # Commission rates
    free_tier_commission: float = 0.02
    pro_tier_commission: float = 0.01
    elite_tier_commission: float = 0.005

    # Monitoring
    sentry_dsn: str | None = None
    log_level: str = "INFO"

    # Rate limits
    rate_limit_per_minute: int = 60
    whale_monitor_interval_seconds: int = 1

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql", "sqlite")):
            raise ValueError("Database URL must be PostgreSQL or SQLite")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Subscription tier configuration
SUBSCRIPTION_TIERS = {
    "FREE": {
        "price_monthly": 0,
        "whales_limit": 5,
        "auto_copy": True,
        "commission_rate": 0.02,
        "futures_enabled": False,
        "max_positions": 5,
        "features": [
            "Auto-copy enabled",
            "Basic analytics",
            "5 whales to follow",
        ],
    },
    "PRO": {
        "price_monthly": 99,
        "whales_limit": 5,
        "auto_copy": True,
        "commission_rate": 0.01,
        "futures_enabled": True,
        "max_positions": 10,
        "features": [
            "Auto-copy enabled",
            "Advanced analytics",
            "Priority execution",
            "FUTURES mode",
            "5 whales to follow",
        ],
    },
    "ELITE": {
        "price_monthly": 299,
        "whales_limit": -1,  # Unlimited
        "auto_copy": True,
        "commission_rate": 0.005,
        "futures_enabled": True,
        "max_positions": -1,  # Unlimited
        "features": [
            "Unlimited whales",
            "Flash copy (MEV protection)",
            "AI whale scoring",
            "Custom strategies",
            "24/7 VIP support",
        ],
    },
}

# Supported DEXes
SUPPORTED_DEXES = {
    "ethereum": ["uniswap_v2", "uniswap_v3", "sushiswap"],
    "bsc": ["pancakeswap_v2", "pancakeswap_v3"],
}

# Supported CEXes
SUPPORTED_CEXES = ["binance", "okx", "bybit"]

# Trading Minimums (G1-G2: Smart position sizing)
MIN_TRADING_BALANCE_USDT = 5.0  # Minimum user balance to allow trading
MIN_TRADE_SIZE_USDT = 5.0  # Minimum trade size (absolute floor)
TRADE_SIZE_BUFFER_PERCENT = 20  # Buffer % above exchange minimum

# Exchange-specific minimum notional values (USD)
EXCHANGE_MIN_NOTIONAL = {
    "binance": {
        "USD-M": 5.0,     # 5 USDT min for USD-M futures
        "COIN-M": 10.0,   # ~0.0001 BTC (~$10) for COIN-M
        "SPOT": 10.0,     # 10 USDT min for spot
    },
    "okx": {
        "USD-M": 5.0,
        "COIN-M": 10.0,
        "SPOT": 5.0,
    },
    "bitget": {
        "USD-M": 5.0,
        "SPOT": 5.0,
    },
}
