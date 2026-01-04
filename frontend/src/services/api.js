/**
 * API Service for Whale Trading Bot
 * Connects frontend to FastAPI backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// Get Telegram WebApp data for authentication
const getTelegramInitData = () => {
  if (window.Telegram?.WebApp?.initData) {
    return window.Telegram.WebApp.initData;
  }
  return null;
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

// Generic API request handler
const apiRequest = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;

  const config = {
    headers: getHeaders(),
    ...options,
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error);
    throw error;
  }
};

// ==================== AUTH API ====================

export const authApi = {
  // Authenticate with Telegram init data
  authenticateTelegram: async (initData) => {
    const response = await fetch(`${API_BASE_URL}/auth/telegram`, {
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

    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
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
      const response = await fetch(`${API_BASE_URL}/auth/me`, {
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

  // Auto-authenticate using Telegram WebApp
  autoAuth: async () => {
    const initData = getTelegramInitData();
    if (!initData) {
      console.log('No Telegram init data available');
      return null;
    }

    try {
      return await authApi.authenticateTelegram(initData);
    } catch (error) {
      console.error('Auto-auth failed:', error);
      return null;
    }
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
  getWhales: (params = {}) => {
    const searchParams = new URLSearchParams();
    if (params.chain) searchParams.append('chain', params.chain);
    if (params.sortBy) searchParams.append('sort_by', params.sortBy);
    if (params.search) searchParams.append('search', params.search);
    if (params.limit) searchParams.append('limit', params.limit);
    if (params.offset) searchParams.append('offset', params.offset);

    const query = searchParams.toString();
    return apiRequest(`/whales${query ? `?${query}` : ''}`);
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
  closePosition: (positionId) =>
    apiRequest(`/trades/positions/${positionId}/close`, {
      method: 'POST',
    }),

  // Get portfolio summary
  getPortfolio: () => apiRequest('/trades/portfolio'),

  // Get list of traded symbols
  getSymbols: () => apiRequest('/trades/symbols'),
};

// ==================== SIGNALS API ====================

export const signalsApi = {
  // Get recent whale signals (live alerts)
  getSignals: (params = {}) => {
    const searchParams = new URLSearchParams();
    if (params.whaleId) searchParams.append('whale_id', params.whaleId);
    if (params.action) searchParams.append('action', params.action);
    if (params.limit) searchParams.append('limit', params.limit);

    const query = searchParams.toString();
    return apiRequest(`/signals${query ? `?${query}` : ''}`);
  },

  // Get single signal details
  getSignal: (signalId) => apiRequest(`/signals/${signalId}`),

  // Copy a signal trade
  copySignal: (signalId) =>
    apiRequest(`/signals/${signalId}/copy`, {
      method: 'POST',
    }),

  // Skip a signal
  skipSignal: (signalId) =>
    apiRequest(`/signals/${signalId}/skip`, {
      method: 'POST',
    }),
};

// ==================== WEBSOCKET CONNECTION ====================

export class SignalWebSocket {
  constructor(onMessage, onError) {
    this.onMessage = onMessage;
    this.onError = onError;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  connect() {
    const wsUrl = import.meta.env.VITE_WS_URL ||
      `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/signals`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
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
        this.attemptReconnect();
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.attemptReconnect();
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
      console.log(`Reconnecting in ${delay}ms...`);
      setTimeout(() => this.connect(), delay);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
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

// Format percentage
export const formatPercent = (value, decimals = 2) => {
  if (value === null || value === undefined) return '0.00%';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
};

// Format large numbers (e.g., $2.4M)
export const formatLargeNumber = (value) => {
  if (value === null || value === undefined) return '$0';
  if (value >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(1)}K`;
  }
  return `$${value.toFixed(2)}`;
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
  signals: signalsApi,
  SignalWebSocket,
  formatCurrency,
  formatPercent,
  formatLargeNumber,
  shortenAddress,
};
