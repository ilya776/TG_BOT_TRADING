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
  Loader2,
  Copy,
  MessageCircle,
  FileText,
  Key,
  Globe,
  Info,
  Sparkles,
  TrendingUp,
  ShieldCheck,
  Target,
  Flame
} from 'lucide-react'
import { useUser, useApiKeys, useBalances } from '../hooks/useApi'
import { authApi, formatCurrency } from '../services/api'
import { useToast } from '../components/Toast'
import { haptic, springs } from '../utils/animations'
import { PremiumBadge, LockedOptionCard } from '../components/FeatureGate'
import { ConfirmModal } from '../components/TradeModal'

const tradingModes = [
  {
    id: 'spot',
    name: 'SPOT',
    description: 'No leverage, safest for beginners',
    icon: '📊',
    risk: 'low',
    requiresPro: false,
    features: ['No leverage risk', 'Lower fees', 'Great for starters'],
  },
  {
    id: 'futures',
    name: 'FUTURES',
    description: 'Up to 10x leverage for max gains',
    icon: '📈',
    risk: 'high',
    requiresPro: true,
    features: ['10x leverage', 'Short positions', 'Higher profits'],
  },
  {
    id: 'mixed',
    name: 'MIXED',
    description: '50/50 spot & futures balance',
    icon: '⚖️',
    risk: 'medium',
    requiresPro: true,
    features: ['Balanced risk', 'Diversified trades', 'Optimal strategy'],
  },
]

