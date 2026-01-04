import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Settings,
  Shield,
  Bell,
  Wallet,
  CreditCard,
  ChevronRight,
  LogOut,
  ExternalLink,
  Check,
  AlertTriangle,
  Zap,
  Crown,
  Star,
  HelpCircle,
  Lock,
  X,
  Plus,
  Loader2
} from 'lucide-react'
import { useUser, useApiKeys } from '../hooks/useApi'

const tradingModes = [
  {
    id: 'spot',
    name: 'SPOT',
    description: 'No leverage, lowest risk',
    icon: '📊',
    risk: 'low',
  },
  {
    id: 'futures',
    name: 'FUTURES',
    description: 'Up to 10x leverage',
    icon: '📈',
    risk: 'high',
  },
  {
    id: 'mixed',
    name: 'MIXED',
    description: '50/50 spot & futures',
    icon: '⚖️',
    risk: 'medium',
  },
]

const subscriptionPlans = [
  {
    id: 'FREE',
    name: 'Free',
    price: 0,
    features: ['1 whale', 'Manual copy only', '2% commission'],
    color: 'from-gray-500 to-gray-600',
  },
  {
    id: 'PRO',
    name: 'Pro',
    price: 99,
    features: ['5 whales', 'Auto-copy', '1% commission', 'FUTURES mode'],
    color: 'from-biolum-cyan to-biolum-blue',
    popular: true,
  },
  {
    id: 'ELITE',
    name: 'Elite',
    price: 299,
    features: ['Unlimited whales', 'Flash copy', '0.5% commission', 'AI scoring', 'VIP support'],
    color: 'from-biolum-purple to-biolum-pink',
  },
]

const exchangeInfo = {
  BINANCE: { name: 'Binance', icon: '🟡' },
  OKX: { name: 'OKX', icon: '⚫' },
  BYBIT: { name: 'Bybit', icon: '🟠' },
}

