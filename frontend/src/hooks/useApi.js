/**
 * React hooks for API integration
 */

import { useState, useEffect, useCallback } from 'react';
import { userApi, whalesApi, tradesApi, signalsApi, SignalWebSocket, authApi } from '../services/api';

// Demo data for unauthenticated users
const DEMO_PORTFOLIO = {
  total_value_usdt: 10000,
  unrealized_pnl: 245.50,
  unrealized_pnl_percent: 2.45,
  daily_pnl: 125.30,
  daily_pnl_percent: 1.25,
  total_positions: 3,
  winning_positions: 2,
};

const DEMO_POSITIONS = [
  {
    id: 1,
    symbol: 'BTCUSDT',
    side: 'LONG',
    entry_price: 42500,
    current_price: 43200,
    size_usdt: 1000,
    unrealized_pnl: 16.47,
    unrealized_pnl_percent: 1.65,
    whale_name: 'BlueWhale_01',
    opened_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 2,
    symbol: 'ETHUSDT',
    side: 'LONG',
    entry_price: 2250,
    current_price: 2310,
    size_usdt: 500,
    unrealized_pnl: 13.33,
    unrealized_pnl_percent: 2.67,
    whale_name: 'CryptoKing',
    opened_at: new Date(Date.now() - 7200000).toISOString(),
  },
];

const DEMO_WHALES = [
  {
    id: 1,
    name: 'BlueWhale_01',
    win_rate: 78.5,
    pnl_7d: 15420,
    pnl_percent_7d: 12.5,
    total_trades_7d: 24,
    avatar: null,
    tier: 'ELITE',
  },
  {
    id: 2,
    name: 'CryptoKing',
    win_rate: 72.3,
    pnl_7d: 8930,
    pnl_percent_7d: 8.2,
    total_trades_7d: 18,
    avatar: null,
    tier: 'PRO',
  },
  {
    id: 3,
    name: 'DeepDiver',
    win_rate: 68.9,
    pnl_7d: 5670,
    pnl_percent_7d: 6.8,
    total_trades_7d: 32,
    avatar: null,
    tier: 'PRO',
  },
];

const DEMO_TRADES = [
  {
    id: 1,
    symbol: 'BTCUSDT',
    side: 'BUY',
    type: 'MARKET',
    price: 42500,
    size_usdt: 1000,
    status: 'FILLED',
    pnl: 165,
    pnl_percent: 1.65,
    whale_name: 'BlueWhale_01',
    executed_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 2,
    symbol: 'ETHUSDT',
    side: 'BUY',
    type: 'MARKET',
    price: 2250,
    size_usdt: 500,
    status: 'FILLED',
    pnl: 45,
    pnl_percent: 0.9,
    whale_name: 'CryptoKing',
    executed_at: new Date(Date.now() - 7200000).toISOString(),
  },
];

const DEMO_SIGNALS = [
  {
    id: 1,
    whale_name: 'BlueWhale_01',
    symbol: 'BTCUSDT',
    action: 'BUY',
    price: 43500,
    size_usdt: 5000,
    created_at: new Date(Date.now() - 300000).toISOString(),
    confidence: 'HIGH',
  },
  {
    id: 2,
    whale_name: 'CryptoKing',
    symbol: 'SOLUSDT',
    action: 'BUY',
    price: 98.5,
    size_usdt: 2500,
    created_at: new Date(Date.now() - 600000).toISOString(),
    confidence: 'MEDIUM',
  },
];

// ==================== GENERIC HOOKS ====================

/**
 * Generic hook for fetching data
 */
export function useFetch(fetchFn, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFn();
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  useEffect(() => {
    refetch();
  }, deps);

  return { data, loading, error, refetch };
}

// Demo user data
const DEMO_USER = {
  id: 0,
  telegram_id: 0,
  username: 'demo_user',
  first_name: 'Demo',
  last_name: 'User',
  subscription_tier: 'FREE',
};

const DEMO_SETTINGS = {
  trading_mode: 'SPOT',
  preferred_exchange: 'BINANCE',
  auto_copy_enabled: false,
  stop_loss_percent: 10,
  daily_loss_limit_usdt: 100,
  max_open_positions: 5,
  notify_whale_alerts: true,
  notify_trade_executed: true,
};

// ==================== USER HOOKS ====================

/**
 * Hook for user profile and settings
 */
