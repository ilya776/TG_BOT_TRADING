/**
 * React hooks for API integration
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { userApi, whalesApi, tradesApi, signalsApi, balanceApi, SignalWebSocket, authApi } from '../services/api';

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

// ==================== ABORT CONTROLLER HELPER ====================

/**
 * Create an AbortController with cleanup function
 * Usage: const { signal, cleanup } = createAbortController(abortControllerRef)
 */
function createAbortController(ref) {
  // Cancel any in-flight request
  if (ref.current) {
    ref.current.abort();
  }

  // Create new controller
  const controller = new AbortController();
  ref.current = controller;

  return {
    signal: controller.signal,
    cleanup: () => {
      if (ref.current === controller) {
        ref.current.abort();
        ref.current = null;
      }
    },
  };
}

/**
 * Check if error is an abort error (should be ignored)
 */
function isAbortError(err) {
  return err.name === 'AbortError' || err.message === 'Aborted';
}

// ==================== GENERIC HOOKS ====================

/**
 * Generic hook for fetching data with AbortController support
 */
export function useFetch(fetchFn, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);
  const isMountedRef = useRef(true);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);

    // Create abort controller for this request
    const { signal, cleanup } = createAbortController(abortControllerRef);

    try {
      const result = await fetchFn({ signal });
      if (isMountedRef.current && !signal.aborted) {
        setData(result);
      }
    } catch (err) {
      if (isAbortError(err)) return; // Ignore abort errors
      if (isMountedRef.current) {
        setError(err.message);
      }
    } finally {
      if (isMountedRef.current && !signal.aborted) {
        setLoading(false);
      }
    }
  }, [fetchFn]);

  useEffect(() => {
    isMountedRef.current = true;
    refetch();

    return () => {
      isMountedRef.current = false;
      // Cancel any in-flight request on unmount
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
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
 * Hook for fetching whales with debounced search and AbortController
 *
 * Features:
 * - Debouncing prevents excessive API calls when user types in search field
 * - AbortController cancels in-flight requests when new request is made
 * - Non-search params (chain, sortBy) trigger immediate fetch
 */
export function useWhales(params = {}) {
  const [whales, setWhales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const debounceTimerRef = useRef(null);
  const abortControllerRef = useRef(null);
  const lastSearchRef = useRef(params.search);
  const isMountedRef = useRef(true);

  const fetchWhales = useCallback(async (fetchParams) => {
    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    try {
      const data = await whalesApi.getWhales(fetchParams, { signal: controller.signal });
      if (isMountedRef.current && !controller.signal.aborted) {
        setWhales(data.items || data);
        setError(null);
      }
    } catch (err) {
      if (isAbortError(err)) return; // Ignore abort errors
      if (isMountedRef.current) {
        setError(err.message);
      }
    } finally {
      if (isMountedRef.current && !controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    // Clear any pending debounce timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Check if search param changed
    const searchChanged = params.search !== lastSearchRef.current;
    lastSearchRef.current = params.search;

    // Debounce only for search changes (500ms delay)
    // Other param changes (chain, sortBy) trigger immediate fetch
    if (searchChanged && params.search) {
      setLoading(true); // Show loading immediately for UX
      debounceTimerRef.current = setTimeout(() => {
        fetchWhales(params);
      }, 500);
    } else {
      // Immediate fetch for non-search params or empty search
      fetchWhales(params);
    }

    // Cleanup on unmount
    return () => {
      isMountedRef.current = false;
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [JSON.stringify(params), fetchWhales]);

  const refetch = useCallback(() => fetchWhales(params), [fetchWhales, params]);

  return { whales, loading, error, refetch };
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
  const isMountedRef = useRef(true);

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
      // Only update state if component is still mounted
      if (isMountedRef.current) {
        setPositions(Array.isArray(data) ? data : []);
        setError(null);
      }
    } catch (err) {
      if (!isMountedRef.current) return;
      if (err.message?.includes('401') || err.message?.includes('authorization')) {
        setPositions([]);
        setError(null);
      } else {
        setError(err.message);
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, []); // Empty deps - stable reference

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

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    fetchPositions();
  }, []); // Run once on mount

  // Auto-refresh positions every 10 seconds (only if authenticated)
  useEffect(() => {
    if (!authApi.isAuthenticated()) return;
    const interval = setInterval(fetchPositions, 10000);
    return () => clearInterval(interval);
  }, []); // Stable - no deps needed

  return { positions, loading, error, refetch: fetchPositions, updatePosition, closePosition };
}

/**
 * Hook for portfolio summary
 */
export function usePortfolio() {
  return useFetch(tradesApi.getPortfolio);
}

// ==================== BALANCE HOOKS ====================

/**
 * Hook for exchange balances
 * Returns balances for all connected exchanges
 */
export function useBalances() {
  const [balances, setBalances] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [syncing, setSyncing] = useState({});

  const fetchBalances = useCallback(async () => {
    // Skip if not authenticated
    if (!authApi.isAuthenticated()) {
      setBalances({
        total_usdt: '0',
        available_usdt: '0',
        exchanges: [],
      });
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const data = await balanceApi.getBalances();
      setBalances(data);
      setError(null);
    } catch (err) {
      if (err.message?.includes('401') || err.message?.includes('authorization')) {
        setBalances({
          total_usdt: '0',
          available_usdt: '0',
          exchanges: [],
        });
        setError(null);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const syncBalance = useCallback(async (exchange) => {
    if (!authApi.isAuthenticated()) {
      throw new Error('Please login via Telegram to sync balances');
    }

    setSyncing(prev => ({ ...prev, [exchange]: true }));
    try {
      const result = await balanceApi.syncBalance(exchange);
      // Refresh all balances after sync
      await fetchBalances();
      return result;
    } finally {
      setSyncing(prev => ({ ...prev, [exchange]: false }));
    }
  }, [fetchBalances]);

  useEffect(() => {
    fetchBalances();
  }, [fetchBalances]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    if (!authApi.isAuthenticated()) return;
    const interval = setInterval(fetchBalances, 60000);
    return () => clearInterval(interval);
  }, [fetchBalances]);

  return {
    balances,
    loading,
    error,
    syncing,
    refetch: fetchBalances,
    fetchBalances, // Alias for backwards compatibility
    syncBalance,
  };
}

// ==================== LIVE SIGNALS HOOK ====================

/**
 * Hook for real-time whale signals via WebSocket with HTTP polling fallback
 *
 * Strategy:
 * 1. Try to connect via WebSocket for real-time updates
 * 2. If WebSocket fails after max retries, fall back to HTTP polling
 * 3. HTTP polling runs every 10 seconds when WebSocket is unavailable
 */
export function useLiveSignals() {
  const [signals, setSignals] = useState([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const [usingFallback, setUsingFallback] = useState(false);
  const wsRef = useRef(null);
  const pollingIntervalRef = useRef(null);
  const isMountedRef = useRef(true);
  const usingFallbackRef = useRef(false); // Ref to avoid stale closure in interval

  // Fetch signals via HTTP (used for initial load and fallback polling)
  const fetchSignals = useCallback(async () => {
    try {
      const data = await signalsApi.getSignals({ limit: 50 });
      if (isMountedRef.current) {
        setSignals(data || []);
        setError(null);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err.message);
      }
    }
  }, []);

  // Start HTTP polling as fallback
  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current) return; // Already polling

    console.log('Starting HTTP polling fallback for signals');
    setUsingFallback(true);
    usingFallbackRef.current = true;

    // Immediate fetch
    fetchSignals();

    // Poll every 10 seconds
    pollingIntervalRef.current = setInterval(fetchSignals, 10000);
  }, [fetchSignals]);

  // Stop HTTP polling
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
      setUsingFallback(false);
      usingFallbackRef.current = false;
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    const handleMessage = (signal) => {
      if (!isMountedRef.current) return;
      setSignals((prev) => [signal, ...prev].slice(0, 50)); // Keep last 50 signals
    };

    const handleError = (err) => {
      if (!isMountedRef.current) return;
      setError(err);
      setConnected(false);
    };

    const handleConnectionFailed = (message) => {
      if (!isMountedRef.current) return;
      console.warn('WebSocket connection failed:', message);
      setConnected(false);
      setError(message);

      // Start HTTP polling as fallback
      startPolling();
    };

    // Called when WebSocket reconnects after fallback started
    const handleReconnected = () => {
      if (!isMountedRef.current) return;
      console.log('WebSocket reconnected, stopping HTTP polling');
      stopPolling();
      setConnected(true);
      setError(null);
    };

    // Create WebSocket with fallback and reconnect handlers
    wsRef.current = new SignalWebSocket(
      handleMessage,
      handleError,
      handleConnectionFailed,
      handleReconnected
    );

    // Try WebSocket first
    wsRef.current.connect();

    // Track connection state (less frequent since we have proper callbacks now)
    const checkConnection = setInterval(() => {
      if (!isMountedRef.current) return;
      const isConnected = wsRef.current?.isConnected() || false;
      setConnected(isConnected);
    }, 5000); // Check every 5s instead of 2s

    // Initial fetch of signals (regardless of WebSocket status)
    fetchSignals();

    return () => {
      isMountedRef.current = false;
      clearInterval(checkConnection);
      stopPolling();
      if (wsRef.current) {
        wsRef.current.disconnect();
        wsRef.current = null;
      }
    };
  }, []); // Empty deps - run once on mount

  // Retry WebSocket connection manually
  const retryConnection = useCallback(() => {
    stopPolling();
    setError(null);
    if (wsRef.current) {
      wsRef.current.reset();
    }
  }, [stopPolling]);

  return { signals, connected, error, usingFallback, retryConnection };
}

// ==================== COMBINED DASHBOARD HOOK ====================

/**
 * Hook for dashboard data (combines multiple API calls)
 * Shows REAL data - whales are public, positions/trades empty if not authenticated
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
  const isMountedRef = useRef(true);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);

    const isAuthenticated = authApi.isAuthenticated();

    try {
      // Whales leaderboard is public - always fetch REAL data
      const whales = await whalesApi.getLeaderboard('7d').catch(() => []);

      if (!isMountedRef.current) return; // Check before state updates

      if (isAuthenticated) {
        // Authenticated: fetch all user-specific data
        const [portfolio, positions, trades] = await Promise.all([
          tradesApi.getPortfolio().catch(() => null),
          tradesApi.getPositions().catch(() => []),
          tradesApi.getTrades({ limit: 5 }).catch(() => []),
        ]);

        if (!isMountedRef.current) return;

        setData({
          portfolio: portfolio || { total_value_usdt: 0, daily_pnl: 0, daily_pnl_percent: 0 },
          positions: positions || [],
          topWhales: Array.isArray(whales) ? whales.slice(0, 3) : [],
          recentTrades: trades?.items || trades || [],
        });
        setIsDemo(false);
      } else {
        // Not authenticated: show REAL whales, empty portfolio/positions (user has none)
        setData({
          portfolio: { total_value_usdt: 0, daily_pnl: 0, daily_pnl_percent: 0, total_positions: 0 },
          positions: [],
          topWhales: Array.isArray(whales) ? whales.slice(0, 3) : [],
          recentTrades: [],
        });
        setIsDemo(true);
      }
      setError(null);
    } catch (err) {
      if (!isMountedRef.current) return;
      console.error('Dashboard fetch error:', err);
      setData({
        portfolio: { total_value_usdt: 0, daily_pnl: 0, daily_pnl_percent: 0, total_positions: 0 },
        positions: [],
        topWhales: [],
        recentTrades: [],
      });
      setIsDemo(true);
      setError(err.message);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, []); // Empty deps - stable reference

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, []); // Run once on mount

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(fetchDashboard, 30000);
    return () => clearInterval(interval);
  }, []); // Stable - no deps needed

  return { ...data, loading, error, isDemo, refetch: fetchDashboard };
}