// Risk presets for Auto-Copy
const riskPresets = [
  {
    id: 'conservative',
    name: 'Conservative',
    icon: ShieldCheck,
    color: 'from-profit/20 to-emerald-500/10',
    borderColor: 'border-profit/30',
    textColor: 'text-profit',
    stopLoss: 5,
    dailyLimit: 50,
    maxPositions: 3,
    description: 'Low risk, steady gains',
  },
  {
    id: 'balanced',
    name: 'Balanced',
    icon: Target,
    color: 'from-biolum-cyan/20 to-biolum-blue/10',
    borderColor: 'border-biolum-cyan/30',
    textColor: 'text-biolum-cyan',
    stopLoss: 10,
    dailyLimit: 100,
    maxPositions: 5,
    description: 'Moderate risk/reward',
  },
  {
    id: 'aggressive',
    name: 'Aggressive',
    icon: Flame,
    color: 'from-loss/20 to-orange-500/10',
    borderColor: 'border-loss/30',
    textColor: 'text-loss',
    stopLoss: 25,
    dailyLimit: 250,
    maxPositions: 10,
    description: 'High risk, high reward',
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
  BINANCE: {
    name: 'Binance',
    icon: '🟡',
    instructions: [
      'Go to API Management in your Binance account',
      'Create a new API key with a label (e.g., "WhaleBot")',
      'Enable "Enable Spot & Margin Trading"',
      'Enable "Enable Futures" if you want futures trading',
      'IMPORTANT: Add IP to whitelist: 34.147.107.174',
      'Copy the API Key and Secret Key (shown only once!)',
      'Do NOT enable withdrawals for security'
    ],
    ipNote: 'Binance REQUIRES IP whitelist for API trading. Add: 34.147.107.174',
    docsUrl: 'https://www.binance.com/en/support/faq/how-to-create-api-keys-on-binance-360002502072'
  },
  OKX: {
    name: 'OKX',
    icon: '⚫',
    instructions: [
      'Go to API in your OKX account settings',
      'Click "Create API key"',
      'Set permissions: "Trade" (required), "Read" (required)',
      'Add IP address to whitelist: 34.147.107.174',
      'Create a passphrase (you\'ll need this!)',
      'Copy API Key, Secret Key, and remember your Passphrase',
      'Do NOT enable withdrawals for security'
    ],
    ipNote: 'OKX requires IP whitelist. Add: 34.147.107.174',
    docsUrl: 'https://www.okx.com/help/how-do-i-create-an-api-key',
    requiresPassphrase: true
  },
  BYBIT: {
    name: 'Bybit',
    icon: '🟠',
    instructions: [
      'Go to API Management in your Bybit account',
      'Click "Create New Key"',
      'Select "System-generated API Keys"',
      'Set API permissions: "Read-Write" for trading',
      'Add IP restriction: 34.147.107.174',
      'Copy the API Key and Secret',
      'Do NOT enable asset transfer for security'
    ],
    ipNote: 'Bybit requires IP restriction for security. Add: 34.147.107.174',
    docsUrl: 'https://www.bybit.com/en/help-center/article/How-to-create-your-API-key'
  },
}

const SERVER_IP = '34.147.107.174'

function SettingsScreen() {
  const { user, settings, loading, error, updateSettings, isDemo } = useUser()
  const { keys: apiKeys, loading: keysLoading, addKey, deleteKey, isDemo: keysDemo } = useApiKeys()
  const { balances } = useBalances()

  const [localSettings, setLocalSettings] = useState({
    trading_mode: 'spot',
    auto_copy_enabled: true,
    stop_loss_percent: 10,
    daily_loss_limit_usdt: 100,
    max_open_positions: 5,
    notification_whale_alerts: true,
    notification_trade_executed: true,
    default_exchange: 'BINANCE',
  })

  const [showPlanModal, setShowPlanModal] = useState(false)
  const [showAddKeyModal, setShowAddKeyModal] = useState(null) // null or exchange name
  const [showSecurityModal, setShowSecurityModal] = useState(false)
  const [showHelpModal, setShowHelpModal] = useState(false)
  const [showTermsModal, setShowTermsModal] = useState(false)
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState(null) // exchange object or null
  const [saving, setSaving] = useState(false)
  const [selectedPreset, setSelectedPreset] = useState('balanced')
  const [showCustomRisk, setShowCustomRisk] = useState(false)
  const toast = useToast()

  const currentPlan = user?.subscription_tier || 'FREE'
  const isPro = currentPlan === 'PRO' || currentPlan === 'ELITE'

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
        default_exchange: settings.default_exchange || 'BINANCE',
      })
      // Detect which preset matches current settings
      const matchingPreset = riskPresets.find(p =>
        p.stopLoss === settings.stop_loss_percent &&
        p.dailyLimit === settings.daily_loss_limit_usdt &&
        p.maxPositions === settings.max_open_positions
      )
      if (matchingPreset) {
        setSelectedPreset(matchingPreset.id)
        setShowCustomRisk(false)
      } else {
        setSelectedPreset('custom')
        setShowCustomRisk(true)
      }
    }
  }, [settings])

  // Apply risk preset - batch update to prevent race conditions
  const applyPreset = async (preset) => {
    haptic.medium()
    setSelectedPreset(preset.id)
    setShowCustomRisk(false)

    // Update local state immediately
    setLocalSettings(prev => ({
      ...prev,
      stop_loss_percent: preset.stopLoss,
      daily_loss_limit_usdt: preset.dailyLimit,
      max_open_positions: preset.maxPositions,
    }))

    // Batch update to API (single request instead of 3 separate)
    setSaving(true)
    try {
      await updateSettings({
        stop_loss_percent: preset.stopLoss,
        daily_loss_limit_usdt: preset.dailyLimit,
        max_open_positions: preset.maxPositions,
      })
    } catch (err) {
      console.error('Failed to apply preset:', err)
    } finally {
      setSaving(false)
    }
  }

  // Request Telegram notifications
  const requestNotifications = () => {
    haptic.medium()
    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.requestWriteAccess((granted) => {
        if (granted) {
          toast.success('Notifications enabled!')
        } else {
          toast.error('Notification permission denied')
        }
      })
    } else {
      toast.info('Open in Telegram to enable notifications')
    }
  }

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

  const subscriptionExpires = user?.subscription_expires_at
    ? new Date(user.subscription_expires_at)
    : null
  const daysUntilRenewal = subscriptionExpires
    ? Math.ceil((subscriptionExpires - new Date()) / (1000 * 60 * 60 * 24))
    : null

  // Get connected exchanges with balances for default exchange selector
  const connectedExchanges = exchanges.filter(ex => ex.connected).map(ex => {
    const balanceData = balances?.exchanges?.find(b => b.exchange === ex.id)
    return {
      ...ex,
      balance: balanceData ? (Number(balanceData.spot_total) + Number(balanceData.futures_total)) : 0
    }
  })

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

      {/* Demo Mode Banner */}
      {(isDemo || keysDemo) && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-5 p-4 rounded-xl bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/20"
        >
          <div className="flex items-center gap-3">
            <AlertTriangle className="text-yellow-400" size={24} />
            <div>
              <p className="text-white font-semibold text-sm">Demo Mode</p>
              <p className="text-gray-400 text-xs">
                {authApi.isInTelegram()
                  ? 'Authentication in progress... Please wait or refresh the app'
                  : 'Open this app in Telegram to connect your exchange and start trading'
                }
              </p>
            </div>
          </div>
        </motion.div>
      )}

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

      {/* Trading Mode - Redesigned with Premium Gates */}
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
        <div className="space-y-3">
          {tradingModes.map((mode, index) => {
            const isLocked = mode.requiresPro && !isPro
            const isSelected = localSettings.trading_mode === mode.id

            if (isLocked) {
              return (
                <LockedOptionCard
                  key={mode.id}
                  title={mode.name}
                  description={mode.description}
                  icon={() => <span className="text-xl">{mode.icon}</span>}
                  onUpgrade={() => setShowPlanModal(true)}
                  isSelected={isSelected}
                />
              )
            }

            return (
              <motion.button
                key={mode.id}
                onClick={() => {
                  haptic.selection()
                  updateSetting('trading_mode', mode.id)
                }}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.05 * index }}
                whileTap={{ scale: 0.98 }}
                className={`w-full glass-card p-4 relative overflow-hidden transition-all ${
                  isSelected
                    ? 'border-biolum-cyan/50 shadow-glow-sm bg-biolum-cyan/5'
                    : 'hover:border-ocean-600'
                }`}
              >
                {/* Selected indicator */}
                {isSelected && (
                  <motion.div
                    layoutId="selectedMode"
                    className="absolute left-0 top-0 bottom-0 w-1 bg-biolum-cyan"
                  />
                )}

                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl ${
                      isSelected
                        ? 'bg-biolum-cyan/20'
                        : 'bg-ocean-700/50'
                    }`}>
                      {mode.icon}
                    </div>
                    <div className="text-left">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="font-semibold text-white">{mode.name}</p>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                          mode.risk === 'low' ? 'bg-profit/20 text-profit' :
                          mode.risk === 'medium' ? 'bg-yellow-400/20 text-yellow-400' :
                          'bg-loss/20 text-loss'
                        }`}>
                          {mode.risk}
                        </span>
                        {!mode.requiresPro && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-ocean-600 text-gray-300">
                            FREE
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mb-2">{mode.description}</p>
                      <div className="flex flex-wrap gap-2">
                        {mode.features.map((feature, i) => (
                          <span key={i} className="text-[10px] text-gray-400 flex items-center gap-1">
                            <Check size={10} className="text-profit" />
                            {feature}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {isSelected && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="w-6 h-6 bg-biolum-cyan rounded-full flex items-center justify-center flex-shrink-0"
                    >
                      <Check size={14} className="text-ocean-900" />
                    </motion.div>
                  )}
                </div>
              </motion.button>
            )
          })}
        </div>
      </motion.div>

      {/* Auto-Copy & Risk - Redesigned with Presets */}
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

        {/* Auto-Copy Toggle Card */}
        <div className="glass-card p-4 mb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                localSettings.auto_copy_enabled
                  ? 'bg-biolum-cyan/20'
                  : 'bg-ocean-700/50'
              }`}>
                <Zap size={18} className={localSettings.auto_copy_enabled ? 'text-biolum-cyan' : 'text-gray-500'} />
              </div>
              <div>
                <p className="font-semibold text-white">Auto-Copy Trades</p>
                <p className="text-xs text-gray-500">Automatically copy when whales trade</p>
              </div>
            </div>
            <motion.button
              onClick={() => {
                haptic.medium()
                updateSetting('auto_copy_enabled', !localSettings.auto_copy_enabled)
              }}
              whileTap={{ scale: 0.95 }}
              className={`w-14 h-7 rounded-full transition-all relative ${
                localSettings.auto_copy_enabled
                  ? 'bg-biolum-cyan shadow-[0_0_15px_rgba(0,255,200,0.3)]'
                  : 'bg-ocean-600'
              }`}
            >
              <motion.div
                layout
                className="absolute top-0.5 w-6 h-6 rounded-full bg-white shadow"
                style={{ left: localSettings.auto_copy_enabled ? 'calc(100% - 26px)' : '2px' }}
              />
            </motion.button>
          </div>
        </div>

        {/* Risk Profile Presets */}
        <div className="mb-3">
          <p className="text-xs text-gray-500 mb-2 flex items-center gap-1">
            <Target size={12} />
            Risk Profile
          </p>
          <div className="grid grid-cols-3 gap-2">
            {riskPresets.map((preset) => {
              const Icon = preset.icon
              const isActive = selectedPreset === preset.id
              return (
                <motion.button
                  key={preset.id}
                  onClick={() => applyPreset(preset)}
                  whileTap={{ scale: 0.95 }}
                  className={`relative p-3 rounded-xl border transition-all ${
                    isActive
                      ? `bg-gradient-to-br ${preset.color} ${preset.borderColor} shadow-glow-sm`
                      : 'bg-ocean-800/50 border-ocean-700/50 hover:border-ocean-600'
                  }`}
                >
                  <Icon size={18} className={isActive ? preset.textColor : 'text-gray-500'} />
                  <p className={`text-xs font-semibold mt-1 ${isActive ? 'text-white' : 'text-gray-400'}`}>
                    {preset.name}
                  </p>
                  {isActive && (
                    <motion.div
                      layoutId="presetIndicator"
                      className="absolute -top-1 -right-1 w-4 h-4 bg-white rounded-full flex items-center justify-center"
                    >
                      <Check size={10} className="text-ocean-900" />
                    </motion.div>
                  )}
                </motion.button>
              )
            })}
          </div>
        </div>

        {/* Custom/Expand Button */}
        <button
          onClick={() => {
            haptic.light()
            setShowCustomRisk(!showCustomRisk)
            if (!showCustomRisk) setSelectedPreset('custom')
          }}
          className="w-full flex items-center justify-between p-3 rounded-xl bg-ocean-800/30 border border-ocean-700/50 hover:border-ocean-600 transition-colors mb-3"
        >
          <span className="text-sm text-gray-400 flex items-center gap-2">
            <Settings size={14} />
            {showCustomRisk ? 'Hide Custom Settings' : 'Customize Risk Parameters'}
          </span>
          <ChevronRight
            size={16}
            className={`text-gray-500 transition-transform ${showCustomRisk ? 'rotate-90' : ''}`}
          />
        </button>

        {/* Custom Sliders - Expandable */}
        <AnimatePresence>
          {showCustomRisk && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="glass-card divide-y divide-ocean-600/50">
                {/* Stop Loss Slider */}
                <div className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="font-semibold text-white text-sm">Stop Loss</p>
                      <p className="text-[10px] text-gray-500">Max loss per trade</p>
                    </div>
                    <span className={`font-mono font-bold px-2 py-1 rounded-lg text-sm ${
                      localSettings.stop_loss_percent <= 10
                        ? 'bg-profit/20 text-profit'
                        : localSettings.stop_loss_percent <= 25
                        ? 'bg-yellow-400/20 text-yellow-400'
                        : 'bg-loss/20 text-loss'
                    }`}>
                      {localSettings.stop_loss_percent}%
                    </span>
                  </div>
                  <div className="relative">
                    <div className="absolute inset-0 h-2 top-1/2 -translate-y-1/2 rounded-full bg-gradient-to-r from-profit via-yellow-400 to-loss opacity-30" />
                    <input
                      type="range"
                      min="5"
                      max="50"
                      step="5"
                      value={localSettings.stop_loss_percent}
                      onChange={(e) => {
                        setSelectedPreset('custom')
                        updateSetting('stop_loss_percent', Number(e.target.value))
                      }}
                      className="w-full h-2 bg-transparent appearance-none cursor-pointer relative z-10 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-biolum-cyan"
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-gray-600 mt-1">
                    <span>Safe (5%)</span>
                    <span>Risky (50%)</span>
                  </div>
                </div>

                {/* Daily Limit Slider */}
                <div className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="font-semibold text-white text-sm">Daily Loss Limit</p>
                      <p className="text-[10px] text-gray-500">Pause after reaching limit</p>
                    </div>
                    <span className="font-mono text-biolum-cyan font-bold text-sm">
                      ${localSettings.daily_loss_limit_usdt}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="50"
                    max="500"
                    step="50"
                    value={localSettings.daily_loss_limit_usdt}
                    onChange={(e) => {
                      setSelectedPreset('custom')
                      updateSetting('daily_loss_limit_usdt', Number(e.target.value))
                    }}
                    className="w-full h-2 bg-ocean-600 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-biolum-cyan [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(0,255,200,0.4)]"
                  />
                  <div className="flex justify-between text-[10px] text-gray-600 mt-1">
                    <span>$50</span>
                    <span>$500</span>
                  </div>
                </div>

                {/* Max Positions Slider */}
                <div className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="font-semibold text-white text-sm">Max Positions</p>
                      <p className="text-[10px] text-gray-500">Concurrent trades limit</p>
                    </div>
                    <span className="font-mono text-biolum-cyan font-bold text-sm">
                      {localSettings.max_open_positions}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    step="1"
                    value={localSettings.max_open_positions}
                    onChange={(e) => {
                      setSelectedPreset('custom')
                      updateSetting('max_open_positions', Number(e.target.value))
                    }}
                    className="w-full h-2 bg-ocean-600 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-biolum-cyan [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(0,255,200,0.4)]"
                  />
                  <div className="flex justify-between text-[10px] text-gray-600 mt-1">
                    <span>1</span>
                    <span>20</span>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
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
            onClick={() => setShowAddKeyModal('BINANCE')}
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
                  haptic.light()
                  if (exchange.connected && exchange.keyId) {
                    // Open confirmation modal instead of browser confirm()
                    setShowDisconnectConfirm(exchange)
                  } else {
                    setShowAddKeyModal(exchange.id)
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

      {/* Default Trading Exchange - NEW */}
      {connectedExchanges.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.28 }}
          className="mb-5"
        >
          <h2 className="text-sm text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-2">
            <CreditCard size={14} />
            Default Trading Exchange
          </h2>
          <p className="text-xs text-gray-500 mb-3">
            All copy trades will use this exchange
          </p>
          <div className="space-y-2">
            {connectedExchanges.map((exchange) => {
              const isSelected = localSettings.default_exchange === exchange.id
              return (
                <motion.button
                  key={exchange.id}
                  onClick={() => {
                    haptic.selection()
                    updateSetting('default_exchange', exchange.id)
                  }}
                  whileTap={{ scale: 0.98 }}
                  className={`w-full glass-card p-4 flex items-center justify-between transition-all ${
                    isSelected
                      ? 'border-biolum-cyan/50 shadow-glow-sm bg-biolum-cyan/5'
                      : 'hover:border-ocean-600'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl ${
                      isSelected ? 'bg-biolum-cyan/20' : 'bg-ocean-700/50'
                    }`}>
                      {exchange.icon}
                    </div>
                    <div className="text-left">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-white">{exchange.name}</p>
                        {isSelected && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-biolum-cyan/20 text-biolum-cyan">
                            DEFAULT
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500">
                        Balance: <span className="text-white font-medium">{formatCurrency(exchange.balance)}</span>
                      </p>
                    </div>
                  </div>

                  {isSelected ? (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="w-6 h-6 bg-biolum-cyan rounded-full flex items-center justify-center"
                    >
                      <Check size={14} className="text-ocean-900" />
                    </motion.div>
                  ) : (
                    <div className="w-6 h-6 rounded-full border-2 border-ocean-600" />
                  )}
                </motion.button>
              )
            })}
          </div>
        </motion.div>
      )}

      {/* Notifications - Redesigned */}
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

        {/* Enable Notifications Button - Main CTA */}
        <motion.button
          onClick={requestNotifications}
          whileTap={{ scale: 0.98 }}
          className="w-full glass-card p-4 mb-3 flex items-center justify-between bg-gradient-to-r from-biolum-cyan/10 to-biolum-blue/5 border-biolum-cyan/30 hover:border-biolum-cyan/50 transition-all"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-biolum-cyan/20 flex items-center justify-center">
              <Bell size={18} className="text-biolum-cyan" />
            </div>
            <div className="text-left">
              <p className="font-semibold text-white">Enable Push Notifications</p>
              <p className="text-xs text-gray-500">Get alerts directly in Telegram</p>
            </div>
          </div>
          <ChevronRight size={18} className="text-biolum-cyan" />
        </motion.button>

        <div className="glass-card divide-y divide-ocean-600/50">
          <div className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Sparkles size={16} className="text-gray-500" />
              <div>
                <p className="font-semibold text-white text-sm">Whale Alerts</p>
                <p className="text-[10px] text-gray-500">When followed whales trade</p>
              </div>
            </div>
            <motion.button
              onClick={() => {
                haptic.light()
                updateSetting('notification_whale_alerts', !localSettings.notification_whale_alerts)
              }}
              whileTap={{ scale: 0.95 }}
              className={`w-12 h-6 rounded-full transition-all relative ${
                localSettings.notification_whale_alerts
                  ? 'bg-biolum-cyan shadow-[0_0_10px_rgba(0,255,200,0.3)]'
                  : 'bg-ocean-600'
              }`}
            >
              <motion.div
                layout
                className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow"
                style={{ left: localSettings.notification_whale_alerts ? 'calc(100% - 22px)' : '2px' }}
              />
            </motion.button>
          </div>

          <div className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <TrendingUp size={16} className="text-gray-500" />
              <div>
                <p className="font-semibold text-white text-sm">Trade Executed</p>
                <p className="text-[10px] text-gray-500">When your trades complete</p>
              </div>
            </div>
            <motion.button
              onClick={() => {
                haptic.light()
                updateSetting('notification_trade_executed', !localSettings.notification_trade_executed)
              }}
              whileTap={{ scale: 0.95 }}
              className={`w-12 h-6 rounded-full transition-all relative ${
                localSettings.notification_trade_executed
                  ? 'bg-biolum-cyan shadow-[0_0_10px_rgba(0,255,200,0.3)]'
                  : 'bg-ocean-600'
              }`}
            >
              <motion.div
                layout
                className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow"
                style={{ left: localSettings.notification_trade_executed ? 'calc(100% - 22px)' : '2px' }}
              />
            </motion.button>
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
          <button
            onClick={() => {
              haptic.light()
              setShowSecurityModal(true)
            }}
            className="w-full p-4 flex items-center justify-between hover:bg-ocean-700/30 transition-colors"
          >
            <div className="flex items-center gap-3">
              <Lock size={18} className="text-biolum-cyan" />
              <span className="text-white">Security Settings</span>
            </div>
            <ChevronRight size={18} className="text-gray-500" />
          </button>

          <button
            onClick={() => {
              haptic.light()
              setShowHelpModal(true)
            }}
            className="w-full p-4 flex items-center justify-between hover:bg-ocean-700/30 transition-colors"
          >
            <div className="flex items-center gap-3">
              <HelpCircle size={18} className="text-biolum-cyan" />
              <span className="text-white">Help & Support</span>
            </div>
            <ChevronRight size={18} className="text-gray-500" />
          </button>

          <button
            onClick={() => {
              haptic.light()
              setShowTermsModal(true)
            }}
            className="w-full p-4 flex items-center justify-between hover:bg-ocean-700/30 transition-colors"
          >
            <div className="flex items-center gap-3">
              <FileText size={18} className="text-biolum-cyan" />
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
            onClose={() => setShowAddKeyModal(null)}
            onAdd={addKey}
            toast={toast}
            initialExchange={showAddKeyModal}
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

      {/* Security Settings Modal */}
      <AnimatePresence>
        {showSecurityModal && (
          <SecurityModal onClose={() => setShowSecurityModal(false)} />
        )}
      </AnimatePresence>

      {/* Help & Support Modal */}
      <AnimatePresence>
        {showHelpModal && (
          <HelpModal onClose={() => setShowHelpModal(false)} />
        )}
      </AnimatePresence>

      {/* Terms of Service Modal */}
      <AnimatePresence>
        {showTermsModal && (
          <TermsModal onClose={() => setShowTermsModal(false)} />
        )}
      </AnimatePresence>

      {/* Disconnect Exchange Confirmation Modal */}
      <ConfirmModal
        isOpen={!!showDisconnectConfirm}
        onClose={() => setShowDisconnectConfirm(null)}
        onConfirm={async () => {
          if (showDisconnectConfirm?.keyId) {
            haptic.medium()
            await deleteKey(showDisconnectConfirm.keyId)
            toast.success(`${showDisconnectConfirm.name} disconnected`)
          }
        }}
        title={`Disconnect ${showDisconnectConfirm?.name || 'Exchange'}?`}
        message="Your API keys will be removed. You'll need to add them again to trade on this exchange."
        confirmText="Disconnect"
        type="danger"
      />
    </div>
  )
}

function AddApiKeyModal({ onClose, onAdd, toast, initialExchange = 'BINANCE' }) {
  const [exchange, setExchange] = useState(initialExchange)
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [passphrase, setPassphrase] = useState('')
  const [isTestnet, setIsTestnet] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showInstructions, setShowInstructions] = useState(true)

  const currentExchange = exchangeInfo[exchange]

  const copyIP = () => {
    navigator.clipboard.writeText(SERVER_IP)
    haptic.success()
    toast?.success('IP copied to clipboard!')
  }

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
      haptic.success()
      toast?.success(`${currentExchange.name} connected successfully!`)
      onClose()
    } catch (err) {
      haptic.error()
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
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="relative w-full max-h-[90vh] overflow-y-auto rounded-t-3xl sm:rounded-2xl sm:max-w-lg sm:max-h-[85vh]"
        style={{
          background: 'linear-gradient(180deg, #1a2235 0%, #0d1117 100%)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Handle bar */}
        <div className="sticky top-0 pt-3 pb-2 flex justify-center bg-gradient-to-b from-[#1a2235] to-transparent sm:hidden">
          <div className="w-10 h-1 rounded-full bg-gray-600" />
        </div>

        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full bg-ocean-700/50 text-gray-400 hover:text-white z-10"
        >
          <X size={20} />
        </button>

        <div className="px-5 pb-8 pt-2 sm:pt-6">
          {/* Header */}
          <div className="flex items-center gap-3 mb-5">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-biolum-cyan/20 to-biolum-blue/20 flex items-center justify-center border border-biolum-cyan/30">
              <Key size={24} className="text-biolum-cyan" />
            </div>
            <div>
              <h2 className="font-display text-xl font-bold text-white">Connect Exchange</h2>
              <p className="text-sm text-gray-400">Add your API credentials securely</p>
            </div>
          </div>

          {/* Exchange Selector */}
          <div className="flex gap-2 mb-5">
            {Object.entries(exchangeInfo).map(([key, info]) => (
              <button
                key={key}
                onClick={() => {
                  setExchange(key)
                  haptic.selection()
                }}
                className={`flex-1 p-3 rounded-xl border transition-all ${
                  exchange === key
                    ? 'bg-biolum-cyan/10 border-biolum-cyan/50 shadow-glow-sm'
                    : 'bg-ocean-700/30 border-ocean-600/50 hover:border-ocean-500'
                }`}
              >
                <span className="text-2xl block mb-1">{info.icon}</span>
                <span className={`text-xs font-semibold ${exchange === key ? 'text-biolum-cyan' : 'text-gray-400'}`}>
                  {info.name}
                </span>
              </button>
            ))}
          </div>

          {/* IP Whitelist Warning - CRITICAL */}
          <div className="mb-5 p-4 rounded-xl bg-gradient-to-r from-loss/10 to-orange-500/10 border border-loss/30">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-loss/20 flex items-center justify-center flex-shrink-0">
                <Globe size={20} className="text-loss" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-white text-sm mb-1">⚠️ IP Whitelist Required</p>
                <p className="text-xs text-gray-400 mb-2">{currentExchange.ipNote}</p>
                <button
                  onClick={copyIP}
                  className="flex items-center gap-2 px-3 py-1.5 bg-ocean-700/50 rounded-lg hover:bg-ocean-600/50 transition-colors"
                >
                  <code className="text-biolum-cyan text-sm font-mono">{SERVER_IP}</code>
                  <Copy size={14} className="text-gray-400" />
                </button>
              </div>
            </div>
          </div>

          {/* Setup Instructions - Collapsible */}
          <div className="mb-5">
            <button
              onClick={() => setShowInstructions(!showInstructions)}
              className="w-full flex items-center justify-between p-3 rounded-xl bg-ocean-700/30 border border-ocean-600/50 hover:border-ocean-500 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Info size={16} className="text-biolum-cyan" />
                <span className="text-sm text-white">Setup Instructions for {currentExchange.name}</span>
              </div>
              <ChevronRight
                size={16}
                className={`text-gray-400 transition-transform ${showInstructions ? 'rotate-90' : ''}`}
              />
            </button>

            <AnimatePresence>
              {showInstructions && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="mt-3 p-4 rounded-xl bg-ocean-800/50 border border-ocean-600/30">
                    <ol className="space-y-2">
                      {currentExchange.instructions.map((instruction, i) => (
                        <li key={i} className="flex gap-2 text-xs">
                          <span className="w-5 h-5 rounded-full bg-biolum-cyan/20 text-biolum-cyan flex items-center justify-center flex-shrink-0 text-[10px] font-bold">
                            {i + 1}
                          </span>
                          <span className={`text-gray-300 ${instruction.includes('IMPORTANT') || instruction.includes('IP') ? 'text-yellow-400 font-medium' : ''}`}>
                            {instruction}
                          </span>
                        </li>
                      ))}
                    </ol>
                    <a
                      href={currentExchange.docsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-3 flex items-center gap-1 text-xs text-biolum-cyan hover:underline"
                    >
                      <ExternalLink size={12} />
                      View Official Guide
                    </a>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-loss/10 rounded-lg border border-loss/20">
              <p className="text-sm text-loss">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">API Key</label>
              <input
                type="text"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Paste your API key here"
                className="w-full bg-ocean-700/50 border border-ocean-600 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:border-biolum-cyan focus:outline-none font-mono text-sm"
                required
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-2">API Secret</label>
              <input
                type="password"
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                placeholder="Paste your API secret here"
                className="w-full bg-ocean-700/50 border border-ocean-600 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:border-biolum-cyan focus:outline-none font-mono text-sm"
                required
              />
            </div>

            {exchange === 'OKX' && (
              <div>
                <label className="block text-sm text-gray-400 mb-2">Passphrase (OKX only)</label>
                <input
                  type="password"
                  value={passphrase}
                  onChange={(e) => setPassphrase(e.target.value)}
                  placeholder="Enter your passphrase"
                  className="w-full bg-ocean-700/50 border border-ocean-600 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:border-biolum-cyan focus:outline-none"
                  required
                />
              </div>
            )}

            <div className="flex items-center gap-3 p-3 bg-ocean-700/30 rounded-xl">
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
              <div>
                <span className="text-sm text-white">Testnet Mode</span>
                <p className="text-xs text-gray-500">Use testnet for paper trading</p>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary py-4 flex items-center justify-center gap-2 text-base font-semibold"
            >
              {loading ? (
                <Loader2 size={20} className="animate-spin" />
              ) : (
                <>
                  <Plus size={20} />
                  Connect {currentExchange.name}
                </>
              )}
            </button>
          </form>
        </div>
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

function SecurityModal({ onClose }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="relative w-full max-h-[85vh] overflow-y-auto rounded-t-3xl sm:rounded-2xl sm:max-w-md"
        style={{
          background: 'linear-gradient(180deg, #1a2235 0%, #0d1117 100%)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 pt-3 pb-2 flex justify-center bg-gradient-to-b from-[#1a2235] to-transparent sm:hidden">
          <div className="w-10 h-1 rounded-full bg-gray-600" />
        </div>

        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full bg-ocean-700/50 text-gray-400 hover:text-white"
        >
          <X size={20} />
        </button>

        <div className="px-5 pb-8 pt-2 sm:pt-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-biolum-cyan/20 to-biolum-blue/20 flex items-center justify-center border border-biolum-cyan/30">
              <Shield size={24} className="text-biolum-cyan" />
            </div>
            <div>
              <h2 className="font-display text-xl font-bold text-white">Security</h2>
              <p className="text-sm text-gray-400">Your data is protected</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-ocean-700/30 border border-ocean-600/50">
              <div className="flex items-center gap-3 mb-2">
                <Lock size={18} className="text-profit" />
                <span className="font-semibold text-white">Encrypted Storage</span>
              </div>
              <p className="text-xs text-gray-400">
                Your API keys are encrypted using AES-256 encryption before being stored. We never store plaintext credentials.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-ocean-700/30 border border-ocean-600/50">
              <div className="flex items-center gap-3 mb-2">
                <Globe size={18} className="text-profit" />
                <span className="font-semibold text-white">IP Whitelist Only</span>
              </div>
              <p className="text-xs text-gray-400">
                Your API keys only work with our whitelisted server IP ({SERVER_IP}). Even if compromised, they can't be used elsewhere.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-ocean-700/30 border border-ocean-600/50">
              <div className="flex items-center gap-3 mb-2">
                <Key size={18} className="text-profit" />
                <span className="font-semibold text-white">No Withdrawal Access</span>
              </div>
              <p className="text-xs text-gray-400">
                We recommend creating API keys without withdrawal permissions. Trading permissions only.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-ocean-700/30 border border-ocean-600/50">
              <div className="flex items-center gap-3 mb-2">
                <Shield size={18} className="text-profit" />
                <span className="font-semibold text-white">Telegram Auth</span>
              </div>
              <p className="text-xs text-gray-400">
                Authentication is handled securely through Telegram's WebApp protocol. No passwords stored.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-full mt-6 btn-secondary py-3"
          >
            Got it
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

function HelpModal({ onClose }) {
  const openTelegram = () => {
    haptic.medium()
    window.open('https://t.me/whale_copy_support', '_blank')
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="relative w-full max-h-[85vh] overflow-y-auto rounded-t-3xl sm:rounded-2xl sm:max-w-md"
        style={{
          background: 'linear-gradient(180deg, #1a2235 0%, #0d1117 100%)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 pt-3 pb-2 flex justify-center bg-gradient-to-b from-[#1a2235] to-transparent sm:hidden">
          <div className="w-10 h-1 rounded-full bg-gray-600" />
        </div>

        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full bg-ocean-700/50 text-gray-400 hover:text-white"
        >
          <X size={20} />
        </button>

        <div className="px-5 pb-8 pt-2 sm:pt-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-biolum-purple/20 to-biolum-pink/20 flex items-center justify-center border border-biolum-purple/30">
              <HelpCircle size={24} className="text-biolum-purple" />
            </div>
            <div>
              <h2 className="font-display text-xl font-bold text-white">Help & Support</h2>
              <p className="text-sm text-gray-400">We're here to help</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-ocean-700/30 border border-ocean-600/50">
              <h3 className="font-semibold text-white mb-2">📚 Getting Started</h3>
              <p className="text-xs text-gray-400 mb-3">
                1. Add your exchange API key with IP whitelist<br />
                2. Follow whale traders on the Discovery page<br />
                3. Enable auto-copy or manually copy signals<br />
                4. Monitor your trades in Trade History
              </p>
            </div>

            <div className="p-4 rounded-xl bg-ocean-700/30 border border-ocean-600/50">
              <h3 className="font-semibold text-white mb-2">❓ FAQ</h3>
              <div className="space-y-2 text-xs">
                <details className="text-gray-400">
                  <summary className="cursor-pointer hover:text-white">Why is my trade not executing?</summary>
                  <p className="mt-1 pl-2 border-l border-ocean-600">
                    Check: 1) API key has trading permissions, 2) IP is whitelisted, 3) Sufficient balance
                  </p>
                </details>
                <details className="text-gray-400">
                  <summary className="cursor-pointer hover:text-white">What are the fees?</summary>
                  <p className="mt-1 pl-2 border-l border-ocean-600">
                    No extra fees from us. You only pay standard exchange trading fees.
                  </p>
                </details>
                <details className="text-gray-400">
                  <summary className="cursor-pointer hover:text-white">How do I cancel a subscription?</summary>
                  <p className="mt-1 pl-2 border-l border-ocean-600">
                    Contact support via Telegram. We'll process your request immediately.
                  </p>
                </details>
              </div>
            </div>

            <button
              onClick={openTelegram}
              className="w-full p-4 rounded-xl bg-gradient-to-r from-[#0088cc]/20 to-[#0088cc]/10 border border-[#0088cc]/30 flex items-center justify-center gap-3 hover:bg-[#0088cc]/20 transition-colors"
            >
              <MessageCircle size={20} className="text-[#0088cc]" />
              <span className="text-white font-semibold">Contact Support on Telegram</span>
            </button>
          </div>

          <button
            onClick={onClose}
            className="w-full mt-4 btn-secondary py-3"
          >
            Close
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

function TermsModal({ onClose }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="relative w-full max-h-[85vh] overflow-y-auto rounded-t-3xl sm:rounded-2xl sm:max-w-md"
        style={{
          background: 'linear-gradient(180deg, #1a2235 0%, #0d1117 100%)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 pt-3 pb-2 flex justify-center bg-gradient-to-b from-[#1a2235] to-transparent sm:hidden">
          <div className="w-10 h-1 rounded-full bg-gray-600" />
        </div>

        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full bg-ocean-700/50 text-gray-400 hover:text-white"
        >
          <X size={20} />
        </button>

        <div className="px-5 pb-8 pt-2 sm:pt-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-gray-500/20 to-gray-600/20 flex items-center justify-center border border-gray-500/30">
              <FileText size={24} className="text-gray-400" />
            </div>
            <div>
              <h2 className="font-display text-xl font-bold text-white">Terms of Service</h2>
              <p className="text-sm text-gray-400">Last updated: Jan 2025</p>
            </div>
          </div>

          <div className="space-y-4 text-xs text-gray-400">
            <div className="p-4 rounded-xl bg-ocean-700/30 border border-ocean-600/50">
              <h3 className="font-semibold text-white mb-2">1. Risk Disclaimer</h3>
              <p>
                Trading cryptocurrencies involves substantial risk of loss. Past performance of whale traders does not guarantee future results. You are solely responsible for your trading decisions and any losses incurred.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-ocean-700/30 border border-ocean-600/50">
              <h3 className="font-semibold text-white mb-2">2. Not Financial Advice</h3>
              <p>
                This service provides tools to copy trades from public leaderboards. Nothing here constitutes financial, investment, or trading advice. Always do your own research.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-ocean-700/30 border border-ocean-600/50">
              <h3 className="font-semibold text-white mb-2">3. API Key Security</h3>
              <p>
                You are responsible for creating API keys with appropriate permissions. We recommend: trading only, no withdrawals, IP whitelist enabled. We encrypt and secure your keys but cannot be held liable for exchange security issues.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-ocean-700/30 border border-ocean-600/50">
              <h3 className="font-semibold text-white mb-2">4. Service Availability</h3>
              <p>
                We strive for 99.9% uptime but cannot guarantee uninterrupted service. Delayed or missed trades due to technical issues are not grounds for refund.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-ocean-700/30 border border-ocean-600/50">
              <h3 className="font-semibold text-white mb-2">5. Subscriptions</h3>
              <p>
                Paid subscriptions are non-refundable after 24 hours of purchase. Cancel anytime, access continues until period ends.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-full mt-6 btn-secondary py-3"
          >
            I Understand
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

export default SettingsScreen