export function useUser() {
  const [user, setUser] = useState(null);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isDemo, setIsDemo] = useState(false);

  const fetchUser = useCallback(async () => {
    setLoading(true);

    // Check if user is authenticated
    if (!authApi.isAuthenticated()) {
      setUser(DEMO_USER);
      setSettings(DEMO_SETTINGS);
      setIsDemo(true);
      setError(null);
      setLoading(false);
      return;
    }

    try {
      const [profileData, settingsData] = await Promise.all([
        userApi.getProfile(),
        userApi.getSettings(),
      ]);
      setUser(profileData);
      setSettings(settingsData);
      setIsDemo(false);
      setError(null);
    } catch (err) {
      // Fallback to demo data on auth error
      if (err.message?.includes('authorization') || err.message?.includes('401')) {
        setUser(DEMO_USER);
        setSettings(DEMO_SETTINGS);
        setIsDemo(true);
        setError(null);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const updateSettings = useCallback(async (newSettings) => {
    if (isDemo) {
      // In demo mode, just update local state
      setSettings(prev => ({ ...prev, ...newSettings }));
      return { ...settings, ...newSettings };
    }
    try {
      const updated = await userApi.updateSettings(newSettings);
      setSettings(updated);
      return updated;
    } catch (err) {
      throw err;
    }
  }, [isDemo, settings]);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  return { user, settings, loading, error, isDemo, refetch: fetchUser, updateSettings };
}

/**
 * Hook for user trading statistics
 */
export function useUserStats() {
  return useFetch(userApi.getStats);
}

/**
 * Hook for user's exchange API keys
 */
export function useApiKeys() {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isDemo, setIsDemo] = useState(false);

  const fetchKeys = useCallback(async () => {
    setLoading(true);

    // Check if user is authenticated
    if (!authApi.isAuthenticated()) {
      setKeys([]);
      setIsDemo(true);
      setError(null);
      setLoading(false);
      return;
    }

    try {
      const data = await userApi.getApiKeys();
      setKeys(data);
      setIsDemo(false);
      setError(null);
    } catch (err) {
      // On auth error, just show empty keys
      if (err.message?.includes('authorization') || err.message?.includes('401')) {
        setKeys([]);
        setIsDemo(true);
        setError(null);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const addKey = useCallback(async (keyData) => {
    if (isDemo) {
      throw new Error('Please open in Telegram to add API keys');
    }
    const newKey = await userApi.addApiKey(keyData);
    setKeys((prev) => [...prev, newKey]);
    return newKey;
  }, [isDemo]);

  const deleteKey = useCallback(async (keyId) => {
    if (isDemo) {
      throw new Error('Please open in Telegram to manage API keys');
    }
    await userApi.deleteApiKey(keyId);
    setKeys((prev) => prev.filter((k) => k.id !== keyId));
  }, [isDemo]);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  return { keys, loading, error, isDemo, refetch: fetchKeys, addKey, deleteKey };
}

// ==================== WHALE HOOKS ====================

/**
 * Hook for whale list with filtering
 */
export function useWhales(params = {}) {
  const [whales, setWhales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchWhales = useCallback(async () => {
    setLoading(true);
    try {
      const data = await whalesApi.getWhales(params);
      setWhales(data.items || data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(params)]);

  useEffect(() => {
    fetchWhales();
  }, [fetchWhales]);

  return { whales, loading, error, refetch: fetchWhales };
}

/**
 * Hook for whale leaderboard
 */
export function useWhaleLeaderboard(period = '7d') {
  return useFetch(() => whalesApi.getLeaderboard(period), [period]);
}

/**
 * Hook for a single whale's details
 */
export function useWhale(whaleId) {
  return useFetch(() => whalesApi.getWhale(whaleId), [whaleId]);
}

/**
 * Hook for whales the user is following
 * Returns empty array if not authenticated
 */
export function useFollowingWhales() {
  const [whales, setWhales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchFollowing = useCallback(async () => {
    // Skip if not authenticated
    if (!authApi.isAuthenticated()) {
      setWhales([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const data = await whalesApi.getFollowing();
      setWhales(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      // On auth error, just return empty
      if (err.message?.includes('401') || err.message?.includes('authorization')) {
        setWhales([]);
        setError(null);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const followWhale = useCallback(async (whaleId, settings = {}) => {
    if (!authApi.isAuthenticated()) {
      throw new Error('Please login via Telegram to follow whales');
    }
    const result = await whalesApi.followWhale(whaleId, settings);
    fetchFollowing();
    return result;
  }, [fetchFollowing]);

  const unfollowWhale = useCallback(async (whaleId) => {
    if (!authApi.isAuthenticated()) {
      throw new Error('Please login via Telegram');
    }
    await whalesApi.unfollowWhale(whaleId);
    setWhales((prev) => prev.filter((w) => w.whale_id !== whaleId));
  }, []);

  const updateFollow = useCallback(async (whaleId, settings) => {
    if (!authApi.isAuthenticated()) {
      throw new Error('Please login via Telegram');
    }
    const updated = await whalesApi.updateFollow(whaleId, settings);
    setWhales((prev) =>
      prev.map((w) => (w.whale_id === whaleId ? { ...w, ...updated } : w))
    );
    return updated;
  }, []);

  useEffect(() => {
    fetchFollowing();
  }, [fetchFollowing]);

  return {
    whales,
    loading,
    error,
    refetch: fetchFollowing,
    followWhale,
    unfollowWhale,
    updateFollow,
  };
}

// ==================== TRADE HOOKS ====================

/**
 * Hook for trade history
 * Returns empty array if not authenticated
 */
export function useTrades(params = {}) {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(false);

  const fetchTrades = useCallback(async (reset = true) => {
    // Skip if not authenticated
    if (!authApi.isAuthenticated()) {
      setTrades([]);
      setLoading(false);
      setHasMore(false);
      return;
    }

    setLoading(true);
    try {
      const data = await tradesApi.getTrades({
        ...params,
        offset: reset ? 0 : trades.length,
      });
      const newTrades = Array.isArray(data) ? data : (data.items || []);
      setTrades(reset ? newTrades : [...trades, ...newTrades]);
      setHasMore(newTrades.length === (params.limit || 20));
      setError(null);
    } catch (err) {
      if (err.message?.includes('401') || err.message?.includes('authorization')) {
        setTrades([]);
        setError(null);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(params), trades.length]);

  const loadMore = useCallback(() => {
    if (!loading && hasMore) {
      fetchTrades(false);
    }
  }, [loading, hasMore, fetchTrades]);

  useEffect(() => {
    fetchTrades(true);
  }, [JSON.stringify(params)]);

  return { trades, loading, error, refetch: () => fetchTrades(true), loadMore, hasMore };
}

/**
 * Hook for open positions
 * Returns empty array if not authenticated
 */
export function usePositions() {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPositions = useCallback(async () => {
    // Skip if not authenticated
    if (!authApi.isAuthenticated()) {
      setPositions([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const data = await tradesApi.getPositions();
      setPositions(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      if (err.message?.includes('401') || err.message?.includes('authorization')) {
        setPositions([]);
        setError(null);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const updatePosition = useCallback(async (positionId, updates) => {
    if (!authApi.isAuthenticated()) {
      throw new Error('Please login via Telegram');
    }
    const updated = await tradesApi.updatePosition(positionId, updates);
    setPositions((prev) =>
      prev.map((p) => (p.id === positionId ? updated : p))
    );
    return updated;
  }, []);

  const closePosition = useCallback(async (positionId) => {
    if (!authApi.isAuthenticated()) {
      throw new Error('Please login via Telegram');
    }
    await tradesApi.closePosition(positionId);
    setPositions((prev) => prev.filter((p) => p.id !== positionId));
  }, []);

  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);

  // Auto-refresh positions every 10 seconds (only if authenticated)
  useEffect(() => {
    if (!authApi.isAuthenticated()) return;
    const interval = setInterval(fetchPositions, 10000);
    return () => clearInterval(interval);
  }, [fetchPositions]);

  return { positions, loading, error, refetch: fetchPositions, updatePosition, closePosition };
}

/**
 * Hook for portfolio summary
 */
export function usePortfolio() {
  return useFetch(tradesApi.getPortfolio);
}

// ==================== LIVE SIGNALS HOOK ====================

/**
 * Hook for real-time whale signals via WebSocket
 */
export function useLiveSignals() {
  const [signals, setSignals] = useState([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const handleMessage = (signal) => {
      setSignals((prev) => [signal, ...prev].slice(0, 50)); // Keep last 50 signals
    };

    const handleError = (err) => {
      setError(err);
      setConnected(false);
    };

    const ws = new SignalWebSocket(handleMessage, handleError);
    ws.connect();

    // Initial fetch of recent signals
    signalsApi.getSignals({ limit: 20 })
      .then((data) => setSignals(data))
      .catch((err) => setError(err.message));

    return () => {
      ws.disconnect();
    };
  }, []);

  return { signals, connected, error };
}

// ==================== COMBINED DASHBOARD HOOK ====================

/**
 * Hook for dashboard data (combines multiple API calls)
 * Returns demo data if user is not authenticated
 */
export function useDashboard() {
  const [data, setData] = useState({
    portfolio: null,
    positions: [],
    topWhales: [],
    recentTrades: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isDemo, setIsDemo] = useState(false);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);

    const isAuthenticated = authApi.isAuthenticated();

    try {
      // Whales leaderboard is public - always fetch real data
      const whales = await whalesApi.getLeaderboard('7d').catch(() => DEMO_WHALES);

      if (isAuthenticated) {
        // Authenticated: fetch all user-specific data
        const [portfolio, positions, trades] = await Promise.all([
          tradesApi.getPortfolio().catch(() => DEMO_PORTFOLIO),
          tradesApi.getPositions().catch(() => []),
          tradesApi.getTrades({ limit: 5 }).catch(() => []),
        ]);

        setData({
          portfolio,
          positions,
          topWhales: whales.slice ? whales.slice(0, 3) : whales,
          recentTrades: trades.items || trades,
        });
        setIsDemo(false);
      } else {
        // Not authenticated: show real whales, demo portfolio/positions
        setData({
          portfolio: DEMO_PORTFOLIO,
          positions: DEMO_POSITIONS,
          topWhales: whales.slice ? whales.slice(0, 3) : DEMO_WHALES,
          recentTrades: DEMO_TRADES,
        });
        setIsDemo(true);
      }
      setError(null);
    } catch (err) {
      // Fallback to demo on any error
      setData({
        portfolio: DEMO_PORTFOLIO,
        positions: DEMO_POSITIONS,
        topWhales: DEMO_WHALES,
        recentTrades: DEMO_TRADES,
      });
      setIsDemo(true);
      setError(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(fetchDashboard, 30000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  return { ...data, loading, error, isDemo, refetch: fetchDashboard };
}
