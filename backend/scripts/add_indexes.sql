-- Performance Indexes for Whale Trading Bot
-- Run this script to add missing indexes for improved query performance

-- Whale Signals - frequently queried by whale_id, status, and timestamp
CREATE INDEX IF NOT EXISTS ix_whale_signals_whale_status
    ON whale_signals(whale_id, status);

CREATE INDEX IF NOT EXISTS ix_whale_signals_detected
    ON whale_signals(detected_at DESC);

CREATE INDEX IF NOT EXISTS ix_whale_signals_status_detected
    ON whale_signals(status, detected_at DESC);

-- Trades - frequently queried by signal_id and user_id
CREATE INDEX IF NOT EXISTS ix_trades_signal
    ON trades(signal_id);

CREATE INDEX IF NOT EXISTS ix_trades_user_created
    ON trades(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_trades_whale
    ON trades(whale_id);

-- Positions - frequently queried by user, symbol, status, and whale
CREATE INDEX IF NOT EXISTS ix_positions_user_symbol_status
    ON positions(user_id, symbol, status);

CREATE INDEX IF NOT EXISTS ix_positions_user_whale_status
    ON positions(user_id, whale_id, status);

CREATE INDEX IF NOT EXISTS ix_positions_open
    ON positions(status) WHERE status = 'OPEN';

-- User Whale Follows - frequently queried for auto-copy
CREATE INDEX IF NOT EXISTS ix_user_whale_follows_whale_autocopy
    ON user_whale_follows(whale_id, auto_copy_enabled);

CREATE INDEX IF NOT EXISTS ix_user_whale_follows_user
    ON user_whale_follows(user_id);

-- Whales - for leaderboard and search
CREATE INDEX IF NOT EXISTS ix_whales_active_public
    ON whales(is_active, is_public);

CREATE INDEX IF NOT EXISTS ix_whales_chain
    ON whales(chain) WHERE is_active = true;

-- Whale Stats - for sorting leaderboards
CREATE INDEX IF NOT EXISTS ix_whale_stats_profit_7d
    ON whale_stats(profit_7d DESC);

CREATE INDEX IF NOT EXISTS ix_whale_stats_profit_30d
    ON whale_stats(profit_30d DESC);

-- Users - for Telegram auth lookups
CREATE INDEX IF NOT EXISTS ix_users_telegram_id
    ON users(telegram_id) WHERE telegram_id IS NOT NULL;

-- API Keys - for exchange lookups
CREATE INDEX IF NOT EXISTS ix_user_api_keys_user_exchange
    ON user_api_keys(user_id, exchange, is_active);
