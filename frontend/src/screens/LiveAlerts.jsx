/**
 * LiveAlerts - Real-time whale trading signals with copy functionality
 * Enhanced with trade size input, exchange selection, and smooth animations
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bell,
  BellOff,
  Zap,
  Clock,
  TrendingUp,
  TrendingDown,
  ExternalLink,
  Copy,
  Check,
  X,
  Pause,
  Play,
  AlertTriangle,
  Sparkles,
  Loader2,
  RefreshCw,
  DollarSign,
  ChevronDown,
  Target,
  Shield
} from 'lucide-react'
import { signalsApi, authApi } from '../services/api'
import { shortenAddress, formatCurrency } from '../services/api'
import { useFollowingWhales } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import {
  springs,
  listContainerVariants,
  listItemVariants,
  haptic
} from '../utils/animations'

// Safe number formatting helper
const safeFixed = (value, decimals = 2) => {
  const num = Number(value)
  return isNaN(num) ? '0' : num.toFixed(decimals)
}

// Exchange options
const EXCHANGES = [
  { id: 'binance', name: 'Binance', icon: '🟡' },
  { id: 'bybit', name: 'Bybit', icon: '🟠' },
  { id: 'okx', name: 'OKX', icon: '⚪' },
]

// Preset trade amounts
const AMOUNT_PRESETS = [10, 25, 50, 100, 250]

function LiveAlerts() {
  const toast = useToast()
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isPaused, setIsPaused] = useState(false)
  const [filter, setFilter] = useState('all')
  const [refreshing, setRefreshing] = useState(false)
  const [showFollowed, setShowFollowed] = useState(true)

  // Fetch followed whales
  const { whales: followedWhales, loading: followedLoading } = useFollowingWhales()
  const isAuthenticated = authApi.isAuthenticated()

  // Fetch signals from API
  const fetchSignals = useCallback(async (showToast = false) => {
    try {
      if (showToast) setRefreshing(true)
      const data = await signalsApi.getSignals({ limit: 50 })

      const transformedAlerts = (data || []).map(signal => ({
        id: signal.id,
        whale: {
          id: signal.whale?.id || 0,
          name: signal.whale?.name || 'Unknown Whale',
          avatar: signal.whale?.avatar || '🐋',
          address: signal.whale?.wallet_address || '',
          winRate: parseFloat(signal.whale?.win_rate || 0),
          totalTrades: signal.whale?.total_trades || 0,
          avgProfit: parseFloat(signal.whale?.avg_profit || 0),
        },
        action: signal.action,
        token: signal.token,
        tokenName: signal.token_name || signal.token,
        amount: parseFloat(signal.amount_usd || 0),
        dex: signal.dex,
        chain: signal.chain,
        entryPrice: parseFloat(signal.entry_price || 0),
        currentPrice: parseFloat(signal.current_price || signal.entry_price || 0),
        confidence: signal.confidence,
        timestamp: new Date(signal.detected_at).getTime(),
        txHash: signal.tx_hash,
        autoCopyIn: signal.auto_copy_in || 0,
        status: signal.status === 'PENDING' ? 'pending' :
                signal.status === 'PROCESSED' ? 'copied' : 'skipped',
        cexSymbol: signal.cex_symbol,
        cexAvailable: signal.cex_available,
        leverage: signal.leverage || 1,
      }))

      setAlerts(transformedAlerts)
      setError(null)

      if (showToast) {
        toast.success('Signals refreshed')
        haptic.success()
      }
    } catch (err) {
      setError(err.message)
      if (showToast) {
        toast.error('Failed to refresh signals')
      }
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [toast])

  useEffect(() => {
    fetchSignals()
    const interval = setInterval(() => fetchSignals(false), 10000)
    return () => clearInterval(interval)
  }, [fetchSignals])

  const handleCopy = async (alertId, tradeSize, exchange) => {
    const alert = alerts.find(a => a.id === alertId)
    const loadingToast = toast.loading(`Copying ${alert?.token} trade...`)
    haptic.medium()

    try {
      await signalsApi.copySignal(alertId, { size_usdt: tradeSize, exchange })
      setAlerts(prev => prev.map(a =>
        a.id === alertId ? { ...a, status: 'copied', autoCopyIn: 0 } : a
      ))
      toast.dismiss(loadingToast)
      toast.success(`Copied ${alert?.token} trade on ${exchange.toUpperCase()}!`, {
        title: 'Trade Copied',
      })
      haptic.success()
    } catch (err) {
      toast.dismiss(loadingToast)
      toast.error(err.message || 'Failed to copy trade')
      haptic.error()
    }
  }

  const handleSkip = async (alertId) => {
    const alert = alerts.find(a => a.id === alertId)
    haptic.light()

    try {
      await signalsApi.skipSignal(alertId)
      setAlerts(prev => prev.map(a =>
        a.id === alertId ? { ...a, status: 'skipped', autoCopyIn: 0 } : a
      ))
      toast.info(`Skipped ${alert?.token} signal`)
    } catch (err) {
      toast.error('Failed to skip signal')
    }
  }

  const handleRefresh = () => {
    haptic.light()
    fetchSignals(true)
  }

  const filteredAlerts = alerts.filter(alert => {
    if (filter === 'all') return true
    return alert.status === filter
  })

  const pendingCount = alerts.filter(a => a.status === 'pending').length

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center gap-4"
        >
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
          >
            <Loader2 className="w-10 h-10 text-biolum-cyan" />
          </motion.div>
          <p className="text-gray-500 text-sm">Loading signals...</p>
        </motion.div>
      </div>
    )
  }

  return (
    <motion.div
      className="px-4 pt-6 pb-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-5"
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-white flex items-center gap-2">
              <motion.div
                animate={pendingCount > 0 ? {
                  scale: [1, 1.1, 1],
                  rotate: [0, -5, 5, 0],
                } : {}}
                transition={{ duration: 0.5, repeat: pendingCount > 0 ? Infinity : 0, repeatDelay: 2 }}
              >
                <Bell className="text-biolum-cyan" size={22} />
              </motion.div>
              Live Alerts
              <AnimatePresence>
                {pendingCount > 0 && (
                  <motion.span
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    exit={{ scale: 0 }}
                    className="ml-1 px-2 py-0.5 bg-loss rounded-full text-xs font-bold text-white"
                  >
                    {pendingCount}
                  </motion.span>
                )}
              </AnimatePresence>
            </h1>
            <p className="text-gray-500 text-xs mt-0.5">Real-time whale activity</p>
          </div>

          <div className="flex items-center gap-2">
            {/* Refresh Button */}
            <motion.button
              onClick={handleRefresh}
              whileTap={{ scale: 0.9 }}
              disabled={refreshing}
              className="p-2.5 rounded-xl bg-ocean-800/50 border border-ocean-700/50 transition-all disabled:opacity-50"
            >
              <RefreshCw size={16} className={`text-gray-400 ${refreshing ? 'animate-spin' : ''}`} />
            </motion.button>

            {/* Pause/Play Toggle */}
            <motion.button
              onClick={() => {
                setIsPaused(!isPaused)
                haptic.selection()
                toast.info(isPaused ? 'Auto-copy resumed' : 'Auto-copy paused')
              }}
              whileTap={{ scale: 0.9 }}
              className={`p-2.5 rounded-xl transition-all ${
                isPaused
                  ? 'bg-loss/20 text-loss border border-loss/30'
                  : 'bg-profit/20 text-profit border border-profit/30'
              }`}
            >
              {isPaused ? <Pause size={16} /> : <Play size={16} />}
            </motion.button>
          </div>
        </div>

        <AnimatePresence>
          {isPaused && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-3 flex items-center gap-2 px-3 py-2 bg-loss/10 rounded-xl border border-loss/20"
            >
              <AlertTriangle size={14} className="text-loss" />
              <span className="text-xs text-loss">Auto-copy paused</span>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Followed Whales Section */}
      {isAuthenticated && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mb-5"
        >
          <button
            onClick={() => {
              setShowFollowed(!showFollowed)
              haptic.selection()
            }}
            className="w-full flex items-center justify-between mb-3"
          >
            <h2 className="font-display text-sm font-semibold text-white flex items-center gap-2">
              <span className="text-lg">🐋</span>
              Your Followed Whales
              {followedWhales?.length > 0 && (
                <span className="text-xs px-1.5 py-0.5 rounded-full bg-biolum-cyan/20 text-biolum-cyan">
                  {followedWhales.length}
                </span>
              )}
            </h2>
            <ChevronDown
              size={16}
              className={`text-gray-500 transition-transform ${showFollowed ? 'rotate-180' : ''}`}
            />
          </button>

          <AnimatePresence>
            {showFollowed && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                {followedLoading ? (
                  <div className="glass-card p-4 flex items-center justify-center">
                    <Loader2 size={16} className="animate-spin text-biolum-cyan" />
                  </div>
                ) : followedWhales?.length > 0 ? (
                  <div className="flex gap-2 overflow-x-auto pb-2">
                    {followedWhales.map((whale, index) => (
                      <motion.div
                        key={whale.whale_id || whale.id || index}
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: 0.05 * index }}
                        className="flex-shrink-0 glass-card p-3 min-w-[140px]"
                      >
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xl">{whale.avatar || '🐋'}</span>
                          <div className="min-w-0 flex-1">
                            <p className="font-semibold text-white text-xs truncate">
                              {whale.name || whale.whale_name || 'Whale'}
                            </p>
                            <p className="text-[10px] text-gray-500">
                              {whale.exchange || 'Multi'}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center justify-between">
                          <div className="text-[10px] text-gray-400">
                            Win Rate
                          </div>
                          <span className={`text-xs font-mono font-bold ${
                            (whale.win_rate || 0) >= 50 ? 'text-profit' : 'text-loss'
                          }`}>
                            {safeFixed(whale.win_rate || 0, 0)}%
                          </span>
                        </div>
                        {whale.auto_copy && (
                          <div className="mt-1 text-[10px] text-biolum-cyan flex items-center gap-1">
                            <Zap size={10} />
                            Auto-copy
                          </div>
                        )}
                      </motion.div>
                    ))}
                  </div>
                ) : (
                  <div className="glass-card p-4 text-center">
                    <span className="text-2xl mb-2 block">🐋</span>
                    <p className="text-gray-400 text-sm">No whales followed yet</p>
                    <p className="text-gray-600 text-xs mt-1">
                      Go to Discovery to find whales to follow
                    </p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}

      {/* Filter Tabs */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="flex gap-2 mb-5 overflow-x-auto pb-1"
      >
        {[
          { id: 'all', label: 'All', count: alerts.length },
          { id: 'pending', label: 'Pending', count: pendingCount },
          { id: 'copied', label: 'Copied', count: alerts.filter(a => a.status === 'copied').length },
          { id: 'skipped', label: 'Skipped', count: alerts.filter(a => a.status === 'skipped').length },
        ].map((tab) => (
          <motion.button
            key={tab.id}
            onClick={() => {
              setFilter(tab.id)
              haptic.selection()
            }}
            whileTap={{ scale: 0.95 }}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5 ${
              filter === tab.id
                ? 'bg-gradient-to-r from-biolum-cyan/20 to-biolum-blue/20 border border-biolum-cyan/30 text-white'
                : 'bg-ocean-800/50 text-gray-400 hover:text-white border border-transparent'
            }`}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                filter === tab.id ? 'bg-biolum-cyan/20' : 'bg-ocean-700'
              }`}>
                {tab.count}
              </span>
            )}
          </motion.button>
        ))}
      </motion.div>

      {/* Error Message */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-4 p-3 bg-loss/10 rounded-xl border border-loss/20 flex items-center gap-2"
          >
            <AlertTriangle size={16} className="text-loss" />
            <p className="text-sm text-loss flex-1">{error}</p>
            <button onClick={handleRefresh} className="text-loss hover:underline text-sm">
              Retry
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Alerts List */}
      <motion.div
        className="space-y-3"
        variants={listContainerVariants}
        initial="hidden"
        animate="visible"
      >
        <AnimatePresence mode="popLayout">
          {filteredAlerts.map((alert, index) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              index={index}
              isPaused={isPaused}
              onCopy={handleCopy}
              onSkip={() => handleSkip(alert.id)}
            />
          ))}
        </AnimatePresence>

        {filteredAlerts.length === 0 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="text-center py-12 glass-card"
          >
            <motion.div
              className="text-5xl mb-4"
              animate={{ y: [0, -5, 0] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              🔔
            </motion.div>
            <p className="text-gray-400 font-medium">No alerts found</p>
            <p className="text-gray-600 text-sm mt-1">
              {alerts.length === 0
                ? 'Follow whales to receive trading signals'
                : 'No signals match your filter'}
            </p>
          </motion.div>
        )}
      </motion.div>
    </motion.div>
  )
}