function SettingsScreen() {
  const { user, settings, loading, error, updateSettings, isDemo } = useUser()
  const { keys: apiKeys, loading: keysLoading, addKey, deleteKey, isDemo: keysDemo } = useApiKeys()

  const [localSettings, setLocalSettings] = useState({
    trading_mode: 'spot',
    auto_copy_enabled: true,
    stop_loss_percent: 10,
    daily_loss_limit_usdt: 100,
    max_open_positions: 5,
    notification_whale_alerts: true,
    notification_trade_executed: true,
  })

  const [showPlanModal, setShowPlanModal] = useState(false)
  const [showAddKeyModal, setShowAddKeyModal] = useState(false)
  const [saving, setSaving] = useState(false)

  // Update local settings when data loads
  useEffect(() => {
    if (settings) {
      setLocalSettings({
        trading_mode: settings.trading_mode?.toLowerCase() || 'spot',
        auto_copy_enabled: settings.auto_copy_enabled ?? true,
        stop_loss_percent: settings.stop_loss_percent || 10,
        daily_loss_limit_usdt: settings.daily_loss_limit_usdt || 100,
        max_open_positions: settings.max_open_positions || 5,
        notification_whale_alerts: settings.notification_whale_alerts ?? true,
        notification_trade_executed: settings.notification_trade_executed ?? true,
      })
    }
  }, [settings])

  const updateSetting = async (key, value) => {
    setLocalSettings(prev => ({ ...prev, [key]: value }))

    // Debounce API call
    setSaving(true)
    try {
      await updateSettings({ [key]: value })
    } catch (err) {
      console.error('Failed to update setting:', err)
    } finally {
      setSaving(false)
    }
  }

  // Build exchanges list from API keys
  const exchanges = ['BINANCE', 'OKX', 'BYBIT'].map(exchange => {
    const key = apiKeys.find(k => k.exchange === exchange && k.is_active)
    return {
      id: exchange,
      ...exchangeInfo[exchange],
      connected: !!key,
      balance: key?.balance || 0,
      keyId: key?.id,
    }
  })

  const currentPlan = user?.subscription_tier || 'FREE'
  const subscriptionExpires = user?.subscription_expires_at
    ? new Date(user.subscription_expires_at)
    : null
  const daysUntilRenewal = subscriptionExpires
    ? Math.ceil((subscriptionExpires - new Date()) / (1000 * 60 * 60 * 24))
    : null

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-biolum-cyan animate-spin" />
      </div>
    )
  }

  return (
    <div className="px-4 pt-6 pb-4">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
      >
        <h1 className="font-display text-2xl font-bold text-white flex items-center gap-2">
          <Settings className="text-biolum-cyan" size={24} />
          Settings
          {saving && <Loader2 size={16} className="animate-spin text-biolum-cyan ml-2" />}
        </h1>
        <p className="text-gray-400 text-sm mt-1">Configure your trading preferences</p>
      </motion.div>

      {/* Error Message */}
      {error && (
        <div className="mb-4 p-3 bg-loss/10 rounded-lg border border-loss/20">
          <p className="text-sm text-loss">{error}</p>
        </div>
      )}

      {/* Subscription Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-5"
      >
        <div className="glass-card p-4 relative overflow-hidden">
          {/* Background Gradient */}
          <div className="absolute inset-0 bg-gradient-to-br from-biolum-cyan/10 to-biolum-purple/10" />

          <div className="relative flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center bg-gradient-to-br ${
                currentPlan === 'ELITE' ? 'from-biolum-purple to-biolum-pink' :
                currentPlan === 'PRO' ? 'from-biolum-cyan to-biolum-blue' :
                'from-gray-500 to-gray-600'
              }`}>
                <Crown size={24} className="text-ocean-900" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-display font-bold text-lg text-white">{currentPlan} Plan</span>
                  <span className="text-xs px-2 py-0.5 bg-profit/20 text-profit rounded-full">Active</span>
                </div>
                <p className="text-sm text-gray-400">
                  {daysUntilRenewal ? `Renews in ${daysUntilRenewal} days` : 'Free forever'}
                </p>
              </div>
            </div>
            {currentPlan !== 'ELITE' && (
              <button
                onClick={() => setShowPlanModal(true)}
                className="btn-secondary px-4 py-2 text-sm"
              >
                Upgrade
              </button>
            )}
          </div>
        </div>
      </motion.div>

      {/* Trading Mode */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="mb-5"
      >
        <h2 className="text-sm text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-2">
          <Zap size={14} />
          Trading Mode
        </h2>
        <div className="space-y-2">
          {tradingModes.map((mode) => (
            <button
              key={mode.id}
              onClick={() => updateSetting('trading_mode', mode.id)}
              className={`w-full glass-card p-4 flex items-center justify-between transition-all ${
                localSettings.trading_mode === mode.id
                  ? 'border-biolum-cyan/50 shadow-glow-sm'
                  : ''
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">{mode.icon}</span>
                <div className="text-left">
                  <p className="font-semibold text-white">{mode.name}</p>
                  <p className="text-xs text-gray-500">{mode.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-[10px] font-bold px-2 py-1 rounded-full uppercase ${
                  mode.risk === 'low' ? 'bg-profit/20 text-profit' :
                  mode.risk === 'medium' ? 'bg-yellow-400/20 text-yellow-400' :
                  'bg-loss/20 text-loss'
                }`}>
                  {mode.risk} risk
                </span>
                {localSettings.trading_mode === mode.id && (
                  <div className="w-6 h-6 bg-biolum-cyan rounded-full flex items-center justify-center">
                    <Check size={14} className="text-ocean-900" />
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
      </motion.div>

      {/* Auto-Copy Settings */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="mb-5"
      >
        <h2 className="text-sm text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-2">
          <Shield size={14} />
          Auto-Copy & Risk
        </h2>
        <div className="glass-card divide-y divide-ocean-600/50">
          {/* Auto-Copy Toggle */}
          <div className="p-4 flex items-center justify-between">
            <div>
              <p className="font-semibold text-white">Auto-Copy</p>
              <p className="text-xs text-gray-500">Automatically copy whale trades</p>
            </div>
            <button
              onClick={() => updateSetting('auto_copy_enabled', !localSettings.auto_copy_enabled)}
              className={`w-14 h-7 rounded-full transition-colors relative ${
                localSettings.auto_copy_enabled ? 'bg-biolum-cyan' : 'bg-ocean-600'
              }`}
            >
              <div
                className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${
                  localSettings.auto_copy_enabled ? 'left-7' : 'left-0.5'
                }`}
              />
            </button>
          </div>

          {/* Max Loss Per Trade */}
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="font-semibold text-white">Max Loss Per Trade</p>
                <p className="text-xs text-gray-500">Stop-loss threshold</p>
              </div>
              <span className="font-mono text-biolum-cyan font-bold">
                {localSettings.stop_loss_percent}%
              </span>
            </div>
            <input
              type="range"
              min="5"
              max="50"
              step="5"
              value={localSettings.stop_loss_percent}
              onChange={(e) => updateSetting('stop_loss_percent', Number(e.target.value))}
              className="w-full accent-biolum-cyan"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>5%</span>
              <span>50%</span>
            </div>
          </div>

          {/* Daily Loss Limit */}
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="font-semibold text-white">Daily Loss Limit</p>
                <p className="text-xs text-gray-500">Pause trading after reaching limit</p>
              </div>
              <span className="font-mono text-biolum-cyan font-bold">
                ${localSettings.daily_loss_limit_usdt}
              </span>
            </div>
            <input
              type="range"
              min="50"
              max="500"
              step="50"
              value={localSettings.daily_loss_limit_usdt}
              onChange={(e) => updateSetting('daily_loss_limit_usdt', Number(e.target.value))}
              className="w-full accent-biolum-cyan"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>$50</span>
              <span>$500</span>
            </div>
          </div>

          {/* Max Positions */}
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="font-semibold text-white">Max Open Positions</p>
                <p className="text-xs text-gray-500">Limit concurrent trades</p>
              </div>
              <span className="font-mono text-biolum-cyan font-bold">
                {localSettings.max_open_positions}
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="20"
              step="1"
              value={localSettings.max_open_positions}
              onChange={(e) => updateSetting('max_open_positions', Number(e.target.value))}
              className="w-full accent-biolum-cyan"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>1</span>
              <span>20</span>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Connected Exchanges */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="mb-5"
      >
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm text-gray-400 uppercase tracking-wide flex items-center gap-2">
            <Wallet size={14} />
            Connected Exchanges
          </h2>
          <button
            onClick={() => setShowAddKeyModal(true)}
            className="text-xs text-biolum-cyan flex items-center gap-1 hover:underline"
          >
            <Plus size={12} />
            Add Key
          </button>
        </div>
        <div className="glass-card divide-y divide-ocean-600/50">
          {exchanges.map((exchange) => (
            <div key={exchange.id} className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{exchange.icon}</span>
                <div>
                  <p className="font-semibold text-white">{exchange.name}</p>
                  {exchange.connected ? (
                    <p className="text-xs text-profit flex items-center gap-1">
                      <Check size={10} />
                      Connected
                    </p>
                  ) : (
                    <p className="text-xs text-gray-500">Not connected</p>
                  )}
                </div>
              </div>
              <button
                onClick={() => {
                  if (exchange.connected && exchange.keyId) {
                    if (confirm('Disconnect this exchange?')) {
                      deleteKey(exchange.keyId)
                    }
                  } else {
                    setShowAddKeyModal(true)
                  }
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  exchange.connected
                    ? 'bg-ocean-600 text-gray-300 hover:bg-ocean-500'
                    : 'bg-biolum-cyan/20 text-biolum-cyan border border-biolum-cyan/30 hover:bg-biolum-cyan/30'
                }`}
              >
                {exchange.connected ? 'Disconnect' : 'Connect'}
              </button>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Notifications */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="mb-5"
      >
        <h2 className="text-sm text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-2">
          <Bell size={14} />
          Notifications
        </h2>
        <div className="glass-card divide-y divide-ocean-600/50">
          <div className="p-4 flex items-center justify-between">
            <div>
              <p className="font-semibold text-white">Whale Alerts</p>
              <p className="text-xs text-gray-500">Get alerts for whale signals</p>
            </div>
            <button
              onClick={() => updateSetting('notification_whale_alerts', !localSettings.notification_whale_alerts)}
              className={`w-14 h-7 rounded-full transition-colors relative ${
                localSettings.notification_whale_alerts ? 'bg-biolum-cyan' : 'bg-ocean-600'
              }`}
            >
              <div
                className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${
                  localSettings.notification_whale_alerts ? 'left-7' : 'left-0.5'
                }`}
              />
            </button>
          </div>

          <div className="p-4 flex items-center justify-between">
            <div>
              <p className="font-semibold text-white">Trade Executed</p>
              <p className="text-xs text-gray-500">Notify when trades complete</p>
            </div>
            <button
              onClick={() => updateSetting('notification_trade_executed', !localSettings.notification_trade_executed)}
              className={`w-14 h-7 rounded-full transition-colors relative ${
                localSettings.notification_trade_executed ? 'bg-biolum-cyan' : 'bg-ocean-600'
              }`}
            >
              <div
                className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${
                  localSettings.notification_trade_executed ? 'left-7' : 'left-0.5'
                }`}
              />
            </button>
          </div>
        </div>
      </motion.div>

      {/* Other Options */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="mb-5"
      >
        <div className="glass-card divide-y divide-ocean-600/50">
          <button className="w-full p-4 flex items-center justify-between hover:bg-ocean-700/30 transition-colors">
            <div className="flex items-center gap-3">
              <Lock size={18} className="text-gray-400" />
              <span className="text-white">Security Settings</span>
            </div>
            <ChevronRight size={18} className="text-gray-500" />
          </button>

          <button className="w-full p-4 flex items-center justify-between hover:bg-ocean-700/30 transition-colors">
            <div className="flex items-center gap-3">
              <HelpCircle size={18} className="text-gray-400" />
              <span className="text-white">Help & Support</span>
            </div>
            <ChevronRight size={18} className="text-gray-500" />
          </button>

          <button className="w-full p-4 flex items-center justify-between hover:bg-ocean-700/30 transition-colors">
            <div className="flex items-center gap-3">
              <ExternalLink size={18} className="text-gray-400" />
              <span className="text-white">Terms of Service</span>
            </div>
            <ChevronRight size={18} className="text-gray-500" />
          </button>
        </div>
      </motion.div>

      {/* Logout */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <button className="w-full glass-card p-4 flex items-center justify-center gap-2 text-loss hover:bg-loss/10 transition-colors">
          <LogOut size={18} />
          <span className="font-semibold">Disconnect Wallet</span>
        </button>
      </motion.div>

      {/* Version */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="text-center text-xs text-gray-600 mt-6"
      >
        Whale Trading v1.0.0
      </motion.p>

      {/* Add API Key Modal */}
      <AnimatePresence>
        {showAddKeyModal && (
          <AddApiKeyModal
            onClose={() => setShowAddKeyModal(false)}
            onAdd={addKey}
          />
        )}
      </AnimatePresence>

      {/* Plan Upgrade Modal */}
      <AnimatePresence>
        {showPlanModal && (
          <PlanModal
            currentPlan={currentPlan}
            onClose={() => setShowPlanModal(false)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function AddApiKeyModal({ onClose, onAdd }) {
  const [exchange, setExchange] = useState('BINANCE')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [passphrase, setPassphrase] = useState('')
  const [isTestnet, setIsTestnet] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await onAdd({
        exchange,
        api_key: apiKey,
        api_secret: apiSecret,
        passphrase: exchange === 'OKX' ? passphrase : undefined,
        is_testnet: isTestnet,
      })
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="relative w-full max-w-md glass-card p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full bg-ocean-700/50 text-gray-400 hover:text-white"
        >
          <X size={20} />
        </button>

        <h2 className="font-display text-xl font-bold text-white mb-4">Add API Key</h2>

        {error && (
          <div className="mb-4 p-3 bg-loss/10 rounded-lg border border-loss/20">
            <p className="text-sm text-loss">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Exchange</label>
            <select
              value={exchange}
              onChange={(e) => setExchange(e.target.value)}
              className="w-full bg-ocean-700 border border-ocean-600 rounded-lg px-4 py-3 text-white focus:border-biolum-cyan focus:outline-none"
            >
              <option value="BINANCE">Binance</option>
              <option value="OKX">OKX</option>
              <option value="BYBIT">Bybit</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">API Key</label>
            <input
              type="text"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your API key"
              className="w-full bg-ocean-700 border border-ocean-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-biolum-cyan focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">API Secret</label>
            <input
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              placeholder="Enter your API secret"
              className="w-full bg-ocean-700 border border-ocean-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-biolum-cyan focus:outline-none"
              required
            />
          </div>

          {exchange === 'OKX' && (
            <div>
              <label className="block text-sm text-gray-400 mb-2">Passphrase</label>
              <input
                type="password"
                value={passphrase}
                onChange={(e) => setPassphrase(e.target.value)}
                placeholder="Enter your passphrase"
                className="w-full bg-ocean-700 border border-ocean-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-biolum-cyan focus:outline-none"
                required
              />
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsTestnet(!isTestnet)}
              className={`w-10 h-5 rounded-full transition-colors relative ${
                isTestnet ? 'bg-yellow-400' : 'bg-ocean-600'
              }`}
            >
              <div
                className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                  isTestnet ? 'left-5' : 'left-0.5'
                }`}
              />
            </button>
            <span className="text-sm text-gray-400">Testnet Mode</span>
          </div>

          <div className="flex items-start gap-2 p-3 bg-yellow-400/10 rounded-lg border border-yellow-400/20">
            <AlertTriangle size={16} className="text-yellow-400 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-yellow-400">
              Make sure your API key has trading permissions but NOT withdrawal permissions for security.
            </p>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-primary py-3 flex items-center justify-center gap-2"
          >
            {loading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <>
                <Plus size={18} />
                Add API Key
              </>
            )}
          </button>
        </form>
      </motion.div>
    </motion.div>
  )
}

