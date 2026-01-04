import React, { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bell,
  BellOff,
  Zap,
  Clock,
  TrendingUp,
  ExternalLink,
  Copy,
  Check,
  X,
  Pause,
  Play,
  AlertTriangle,
  Sparkles,
  Loader2
} from 'lucide-react'
import { signalsApi } from '../services/api'
import { shortenAddress, formatCurrency } from '../services/api'

function LiveAlerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isPaused, setIsPaused] = useState(false)
  const [filter, setFilter] = useState('all') // all, pending, copied, skipped

  // Fetch signals from API
  const fetchSignals = useCallback(async () => {
    try {
      const data = await signalsApi.getSignals({ limit: 50 })
      // Transform API response to alert format
      const transformedAlerts = (data || []).map(signal => ({
        id: signal.id,
        whale: {
          id: signal.whale?.id || 0,
          name: signal.whale?.name || 'Unknown Whale',
          avatar: signal.whale?.avatar || '🐋',
          address: signal.whale?.wallet_address || '',
          winRate: parseFloat(signal.whale?.win_rate || 0),
        },
        action: signal.action,
        token: signal.token,
        tokenName: signal.token_name || signal.token,
        amount: parseFloat(signal.amount_usd || 0),
        dex: signal.dex,
        chain: signal.chain,
        entryPrice: parseFloat(signal.entry_price || 0),
        confidence: signal.confidence,
        timestamp: new Date(signal.detected_at).getTime(),
        txHash: signal.tx_hash,
        autoCopyIn: signal.auto_copy_in || 0,
        status: signal.status === 'PENDING' ? 'pending' :
                signal.status === 'PROCESSED' ? 'copied' : 'skipped',
        cexSymbol: signal.cex_symbol,
        cexAvailable: signal.cex_available,
      }))
      setAlerts(transformedAlerts)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSignals()
    // Refresh every 10 seconds
    const interval = setInterval(fetchSignals, 10000)
    return () => clearInterval(interval)
  }, [fetchSignals])

  const handleCopy = async (alertId) => {
    try {
      await signalsApi.copySignal(alertId)
      setAlerts(alerts.map(a =>
        a.id === alertId ? { ...a, status: 'copied', autoCopyIn: 0 } : a
      ))
    } catch (err) {
      console.error('Failed to copy signal:', err)
    }
  }

  const handleSkip = async (alertId) => {
    try {
      await signalsApi.skipSignal(alertId)
      setAlerts(alerts.map(a =>
        a.id === alertId ? { ...a, status: 'skipped', autoCopyIn: 0 } : a
      ))
    } catch (err) {
      console.error('Failed to skip signal:', err)
    }
  }

  const filteredAlerts = alerts.filter(alert => {
    if (filter === 'all') return true
    return alert.status === filter
  })

  const pendingCount = alerts.filter(a => a.status === 'pending').length

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
        className="mb-5"
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-2xl font-bold text-white flex items-center gap-2">
              <Bell className="text-biolum-cyan" size={24} />
              Live Alerts
              {pendingCount > 0 && (
                <span className="ml-2 px-2 py-0.5 bg-loss rounded-full text-xs font-bold text-white animate-pulse">
                  {pendingCount}
                </span>
              )}
            </h1>
            <p className="text-gray-400 text-sm mt-1">Real-time whale activity</p>
          </div>

          {/* Pause/Play Toggle */}
          <button
            onClick={() => setIsPaused(!isPaused)}
            className={`p-3 rounded-xl transition-all ${
              isPaused
                ? 'bg-loss/20 text-loss border border-loss/30'
                : 'bg-profit/20 text-profit border border-profit/30'
            }`}
          >
            {isPaused ? <Pause size={20} /> : <Play size={20} />}
          </button>
        </div>

        {isPaused && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-3 flex items-center gap-2 px-3 py-2 bg-loss/10 rounded-lg border border-loss/20"
          >
            <AlertTriangle size={16} className="text-loss" />
            <span className="text-sm text-loss">Auto-copy paused. New signals won't be copied automatically.</span>
          </motion.div>
        )}
      </motion.div>

      {/* Filter Tabs */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="flex gap-2 mb-5"
      >
        {[
          { id: 'all', label: 'All' },
          { id: 'pending', label: 'Pending' },
          { id: 'copied', label: 'Copied' },
          { id: 'skipped', label: 'Skipped' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilter(tab.id)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              filter === tab.id
                ? 'bg-gradient-to-r from-biolum-cyan/20 to-biolum-blue/20 border border-biolum-cyan/30 text-white'
                : 'bg-ocean-700/50 text-gray-400 hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </motion.div>

      {/* Error Message */}
      {error && (
        <div className="mb-4 p-3 bg-loss/10 rounded-lg border border-loss/20">
          <p className="text-sm text-loss">{error}</p>
        </div>
      )}

      {/* Alerts List */}
      <div className="space-y-4">
        <AnimatePresence>
          {filteredAlerts.map((alert, index) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              index={index}
              isPaused={isPaused}
              onCopy={() => handleCopy(alert.id)}
              onSkip={() => handleSkip(alert.id)}
            />
          ))}
        </AnimatePresence>

        {filteredAlerts.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-12"
          >
            <div className="text-4xl mb-3">🔔</div>
            <p className="text-gray-400">No alerts found</p>
            <p className="text-gray-500 text-sm">
              {alerts.length === 0
                ? 'Follow whales to receive trading signals'
                : 'No signals match your filter'}
            </p>
          </motion.div>
        )}
      </div>
    </div>
  )
}

