import React, { useState } from 'react'
import { motion } from 'framer-motion'
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
  ToggleLeft,
  ToggleRight
} from 'lucide-react'

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
    id: 'free',
    name: 'Free',
    price: 0,
    features: ['1 whale', 'Manual copy only', '2% commission'],
    color: 'from-gray-500 to-gray-600',
  },
  {
    id: 'pro',
    name: 'Pro',
    price: 99,
    features: ['5 whales', 'Auto-copy', '1% commission', 'FUTURES mode'],
    color: 'from-biolum-cyan to-biolum-blue',
    popular: true,
  },
  {
    id: 'elite',
    name: 'Elite',
    price: 299,
    features: ['Unlimited whales', 'Flash copy', '0.5% commission', 'AI scoring', 'VIP support'],
    color: 'from-biolum-purple to-biolum-pink',
  },
]

const mockExchanges = [
  {
    id: 'binance',
    name: 'Binance',
    icon: '🟡',
    connected: true,
    balance: 12847.53,
  },
  {
    id: 'okx',
    name: 'OKX',
    icon: '⚫',
    connected: false,
    balance: 0,
  },
  {
    id: 'bybit',
    name: 'Bybit',
    icon: '🟠',
    connected: false,
    balance: 0,
  },
]

function SettingsScreen() {
  const [settings, setSettings] = useState({
    tradingMode: 'spot',
    autoCopy: true,
    maxLossPerTrade: 10,
    dailyLossLimit: 100,
    maxPositions: 5,
    notifications: true,
    soundAlerts: true,
  })

  const [currentPlan, setCurrentPlan] = useState('pro')
  const [showPlanModal, setShowPlanModal] = useState(false)

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }))
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
        </h1>
        <p className="text-gray-400 text-sm mt-1">Configure your trading preferences</p>
      </motion.div>

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
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-biolum-cyan to-biolum-blue flex items-center justify-center">
                <Crown size={24} className="text-ocean-900" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-display font-bold text-lg text-white">Pro Plan</span>
                  <span className="text-xs px-2 py-0.5 bg-profit/20 text-profit rounded-full">Active</span>
                </div>
                <p className="text-sm text-gray-400">Renews in 23 days</p>
              </div>
            </div>
            <button
              onClick={() => setShowPlanModal(true)}
              className="btn-secondary px-4 py-2 text-sm"
            >
              Upgrade
            </button>
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
              onClick={() => updateSetting('tradingMode', mode.id)}
              className={`w-full glass-card p-4 flex items-center justify-between transition-all ${
                settings.tradingMode === mode.id
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
                {settings.tradingMode === mode.id && (
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
              onClick={() => updateSetting('autoCopy', !settings.autoCopy)}
              className={`w-14 h-7 rounded-full transition-colors relative ${
                settings.autoCopy ? 'bg-biolum-cyan' : 'bg-ocean-600'
              }`}
            >
              <div
                className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${
                  settings.autoCopy ? 'left-7' : 'left-0.5'
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
                {settings.maxLossPerTrade}%
              </span>
            </div>
            <input
              type="range"
              min="5"
              max="50"
              step="5"
              value={settings.maxLossPerTrade}
              onChange={(e) => updateSetting('maxLossPerTrade', Number(e.target.value))}
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
                ${settings.dailyLossLimit}
              </span>
            </div>
            <input
              type="range"
              min="50"
              max="500"
              step="50"
              value={settings.dailyLossLimit}
              onChange={(e) => updateSetting('dailyLossLimit', Number(e.target.value))}
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
                {settings.maxPositions}
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="20"
              step="1"
              value={settings.maxPositions}
              onChange={(e) => updateSetting('maxPositions', Number(e.target.value))}
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
        <h2 className="text-sm text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-2">
          <Wallet size={14} />
          Connected Exchanges
        </h2>
        <div className="glass-card divide-y divide-ocean-600/50">
          {mockExchanges.map((exchange) => (
            <div key={exchange.id} className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{exchange.icon}</span>
                <div>
                  <p className="font-semibold text-white">{exchange.name}</p>
                  {exchange.connected ? (
                    <p className="text-xs text-profit flex items-center gap-1">
                      <Check size={10} />
                      Connected • ${exchange.balance.toLocaleString()}
                    </p>
                  ) : (
                    <p className="text-xs text-gray-500">Not connected</p>
                  )}
                </div>
              </div>
              <button
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  exchange.connected
                    ? 'bg-ocean-600 text-gray-300 hover:bg-ocean-500'
                    : 'bg-biolum-cyan/20 text-biolum-cyan border border-biolum-cyan/30 hover:bg-biolum-cyan/30'
                }`}
              >
                {exchange.connected ? 'Manage' : 'Connect'}
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
              <p className="font-semibold text-white">Push Notifications</p>
              <p className="text-xs text-gray-500">Get alerts for whale signals</p>
            </div>
            <button
              onClick={() => updateSetting('notifications', !settings.notifications)}
              className={`w-14 h-7 rounded-full transition-colors relative ${
                settings.notifications ? 'bg-biolum-cyan' : 'bg-ocean-600'
              }`}
            >
              <div
                className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${
                  settings.notifications ? 'left-7' : 'left-0.5'
                }`}
              />
            </button>
          </div>

          <div className="p-4 flex items-center justify-between">
            <div>
              <p className="font-semibold text-white">Sound Alerts</p>
              <p className="text-xs text-gray-500">Play sound for new signals</p>
            </div>
            <button
              onClick={() => updateSetting('soundAlerts', !settings.soundAlerts)}
              className={`w-14 h-7 rounded-full transition-colors relative ${
                settings.soundAlerts ? 'bg-biolum-cyan' : 'bg-ocean-600'
              }`}
            >
              <div
                className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-transform ${
                  settings.soundAlerts ? 'left-7' : 'left-0.5'
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
    </div>
  )
}

export default SettingsScreen
