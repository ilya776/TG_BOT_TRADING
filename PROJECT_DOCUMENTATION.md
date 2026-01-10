# Whale Copy Trading - Comprehensive Project Documentation

**Version:** 1.0.0
**Last Updated:** January 2026
**Project Type:** Telegram Mini App for Cryptocurrency Copy Trading

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Backend Architecture](#backend-architecture)
5. [Database Architecture](#database-architecture)
6. [Frontend Architecture](#frontend-architecture)
7. [Worker System (Celery)](#worker-system-celery)
8. [Exchange Integrations](#exchange-integrations)
9. [Signal Generation System](#signal-generation-system)
10. [Copy Trading Engine](#copy-trading-engine)
11. [Risk Management](#risk-management)
12. [Security Architecture](#security-architecture)
13. [Deployment Architecture](#deployment-architecture)
14. [API Reference](#api-reference)
15. [Configuration Reference](#configuration-reference)
16. [Data Flow Diagrams](#data-flow-diagrams)
17. [Monitoring and Observability](#monitoring-and-observability)

---

## Executive Summary

**Whale Copy Trading** is a sophisticated cryptocurrency copy trading platform delivered as a **Telegram Mini App**. The platform automatically monitors top traders ("whales") across major centralized exchanges (CEX) including Binance, OKX, Bitget, and Bybit, generates trading signals when these traders open or close positions, and automatically copies those trades for subscribed users.

### Key Features

- **Multi-Exchange Support**: Binance, OKX, Bitget, Bybit (USD-M and COIN-M futures)
- **Real-time Signal Generation**: 10-15 second polling intervals for position changes
- **Automated Copy Trading**: 2-phase commit pattern for reliable trade execution
- **Risk Management**: Stop-loss, take-profit, daily loss limits, position limits
- **Tiered Subscriptions**: FREE, PRO ($99/mo), ELITE ($299/mo) with different features
- **Telegram Integration**: Native Mini App with WebApp authentication

### Core Workflow

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Exchange APIs   │───>│  Signal Service  │───>│  Copy Trade      │
│  (Leaderboards)  │    │  (Position       │    │  Engine          │
│                  │    │   Monitoring)    │    │                  │
└──────────────────┘    └──────────────────┘    └──────────────────┘
                                 │                       │
                                 v                       v
                        ┌──────────────────┐    ┌──────────────────┐
                        │   Redis Cache    │    │  User Exchanges  │
                        │   (Positions)    │    │  (Trade Exec)    │
                        └──────────────────┘    └──────────────────┘
```

---

## System Architecture

### High-Level Architecture

```
                              ┌─────────────────────────────────────┐
                              │           INTERNET                   │
                              └──────────────┬──────────────────────┘
                                             │
                              ┌──────────────▼──────────────────────┐
                              │    Caddy (Reverse Proxy + SSL)       │
                              │    - Auto HTTPS via Let's Encrypt    │
                              │    - Load balancing                  │
                              │    - Rate limiting                   │
                              └──────────────┬──────────────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
         ┌──────────▼──────────┐  ┌──────────▼──────────┐            │
         │   Frontend (nginx)   │  │   Backend (FastAPI)  │            │
         │   - React SPA        │  │   - REST API         │            │
         │   - Telegram WebApp  │  │   - WebSocket        │            │
         │   - TailwindCSS      │  │   - 4 workers        │            │
         └──────────────────────┘  └──────────┬──────────┘            │
                                              │                        │
                         ┌────────────────────┼────────────────────────┤
                         │                    │                        │
              ┌──────────▼──────────┐  ┌──────▼───────┐  ┌────────────▼────────────┐
              │   PostgreSQL 15     │  │    Redis 7   │  │     Celery Workers      │
              │   - Main database   │  │   - Cache    │  │   - celery_worker (2)   │
              │   - Alembic mgmt    │  │   - Broker   │  │   - celery_beat (1)     │
              │                     │  │   - Sessions │  │   - whale_monitor (1)   │
              └─────────────────────┘  └──────────────┘  └─────────────────────────┘
```

### Container Architecture

| Service | Container | Memory Limit | Purpose |
|---------|-----------|--------------|---------|
| `whale_postgres` | PostgreSQL 15 Alpine | - | Primary database |
| `whale_redis` | Redis 7 Alpine | 512MB | Cache, message broker |
| `whale_backend` | Python 3.11 | 512MB | FastAPI API server |
| `whale_celery_worker` | Python 3.11 | 1024MB | Trade execution, position monitoring |
| `whale_celery_beat` | Python 3.11 | 256MB | Task scheduler |
| `whale_monitor` | Python 3.11 | 256MB | Blockchain/whale monitoring |
| `whale_frontend` | Nginx + React | 128MB | Static frontend serving |
| `whale_caddy` | Caddy 2 Alpine | 128MB | Reverse proxy, SSL termination |
| `whale_flower` | Python 3.11 | - | Celery monitoring (optional) |

### Network Architecture

All services communicate over an internal Docker bridge network (`whale_internal`). External access is only through Caddy on ports 80/443.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      whale_network (bridge)                          │
│                                                                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐│
│  │postgres │ │  redis  │ │ backend │ │frontend │ │ celery_worker   ││
│  │  :5432  │ │  :6379  │ │  :8000  │ │   :80   │ │                 ││
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────────────┘│
│                                                                      │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐│
│  │  celery_beat    │ │  whale_monitor  │ │     caddy :80/:443      ││
│  └─────────────────┘ └─────────────────┘ └─────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Backend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Primary language |
| **FastAPI** | 0.109.2 | Async web framework |
| **Uvicorn** | 0.27.1 | ASGI server |
| **SQLAlchemy** | 2.0.27 | ORM with async support |
| **Alembic** | 1.13.1 | Database migrations |
| **asyncpg** | 0.29.0 | Async PostgreSQL driver |
| **Celery** | 5.3.6 | Distributed task queue |
| **Redis** | 5.0.1 | Caching, Celery broker |
| **Pydantic** | 2.5.3 | Data validation |
| **httpx** | 0.26.0 | Async HTTP client |
| **python-binance** | 1.0.19 | Binance API client |
| **ccxt** | 4.2.27 | Multi-exchange library |
| **aiogram** | 3.4.1 | Telegram Bot API |
| **web3** | 6.15.1 | Blockchain interaction |
| **cryptography** | 42.0.2 | API key encryption |
| **structlog** | 24.1.0 | Structured logging |

### Frontend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 18.2.0 | UI framework |
| **Vite** | 5.0.0 | Build tool |
| **TailwindCSS** | 3.3.5 | Styling |
| **Framer Motion** | 10.16.4 | Animations |
| **Recharts** | 2.10.3 | Charts/graphs |
| **Lucide React** | 0.294.0 | Icons |

### Infrastructure

| Technology | Version | Purpose |
|------------|---------|---------|
| **Docker** | 3.8 compose | Containerization |
| **PostgreSQL** | 15 Alpine | Primary database |
| **Redis** | 7 Alpine | Cache/broker |
| **Caddy** | 2 Alpine | Reverse proxy, SSL |
| **Nginx** | Alpine | Frontend serving |

---

## Backend Architecture

### Directory Structure

```
backend/
├── alembic/                    # Database migrations
│   ├── versions/              # Migration scripts
│   └── env.py                 # Alembic configuration
├── app/
│   ├── api/
│   │   ├── routes/            # API endpoints
│   │   │   ├── auth.py        # Authentication (/api/v1/auth)
│   │   │   ├── users.py       # User management (/api/v1/users)
│   │   │   ├── whales.py      # Whale discovery (/api/v1/whales)
│   │   │   ├── trades.py      # Trade management (/api/v1/trades)
│   │   │   ├── signals.py     # Trading signals (/api/v1/signals)
│   │   │   ├── balance.py     # Balance queries (/api/v1/balance)
│   │   │   ├── subscriptions.py # Subscriptions (/api/v1/subscriptions)
│   │   │   └── webhooks.py    # Telegram/payment webhooks
│   │   └── deps.py            # Dependency injection
│   ├── models/                # SQLAlchemy models
│   │   ├── user.py            # User, UserSettings, UserAPIKey
│   │   ├── whale.py           # Whale, WhaleStats, UserWhaleFollow
│   │   ├── trade.py           # Trade, Position
│   │   ├── signal.py          # WhaleSignal
│   │   ├── subscription.py    # Subscription, Payment
│   │   ├── proxy.py           # Proxy configuration
│   │   └── onchain_wallet.py  # On-chain wallet tracking
│   ├── services/
│   │   ├── exchanges/         # Exchange integrations
│   │   │   ├── base.py        # Abstract base class
│   │   │   ├── binance_executor.py
│   │   │   ├── okx_executor.py
│   │   │   ├── bybit_executor.py
│   │   │   └── __init__.py    # Factory function
│   │   ├── copy_trade_engine.py   # Core copy trading logic
│   │   ├── risk_manager.py        # Risk management
│   │   ├── trader_signals.py      # Signal generation
│   │   ├── exchange_leaderboard.py # Whale discovery
│   │   ├── wallet_manager.py      # Fund transfers
│   │   ├── circuit_breaker.py     # API failure protection
│   │   ├── whale_monitor.py       # On-chain monitoring
│   │   ├── sharing_validator.py   # Position sharing validation
│   │   └── price_service.py       # Price feeds
│   ├── workers/
│   │   ├── celery_app.py      # Celery configuration
│   │   └── tasks/
│   │       ├── trade_tasks.py      # Trade execution tasks
│   │       ├── whale_tasks.py      # Whale monitoring tasks
│   │       └── notification_tasks.py # Alert tasks
│   ├── utils/
│   │   ├── encryption.py      # API key encryption
│   │   └── telegram.py        # Telegram utilities
│   ├── config.py              # Application configuration
│   ├── database.py            # Database connection
│   └── main.py                # FastAPI application entry
├── Dockerfile
└── requirements.txt
```

### Application Entry Point (`main.py`)

```python
# Key components:
# 1. Lifespan manager for startup/shutdown
# 2. Structured logging with structlog
# 3. CORS middleware for Telegram WebApp
# 4. Exception handlers for validation/general errors
# 5. Router includes for all API modules

app = FastAPI(
    title="Whale Copy Trading Bot API",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,  # Disabled in production
)

# API Routes mounted at /api/v1/*
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(users.router, prefix="/api/v1/users")
app.include_router(whales.router, prefix="/api/v1/whales")
app.include_router(trades.router, prefix="/api/v1/trades")
app.include_router(signals.router, prefix="/api/v1/signals")
app.include_router(balance.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1/subscriptions")
app.include_router(webhooks.router, prefix="/webhook")
```

### Configuration System (`config.py`)

The application uses **Pydantic Settings** for configuration management with environment variable loading:

```python
class Settings(BaseSettings):
    # Application
    app_env: Literal["development", "staging", "production"]
    secret_key: str  # Min 32 characters
    encryption_key: str  # Min 32 characters for API key encryption

    # Database
    database_url: str  # postgresql+asyncpg://...

    # Redis
    redis_url: str  # redis://:password@host:port/db

    # Telegram
    telegram_bot_token: str
    telegram_webhook_url: str | None
    telegram_webapp_url: str | None

    # Exchange credentials (optional, for system operations)
    binance_api_key: str | None
    okx_api_key: str | None
    bybit_api_key: str | None

    # Blockchain RPC
    eth_rpc_url: str
    bsc_rpc_url: str

    # Subscription tiers configuration
    free_tier_commission: float = 0.02  # 2%
    pro_tier_commission: float = 0.01   # 1%
    elite_tier_commission: float = 0.005 # 0.5%
```

### Subscription Tiers

```python
SUBSCRIPTION_TIERS = {
    "FREE": {
        "price_monthly": 0,
        "whales_limit": 5,
        "auto_copy": True,
        "commission_rate": 0.02,
        "futures_enabled": False,
        "max_positions": 5,
    },
    "PRO": {
        "price_monthly": 99,
        "whales_limit": 5,
        "auto_copy": True,
        "commission_rate": 0.01,
        "futures_enabled": True,
        "max_positions": 10,
    },
    "ELITE": {
        "price_monthly": 299,
        "whales_limit": -1,  # Unlimited
        "auto_copy": True,
        "commission_rate": 0.005,
        "futures_enabled": True,
        "max_positions": -1,  # Unlimited
    },
}
```

---

## Database Architecture

### Entity-Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│      User       │       │     Whale       │       │   WhaleSignal   │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ telegram_id     │       │ wallet_address  │       │ whale_id (FK)   │
│ username        │       │ name            │       │ tx_hash         │
│ subscription    │       │ exchange        │       │ action          │
│ total_balance   │       │ exchange_uid    │       │ cex_symbol      │
│ available_bal   │       │ whale_type      │       │ leverage        │
│ totp_enabled    │       │ data_status     │       │ is_close_signal │
└────────┬────────┘       │ priority_score  │       │ confidence      │
         │                └────────┬────────┘       │ status          │
         │                         │                └─────────────────┘
         │                         │
         │    ┌────────────────────┼────────────────────┐
         │    │                    │                    │
         v    v                    v                    │
┌─────────────────┐       ┌─────────────────┐          │
│ UserWhaleFollow │       │   WhaleStats    │          │
├─────────────────┤       ├─────────────────┤          │
│ id (PK)         │       │ id (PK)         │          │
│ user_id (FK)    │       │ whale_id (FK)   │          │
│ whale_id (FK)   │       │ win_rate        │          │
│ auto_copy       │       │ profit_7d       │          │
│ trade_size_usdt │       │ profit_30d      │          │
│ stop_loss_%     │       │ total_trades    │          │
│ take_profit_%   │       └─────────────────┘          │
│ leverage        │                                    │
│ copy_leverage   │                                    │
└─────────────────┘                                    │
                                                       │
┌─────────────────┐       ┌─────────────────┐          │
│     Trade       │       │    Position     │<─────────┘
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ user_id (FK)    │       │ user_id (FK)    │
│ signal_id (FK)  │       │ whale_id (FK)   │
│ whale_id (FK)   │       │ entry_trade (FK)│
│ exchange        │       │ exit_trade (FK) │
│ symbol          │       │ symbol          │
│ side            │       │ side            │
│ quantity        │       │ entry_price     │
│ executed_price  │       │ stop_loss_price │
│ status          │       │ take_profit     │
│ leverage        │       │ unrealized_pnl  │
└─────────────────┘       │ realized_pnl    │
                          │ status          │
                          └─────────────────┘
```

### Model Details

#### User Model (`user.py`)

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int]  # Primary key
    telegram_id: Mapped[int]  # Unique, indexed
    username: Mapped[str | None]
    first_name: Mapped[str | None]

    # Balance tracking (USDT equivalent)
    total_balance: Mapped[Decimal]  # Total portfolio value
    available_balance: Mapped[Decimal]  # Available for trading

    # Subscription
    subscription_tier: Mapped[SubscriptionTier]  # FREE, PRO, ELITE
    subscription_expires_at: Mapped[datetime | None]

    # 2FA (optional)
    totp_secret: Mapped[str | None]
    totp_enabled: Mapped[bool]

    # Relationships
    settings: Mapped["UserSettings"]  # 1:1
    api_keys: Mapped[list["UserAPIKey"]]  # 1:N
    whale_follows: Mapped[list["UserWhaleFollow"]]  # N:M pivot
    trades: Mapped[list["Trade"]]  # 1:N
    positions: Mapped[list["Position"]]  # 1:N
```

#### UserSettings Model

```python
class UserSettings(Base):
    __tablename__ = "user_settings"

    # Trading mode
    trading_mode: Mapped[TradingMode]  # SPOT, FUTURES, MIXED
    preferred_exchange: Mapped[ExchangeName]  # BINANCE, OKX, BYBIT

    # Copy trading settings
    auto_copy_enabled: Mapped[bool]
    auto_copy_delay_seconds: Mapped[int]
    default_trade_size_usdt: Mapped[Decimal]
    max_trade_size_usdt: Mapped[Decimal]

    # Risk management
    stop_loss_percent: Mapped[Decimal]
    take_profit_percent: Mapped[Decimal | None]
    daily_loss_limit_usdt: Mapped[Decimal]
    max_open_positions: Mapped[int]

    # Futures settings
    default_leverage: Mapped[int]
    max_leverage: Mapped[int]

    # Behavior
    auto_close_on_tp: Mapped[bool]  # Auto-close at take profit
    auto_close_on_whale_exit: Mapped[bool]  # Close when whale closes
```

#### UserAPIKey Model (Encrypted)

```python
class UserAPIKey(Base):
    __tablename__ = "user_api_keys"

    user_id: Mapped[int]  # FK to users
    exchange: Mapped[ExchangeName]  # BINANCE, OKX, BYBIT

    # Encrypted credentials (AES-256-GCM)
    api_key_encrypted: Mapped[str]
    api_secret_encrypted: Mapped[str]
    passphrase_encrypted: Mapped[str | None]  # OKX only

    # Metadata
    label: Mapped[str | None]
    is_active: Mapped[bool]
    is_testnet: Mapped[bool]

    # Permissions (informational)
    can_spot_trade: Mapped[bool]
    can_futures_trade: Mapped[bool]
    can_withdraw: Mapped[bool]  # Should be False
```

#### Whale Model (`whale.py`)

```python
class Whale(Base):
    __tablename__ = "whales"

    # Identification
    wallet_address: Mapped[str]  # Format: "exchange_uid" (e.g., "binance_ABC123")
    name: Mapped[str]  # Trader nickname

    # Type and source
    whale_type: Mapped[str]  # "CEX_TRADER" or "ONCHAIN_WALLET"
    exchange: Mapped[str | None]  # BINANCE, OKX, BITGET, BYBIT
    exchange_uid: Mapped[str | None]  # Original UID from exchange

    # Data availability
    data_status: Mapped[str]  # ACTIVE, SHARING_DISABLED, RATE_LIMITED
    consecutive_empty_checks: Mapped[int]  # For detecting disabled sharing

    # Polling optimization
    priority_score: Mapped[int]  # 1-100, higher = poll more frequently
    polling_interval_seconds: Mapped[int]

    # Performance
    rank: Mapped[WhaleRank]  # BRONZE, SILVER, GOLD, PLATINUM, DIAMOND
    score: Mapped[Decimal]  # 0-100 based on ROI
```

#### WhaleSignal Model (`signal.py`)

```python
class WhaleSignal(Base):
    __tablename__ = "whale_signals"

    whale_id: Mapped[int]  # FK to whales
    tx_hash: Mapped[str]  # Unique, generated hash for CEX signals

    # Trade details
    action: Mapped[SignalAction]  # BUY, SELL
    cex_symbol: Mapped[str | None]  # e.g., "BTCUSDT"
    cex_available: Mapped[bool]  # Can be copied on CEX

    # Position metadata
    futures_type: Mapped[str | None]  # "USD-M" or "COIN-M"
    leverage: Mapped[int | None]  # Whale's leverage for copy_leverage
    is_close_signal: Mapped[bool]  # True if whale is closing position

    # Value
    amount_usd: Mapped[Decimal]
    price_at_signal: Mapped[Decimal | None]

    # Quality scoring
    confidence: Mapped[SignalConfidence]  # LOW, MEDIUM, HIGH, VERY_HIGH
    confidence_score: Mapped[Decimal]  # 0-100

    # Processing
    status: Mapped[SignalStatus]  # PENDING, PROCESSING, PROCESSED, SKIPPED
    processed_at: Mapped[datetime | None]
```

#### Trade Model (`trade.py`)

```python
class Trade(Base):
    __tablename__ = "trades"

    user_id: Mapped[int]  # FK to users
    signal_id: Mapped[int | None]  # FK to whale_signals
    whale_id: Mapped[int | None]  # FK to whales
    is_copy_trade: Mapped[bool]  # True if from copy trading

    # Exchange details
    exchange: Mapped[str]  # BINANCE, OKX, BYBIT
    exchange_order_id: Mapped[str | None]

    # Trade details
    symbol: Mapped[str]  # e.g., "BTCUSDT"
    trade_type: Mapped[TradeType]  # SPOT, FUTURES
    side: Mapped[TradeSide]  # BUY, SELL, LONG, SHORT
    order_type: Mapped[OrderType]  # MARKET, LIMIT

    # Quantities and prices
    quantity: Mapped[Decimal]
    filled_quantity: Mapped[Decimal]
    executed_price: Mapped[Decimal | None]
    trade_value_usdt: Mapped[Decimal]
    leverage: Mapped[int | None]

    # Status
    status: Mapped[TradeStatus]  # PENDING, EXECUTING, FILLED, FAILED
```

#### Position Model

```python
class Position(Base):
    __tablename__ = "positions"

    user_id: Mapped[int]  # FK to users
    whale_id: Mapped[int | None]  # FK to whales (for tracking)
    entry_trade_id: Mapped[int | None]  # FK to trades

    # Position details
    symbol: Mapped[str]
    position_type: Mapped[TradeType]  # SPOT, FUTURES
    side: Mapped[TradeSide]  # BUY (long), SELL (short)

    # Prices
    entry_price: Mapped[Decimal]
    current_price: Mapped[Decimal | None]
    exit_price: Mapped[Decimal | None]

    # Risk management (exchange-side orders)
    stop_loss_price: Mapped[Decimal | None]
    stop_loss_order_id: Mapped[str | None]  # Exchange SL order ID
    take_profit_price: Mapped[Decimal | None]
    take_profit_order_id: Mapped[str | None]  # Exchange TP order ID

    # PnL
    unrealized_pnl: Mapped[Decimal]
    unrealized_pnl_percent: Mapped[Decimal]
    realized_pnl: Mapped[Decimal]

    # Status
    status: Mapped[PositionStatus]  # OPEN, CLOSED, LIQUIDATED
    close_reason: Mapped[CloseReason | None]  # MANUAL, STOP_LOSS, etc.
```

### Database Indexes

```sql
-- User queries
CREATE INDEX ix_users_telegram_id ON users(telegram_id);
CREATE INDEX ix_users_subscription_tier ON users(subscription_tier);

-- Whale queries
CREATE INDEX ix_whales_wallet_address ON whales(wallet_address);
CREATE INDEX ix_whales_exchange_status ON whales(exchange, data_status);
CREATE INDEX ix_whales_data_status_priority ON whales(data_status, priority_score);

-- Signal queries
CREATE INDEX ix_whale_signals_status_detected ON whale_signals(status, detected_at);
CREATE INDEX ix_whale_signals_cex_symbol ON whale_signals(cex_symbol);

-- Trade queries
CREATE INDEX ix_trades_user_status ON trades(user_id, status);
CREATE INDEX ix_trades_whale_id ON trades(whale_id);

-- Position queries
CREATE INDEX ix_positions_user_status ON positions(user_id, status);
CREATE INDEX ix_positions_symbol_status ON positions(symbol, status);
```

---

## Frontend Architecture

### Directory Structure

```
frontend/
├── src/
│   ├── screens/           # Main application screens
│   │   ├── Dashboard.jsx      # Portfolio overview, positions
│   │   ├── WhaleDiscovery.jsx # Browse/follow whales
│   │   ├── TradeHistory.jsx   # Historical trades
│   │   ├── LiveAlerts.jsx     # Real-time signals
│   │   ├── Statistics.jsx     # Performance analytics
│   │   └── Settings.jsx       # User settings, API keys
│   ├── components/        # Reusable UI components
│   │   ├── ErrorBoundary.jsx  # Error handling
│   │   ├── Toast.jsx          # Notifications
│   │   ├── FeatureGate.jsx    # Subscription-gated features
│   │   └── TradeModal.jsx     # Trade execution modal
│   ├── hooks/
│   │   └── useApi.js          # API data fetching hook
│   ├── services/
│   │   └── api.js             # API client configuration
│   ├── utils/
│   │   └── animations.js      # Framer Motion presets
│   ├── App.jsx            # Main application component
│   ├── main.jsx           # Application entry point
│   └── index.css          # Global styles (Tailwind)
├── tailwind.config.js     # Tailwind configuration
├── vite.config.js         # Vite build configuration
└── package.json
```

### Application Flow

```jsx
// main.jsx - Entry point
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

// App.jsx - Main component with routing
function App() {
  const [currentScreen, setCurrentScreen] = useState('dashboard');
  const [user, setUser] = useState(null);

  // Initialize Telegram WebApp SDK
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      // Get user from initData
    }
  }, []);

  // Screen routing
  const renderScreen = () => {
    switch (currentScreen) {
      case 'dashboard': return <Dashboard />;
      case 'whales': return <WhaleDiscovery />;
      case 'trades': return <TradeHistory />;
      case 'alerts': return <LiveAlerts />;
      case 'stats': return <Statistics />;
      case 'settings': return <Settings />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-900">
      <Navigation current={currentScreen} onChange={setCurrentScreen} />
      <ErrorBoundary>
        {renderScreen()}
      </ErrorBoundary>
      <Toast />
    </div>
  );
}
```

### Key Screens

#### Dashboard
- Portfolio overview (total balance, PnL)
- Active positions with real-time prices
- Quick actions (close position, set SL/TP)
- Recent signals summary

#### WhaleDiscovery
- Browse top traders from exchanges
- Filter by exchange, ROI, win rate
- Follow/unfollow whales
- Configure per-whale copy settings

#### TradeHistory
- Historical trades with P&L
- Filter by symbol, whale, status
- Trade details and execution info

#### LiveAlerts
- Real-time signal feed
- Signal confidence indicators
- Manual copy execution

#### Settings
- Exchange API key management
- Copy trading preferences
- Risk management settings
- Notification preferences

### API Integration (`services/api.js`)

```javascript
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const api = {
  // Get Telegram initData for authentication
  getAuthHeaders() {
    const tg = window.Telegram?.WebApp;
    return {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': tg?.initData || '',
    };
  },

  // API methods
  async getUser() { /* ... */ },
  async getWhales(params) { /* ... */ },
  async followWhale(whaleId, settings) { /* ... */ },
  async getPositions() { /* ... */ },
  async closePosition(positionId) { /* ... */ },
  async getTrades(params) { /* ... */ },
  async getSignals(params) { /* ... */ },
  async copySignal(signalId, options) { /* ... */ },
  async updateSettings(settings) { /* ... */ },
  async addApiKey(exchange, credentials) { /* ... */ },
};
```

### Custom Hooks (`hooks/useApi.js`)

```javascript
export function useApi(endpoint, options = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(endpoint, {
        headers: api.getAuthHeaders(),
        ...options,
      });
      const json = await response.json();
      setData(json);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}
```

### Styling (TailwindCSS)

Custom Telegram-native color scheme:

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        'tg-bg': 'var(--tg-theme-bg-color)',
        'tg-text': 'var(--tg-theme-text-color)',
        'tg-hint': 'var(--tg-theme-hint-color)',
        'tg-link': 'var(--tg-theme-link-color)',
        'tg-button': 'var(--tg-theme-button-color)',
        'tg-button-text': 'var(--tg-theme-button-text-color)',
      },
    },
  },
};
```

---

## Worker System (Celery)

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Celery Beat (Scheduler)                      │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ check-whale-    │  │ update-position-│  │ sync-exchange-      │  │
│  │ positions (10s) │  │ prices (10s)    │  │ leaderboards (120s) │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ monitor-        │  │ sync-user-      │  │ sync-positions-     │  │
│  │ positions (10s) │  │ balances (15s)  │  │ with-exchange (30s) │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │              TIERED POLLING SYSTEM                              ││
│  │  • Critical (15s): Followed whales with recent activity         ││
│  │  • High (30s): Bitget (always public) + high-score whales       ││
│  │  • Normal (45s): Standard active whales                         ││
│  │  • Low (120s): Low activity whales                              ││
│  └─────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   v
┌─────────────────────────────────────────────────────────────────────┐
│                        Redis (Message Broker)                        │
│                                                                      │
│  Queues: celery, trades, notifications, whales                       │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   v
┌─────────────────────────────────────────────────────────────────────┐
│                      Celery Worker (2 concurrency)                   │
│                                                                      │
│  Trade Tasks:                    Whale Tasks:                        │
│  • execute_copy_trade           • check_whale_positions              │
│  • close_position               • poll_whales_by_tier                │
│  • sync_all_user_balances       • sync_exchange_leaderboards         │
│  • update_position_prices       • update_whale_statistics            │
│  • monitor_positions            • validate_sharing_status            │
│  • sync_positions_with_exchange • recalculate_whale_priorities       │
│                                                                      │
│  Notification Tasks:                                                 │
│  • send_whale_alert                                                  │
│  • send_trade_notification                                           │
│  • cleanup_old_notifications                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Task Configuration

```python
# celery_app.py
celery_app.conf.update(
    # Task execution
    task_acks_late=True,  # Acknowledge after completion
    task_reject_on_worker_lost=True,  # Re-queue on worker crash
    task_time_limit=600,  # 10 minutes max
    task_soft_time_limit=540,  # 9 minutes soft limit

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time
    worker_concurrency=2,  # 2 concurrent tasks

    # Task routing
    task_routes={
        "app.workers.tasks.trade_tasks.*": {"queue": "trades"},
        "app.workers.tasks.notification_tasks.*": {"queue": "notifications"},
        "app.workers.tasks.whale_tasks.*": {"queue": "whales"},
    },
)
```

### Critical Tasks

#### `execute_copy_trade`

Executes copy trades with idempotency protection:

```python
@celery_app.task(bind=True, max_retries=3)
def execute_copy_trade(self, signal_id, user_id=None, size_usdt=None, exchange=None):
    """
    Execute copy trades for a whale signal.

    Features:
    - Idempotency lock (Redis) prevents duplicate execution
    - Double-checks signal status before processing
    - Supports manual copy (user_id specified) or auto-copy (all followers)
    - Optional size and exchange overrides
    """
    with IdempotencyLock("trade", signal_id, user_id or "auto") as lock:
        if lock.already_completed:
            return {"status": "already_completed"}
        if not lock.acquired:
            return {"status": "skipped", "reason": "duplicate_execution"}

        # Process signal through CopyTradeEngine
        results = run_async(process_signal_async(signal_id, user_id, size_usdt, exchange))

        lock.mark_completed({"successful": sum(r.success for r in results)})
        return results
```

#### `close_position`

Closes positions with atomic locking:

```python
@celery_app.task(bind=True, max_retries=3)
def close_position(self, user_id, position_id, reason="manual"):
    """
    Close an open position.

    Features:
    - Row-level locking (SELECT FOR UPDATE) prevents race conditions
    - Supports multiple close reasons: manual, stop_loss, take_profit, whale_exit
    - Updates user balance with realized PnL
    - Creates closing trade record
    """
    with IdempotencyLock("close_position", position_id) as lock:
        # ... atomic close logic
```

#### `sync_positions_with_exchange`

Detects externally closed positions:

```python
@celery_app.task
def sync_positions_with_exchange():
    """
    CRITICAL: Sync position statuses with exchange.

    Detects positions closed on exchange but still OPEN in DB:
    - Manual close on exchange
    - Liquidation
    - Exchange-side TP/SL triggered
    - Bot crash after exchange close

    Auto-closes orphaned positions and returns margin to user.
    """
```

### Dead Letter Queue (DLQ)

Failed tasks are captured for analysis:

```python
@task_failure.connect
def handle_task_failure(sender, task_id, exception, args, kwargs, traceback, **kw):
    """Store failed tasks in Redis DLQ for later analysis."""
    failed_task = {
        "task_id": task_id,
        "task_name": sender.name,
        "exception": str(exception),
        "traceback": str(traceback)[-2000:],
        "failed_at": datetime.utcnow().isoformat(),
    }
    redis_client.lpush("whale_trading:dead_letter_queue", json.dumps(failed_task))
    redis_client.ltrim("whale_trading:dead_letter_queue", 0, 999)  # Keep last 1000
```

---

## Exchange Integrations

### Supported Exchanges

| Exchange | Spot | USD-M Futures | COIN-M Futures | Copy Trading API |
|----------|------|---------------|----------------|------------------|
| **Binance** | ✅ | ✅ | ✅ | ✅ (Leaderboard) |
| **OKX** | ✅ | ✅ | ✅ | ✅ (Copy Trading) |
| **Bybit** | ✅ | ✅ | ❌ | ✅ (Copy Trading) |
| **Bitget** | ❌ | ✅ | ✅ | ✅ (Copy Trading) |

### Base Exchange Interface

```python
class BaseExchange(ABC):
    """Abstract base class for all exchange integrations."""

    # Account
    @abstractmethod
    async def get_account_balance(self) -> list[Balance]: pass

    # Spot Trading
    @abstractmethod
    async def spot_market_buy(self, symbol, quantity, quote_order_qty=None) -> OrderResult: pass
    @abstractmethod
    async def spot_market_sell(self, symbol, quantity) -> OrderResult: pass

    # Futures Trading
    @abstractmethod
    async def set_leverage(self, symbol, leverage) -> bool: pass
    @abstractmethod
    async def futures_market_long(self, symbol, quantity) -> OrderResult: pass
    @abstractmethod
    async def futures_market_short(self, symbol, quantity) -> OrderResult: pass
    @abstractmethod
    async def futures_close_position(self, symbol, position_side, quantity=None) -> OrderResult: pass

    # Positions & Orders
    @abstractmethod
    async def get_open_positions(self, symbol=None) -> list[Position]: pass
    @abstractmethod
    async def get_ticker_price(self, symbol) -> Decimal | None: pass

    # Circuit breaker integration
    def record_success(self): pass
    def record_failure(self, exception): pass
```

### Binance Executor

Full implementation supporting:
- **Spot**: Market/limit buy/sell
- **USD-M Futures**: Long/short with leverage up to 125x
- **COIN-M Futures**: Coin-margined perpetuals
- **Wallet Management**: Spot ↔ Futures transfers
- **Stop Loss Orders**: Native exchange SL placement

Key methods:
```python
class BinanceExecutor(BaseExchange):
    # USD-M Futures
    async def futures_market_long(self, symbol, quantity) -> OrderResult
    async def futures_market_short(self, symbol, quantity) -> OrderResult
    async def set_leverage(self, symbol, leverage) -> bool
    async def get_futures_balance() -> list[Balance]

    # COIN-M Futures
    async def coinm_market_long(self, symbol, quantity) -> OrderResult
    async def coinm_market_short(self, symbol, quantity) -> OrderResult
    async def coinm_set_leverage(self, symbol, leverage) -> bool

    # Stop Loss
    async def place_stop_loss_order(self, symbol, side, quantity, stop_price) -> dict

    # Wallet transfers
    async def transfer_spot_to_futures(self, amount, currency="USDT") -> bool
    async def transfer_futures_to_spot(self, amount, currency="USDT") -> bool
```

### Circuit Breaker

Protects against exchange API failures:

```python
class CircuitBreaker:
    """
    Implements circuit breaker pattern for exchange APIs.

    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: Too many failures, requests blocked
    - HALF_OPEN: Testing if service recovered

    Configuration:
    - failure_threshold: 5 failures to open circuit
    - reset_timeout: 60 seconds before half-open
    - half_open_max_calls: 3 test calls in half-open
    """

    def record_failure(self, exception=None):
        """Record a failed API call."""

    def record_success(self):
        """Record a successful API call."""

    def can_execute(self) -> bool:
        """Check if requests are allowed."""
```

### Exchange Priority Scores

For whale polling optimization:

```python
EXCHANGE_PRIORITY_SCORES = {
    "BINANCE": 50,   # ~40% share positions publicly
    "BITGET": 80,    # 100% always public (copy trading)
    "OKX": 70,       # ~70% public
    "BYBIT": 60,     # Variable
}
```

---

## Signal Generation System

### Overview

The signal generation system monitors top traders on exchanges and creates trading signals when they open or close positions.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Exchange        │    │ TraderSignal    │    │ WhaleSignal     │
│ Leaderboard     │───>│ Service         │───>│ (Database)      │
│ APIs            │    │                 │    │                 │
└─────────────────┘    └────────┬────────┘    └────────┬────────┘
                                │                      │
                                v                      v
                       ┌─────────────────┐    ┌─────────────────┐
                       │ Redis Cache     │    │ CopyTradeEngine │
                       │ (Position State)│    │ (Execution)     │
                       └─────────────────┘    └─────────────────┘
```

### TraderSignalService

```python
class TraderSignalService:
    """
    Monitors top traders and generates signals when they open/close positions.
    """

    async def fetch_binance_trader_positions(self, encrypted_uid) -> list[TraderPosition]:
        """Fetch USD-M and COIN-M positions for a Binance trader."""

    async def fetch_okx_trader_positions(self, unique_code) -> list[TraderPosition]:
        """Fetch positions for an OKX copy trading leader."""

    async def fetch_bitget_trader_positions(self, trader_uid) -> list[TraderPosition]:
        """Fetch positions for a Bitget copy trading master."""

    async def check_and_generate_signals(self, max_traders=100) -> int:
        """
        Main signal generation loop.

        1. Get whales to check (followed first, then by priority)
        2. Fetch current positions from exchange
        3. Compare with cached previous positions
        4. Generate BUY signal for new positions
        5. Generate SELL signal for closed positions
        6. Update Redis cache
        """
```

### Position Change Detection

```python
# Compare positions
previous_positions = self._get_cached_positions(cache_key)
current_positions = await self.fetch_positions(whale)

previous_symbols = {p.symbol for p in previous_positions}
current_symbols = {p.symbol for p in current_positions}

# New positions → BUY signals
new_symbols = current_symbols - previous_symbols
for pos in current_positions:
    if pos.symbol in new_symbols:
        await self._create_signal(whale, pos, SignalAction.BUY)

# Closed positions → SELL signals (with is_close_signal=True)
closed_symbols = previous_symbols - current_symbols
for prev_pos in previous_positions:
    if prev_pos.symbol in closed_symbols:
        action = SignalAction.SELL if prev_pos.side == "LONG" else SignalAction.BUY
        await self._create_signal(whale, prev_pos, action, is_close=True)

# Update cache
self._set_cached_positions(cache_key, current_positions)
```

### Signal Confidence Scoring

```python
def _calculate_confidence_score(self, position, whale_score) -> Decimal:
    """
    Calculate signal confidence (0-100).

    Factors:
    - Whale score (0-50 points): Based on historical performance
    - ROE contribution (0-30 points): Current position profitability
    - Leverage penalty (0-20 points): Higher leverage = lower confidence
    """
    base_score = whale_score * 0.5
    roe_score = min(30, abs(position.roe) * 3)
    leverage_penalty = min(20, position.leverage * 1.5)

    return max(10, min(100, base_score + roe_score - leverage_penalty))
```

### Sharing Status Validation

Detects when traders disable position sharing:

```python
class SharingValidator:
    """
    Tracks consecutive empty position checks to detect disabled sharing.

    Binance traders can disable position sharing at any time.
    After 5 consecutive empty checks, mark as SHARING_DISABLED.
    Recheck after 24 hours.
    """

    EMPTY_CHECK_THRESHOLD = 5
    RECHECK_HOURS = 24

    async def check_and_update_status(self, whale, positions, error=None) -> str:
        if positions:
            whale.consecutive_empty_checks = 0
            whale.last_position_found = datetime.utcnow()
            whale.data_status = "ACTIVE"
        else:
            whale.consecutive_empty_checks += 1
            if whale.consecutive_empty_checks >= self.EMPTY_CHECK_THRESHOLD:
                whale.data_status = "SHARING_DISABLED"
                whale.sharing_disabled_at = datetime.utcnow()
                whale.sharing_recheck_at = datetime.utcnow() + timedelta(hours=24)
```

---

## Copy Trading Engine

### 2-Phase Commit Pattern

The copy trade engine uses a 2-phase commit pattern to ensure trade reliability and prevent orphaned trades:

```
PHASE 1 (Reserve):
┌────────────────────────────────────────────────────────────────────┐
│ 1. Lock user row (SELECT FOR UPDATE)                               │
│ 2. Check available balance                                         │
│ 3. Create PENDING trade record                                     │
│ 4. Reserve balance (deduct from available)                         │
│ 5. COMMIT                                                          │
└────────────────────────────────────────────────────────────────────┘
                                 │
                                 v
EXCHANGE CALL (Between phases - recoverable):
┌────────────────────────────────────────────────────────────────────┐
│ 1. Update trade status to EXECUTING                                │
│ 2. Auto-transfer funds to futures if needed                        │
│ 3. Set leverage on exchange                                        │
│ 4. Execute market order                                            │
│ - If crash here: PENDING trade exists for reconciliation           │
└────────────────────────────────────────────────────────────────────┘
                                 │
                                 v
PHASE 2 (Confirm/Rollback):
┌────────────────────────────────────────────────────────────────────┐
│ On SUCCESS:                                                        │
│ 1. Update trade with exchange results (order_id, fill_price)       │
│ 2. Set status to FILLED                                            │
│ 3. Create/update Position record                                   │
│ 4. Place auto stop-loss order on exchange                          │
│ 5. COMMIT                                                          │
│                                                                    │
│ On FAILURE:                                                        │
│ 1. Set trade status to FAILED                                      │
│ 2. Restore reserved balance                                        │
│ 3. COMMIT                                                          │
└────────────────────────────────────────────────────────────────────┘
```

### CopyTradeEngine Class

```python
class CopyTradeEngine:
    """
    Executes copy trades based on whale signals.

    Workflow:
    1. Receive signal from whale monitor
    2. Find all users following this whale with auto-copy enabled
    3. For each user:
       - Check risk limits
       - Calculate position size
       - Execute trade on their preferred exchange
       - Create trade/position records
       - Place stop-loss order
    """

    async def process_signal(self, signal, user_id=None, size_override=None, exchange_override=None):
        """Main entry point for processing a whale signal."""

        # Check if signal is valid for copy trading
        if not signal.cex_available:
            signal.status = SignalStatus.SKIPPED
            return []

        # Get followers (or specific user for manual copy)
        if user_id:
            followers = await self._get_specific_user_for_copy(user_id, signal.whale_id)
        else:
            followers = await self._get_auto_copy_followers(signal.whale_id)

        # Process each follower
        results = []
        for follow, user, settings in followers:
            result = await self._execute_copy_trade(signal, follow, user, settings)
            results.append(result)

        return results
```

### Trade Size Calculation

```python
async def _calculate_trade_size(self, follow, user, settings, signal) -> Decimal:
    """
    Calculate trade size with priority:
    1. Follow-specific trade size (per-whale setting)
    2. Follow-specific percentage of balance
    3. User's default trade size (from settings)
    4. Fallback: 1% of balance
    """
    if follow.trade_size_usdt:
        return follow.trade_size_usdt

    if follow.trade_size_percent:
        return user.available_balance * (follow.trade_size_percent / 100)

    if settings and settings.default_trade_size_usdt:
        return settings.default_trade_size_usdt

    return user.available_balance * Decimal("0.01")
```

### Leverage Handling

```python
def _get_leverage(self, follow, settings, signal, is_futures) -> int:
    """
    Get leverage for the trade with priority:
    1. Follow-specific leverage (user explicitly set per-whale)
    2. Whale's actual leverage from signal (DEFAULT - copy what whale uses)
    3. User's max_leverage as safety cap
    4. Default: 5x
    """
    if not is_futures:
        return 1

    max_leverage = settings.max_leverage if settings else 125

    # Per-whale override takes precedence
    if follow.leverage:
        return min(follow.leverage, max_leverage)

    # Default: copy whale's leverage
    if signal.leverage:
        return min(signal.leverage, max_leverage)

    # Fallback to user's default
    if settings and settings.default_leverage:
        return min(settings.default_leverage, max_leverage)

    return 5
```

### Close Signal Handling

When a whale closes a position, followers' positions can be auto-closed:

```python
async def _execute_close_trade(self, signal, user, settings) -> CopyTradeResult:
    """
    Close user's position when whale closes theirs.

    Respects user's auto_close_on_whale_exit setting.
    """
    # Check if user wants auto-close
    if not settings.auto_close_on_whale_exit:
        return CopyTradeResult(success=True, details={"reason": "auto_close_disabled"})

    # Find matching open position
    position = await db.execute(
        select(Position).where(
            Position.user_id == user.id,
            Position.whale_id == signal.whale_id,
            Position.symbol == signal.cex_symbol,
            Position.status == PositionStatus.OPEN,
        )
    )

    if not position:
        return CopyTradeResult(success=True, details={"reason": "no_open_position"})

    # Queue position close
    close_position.delay(user.id, position.id, "whale_exit")

    return CopyTradeResult(success=True, position_id=position.id)
```

---

## Risk Management

### RiskManager Class

```python
class RiskManager:
    """
    Manages trading risk and enforces limits.

    Responsibilities:
    - Pre-trade risk checks
    - Position sizing
    - Daily loss limits
    - Max position limits
    - Stop-loss monitoring
    """

    async def check_trade_risk(self, user, symbol, trade_size_usdt, is_futures, leverage) -> RiskCheckResult:
        """
        Pre-trade risk validation.

        Checks:
        1. User is active (not banned)
        2. Minimum balance ($5 USDT)
        3. Minimum trade size ($5 USDT)
        4. Futures permission (PRO+ subscription)
        5. Available balance (auto-adjust if insufficient)
        6. Max trade size limit
        7. Daily loss limit
        8. Max open positions
        9. Leverage limits
        """
```

### Risk Check Flow

```python
async def check_trade_risk(self, user, symbol, trade_size_usdt, is_futures, leverage):
    warnings = []

    # Check 1: User status
    if not user.is_active or user.is_banned:
        return RiskCheckResult(allowed=False, reason="User account is not active")

    # Check 2: Minimum balance
    if user.available_balance < MIN_TRADING_BALANCE_USDT:  # $5
        return RiskCheckResult(
            allowed=False,
            reason=f"Balance below minimum ${MIN_TRADING_BALANCE_USDT}"
        )

    # Check 3: Minimum trade size
    if trade_size_usdt < MIN_TRADE_SIZE_USDT:  # $5
        return RiskCheckResult(allowed=False, reason=f"Trade size below minimum")

    # Check 4: Futures permission
    tier_config = SUBSCRIPTION_TIERS[user.subscription_tier]
    if is_futures and not tier_config["futures_enabled"]:
        return RiskCheckResult(allowed=False, reason="Futures requires PRO subscription")

    # Check 5: Auto-adjust trade size to fit balance
    if user.available_balance < trade_size_usdt:
        adjusted = user.available_balance * Decimal("0.80")  # 80% of balance
        if adjusted >= MIN_TRADE_SIZE_USDT:
            warnings.append(f"Trade size auto-adjusted to ${adjusted}")
            trade_size_usdt = adjusted
        else:
            return RiskCheckResult(allowed=False, reason="Insufficient balance")

    # Check 6: Max trade size
    if settings.max_trade_size_usdt and trade_size_usdt > settings.max_trade_size_usdt:
        trade_size_usdt = settings.max_trade_size_usdt
        warnings.append(f"Trade size reduced to max limit")

    # Check 7: Daily loss limit
    daily_loss = await self._get_daily_loss(user.id)
    if daily_loss >= settings.daily_loss_limit_usdt:
        return RiskCheckResult(allowed=False, reason="Daily loss limit reached")

    # Check 8: Max positions
    open_positions = await self._get_open_positions_count(user.id)
    max_positions = tier_config["max_positions"]
    if max_positions > 0 and open_positions >= max_positions:
        return RiskCheckResult(allowed=False, reason="Maximum open positions reached")

    return RiskCheckResult(
        allowed=True,
        adjusted_quantity=trade_size_usdt,
        warnings=warnings
    )
```

### Exchange Minimum Notional Values

```python
EXCHANGE_MIN_NOTIONAL = {
    "binance": {
        "USD-M": 5.0,     # 5 USDT minimum for USD-M futures
        "COIN-M": 10.0,   # ~$10 for COIN-M
        "SPOT": 10.0,     # 10 USDT minimum for spot
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
```

### Smart Position Sizing

```python
def calculate_safe_trade_size(self, balance, leverage, exchange, futures_type, percent=1):
    """
    Calculate safe trade size respecting exchange minimums.

    Args:
        balance: User's available balance
        leverage: Leverage to use
        exchange: Exchange name
        futures_type: USD-M, COIN-M, or SPOT
        percent: Percentage of balance to use (default 1%)

    Returns:
        Safe margin size in USDT
    """
    # Get exchange minimum notional
    min_notional = EXCHANGE_MIN_NOTIONAL[exchange][futures_type]

    # Calculate minimum margin (notional / leverage)
    min_margin = min_notional / leverage

    # Add 20% buffer for fees and slippage
    min_margin_buffered = min_margin * 1.20

    # User's default size
    user_size = balance * (percent / 100)

    # Use larger of minimum or user preference
    base_size = max(min_margin_buffered, user_size)

    # Cap at 10% of balance
    max_size = balance * 0.10

    return min(base_size, max_size, balance)
```

---

## Security Architecture

### API Key Encryption

User exchange API keys are encrypted using **AES-256-GCM**:

```python
class EncryptionManager:
    """
    AES-256-GCM encryption for sensitive data.

    Features:
    - 256-bit key derived from ENCRYPTION_KEY setting
    - Random 12-byte nonce per encryption
    - Authentication tag prevents tampering
    """

    def encrypt(self, plaintext: str) -> str:
        """Encrypt and return base64-encoded ciphertext."""
        nonce = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext.encode()) + encryptor.finalize()
        return base64.b64encode(nonce + encryptor.tag + ciphertext).decode()

    def decrypt(self, encrypted: str) -> str:
        """Decrypt base64-encoded ciphertext."""
        data = base64.b64decode(encrypted)
        nonce = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(nonce, tag))
        decryptor = cipher.decryptor()
        return (decryptor.update(ciphertext) + decryptor.finalize()).decode()
```

### Telegram WebApp Authentication

```python
def verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """
    Verify Telegram WebApp initData using HMAC-SHA256.

    Process:
    1. Parse initData as URL query string
    2. Sort parameters alphabetically (excluding 'hash')
    3. Create data-check-string: "key=value\nkey=value\n..."
    4. Compute HMAC-SHA256 using secret_key = HMAC-SHA256("WebAppData", bot_token)
    5. Compare computed hash with provided hash
    """
    parsed = urllib.parse.parse_qs(init_data)

    # Extract and verify hash
    received_hash = parsed.pop('hash', [None])[0]

    # Create data-check-string
    data_check_string = '\n'.join(
        f"{k}={v[0]}" for k, v in sorted(parsed.items())
    )

    # Compute secret key
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()

    # Compute and compare hash
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    return computed_hash == received_hash
```

### CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://web.telegram.org",
        "https://*.telegram.org",
        settings.telegram_webapp_url,
    ] + (["http://localhost:3000", "http://localhost:5173"] if settings.debug else []),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2FA Support (TOTP)

Optional TOTP-based two-factor authentication:

```python
# User model fields
totp_secret: str | None  # 32-character secret
totp_enabled: bool

# Verification
import pyotp

def verify_totp(user: User, code: str) -> bool:
    if not user.totp_enabled or not user.totp_secret:
        return True  # 2FA not enabled

    totp = pyotp.TOTP(user.totp_secret)
    return totp.verify(code)
```

---

## Deployment Architecture

### Docker Compose Configuration

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: whale_copy_trading
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
    networks:
      - whale_internal

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD} --maxmemory 512mb
    volumes:
      - redis_data:/data
    networks:
      - whale_internal

  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:${DB_PASSWORD}@postgres:5432/whale_copy_trading
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    command: sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    networks:
      - whale_internal

  celery_worker:
    build: ./backend
    command: celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 -Q celery,trades,notifications,whales
    stop_grace_period: 60s  # Critical for trade completion
    deploy:
      resources:
        limits:
          memory: 1024M
    networks:
      - whale_internal

  celery_beat:
    build: ./backend
    command: sh -c "rm -f /tmp/celerybeat.pid && celery -A app.workers.celery_app beat --loglevel=info"
    networks:
      - whale_internal

  frontend:
    build:
      context: ./frontend
      args:
        - VITE_API_URL=/api/v1
    networks:
      - whale_internal

  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
    networks:
      - whale_internal

volumes:
  postgres_data:
  redis_data:
  caddy_data:

networks:
  whale_internal:
    driver: bridge
    name: whale_network
```

### Environment Variables

```bash
# Required
SECRET_KEY=your-32-character-minimum-secret-key
ENCRYPTION_KEY=your-32-character-minimum-encryption-key
DB_PASSWORD=secure-database-password
REDIS_PASSWORD=secure-redis-password
TELEGRAM_BOT_TOKEN=your-telegram-bot-token

# Optional - Exchange credentials (for system operations)
BINANCE_API_KEY=
BINANCE_API_SECRET=
OKX_API_KEY=
OKX_API_SECRET=
OKX_PASSPHRASE=
BYBIT_API_KEY=
BYBIT_API_SECRET=

# Blockchain RPC
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/your-key
BSC_RPC_URL=https://bsc-dataseed.binance.org/

# Application
APP_ENV=production
LOG_LEVEL=INFO
```

### Caddyfile

```caddyfile
your-domain.com {
    # Frontend
    handle /* {
        reverse_proxy frontend:80
    }

    # API
    handle /api/* {
        reverse_proxy backend:8000
    }

    # WebSocket
    handle /ws/* {
        reverse_proxy backend:8000
    }

    # Webhooks
    handle /webhook/* {
        reverse_proxy backend:8000
    }
}
```

---

## API Reference

### Authentication

All API endpoints require Telegram WebApp authentication via the `X-Telegram-Init-Data` header.

### Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/telegram` | Authenticate with Telegram initData |
| GET | `/api/v1/users/me` | Get current user |
| PATCH | `/api/v1/users/me/settings` | Update user settings |
| POST | `/api/v1/users/me/api-keys` | Add exchange API key |
| DELETE | `/api/v1/users/me/api-keys/{id}` | Remove API key |
| GET | `/api/v1/whales` | List whales (with filters) |
| GET | `/api/v1/whales/{id}` | Get whale details |
| POST | `/api/v1/whales/{id}/follow` | Follow a whale |
| DELETE | `/api/v1/whales/{id}/follow` | Unfollow a whale |
| PATCH | `/api/v1/whales/{id}/follow` | Update follow settings |
| GET | `/api/v1/trades` | List user's trades |
| GET | `/api/v1/trades/positions` | List open positions |
| POST | `/api/v1/trades/positions/{id}/close` | Close a position |
| PATCH | `/api/v1/trades/positions/{id}` | Update SL/TP |
| GET | `/api/v1/signals` | List recent signals |
| POST | `/api/v1/signals/{id}/copy` | Manually copy a signal |
| GET | `/api/v1/balance` | Get aggregated balance |

### Example Requests

#### Get User Profile
```http
GET /api/v1/users/me
X-Telegram-Init-Data: query_id=...&user=...&hash=...

Response:
{
  "id": 1,
  "telegram_id": 123456789,
  "username": "trader",
  "subscription_tier": "PRO",
  "total_balance": "5000.00",
  "available_balance": "4500.00",
  "settings": {
    "trading_mode": "FUTURES",
    "preferred_exchange": "BINANCE",
    "auto_copy_enabled": true,
    "default_trade_size_usdt": "100.00",
    "stop_loss_percent": "10.00"
  }
}
```

#### Follow a Whale
```http
POST /api/v1/whales/42/follow
Content-Type: application/json

{
  "auto_copy_enabled": true,
  "trade_size_usdt": "50.00",
  "stop_loss_percent": "5.00",
  "take_profit_percent": "15.00",
  "copy_leverage": true
}

Response:
{
  "id": 100,
  "whale_id": 42,
  "user_id": 1,
  "auto_copy_enabled": true,
  "trade_size_usdt": "50.00",
  "followed_at": "2026-01-06T12:00:00Z"
}
```

#### Copy a Signal Manually
```http
POST /api/v1/signals/999/copy
Content-Type: application/json

{
  "size_usdt": 25.00,
  "exchange": "BINANCE"
}

Response:
{
  "status": "queued",
  "task_id": "abc123",
  "signal_id": 999,
  "estimated_execution": "< 5 seconds"
}
```

---

## Configuration Reference

### Trading Limits

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MIN_TRADING_BALANCE_USDT` | 5.0 | Minimum balance to allow trading |
| `MIN_TRADE_SIZE_USDT` | 5.0 | Minimum trade size |
| `TRADE_SIZE_BUFFER_PERCENT` | 20 | Buffer above exchange minimum |

### Celery Schedule

| Task | Interval | Purpose |
|------|----------|---------|
| `check-whale-positions` | 10s | Generate trading signals |
| `update-position-prices` | 10s | Update current prices |
| `monitor-positions` | 10s | Check SL/TP triggers |
| `sync-user-balances` | 15s | Sync exchange balances |
| `sync-positions-with-exchange` | 30s | Detect externally closed positions |
| `poll-critical-whales` | 15s | Followed whales |
| `poll-high-whales` | 30s | Bitget + high-score |
| `poll-normal-whales` | 45s | Standard active |
| `poll-low-whales` | 120s | Low activity |
| `sync-exchange-leaderboards` | 120s | Discover new whales |
| `update-whale-stats` | 3600s | Update performance metrics |
| `validate-sharing-status` | 3600s | Recheck disabled whales |

### Circuit Breaker

| Parameter | Value | Description |
|-----------|-------|-------------|
| `failure_threshold` | 5 | Failures before opening circuit |
| `reset_timeout` | 60s | Time before half-open |
| `half_open_max_calls` | 3 | Test calls in half-open |

---

## Data Flow Diagrams

### Signal Generation Flow

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Celery Beat   │────>│ poll_whales   │────>│ Exchange API  │
│ (scheduler)   │     │ _by_tier      │     │ (positions)   │
└───────────────┘     └───────────────┘     └───────────────┘
                             │                      │
                             │                      v
                             │              ┌───────────────┐
                             │              │ Redis Cache   │
                             │              │ (prev state)  │
                             │              └───────────────┘
                             │                      │
                             v                      v
                      ┌───────────────────────────────────┐
                      │     Position Comparison           │
                      │     new = current - previous      │
                      │     closed = previous - current   │
                      └───────────────────────────────────┘
                                      │
                                      v
                      ┌───────────────────────────────────┐
                      │     Create WhaleSignal records    │
                      │     BUY for new, SELL for closed  │
                      └───────────────────────────────────┘
                                      │
                                      v
                      ┌───────────────────────────────────┐
                      │     Queue execute_copy_trade      │
                      │     task in Celery                │
                      └───────────────────────────────────┘
```

### Copy Trade Execution Flow

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ execute_copy  │────>│ Idempotency   │────>│ Get Followers │
│ _trade task   │     │ Lock Check    │     │ (auto-copy)   │
└───────────────┘     └───────────────┘     └───────────────┘
                                                   │
                                                   v
                                           ┌───────────────┐
                                           │ For each      │
                                           │ follower:     │
                                           └───────────────┘
                                                   │
                    ┌──────────────────────────────┼──────────────────────────────┐
                    │                              │                              │
                    v                              v                              v
            ┌───────────────┐           ┌───────────────┐             ┌───────────────┐
            │ Risk Check    │           │ Calculate     │             │ Get API Key   │
            │ (limits)      │           │ Trade Size    │             │ (decrypt)     │
            └───────────────┘           └───────────────┘             └───────────────┘
                    │                              │                              │
                    └──────────────────────────────┼──────────────────────────────┘
                                                   │
                                                   v
                                    ┌──────────────────────────┐
                                    │ PHASE 1: Reserve         │
                                    │ - Lock user              │
                                    │ - Create PENDING trade   │
                                    │ - Deduct balance         │
                                    │ - COMMIT                 │
                                    └──────────────────────────┘
                                                   │
                                                   v
                                    ┌──────────────────────────┐
                                    │ EXCHANGE CALL            │
                                    │ - Set leverage           │
                                    │ - Execute market order   │
                                    └──────────────────────────┘
                                                   │
                           ┌───────────────────────┼───────────────────────┐
                           │ Success               │                       │ Failure
                           v                       │                       v
            ┌──────────────────────────┐           │         ┌──────────────────────────┐
            │ PHASE 2: Confirm         │           │         │ PHASE 2: Rollback        │
            │ - Update trade (FILLED)  │           │         │ - Update trade (FAILED)  │
            │ - Create Position        │           │         │ - Restore balance        │
            │ - Place SL order         │           │         │ - COMMIT                 │
            │ - COMMIT                 │           │         └──────────────────────────┘
            └──────────────────────────┘           │
```

---

## Monitoring and Observability

### Structured Logging

```python
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()

# Usage
logger.info(
    "Trade executed",
    user_id=user.id,
    symbol=signal.cex_symbol,
    size_usdt=trade_size,
    exchange=exchange.value,
)
```

### Sentry Integration

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    integrations=[
        FastApiIntegration(),
        CeleryIntegration(),
    ],
    environment=settings.app_env,
)
```

### Flower (Celery Monitoring)

Access at `http://localhost:5555` (monitoring profile):

```bash
docker-compose --profile monitoring up flower
```

### Health Check Endpoint

```http
GET /health

Response:
{
  "status": "healthy",
  "app_name": "WhaleCopyTrading",
  "environment": "production",
  "version": "1.0.0"
}
```

### Key Metrics to Monitor

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| Trade Execution Time | Time from signal to trade | > 10s |
| Signal Processing Lag | Time signals stay PENDING | > 30s |
| Circuit Breaker Opens | Exchange API failures | Any open |
| DLQ Size | Failed tasks in dead letter | > 10 |
| Position Sync Discrepancy | DB vs Exchange mismatch | Any |
| Daily Active Users | Users with trades | < 50% drop |

---

## Appendix: Quick Reference

### Commands

```bash
# Development
docker-compose up -d                    # Start all services
docker-compose logs -f backend          # View backend logs
docker-compose exec backend bash        # Shell into backend

# Database
docker-compose exec backend alembic upgrade head    # Run migrations
docker-compose exec backend alembic revision -m "description"  # New migration

# Celery
docker-compose logs -f celery_worker    # Worker logs
docker-compose logs -f celery_beat      # Scheduler logs

# Production
docker-compose down && docker-compose up -d --build  # Rebuild and restart
```

### File Locations

| Item | Location |
|------|----------|
| Main API | `backend/app/main.py` |
| Configuration | `backend/app/config.py` |
| Database Models | `backend/app/models/` |
| Exchange Integrations | `backend/app/services/exchanges/` |
| Copy Trade Engine | `backend/app/services/copy_trade_engine.py` |
| Celery Tasks | `backend/app/workers/tasks/` |
| Frontend Entry | `frontend/src/main.jsx` |
| API Client | `frontend/src/services/api.js` |
| Docker Config | `docker-compose.yml` |
| Reverse Proxy | `Caddyfile` |

---

**Document Version:** 1.0.0
**Generated:** January 2026
**Platform:** Whale Copy Trading - Telegram Mini App
