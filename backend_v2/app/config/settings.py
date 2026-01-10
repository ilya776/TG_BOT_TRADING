"""Application Settings using Pydantic.

Environment-based configuration with validation.
All secrets should be passed via environment variables.

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
    REDIS_URL: Redis connection string (for Celery)
    SECRET_KEY: Application secret key
    ENVIRONMENT: development | staging | production
    DEBUG: Enable debug mode (default: False)

Example .env file:
    DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/trading
    REDIS_URL=redis://localhost:6379/0
    SECRET_KEY=your-secret-key-here
    ENVIRONMENT=production
    DEBUG=false
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    All settings can be overridden via environment variables.
    Prefixed environment variables take priority (e.g., APP_DATABASE_URL).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==================== Core ====================
    app_name: str = "Copy Trading Backend v2"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production", min_length=32)

    # ==================== Database ====================
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/tg_bot_trading",
        description="PostgreSQL connection string (async)",
    )

    # Connection pool settings
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    db_pool_timeout: int = Field(default=30, ge=1)
    db_pool_recycle: int = Field(default=1800, description="Recycle connections after N seconds")
    db_echo: bool = Field(default=False, description="Log SQL queries")

    # ==================== Redis / Celery ====================
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Celery broker and result backend",
    )

    celery_broker_url: str | None = None  # Defaults to redis_url
    celery_result_backend: str | None = None  # Defaults to redis_url

    # Worker settings
    celery_worker_concurrency: int = Field(default=4, ge=1, le=32)
    celery_task_acks_late: bool = True
    celery_task_reject_on_worker_lost: bool = True

    # Beat settings
    signal_processing_interval: float = Field(
        default=5.0,
        description="Seconds between signal processing batches",
    )
    signal_cleanup_interval: int = Field(
        default=300,
        description="Seconds between expired signal cleanup (5 min)",
    )

    # ==================== Exchange API ====================
    # Rate limiting
    exchange_rate_limit_requests: int = Field(default=10, description="Requests per window")
    exchange_rate_limit_window: int = Field(default=1, description="Window in seconds")

    # Retry settings
    exchange_max_retries: int = Field(default=3, ge=1, le=10)
    exchange_retry_base_delay: float = Field(default=1.0, description="Base delay in seconds")
    exchange_retry_max_delay: float = Field(default=30.0, description="Max delay in seconds")

    # Circuit breaker
    circuit_breaker_failure_threshold: int = Field(default=5, ge=1)
    circuit_breaker_recovery_timeout: int = Field(default=60, description="Seconds before retry")

    # ==================== Trading ====================
    min_trade_size_usdt: float = Field(default=10.0, ge=1.0)
    max_trade_size_usdt: float = Field(default=10000.0, le=100000.0)
    max_leverage: int = Field(default=20, ge=1, le=125)
    default_leverage: int = Field(default=5, ge=1, le=125)

    # Signal processing
    signal_expiry_seconds: int = Field(default=60, description="Signals older than this are expired")
    max_signals_per_batch: int = Field(default=10, ge=1, le=100)

    # ==================== Logging ====================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    log_file: str | None = None

    # ==================== Monitoring ====================
    enable_metrics: bool = True
    metrics_port: int = Field(default=9090, ge=1024, le=65535)

    # ==================== Security ====================
    cors_origins: list[str] = Field(default=["http://localhost:3000"])
    api_rate_limit: int = Field(default=100, description="Requests per minute per IP")

    # ==================== JWT Auth ====================
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=60 * 24, description="24 hours")
    jwt_refresh_token_expire_days: int = Field(default=30, description="30 days")

    # ==================== Telegram Auth ====================
    telegram_bot_token: str = Field(
        default="",
        description="Telegram Bot Token for Mini App auth verification",
    )
    disable_desktop_auth: bool = Field(
        default=False,
        description="Disable desktop/fallback auth (Telegram only)",
    )

    # ==================== Encryption ====================
    encryption_key: str = Field(
        default="",
        description="Fernet encryption key for API secrets (32-byte base64)",
    )

    # ==================== Validators ====================

    @field_validator("celery_broker_url", mode="before")
    @classmethod
    def set_celery_broker(cls, v, info):
        """Default celery_broker_url to redis_url if not set."""
        return v or info.data.get("redis_url", "redis://localhost:6379/0")

    @field_validator("celery_result_backend", mode="before")
    @classmethod
    def set_celery_backend(cls, v, info):
        """Default celery_result_backend to redis_url if not set."""
        return v or info.data.get("redis_url", "redis://localhost:6379/0")

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL (for Alembic)."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.
    Call get_settings.cache_clear() to reload.

    Returns:
        Settings instance.
    """
    return Settings()