function PlanModal({ currentPlan, onClose }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-end justify-center"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <motion.div
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="relative w-full max-h-[85vh] overflow-y-auto rounded-t-3xl"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'linear-gradient(180deg, #151d2e 0%, #0a0e17 100%)',
        }}
      >
        <div className="sticky top-0 pt-3 pb-4 flex justify-center bg-gradient-to-b from-ocean-700 to-transparent">
          <div className="w-10 h-1 rounded-full bg-gray-600" />
        </div>

        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full bg-ocean-700/50 text-gray-400 hover:text-white"
        >
          <X size={20} />
        </button>

        <div className="px-5 pb-8">
          <h2 className="font-display text-2xl font-bold text-white text-center mb-2">
            Upgrade Your Plan
          </h2>
          <p className="text-gray-400 text-center mb-6">
            Unlock more features and maximize your trading potential
          </p>

          <div className="space-y-4">
            {subscriptionPlans.map((plan) => (
              <div
                key={plan.id}
                className={`glass-card p-4 relative overflow-hidden ${
                  plan.popular ? 'border-biolum-cyan/50' : ''
                } ${currentPlan === plan.id ? 'ring-2 ring-profit' : ''}`}
              >
                {plan.popular && (
                  <div className="absolute top-0 right-0 bg-biolum-cyan text-ocean-900 text-xs font-bold px-2 py-1 rounded-bl-lg">
                    POPULAR
                  </div>
                )}

                <div className="flex items-center gap-3 mb-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-br ${plan.color}`}>
                    <Star size={20} className="text-white" />
                  </div>
                  <div>
                    <h3 className="font-display font-bold text-lg text-white">{plan.name}</h3>
                    <p className="text-biolum-cyan font-mono font-bold">
                      {plan.price === 0 ? 'Free' : `$${plan.price}/mo`}
                    </p>
                  </div>
                </div>

                <ul className="space-y-2 mb-4">
                  {plan.features.map((feature, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-gray-300">
                      <Check size={14} className="text-profit" />
                      {feature}
                    </li>
                  ))}
                </ul>

                <button
                  disabled={currentPlan === plan.id}
                  className={`w-full py-3 rounded-xl font-semibold transition-all ${
                    currentPlan === plan.id
                      ? 'bg-profit/20 text-profit cursor-default'
                      : `bg-gradient-to-r ${plan.color} text-white hover:opacity-90`
                  }`}
                >
                  {currentPlan === plan.id ? 'Current Plan' : 'Select Plan'}
                </button>
              </div>
            ))}
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

export default SettingsScreen
