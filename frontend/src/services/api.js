/**
 * API Service for Whale Trading Bot
 * Connects frontend to FastAPI backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// Get Telegram WebApp data for authentication
const getTelegramInitData = () => {
  // Check if Telegram WebApp is available
  if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
    const webApp = window.Telegram.WebApp;
    const initData = webApp.initData;

    // Primary check: initData string exists and has content
    if (initData && initData.length > 0) {
      console.log('Telegram initData available, platform:', webApp.platform);
      return initData;
    }

    // Log Desktop detection for debugging
    if (webApp.initDataUnsafe?.user?.id) {
      console.log('Telegram Desktop detected with user:', webApp.initDataUnsafe.user.id, 'platform:', webApp.platform);
      console.log('Note: initData is empty on Desktop - auth may not work');
    }

    console.log('Telegram WebApp available but no auth data, platform:', webApp.platform);
  }
  console.log('Telegram WebApp not available');
  return null;
};

// Check if running inside Telegram (more robust detection)
const isInTelegram = () => {
  if (typeof window === 'undefined') return false;

  const webApp = window.Telegram?.WebApp;
  if (!webApp) return false;

  // Check for valid initData (preferred - this means auth will work)
  if (webApp.initData && webApp.initData.length > 0) {
    return true;
  }

  // Telegram Desktop detection: initDataUnsafe has user even when initData is empty
  // This helps show proper UI even though auth might fail
  if (webApp.initDataUnsafe?.user?.id) {
    return true;
  }

  // Additional check: platform indicates Telegram context
  const platform = webApp.platform;
  if (platform && platform !== 'unknown') {
    console.log('Detected Telegram platform:', platform);
    return true;
  }

  return false;
};

// Check if auth data is available (can actually authenticate)
const canAuthenticate = () => {
  if (typeof window === 'undefined') return false;
  const webApp = window.Telegram?.WebApp;
  return webApp?.initData && webApp.initData.length > 0;
};

// Get user info from Telegram (for display, even when auth fails)
const getTelegramUser = () => {
  if (typeof window === 'undefined') return null;
  return window.Telegram?.WebApp?.initDataUnsafe?.user || null;
};

// Create headers with authentication
const getHeaders = () => {
  const headers = {
    'Content-Type': 'application/json',
  };

  const token = localStorage.getItem('auth_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
};

// Request timeout configuration (milliseconds)
const DEFAULT_TIMEOUT = 15000; // 15 seconds for most requests
const AUTH_TIMEOUT = 10000;    // 10 seconds for auth requests
const TRADE_TIMEOUT = 30000;   // 30 seconds for trade operations

// Track if we're currently refreshing to prevent multiple simultaneous refreshes
let isRefreshing = false;
let refreshPromise = null;

// Attempt to refresh the auth token
const attemptTokenRefresh = async () => {
  // If already refreshing, wait for that attempt
  if (isRefreshing) {
    return refreshPromise;
  }

  isRefreshing = true;

  refreshPromise = (async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        throw new Error('No refresh token');
      }

      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        throw new Error('Refresh failed');
      }

      const data = await response.json();

      // Update tokens
      if (data.access_token) {
        localStorage.setItem('auth_token', data.access_token);
      }
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token);
      }

      console.log('Token refreshed successfully');
      return true;
    } catch (error) {
      console.error('Token refresh failed:', error);
      // Clear tokens on refresh failure
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      return false;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  return refreshPromise;
};

// Generic API request handler with timeout, AbortController, and auto token refresh
const apiRequest = async (endpoint, options = {}, _isRetry = false) => {
  const url = `${API_BASE_URL}${endpoint}`;

  // Determine timeout based on endpoint type
  let timeout = options.timeout || DEFAULT_TIMEOUT;
  if (endpoint.includes('/auth/')) {
    timeout = AUTH_TIMEOUT;
  } else if (endpoint.includes('/copy') || endpoint.includes('/close')) {
    timeout = TRADE_TIMEOUT;
  }

  // Create AbortController for timeout handling
  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => timeoutController.abort(), timeout);

  // Handle external signal (from caller) + internal timeout signal
  const externalSignal = options.signal;
  let isExternalAbort = false;

  // If caller provided a signal, listen for abort
  if (externalSignal) {
    if (externalSignal.aborted) {
      // Already aborted before we started
      clearTimeout(timeoutId);
      const abortError = new Error('Aborted');
      abortError.name = 'AbortError';
      throw abortError;
    }

    // When external signal aborts, also abort our request
    externalSignal.addEventListener('abort', () => {
      isExternalAbort = true;
      timeoutController.abort();
    });
  }

  const config = {
    headers: getHeaders(),
    signal: timeoutController.signal,
    ...options,
  };

  // Remove custom fields from fetch options
  delete config.timeout;
  delete config.signal;
  config.signal = timeoutController.signal;

  try {
    const response = await fetch(url, config);

    // Handle 401 Unauthorized - attempt token refresh
    if (response.status === 401 && !_isRetry && !endpoint.includes('/auth/')) {
      console.log('Got 401, attempting token refresh...');
      clearTimeout(timeoutId); // Clear timeout before async refresh

      const refreshed = await attemptTokenRefresh();
      if (refreshed) {
        // Retry the original request with new token
        return apiRequest(endpoint, options, true);
      }
      // Refresh failed - throw auth error
      const authError = new Error('Session expired. Please log in again.');
      authError.isAuthError = true;
      throw authError;
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    // Handle abort/timeout specifically
    if (error.name === 'AbortError') {
      if (isExternalAbort) {
        // Caller aborted - pass through as AbortError
        const abortError = new Error('Aborted');
        abortError.name = 'AbortError';
        throw abortError;
      }
      // Timeout - create specific error
      const timeoutError = new Error(`Request timeout after ${timeout / 1000}s`);
      timeoutError.isTimeout = true;
      console.error(`API Timeout [${endpoint}]:`, timeoutError.message);
      throw timeoutError;
    }
    // Pass through auth errors
    if (error.isAuthError) {
      throw error;
    }
    console.error(`API Error [${endpoint}]:`, error);
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
};

// ==================== AUTH API ====================

// Helper for auth requests with timeout
const authFetch = async (url, options) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), AUTH_TIMEOUT);

  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    return response;
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('Authentication request timed out');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
};

export const authApi = {
  // Authenticate with Telegram init data
  authenticateTelegram: async (initData) => {
    const response = await authFetch(`${API_BASE_URL}/auth/telegram`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ init_data: initData }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Authentication failed' }));
      throw new Error(error.detail || 'Authentication failed');
    }

    const data = await response.json();

    // Store tokens
    if (data.access_token) {
      localStorage.setItem('auth_token', data.access_token);
    }
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token);
    }

    return data;
  },

  // Refresh access token
  refreshToken: async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      throw new Error('No refresh token');
    }

    const response = await authFetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      // Clear tokens on refresh failure
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      throw new Error('Token refresh failed');
    }

    const data = await response.json();

    // Update tokens
    if (data.access_token) {
      localStorage.setItem('auth_token', data.access_token);
    }
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token);
    }

    return data;
  },

  // Check current auth status
  checkAuth: async () => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      return { authenticated: false, user: null };
    }

    try {
      const response = await authFetch(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        return { authenticated: false, user: null };
      }

      return await response.json();
    } catch {
      return { authenticated: false, user: null };
    }
  },

  // Desktop fallback authentication using initDataUnsafe
  authenticateTelegramDesktop: async (userData) => {
    const response = await authFetch(`${API_BASE_URL}/auth/telegram/desktop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        telegram_id: userData.id,
        username: userData.username || null,
        first_name: userData.first_name || null,
        last_name: userData.last_name || null,
        language_code: userData.language_code || 'en',
        platform: window.Telegram?.WebApp?.platform || 'unknown',
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Desktop authentication failed' }));
      throw new Error(error.detail || 'Desktop authentication failed');
    }

    const data = await response.json();

    // Store tokens
    if (data.access_token) {
      localStorage.setItem('auth_token', data.access_token);
    }
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token);
    }

    return data;
  },

  // Auto-authenticate using Telegram WebApp
  autoAuth: async () => {
    const initData = getTelegramInitData();

    // Primary path: use initData (cryptographically verified)
    if (initData) {
      try {
        return await authApi.authenticateTelegram(initData);
      } catch (error) {
        console.error('Primary auth failed:', error);
        // Fall through to Desktop fallback
      }
    }

    // Fallback path: Desktop Telegram (initDataUnsafe only)
    const telegramUser = getTelegramUser();
    if (telegramUser?.id) {
      console.log('Attempting Desktop fallback auth for user:', telegramUser.id);
      try {
        return await authApi.authenticateTelegramDesktop(telegramUser);
      } catch (error) {
        console.error('Desktop fallback auth failed:', error);
        return null;
      }
    }

    console.log('No Telegram auth data available');
    return null;
  },

  // Logout
  logout: () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('refresh_token');
  },

  // Check if user is authenticated
  isAuthenticated: () => {
    return !!localStorage.getItem('auth_token');
  },

  // Get Telegram init data
  getTelegramInitData,

  // Check if in Telegram
  isInTelegram,

  // Check if can actually authenticate
  canAuthenticate,

  // Get Telegram user info (for display)
  getTelegramUser,

  // Check if Desktop fallback is available
  canUseDesktopFallback: () => {
    const telegramUser = getTelegramUser();
    return !canAuthenticate() && !!telegramUser?.id;
  },
};

// ==================== USER API ====================

export const userApi = {
  // Get current user profile
  getProfile: () => apiRequest('/users/me'),

  // Get user settings
  getSettings: () => apiRequest('/users/me/settings'),

  // Update user settings
  updateSettings: (settings) =>
    apiRequest('/users/me/settings', {
      method: 'PATCH',
      body: JSON.stringify(settings),
    }),

  // Get user trading statistics
  getStats: () => apiRequest('/users/me/stats'),

  // Get user's API keys (for connected exchanges)
  getApiKeys: () => apiRequest('/users/me/api-keys'),

  // Add a new API key
  addApiKey: (keyData) =>
    apiRequest('/users/me/api-keys', {
      method: 'POST',
      body: JSON.stringify(keyData),
    }),

  // Delete an API key
  deleteApiKey: (keyId) =>
    apiRequest(`/users/me/api-keys/${keyId}`, {
      method: 'DELETE',
    }),
};

// ==================== WHALES API ====================

export const whalesApi = {
  // Get list of whales with filtering and sorting
  // Supports AbortController signal for request cancellation
  getWhales: (params = {}, options = {}) => {
    const searchParams = new URLSearchParams();
    if (params.chain) searchParams.append('chain', params.chain);
    if (params.sortBy) searchParams.append('sort_by', params.sortBy);
    if (params.search) searchParams.append('search', params.search);
    if (params.limit) searchParams.append('limit', params.limit);
    if (params.offset) searchParams.append('offset', params.offset);

    const query = searchParams.toString();
    return apiRequest(`/whales${query ? `?${query}` : ''}`, options);
  },

  // Get whale leaderboard
  getLeaderboard: (period = '7d') =>
    apiRequest(`/whales/leaderboard?period=${period}`),

  // Get single whale details
  getWhale: (whaleId) => apiRequest(`/whales/${whaleId}`),

  // Get whales the current user is following
  getFollowing: () => apiRequest('/whales/me/following'),

  // Follow a whale
  followWhale: (whaleId, settings = {}) =>
    apiRequest(`/whales/${whaleId}/follow`, {
      method: 'POST',
      body: JSON.stringify(settings),
    }),

  // Update follow settings
  updateFollow: (whaleId, settings) =>
    apiRequest(`/whales/${whaleId}/follow`, {
      method: 'PATCH',
      body: JSON.stringify(settings),
    }),

  // Unfollow a whale
  unfollowWhale: (whaleId) =>
    apiRequest(`/whales/${whaleId}/follow`, {
      method: 'DELETE',
    }),
};

// ==================== TRADES API ====================

export const tradesApi = {
  // Get trade history
  getTrades: (params = {}) => {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.append('status', params.status);
    if (params.symbol) searchParams.append('symbol', params.symbol);
    if (params.startDate) searchParams.append('start_date', params.startDate);
    if (params.endDate) searchParams.append('end_date', params.endDate);
    if (params.limit) searchParams.append('limit', params.limit);
    if (params.offset) searchParams.append('offset', params.offset);

    const query = searchParams.toString();
    return apiRequest(`/trades/trades${query ? `?${query}` : ''}`);
  },

  // Get single trade details
  getTrade: (tradeId) => apiRequest(`/trades/trades/${tradeId}`),

  // Get open positions
  getPositions: () => apiRequest('/trades/positions'),

  // Get single position
  getPosition: (positionId) => apiRequest(`/trades/positions/${positionId}`),

  // Update position (stop-loss, take-profit)
  updatePosition: (positionId, updates) =>
    apiRequest(`/trades/positions/${positionId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    }),

  // Close a position
  closePosition: (positionId, reason = 'MANUAL') =>
    apiRequest(`/trades/positions/${positionId}/close`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  // Get portfolio summary
  getPortfolio: () => apiRequest('/trades/portfolio'),

  // Get list of traded symbols
  getSymbols: () => apiRequest('/trades/symbols'),
};

// ==================== BALANCE API ====================

export const balanceApi = {
  // Get all exchange balances
  getBalances: () => apiRequest('/balance/'),

  // Sync balance for specific exchange
  syncBalance: (exchange) =>
    apiRequest(`/balance/${exchange}/sync`, {
      method: 'POST',
    }),
};

// ==================== SIGNALS API ====================

export const signalsApi = {
  // Get recent whale signals (live alerts)
  // Supports AbortController signal for request cancellation
  getSignals: (params = {}, options = {}) => {
    const searchParams = new URLSearchParams();
    if (params.whaleId) searchParams.append('whale_id', params.whaleId);
    if (params.action) searchParams.append('action', params.action);
    if (params.limit) searchParams.append('limit', params.limit);

    const query = searchParams.toString();
    return apiRequest(`/signals${query ? `?${query}` : ''}`, options);
  },

  // Get single signal details
  getSignal: (signalId) => apiRequest(`/signals/${signalId}`),

  // Copy a signal trade with size and exchange
  copySignal: (signalId, { size_usdt, exchange } = {}) =>
    apiRequest(`/signals/${signalId}/copy`, {
      method: 'POST',
      body: JSON.stringify({
        size_usdt: size_usdt || 100,
        exchange: (exchange || 'binance').toUpperCase(),
      }),
    }),

  // Skip a signal
  skipSignal: (signalId) =>
    apiRequest(`/signals/${signalId}/skip`, {
      method: 'POST',
    }),
};

// ==================== WEBSOCKET CONNECTION ====================

/**
 * WebSocket connection with intelligent reconnection strategy:
 * 1. Fast reconnects with exponential backoff (5 attempts, max 30s delay)
 * 2. After fast retries fail, fall back to HTTP polling via onConnectionFailed
 * 3. Continue slow reconnection attempts in background (every 60s)
 * 4. When reconnected, notify via callback so caller can stop HTTP polling
 */
