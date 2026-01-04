/**
 * React hooks for API integration
 */

import { useState, useEffect, useCallback } from 'react';
import { userApi, whalesApi, tradesApi, signalsApi, SignalWebSocket } from '../services/api';

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

// ==================== USER HOOKS ====================

/**
 * Hook for user profile and settings
 */
export function useUser() {
  const [user, setUser] = useState(null);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchUser = useCallback(async () => {
    setLoading(true);
    try {
      const [profileData, settingsData] = await Promise.all([
        userApi.getProfile(),
        userApi.getSettings(),
      ]);
      setUser(profileData);
      setSettings(settingsData);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const updateSettings = useCallback(async (newSettings) => {
    try {
      const updated = await userApi.updateSettings(newSettings);
      setSettings(updated);
      return updated;
    } catch (err) {
      throw err;
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  return { user, settings, loading, error, refetch: fetchUser, updateSettings };
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

  const fetchKeys = useCallback(async () => {
    setLoading(true);
    try {
      const data = await userApi.getApiKeys();
      setKeys(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const addKey = useCallback(async (keyData) => {
    const newKey = await userApi.addApiKey(keyData);
    setKeys((prev) => [...prev, newKey]);
    return newKey;
  }, []);

  const deleteKey = useCallback(async (keyId) => {
    await userApi.deleteApiKey(keyId);
    setKeys((prev) => prev.filter((k) => k.id !== keyId));
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  return { keys, loading, error, refetch: fetchKeys, addKey, deleteKey };
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
 */
export function useFollowingWhales() {
  const [whales, setWhales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchFollowing = useCallback(async () => {
    setLoading(true);
    try {
      const data = await whalesApi.getFollowing();
      setWhales(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const followWhale = useCallback(async (whaleId, settings = {}) => {
    const result = await whalesApi.followWhale(whaleId, settings);
    fetchFollowing(); // Refresh list
    return result;
  }, [fetchFollowing]);

  const unfollowWhale = useCallback(async (whaleId) => {
    await whalesApi.unfollowWhale(whaleId);
    setWhales((prev) => prev.filter((w) => w.whale_id !== whaleId));
  }, []);

  const updateFollow = useCallback(async (whaleId, settings) => {
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
 */
export function useTrades(params = {}) {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(true);

  const fetchTrades = useCallback(async (reset = true) => {
    setLoading(true);
    try {
      const data = await tradesApi.getTrades({
        ...params,
        offset: reset ? 0 : trades.length,
      });
      const newTrades = data.items || data;
      setTrades(reset ? newTrades : [...trades, ...newTrades]);
      setHasMore(newTrades.length === (params.limit || 20));
      setError(null);
    } catch (err) {
      setError(err.message);
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
 */
export function usePositions() {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPositions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await tradesApi.getPositions();
      setPositions(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const updatePosition = useCallback(async (positionId, updates) => {
    const updated = await tradesApi.updatePosition(positionId, updates);
    setPositions((prev) =>
      prev.map((p) => (p.id === positionId ? updated : p))
    );
    return updated;
  }, []);

  const closePosition = useCallback(async (positionId) => {
    await tradesApi.closePosition(positionId);
    setPositions((prev) => prev.filter((p) => p.id !== positionId));
  }, []);

  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);

  // Auto-refresh positions every 10 seconds
  useEffect(() => {
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

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const [portfolio, positions, whales, trades] = await Promise.all([
        tradesApi.getPortfolio(),
        tradesApi.getPositions(),
        whalesApi.getLeaderboard('7d'),
        tradesApi.getTrades({ limit: 5 }),
      ]);

      setData({
        portfolio,
        positions,
        topWhales: whales.slice(0, 3),
        recentTrades: trades.items || trades,
      });
      setError(null);
    } catch (err) {
      setError(err.message);
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

  return { ...data, loading, error, refetch: fetchDashboard };
}