function AlertCard({ alert, index, isPaused, onCopy, onSkip }) {
  const [countdown, setCountdown] = useState(alert.autoCopyIn)
  const [timeAgo, setTimeAgo] = useState('')
  const [tradeSize, setTradeSize] = useState(100) // Default 100 USDT
  const [selectedExchange, setSelectedExchange] = useState('binance')
  const [showExchangeDropdown, setShowExchangeDropdown] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [autoCopyTriggered, setAutoCopyTriggered] = useState(false)

  // Ref to hold current handleCopy function (prevents stale closure in countdown)
  const handleCopyRef = useRef(null)

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

  // Handle copy action - wrapped to always use current state values
  const handleCopy = useCallback(async () => {
    if (isSubmitting) return // Prevent double submission
    setIsSubmitting(true)
    try {
      await onCopy(alert.id, tradeSize, selectedExchange)
    } catch (err) {
      console.error('Copy failed:', err)
    } finally {
      setIsSubmitting(false)
    }
  }, [alert.id, tradeSize, selectedExchange, isSubmitting, onCopy])

  // Keep ref updated with latest handleCopy (fixes stale closure issue)
  useEffect(() => {
    handleCopyRef.current = handleCopy
  }, [handleCopy])

  // Countdown timer for auto-copy - uses ref to get current handleCopy
  useEffect(() => {
    if (alert.status !== 'pending' || isPaused || countdown <= 0 || autoCopyTriggered) return

    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          // Trigger auto-copy using ref to get current function with fresh state
          setAutoCopyTriggered(true)
          handleCopyRef.current?.()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [alert.status, isPaused, countdown, autoCopyTriggered])

  const confidenceConfig = {
    HIGH: { color: 'text-profit', bg: 'bg-profit/10', border: 'border-profit/30', label: 'HIGH' },
    VERY_HIGH: { color: 'text-profit', bg: 'bg-profit/10', border: 'border-profit/30', label: 'VERY HIGH' },
    MEDIUM: { color: 'text-amber-400', bg: 'bg-amber-400/10', border: 'border-amber-400/30', label: 'MEDIUM' },
    LOW: { color: 'text-loss', bg: 'bg-loss/10', border: 'border-loss/30', label: 'LOW' },
  }

  const confidence = confidenceConfig[alert.confidence] || confidenceConfig.MEDIUM

  const priceChange = alert.currentPrice && alert.entryPrice
    ? ((alert.currentPrice - alert.entryPrice) / alert.entryPrice * 100)
    : 0

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
      layout
      variants={listItemVariants}
      exit={{ opacity: 0, x: -100, scale: 0.9 }}
      className={`glass-card overflow-hidden relative ${
        alert.status === 'pending' ? 'border-biolum-cyan/30 shadow-[0_0_20px_rgba(0,255,200,0.1)]' : ''
      }`}
    >
      {/* Countdown Progress Bar */}
      <AnimatePresence>
        {alert.status === 'pending' && countdown > 0 && !isPaused && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="h-1 bg-ocean-700"
          >
            <motion.div
              className="h-full bg-gradient-to-r from-biolum-cyan to-biolum-blue"
              initial={{ width: '100%' }}
              animate={{ width: '0%' }}
              transition={{ duration: countdown, ease: 'linear' }}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="p-4">
        {/* Header - Whale Info */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="relative">
              <motion.div
                className="w-11 h-11 rounded-xl bg-gradient-to-br from-biolum-cyan/20 to-biolum-purple/20 flex items-center justify-center text-xl"
                whileHover={{ scale: 1.05 }}
              >
                {alert.whale.avatar}
              </motion.div>
              {alert.status === 'pending' && (
                <motion.div
                  className="absolute -top-1 -right-1 w-4 h-4 bg-biolum-cyan rounded-full flex items-center justify-center"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                >
                  <Zap size={10} className="text-ocean-900" />
                </motion.div>
              )}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white text-sm">{alert.whale.name}</span>
                {Number(alert.whale.winRate) > 0 && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-profit/10 text-profit">
                    {safeFixed(alert.whale.winRate, 0)}% win
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-[11px] text-gray-500">
                <Clock size={10} />
                {timeAgo}
                {alert.whale.totalTrades > 0 && (
                  <>
                    <span>•</span>
                    <span>{alert.whale.totalTrades} trades</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Confidence Badge */}
          <div className={`flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-lg ${confidence.bg} ${confidence.color} border ${confidence.border}`}>
            <Target size={10} />
            {confidence.label}
          </div>
        </div>

        {/* Trade Details Card */}
        <div className="bg-ocean-800/50 rounded-xl p-3 mb-3">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className={`text-[10px] font-bold px-2 py-1 rounded ${
                alert.action === 'BUY' ? 'bg-profit/20 text-profit' : 'bg-loss/20 text-loss'
              }`}>
                {alert.action}
              </span>
              <span className="font-display font-bold text-lg text-white">{alert.token}</span>
              {alert.leverage > 1 && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-biolum-purple/20 text-biolum-purple">
                  {alert.leverage}x
                </span>
              )}
            </div>
            <div className="text-right">
              <span className={`text-sm font-mono font-bold ${priceChange >= 0 ? 'text-profit' : 'text-loss'}`}>
                {priceChange >= 0 ? '+' : ''}{safeFixed(priceChange, 2)}%
              </span>
              <p className="text-[10px] text-gray-500">since signal</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 text-xs">
            <div>
              <p className="text-gray-500 text-[10px] mb-0.5">Amount</p>
              <p className="font-mono font-semibold text-white">{formatCurrency(alert.amount)}</p>
            </div>
            <div>
              <p className="text-gray-500 text-[10px] mb-0.5">Entry</p>
              <p className="font-mono font-semibold text-white">
                ${Number(alert.entryPrice) < 0.01 ? safeFixed(alert.entryPrice, 6) : safeFixed(alert.entryPrice, 2)}
              </p>
            </div>
            <div>
              <p className="text-gray-500 text-[10px] mb-0.5">Source</p>
              <p className="font-semibold text-white flex items-center gap-1">
                {alert.dex}
                <span className="text-[10px] px-1 py-0.5 bg-ocean-600 rounded text-gray-400">
                  {alert.chain}
                </span>
              </p>
            </div>
          </div>

          {alert.txHash && (
            <div className="mt-2 pt-2 border-t border-ocean-700">
              <a
                href={getExplorerUrl(alert.chain, alert.txHash)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[10px] text-biolum-cyan flex items-center gap-1 hover:underline"
              >
                View on explorer <ExternalLink size={10} />
              </a>
            </div>
          )}
        </div>

        {/* Trade Setup - Only for pending & CEX available */}
        {alert.status === 'pending' && alert.cexAvailable && (
          <>
            {/* Trade Size Selector */}
            <div className="mb-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-400">Trade Size (USDT)</span>
                {countdown > 0 && !isPaused && (
                  <motion.span
                    className="text-xs font-mono font-bold text-biolum-cyan"
                    animate={{ opacity: [1, 0.5, 1] }}
                    transition={{ duration: 0.5, repeat: Infinity }}
                  >
                    Auto-copy in {countdown}s
                  </motion.span>
                )}
              </div>

              {/* Amount Presets */}
              <div className="flex gap-2 mb-2">
                {AMOUNT_PRESETS.map((amount) => (
                  <motion.button
                    key={amount}
                    onClick={() => setTradeSize(amount)}
                    whileTap={{ scale: 0.95 }}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      tradeSize === amount
                        ? 'bg-biolum-cyan/20 text-biolum-cyan border border-biolum-cyan/30'
                        : 'bg-ocean-700/50 text-gray-400 hover:text-white border border-transparent'
                    }`}
                  >
                    ${amount}
                  </motion.button>
                ))}
              </div>

              {/* Custom Amount Input with validation */}
              <div className="relative">
                <DollarSign size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="number"
                  value={tradeSize}
                  onChange={(e) => {
                    const value = Number(e.target.value) || 0;
                    // Clamp value between min and max
                    const clampedValue = Math.min(Math.max(value, 0), 100000);
                    setTradeSize(clampedValue);
                  }}
                  min={10}
                  max={100000}
                  step={10}
                  className="w-full pl-8 pr-4 py-2 bg-ocean-700/50 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-biolum-cyan/50 border border-ocean-600"
                  placeholder="Custom amount ($10 - $100,000)"
                />
                {tradeSize > 0 && tradeSize < 10 && (
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-coral-400">Min $10</span>
                )}
              </div>
            </div>

            {/* Exchange Selector with keyboard support */}
            <div className="mb-4">
              <span className="text-xs text-gray-400 mb-2 block">Exchange</span>
              <div className="relative">
                <button
                  onClick={() => setShowExchangeDropdown(!showExchangeDropdown)}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') {
                      setShowExchangeDropdown(false);
                    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                      e.preventDefault();
                      if (!showExchangeDropdown) {
                        setShowExchangeDropdown(true);
                      } else {
                        const currentIndex = EXCHANGES.findIndex(ex => ex.id === selectedExchange);
                        const newIndex = e.key === 'ArrowDown'
                          ? Math.min(currentIndex + 1, EXCHANGES.length - 1)
                          : Math.max(currentIndex - 1, 0);
                        setSelectedExchange(EXCHANGES[newIndex].id);
                      }
                    } else if (e.key === 'Enter' && showExchangeDropdown) {
                      setShowExchangeDropdown(false);
                      haptic.selection();
                    }
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 bg-ocean-700/50 rounded-lg border border-ocean-600 text-sm"
                  aria-haspopup="listbox"
                  aria-expanded={showExchangeDropdown}
                >
                  <div className="flex items-center gap-2">
                    <span>{EXCHANGES.find(e => e.id === selectedExchange)?.icon}</span>
                    <span className="text-white font-medium">
                      {EXCHANGES.find(e => e.id === selectedExchange)?.name}
                    </span>
                  </div>
                  <ChevronDown size={16} className={`text-gray-400 transition-transform ${showExchangeDropdown ? 'rotate-180' : ''}`} />
                </button>

                <AnimatePresence>
                  {showExchangeDropdown && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="absolute top-full left-0 right-0 mt-1 bg-ocean-800 border border-ocean-600 rounded-lg overflow-hidden z-10"
                      role="listbox"
                    >
                      {EXCHANGES.map((exchange, index) => (
                        <button
                          key={exchange.id}
                          onClick={() => {
                            setSelectedExchange(exchange.id)
                            setShowExchangeDropdown(false)
                            haptic.selection()
                          }}
                          role="option"
                          aria-selected={selectedExchange === exchange.id}
                          className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-ocean-700 transition-colors ${
                            selectedExchange === exchange.id ? 'bg-ocean-700 text-white' : 'text-gray-400'
                          }`}
                        >
                          <span>{exchange.icon}</span>
                          <span>{exchange.name}</span>
                          {selectedExchange === exchange.id && (
                            <Check size={14} className="ml-auto text-biolum-cyan" />
                          )}
                        </button>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3">
              <motion.button
                onClick={handleCopy}
                disabled={isSubmitting || tradeSize <= 0}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex-1 btn-primary flex items-center justify-center gap-2 py-3 disabled:opacity-50"
              >
                {isSubmitting ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <>
                    <Check size={18} />
                    Copy ${tradeSize}
                  </>
                )}
              </motion.button>
              <motion.button
                onClick={onSkip}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex-1 btn-secondary flex items-center justify-center gap-2 py-3"
              >
                <X size={18} />
                Skip
              </motion.button>
            </div>
          </>
        )}

        {/* Not available on CEX warning */}
        {alert.status === 'pending' && !alert.cexAvailable && (
          <>
            <div className="mb-3 flex items-center gap-2 px-3 py-2 bg-amber-400/10 rounded-xl border border-amber-400/20">
              <AlertTriangle size={14} className="text-amber-400" />
              <span className="text-xs text-amber-400">Token not available on CEX</span>
            </div>
            <motion.button
              onClick={onSkip}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="w-full btn-secondary flex items-center justify-center gap-2 py-3"
            >
              <X size={18} />
              Dismiss
            </motion.button>
          </>
        )}

        {/* Copied State */}
        {alert.status === 'copied' && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center justify-center gap-2 py-3 bg-profit/10 rounded-xl border border-profit/20"
          >
            <Check size={18} className="text-profit" />
            <span className="text-profit font-semibold text-sm">Trade Copied Successfully</span>
          </motion.div>
        )}

        {/* Skipped State */}
        {alert.status === 'skipped' && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center justify-center gap-2 py-3 bg-gray-500/10 rounded-xl border border-gray-500/20"
          >
            <X size={18} className="text-gray-400" />
            <span className="text-gray-400 font-semibold text-sm">Signal Skipped</span>
          </motion.div>
        )}
      </div>
    </motion.div>
  )
}

export default LiveAlerts