export class SignalWebSocket {
  constructor(onMessage, onError, onConnectionFailed, onReconnected) {
    this.onMessage = onMessage;
    this.onError = onError;
    this.onConnectionFailed = onConnectionFailed; // Called when fast retries exhausted
    this.onReconnected = onReconnected; // Called when reconnected after failure
    this.ws = null;
    this.reconnectAttempts = 0;
    this.fastReconnectLimit = 5; // Fast reconnect attempts before falling back
    this.reconnectTimeout = null;
    this.isIntentionalClose = false;
    this.hasFallbackStarted = false; // Track if we've already triggered fallback
  }

  connect() {
    // Clear any pending reconnect
    this.clearReconnectTimeout();
    this.isIntentionalClose = false;

    const wsUrl = import.meta.env.VITE_WS_URL ||
      `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/signals`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        const wasReconnecting = this.reconnectAttempts > 0;
        const wasFallback = this.hasFallbackStarted;

        // Reset state
        this.reconnectAttempts = 0;

        // Notify if this was a reconnection after failure
        if (wasFallback) {
          console.log('WebSocket reconnected after fallback');
          this.hasFallbackStarted = false;
          this.onReconnected?.();
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.onMessage(data);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.onError?.(error);
      };

      this.ws.onclose = () => {
        console.log('WebSocket closed');
        if (!this.isIntentionalClose) {
          this.attemptReconnect();
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.attemptReconnect();
    }
  }

  attemptReconnect() {
    this.reconnectAttempts++;

    if (this.reconnectAttempts <= this.fastReconnectLimit) {
      // Fast reconnect phase: exponential backoff up to 30s
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
      console.log(`WebSocket: Fast reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.fastReconnectLimit})`);
      this.reconnectTimeout = setTimeout(() => this.connect(), delay);
    } else {
      // Fast retries exhausted - trigger fallback to HTTP polling (once)
      if (!this.hasFallbackStarted) {
        this.hasFallbackStarted = true;
        console.warn('WebSocket: Fast reconnects exhausted, starting HTTP fallback');
        this.onConnectionFailed?.('Connection lost. Using HTTP updates.');
      }

      // Continue slow reconnection attempts in background
      // Try every 60 seconds indefinitely
      const slowDelay = 60000;
      console.log(`WebSocket: Slow reconnect in ${slowDelay / 1000}s (background attempt)`);
      this.reconnectTimeout = setTimeout(() => this.connect(), slowDelay);
    }
  }

  clearReconnectTimeout() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  disconnect() {
    this.isIntentionalClose = true;
    this.clearReconnectTimeout();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  // Reset and reconnect (can be called to force immediate reconnection)
  reset() {
    this.disconnect();
    this.reconnectAttempts = 0;
    this.hasFallbackStarted = false;
    this.isIntentionalClose = false;
    this.connect();
  }

  // Check if currently connected
  isConnected() {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// ==================== UTILITY FUNCTIONS ====================

// Format currency
export const formatCurrency = (value, decimals = 2) => {
  if (value === null || value === undefined) return '$0.00';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
};

// Format percentage - safely handles null, undefined, NaN, and strings
export const formatPercent = (value, decimals = 2) => {
  const num = Number(value);
  if (value === null || value === undefined || isNaN(num)) return '+0.00%';
  const sign = num >= 0 ? '+' : '';
  return `${sign}${num.toFixed(decimals)}%`;
};

// Format large numbers (e.g., $2.4M) - safely handles null, undefined, NaN, strings
export const formatLargeNumber = (value) => {
  const num = Number(value);
  if (value === null || value === undefined || isNaN(num)) return '$0';
  if (num >= 1000000) {
    return `$${(num / 1000000).toFixed(1)}M`;
  }
  if (num >= 1000) {
    return `$${(num / 1000).toFixed(1)}K`;
  }
  return `$${num.toFixed(2)}`;
};

// Shorten wallet address
export const shortenAddress = (address) => {
  if (!address) return '';
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
};

// Default export with all APIs
export default {
  auth: authApi,
  user: userApi,
  whales: whalesApi,
  trades: tradesApi,
  balance: balanceApi,
  signals: signalsApi,
  SignalWebSocket,
  formatCurrency,
  formatPercent,
  formatLargeNumber,
  shortenAddress,
};