function AlertCard({ alert, index, isPaused, onCopy, onSkip }) {
  const [countdown, setCountdown] = useState(alert.autoCopyIn)
  const [timeAgo, setTimeAgo] = useState('')

  // Update time ago
  useEffect(() => {
    const updateTime = () => {
      const seconds = Math.floor((Date.now() - alert.timestamp) / 1000)
      if (seconds < 60) {
        setTimeAgo(`${seconds}s ago`)
      } else if (seconds < 3600) {
        setTimeAgo(`${Math.floor(seconds / 60)}m ago`)
      } else {
        setTimeAgo(`${Math.floor(seconds / 3600)}h ago`)
      }
    }

    updateTime()
    const interval = setInterval(updateTime, 1000)
    return () => clearInterval(interval)
  }, [alert.timestamp])

  // Countdown timer for auto-copy
  useEffect(() => {
    if (alert.status !== 'pending' || isPaused || countdown <= 0) return

    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          onCopy()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [alert.status, isPaused, countdown, onCopy])

  const confidenceColor = {
    HIGH: 'text-profit bg-profit/10 border-profit/30',
    VERY_HIGH: 'text-profit bg-profit/10 border-profit/30',
    MEDIUM: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
    LOW: 'text-loss bg-loss/10 border-loss/30',
  }

  const statusBadge = {
    pending: null,
    copied: { text: 'Copied', color: 'bg-profit/20 text-profit' },
    skipped: { text: 'Skipped', color: 'bg-gray-500/20 text-gray-400' },
  }

  const getExplorerUrl = (chain, txHash) => {
    const explorers = {
      'ETH': 'https://etherscan.io/tx/',
      'ETHEREUM': 'https://etherscan.io/tx/',
      'BSC': 'https://bscscan.com/tx/',
      'ARB': 'https://arbiscan.io/tx/',
      'ARBITRUM': 'https://arbiscan.io/tx/',
      'POLYGON': 'https://polygonscan.com/tx/',
      'OPTIMISM': 'https://optimistic.etherscan.io/tx/',
    }
    return (explorers[chain?.toUpperCase()] || 'https://etherscan.io/tx/') + txHash
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.95 }}
      transition={{ delay: 0.05 * index }}
      className={`glass-card overflow-hidden ${
        alert.status === 'pending' ? 'border-biolum-cyan/30' : ''
      }`}
    >
      {/* Countdown Bar */}
      {alert.status === 'pending' && countdown > 0 && !isPaused && (
        <div className="h-1 bg-ocean-700">
          <motion.div
            className="h-full bg-gradient-to-r from-biolum-cyan to-biolum-blue"
            initial={{ width: '100%' }}
            animate={{ width: '0%' }}
            transition={{ duration: countdown, ease: 'linear' }}
          />
        </div>
      )}

      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            {/* Whale Avatar */}
            <div className="relative">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-biolum-cyan/20 to-biolum-purple/20 flex items-center justify-center text-2xl">
                {alert.whale.avatar}
              </div>
              {alert.status === 'pending' && (
                <div className="absolute -top-1 -right-1 w-4 h-4 bg-biolum-cyan rounded-full flex items-center justify-center">
                  <Zap size={10} className="text-ocean-900" />
                </div>
              )}
            </div>

            {/* Whale Info */}
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">{alert.whale.name}</span>
                <span className="text-xs text-gray-500">
                  {alert.whale.winRate > 0 ? `${alert.whale.winRate.toFixed(0)}% win` : ''}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs text-gray-500 flex items-center gap-1">
                  <Clock size={10} />
                  {timeAgo}
                </span>
              </div>
            </div>
          </div>

          {/* Status Badge */}
          {statusBadge[alert.status] && (
            <span className={`text-xs font-semibold px-2 py-1 rounded-lg ${statusBadge[alert.status].color}`}>
              {statusBadge[alert.status].text}
            </span>
          )}
        </div>

        {/* Alert Content */}
        <div className="glass-card bg-ocean-800/50 p-3 rounded-xl mb-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold px-2 py-1 rounded ${
                alert.action === 'BUY' ? 'bg-profit/20 text-profit' : 'bg-loss/20 text-loss'
              }`}>
                {alert.action}
              </span>
              <span className="font-display font-bold text-xl text-white">{alert.token}</span>
              <span className="text-gray-500 text-sm">({alert.tokenName})</span>
            </div>
            <span className={`text-[10px] font-bold px-2 py-1 rounded border ${confidenceColor[alert.confidence] || confidenceColor.MEDIUM}`}>
              {alert.confidence}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-gray-500 text-xs">Amount</p>
              <p className="font-mono font-semibold text-white">
                {formatCurrency(alert.amount)}
              </p>
            </div>
            <div>
              <p className="text-gray-500 text-xs">DEX</p>
              <p className="font-semibold text-white flex items-center gap-1">
                {alert.dex}
                <span className="text-xs px-1 py-0.5 bg-ocean-600 rounded text-gray-400">
                  {alert.chain}
                </span>
              </p>
            </div>
            <div>
              <p className="text-gray-500 text-xs">Entry Price</p>
              <p className="font-mono font-semibold text-white">
                ${alert.entryPrice < 0.01 ? alert.entryPrice.toFixed(8) : alert.entryPrice.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-gray-500 text-xs">TX Hash</p>
              <a
                href={getExplorerUrl(alert.chain, alert.txHash)}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-xs text-biolum-cyan flex items-center gap-1 hover:underline"
              >
                {shortenAddress(alert.txHash)}
                <ExternalLink size={10} />
              </a>
            </div>
          </div>
        </div>

        {/* Your Copy Info */}
        {alert.status === 'pending' && alert.cexAvailable && (
          <div className="mb-4">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-gray-400 flex items-center gap-1">
                <Sparkles size={14} className="text-biolum-cyan" />
                Your Copy Trade
              </span>
              {countdown > 0 && !isPaused && (
                <span className="text-biolum-cyan font-mono font-bold">
                  Auto-copy in {countdown}s
                </span>
              )}
            </div>
            <div className="flex items-center justify-between bg-ocean-800/50 px-3 py-2 rounded-lg">
              <span className="text-gray-400">Symbol</span>
              <span className="font-mono font-semibold text-white">{alert.cexSymbol || 'N/A'}</span>
            </div>
          </div>
        )}

        {/* Not available on CEX warning */}
        {alert.status === 'pending' && !alert.cexAvailable && (
          <div className="mb-4 flex items-center gap-2 px-3 py-2 bg-yellow-400/10 rounded-lg border border-yellow-400/20">
            <AlertTriangle size={16} className="text-yellow-400" />
            <span className="text-sm text-yellow-400">Token not available on CEX</span>
          </div>
        )}

        {/* Action Buttons */}
        {alert.status === 'pending' && alert.cexAvailable && (
          <div className="flex gap-3">
            <button
              onClick={onCopy}
              className="flex-1 btn-primary flex items-center justify-center gap-2 py-3"
            >
              <Check size={18} />
              Copy Now
            </button>
            <button
              onClick={onSkip}
              className="flex-1 btn-secondary flex items-center justify-center gap-2 py-3"
            >
              <X size={18} />
              Skip
            </button>
          </div>
        )}

        {/* Skip only for tokens not on CEX */}
        {alert.status === 'pending' && !alert.cexAvailable && (
          <button
            onClick={onSkip}
            className="w-full btn-secondary flex items-center justify-center gap-2 py-3"
          >
            <X size={18} />
            Dismiss
          </button>
        )}

        {/* Copied/Skipped State */}
        {alert.status === 'copied' && (
          <div className="flex items-center justify-center gap-2 py-3 bg-profit/10 rounded-xl border border-profit/20">
            <Check size={18} className="text-profit" />
            <span className="text-profit font-semibold">Trade Copied Successfully</span>
          </div>
        )}

        {alert.status === 'skipped' && (
          <div className="flex items-center justify-center gap-2 py-3 bg-gray-500/10 rounded-xl border border-gray-500/20">
            <X size={18} className="text-gray-400" />
            <span className="text-gray-400 font-semibold">Signal Skipped</span>
          </div>
        )}
      </div>
    </motion.div>
  )
}

export default LiveAlerts
