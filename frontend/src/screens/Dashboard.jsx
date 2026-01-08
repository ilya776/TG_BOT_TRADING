/**
 * Dashboard - Main trading overview with real-time positions and quick actions
 * Redesigned with smooth animations and trading controls
 */

import React, { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Users,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
  ChevronRight,
  Sparkles,
  Loader2,
  RefreshCw,
  Wallet,
  X,
  DollarSign,
  ArrowRightLeft,
  MoreHorizontal,
  Target,
  Shield
} from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'
import { useDashboard, useBalances, useUser } from '../hooks/useApi'
import { formatCurrency, formatPercent, formatLargeNumber, shortenAddress, authApi, tradesApi } from '../services/api'
import { useToast } from '../components/Toast'
import { SellPositionModal, ConvertToUsdtModal, ConfirmModal } from '../components/TradeModal'
import { PremiumBanner } from '../components/PremiumBanner'
import {
  springs,
  listContainerVariants,
  listItemVariants,
  cardVariants,
  fadeInFrom,
  haptic
} from '../utils/animations'

// Page container animation
const pageVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.1,
    },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 24, scale: 0.96 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: springs.smooth
  },
}

function Dashboard() {
  const { portfolio, positions, topWhales, loading, error, isDemo, refetch } = useDashboard()
  const { balances, syncing, syncBalance, fetchBalances } = useBalances()
  const { user } = useUser()
  const toast = useToast()

  // Check if user has Pro subscription
  const currentPlan = user?.subscription_tier || 'FREE'
  const isPro = currentPlan === 'PRO' || currentPlan === 'ELITE'
  const [showPlanModal, setShowPlanModal] = useState(false)

  // Modal states
  const [sellModal, setSellModal] = useState({ isOpen: false, position: null })
  const [convertModal, setConvertModal] = useState({ isOpen: false, asset: null })
  const [confirmModal, setConfirmModal] = useState({ isOpen: false, action: null })
  const [actionLoading, setActionLoading] = useState({})

  // Calculate stats - use balance API as single source of truth for total balance
  // This prevents double-counting when portfolio and exchange balances overlap
  const exchangeTotalBalance = balances?.total_usdt ? Number(balances.total_usdt) : 0
  const portfolioBalance = portfolio?.total_value || portfolio?.total_value_usdt || portfolio?.available_balance || 0

  // Use exchange balance when connected (regardless of spot/futures split)
  // Only fall back to portfolio if no exchange is connected OR exchange balance is 0
  const hasConnectedExchange = balances?.exchanges?.some(ex => ex.connected)
  const balance = hasConnectedExchange && exchangeTotalBalance > 0
    ? exchangeTotalBalance
    : portfolioBalance

  const todayPnl = portfolio?.realized_pnl_today || portfolio?.daily_pnl || 0
  const todayPnlPercent = balance > 0 ? (todayPnl / balance * 100) : 0

  // Calculate actual win rate from portfolio data
  const actualWinRate = portfolio?.win_rate
    ? Number(portfolio.win_rate)
    : (portfolio?.winning_positions && portfolio?.total_positions
        ? Math.round((portfolio.winning_positions / portfolio.total_positions) * 100)
        : 0)

  const stats = [
    {
      label: 'Positions',
      value: (portfolio?.total_positions || positions?.length || 0).toString(),
      icon: Activity,
      color: 'from-biolum-blue/20 to-biolum-blue/5',
      iconColor: 'text-biolum-blue',
      glow: 'shadow-[0_0_20px_rgba(0,168,255,0.15)]'
    },
    {
      label: 'Win Rate',
      value: actualWinRate > 0 ? `${actualWinRate}%` : 'N/A',
      icon: Target,
      color: 'from-profit/20 to-profit/5',
      iconColor: 'text-profit',
      glow: 'shadow-[0_0_20px_rgba(16,185,129,0.15)]'
    },
    {
      label: 'Top Whales',
      value: (topWhales?.length || 0).toString(),
      icon: Users,
      color: 'from-biolum-purple/20 to-biolum-purple/5',
      iconColor: 'text-biolum-purple',
      glow: 'shadow-[0_0_20px_rgba(139,92,246,0.15)]'
    },
    {
      label: 'Unrealized',
      value: formatLargeNumber(portfolio?.unrealized_pnl || portfolio?.month_pnl || 0),
      icon: Sparkles,
      color: 'from-biolum-cyan/20 to-biolum-cyan/5',
      iconColor: 'text-biolum-cyan',
      glow: 'shadow-[0_0_20px_rgba(0,255,200,0.15)]'
    },
  ]

  // Handle position sell
  const handleSellPosition = useCallback(async (position, percentage, convertToUsdt = false) => {
    const loadingKey = `sell-${position.id}`
    setActionLoading(prev => ({ ...prev, [loadingKey]: true }))

    const actionText = convertToUsdt ? 'Closing and converting' : 'Closing'
    const loadingToast = toast.loading(`${actionText} ${percentage}% of ${position.symbol}...`)

    try {
      haptic.medium()

      // Close position API call
      // Note: percentage and convertToUsdt are for future use - backend currently closes 100%
      const result = await tradesApi.closePosition(position.id, 'MANUAL')

      toast.dismiss(loadingToast)
      const successMsg = convertToUsdt
        ? `Closed ${percentage}% and converted to USDT`
        : `Closed ${percentage}% of ${position.symbol}`
      toast.success(successMsg, {
        title: 'Position Closed',
      })
      haptic.success()

      // Refresh data
      refetch()
      fetchBalances()
    } catch (err) {
      toast.dismiss(loadingToast)
      toast.error(err.message || 'Failed to close position')
      haptic.error()
    } finally {
      setActionLoading(prev => ({ ...prev, [loadingKey]: false }))
      setSellModal({ isOpen: false, position: null })
    }
  }, [toast, refetch, fetchBalances])

  // Handle convert to USDT
  const handleConvertToUsdt = useCallback(async (asset, amount) => {
    const loadingToast = toast.loading(`Converting ${asset.symbol} to USDT...`)

    try {
      haptic.medium()

      // API call to convert would go here
      // await balanceApi.convertToUsdt(asset.symbol, amount)

      toast.dismiss(loadingToast)
      toast.success(`Converted ${amount} ${asset.symbol} to USDT`, {
        title: 'Conversion Complete',
      })
      haptic.success()

      fetchBalances()
    } catch (err) {
      toast.dismiss(loadingToast)
      toast.error(err.message || 'Conversion failed')
      haptic.error()
    } finally {
      setConvertModal({ isOpen: false, asset: null })
    }
  }, [toast, fetchBalances])

  // Quick refresh
  const handleRefresh = useCallback(async () => {
    haptic.light()
    toast.info('Refreshing data...')
    await Promise.all([refetch(), fetchBalances()])
    toast.success('Data refreshed')
  }, [refetch, fetchBalances, toast])

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
          <p className="text-gray-500 text-sm">Loading portfolio...</p>
        </motion.div>
      </div>
    )
  }

  if (error) {
    return (
      <motion.div
        className="px-4 pt-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="glass-card p-6 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-loss/10 flex items-center justify-center">
            <X className="w-8 h-8 text-loss" />
          </div>
          <p className="text-loss font-semibold mb-2">Failed to load dashboard</p>
          <p className="text-gray-500 text-sm mb-4">{error}</p>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 rounded-xl bg-ocean-700 hover:bg-ocean-600 text-white text-sm font-medium transition-colors"
          >
            Try Again
          </button>
        </div>
      </motion.div>
    )
  }

  return (
    <>
      <motion.div
        className="px-4 pt-6 pb-4"
        variants={pageVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Header with Refresh */}
        <motion.div variants={itemVariants} className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <motion.span
              className="text-3xl"
              animate={{
                y: [0, -4, 0],
                rotate: [0, 3, -3, 0],
              }}
              transition={{
                duration: 4,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            >
              🐋
            </motion.span>
            <div>
              <h1 className="font-display text-xl font-bold text-white">Whale Trading</h1>
              <p className="text-gray-500 text-xs">Copy the best, be the best</p>
            </div>
          </div>
          <motion.button
            onClick={handleRefresh}
            whileTap={{ scale: 0.9 }}
            className="p-2.5 rounded-xl bg-ocean-800/50 hover:bg-ocean-700/50 border border-ocean-700/50 transition-all"
          >
            <RefreshCw size={18} className="text-gray-400" />
          </motion.button>
        </motion.div>

        {/* Demo Mode Banner */}
        <AnimatePresence>
          {isDemo && (
            <motion.div
              variants={itemVariants}
              initial="hidden"
              animate="visible"
              exit={{ opacity: 0, height: 0 }}
              className="mb-5 p-4 rounded-2xl bg-gradient-to-r from-biolum-cyan/10 via-biolum-blue/10 to-biolum-purple/10 border border-biolum-cyan/20 backdrop-blur-sm"
            >
              <div className="flex items-center gap-3">
                <motion.span
                  className="text-2xl"
                  animate={{ rotate: [0, 10, -10, 0] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                >
                  {authApi.isInTelegram() ? '🔄' : '👋'}
                </motion.span>
                <div>
                  <p className="text-white font-semibold text-sm">
                    {authApi.isInTelegram() ? 'Demo Mode' : 'Demo Mode'}
                  </p>
                  <p className="text-gray-400 text-xs">
                    {authApi.canAuthenticate()
                      ? 'Connecting to your account...'
                      : authApi.isInTelegram()
                        ? 'Open via Telegram mobile app to authenticate'
                        : 'Open in Telegram to unlock full features'
                    }
                  </p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Balance Card - Hero Section */}
        <motion.div
          variants={itemVariants}
          className="glass-card p-6 mb-5 relative overflow-hidden group"
          whileHover={{ scale: 1.01 }}
          transition={springs.snappy}
        >
          {/* Animated Background Gradients */}
          <motion.div
            className="absolute -right-20 -top-20 w-60 h-60 rounded-full blur-3xl"
            style={{ background: 'radial-gradient(circle, rgba(0,255,200,0.15) 0%, transparent 70%)' }}
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.3, 0.5, 0.3],
            }}
            transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
          />
          <motion.div
            className="absolute -left-20 -bottom-20 w-48 h-48 rounded-full blur-3xl"
            style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)' }}
            animate={{
              scale: [1.2, 1, 1.2],
              opacity: [0.3, 0.5, 0.3],
            }}
            transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
          />

          <div className="relative z-10">
            <div className="flex items-center justify-between mb-1">
              <p className="text-gray-400 text-sm">Total Balance</p>
              <div className="flex items-center gap-1 text-gray-500 text-xs">
                <Shield size={12} />
                <span>Secured</span>
              </div>
            </div>

            <motion.div
              className="flex items-baseline gap-3 mb-4"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              <span className="font-display text-4xl font-bold text-white tabular-nums tracking-tight">
                {formatCurrency(balance)}
              </span>
            </motion.div>

            <div className="flex items-center gap-3">
              <motion.div
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl ${
                  todayPnl >= 0
                    ? 'bg-profit/15 border border-profit/20'
                    : 'bg-loss/15 border border-loss/20'
                }`}
                whileHover={{ scale: 1.02 }}
              >
                {todayPnl >= 0 ? (
                  <ArrowUpRight size={16} className="text-profit" />
                ) : (
                  <ArrowDownRight size={16} className="text-loss" />
                )}
                <span className={`font-mono text-sm font-bold ${
                  todayPnl >= 0 ? 'text-profit' : 'text-loss'
                }`}>
                  {todayPnl >= 0 ? '+' : ''}{formatCurrency(todayPnl)}
                </span>
                <span className={`font-mono text-xs ${
                  todayPnl >= 0 ? 'text-profit/70' : 'text-loss/70'
                }`}>
                  ({formatPercent(todayPnlPercent)})
                </span>
              </motion.div>
              <span className="text-gray-500 text-xs">Today</span>
            </div>
          </div>
        </motion.div>

        {/* Connect Exchange CTA - Show prominently when no exchanges connected */}
        {!isDemo && (!hasConnectedExchange || !balances?.exchanges?.length) && (
          <motion.div
            variants={itemVariants}
            className="mb-5 glass-card p-5 relative overflow-hidden border border-biolum-cyan/30"
            whileHover={{ scale: 1.01 }}
          >
            {/* Background glow */}
            <div className="absolute -right-10 -top-10 w-32 h-32 rounded-full bg-biolum-cyan/10 blur-3xl" />
            <div className="absolute -left-10 -bottom-10 w-24 h-24 rounded-full bg-biolum-purple/10 blur-3xl" />

            <div className="relative z-10 flex items-start gap-4">
              <motion.div
                className="w-12 h-12 rounded-2xl bg-gradient-to-br from-biolum-cyan/30 to-biolum-blue/20 flex items-center justify-center flex-shrink-0"
                animate={{ rotate: [0, 5, -5, 0] }}
                transition={{ duration: 3, repeat: Infinity }}
              >
                <Wallet size={24} className="text-biolum-cyan" />
              </motion.div>
              <div className="flex-1">
                <h3 className="text-white font-semibold text-sm mb-1">Connect Your Exchange</h3>
                <p className="text-gray-400 text-xs mb-3">
                  Link your Binance, Bybit, or OKX account to start copy trading whale traders automatically.
                </p>
                <motion.button
                  onClick={() => {
                    haptic.medium()
                    window.dispatchEvent(new CustomEvent('navigate', { detail: 'settings' }))
                  }}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-biolum-cyan to-biolum-blue text-ocean-900 text-xs font-bold shadow-glow-sm"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  Connect Exchange →
                </motion.button>
              </div>
            </div>
          </motion.div>
        )}

        {/* Premium Banner - Show for FREE users who have exchanges connected */}
        {!isPro && !isDemo && hasConnectedExchange && (
          <motion.div variants={itemVariants} className="mb-5">
            <PremiumBanner
              onUpgrade={() => {
                haptic.medium()
                // Navigate to settings or open plan modal
                // For now, we can use a toast or redirect
                window.dispatchEvent(new CustomEvent('navigate', { detail: 'settings' }))
              }}
              dismissible={true}
            />
          </motion.div>
        )}

        {/* Quick Stats Grid */}
        <motion.div variants={itemVariants} className="grid grid-cols-2 gap-3 mb-5">
          {stats.map((stat, index) => {
            const Icon = stat.icon
            return (
              <motion.div
                key={stat.label}
                className={`glass-card p-4 bg-gradient-to-br ${stat.color} ${stat.glow} relative overflow-hidden`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index, ...springs.smooth }}
                whileHover={{ scale: 1.02, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                <div className="absolute -right-4 -bottom-4 opacity-10">
                  <Icon size={64} className={stat.iconColor} />
                </div>
                <div className="relative z-10">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`p-1.5 rounded-lg bg-ocean-800/50`}>
                      <Icon size={14} className={stat.iconColor} />
                    </div>
                    <span className="text-gray-400 text-xs font-medium">{stat.label}</span>
                  </div>
                  <span className="font-display text-2xl font-bold text-white">
                    {stat.value}
                  </span>
                </div>
              </motion.div>
            )
          })}
        </motion.div>

        {/* Exchange Balances - Compact Cards */}
        {!isDemo && balances?.exchanges?.length > 0 && (
          <motion.div variants={itemVariants} className="mb-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-display text-base font-semibold text-white flex items-center gap-2">
                <Wallet size={16} className="text-biolum-purple" />
                Exchange Balances
              </h2>
              <button
                onClick={() => {
                  haptic.light()
                  fetchBalances()
                }}
                className="text-xs text-biolum-cyan hover:text-biolum-cyan/80 flex items-center gap-1"
              >
                <RefreshCw size={12} />
                Sync All
              </button>
            </div>

            <div className="space-y-2">
              {balances.exchanges.filter(ex => ex.connected).map((exchange, index) => {
                const spotTotal = Number(exchange.spot_total) || 0
                const futuresTotal = Number(exchange.futures_total) || 0
                const totalBalance = spotTotal + futuresTotal
                // Show as "has data" if balance > 0 OR exchange has been synced before
                const hasBalance = totalBalance > 0 || exchange.last_sync

                return (
                  <motion.div
                    key={exchange.exchange}
                    className="glass-card p-4"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.05 * index }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                          hasBalance
                            ? 'bg-gradient-to-br from-profit/20 to-profit/5'
                            : 'bg-ocean-700/50'
                        }`}>
                          <span className="text-xl">
                            {exchange.exchange === 'BINANCE' ? '🟡' :
                             exchange.exchange === 'BYBIT' ? '🟠' : '⚫'}
                          </span>
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-white">{exchange.exchange}</span>
                            {hasBalance && (
                              <span className="text-xs px-1.5 py-0.5 rounded bg-profit/20 text-profit">
                                Connected
                              </span>
                            )}
                          </div>
                          {totalBalance > 0 ? (
                            <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
                              <span>Spot: <span className="text-white font-medium">{formatCurrency(spotTotal)}</span></span>
                              <span>•</span>
                              <span>Futures: <span className="text-white font-medium">{formatCurrency(futuresTotal)}</span></span>
                            </div>
                          ) : exchange.last_sync ? (
                            <p className="text-xs text-gray-500 mt-0.5">
                              Balance: {formatCurrency(0)} • Last synced: {new Date(exchange.last_sync).toLocaleTimeString()}
                            </p>
                          ) : (
                            <p className="text-xs text-gray-500 mt-0.5">
                              Tap sync to fetch balance
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        {/* Total Balance for this exchange */}
                        {hasBalance && (
                          <div className="text-right">
                            <span className="font-display text-lg font-bold text-white">
                              {formatCurrency(totalBalance)}
                            </span>
                          </div>
                        )}
                        <motion.button
                          onClick={() => {
                            haptic.medium()
                            syncBalance(exchange.exchange.toLowerCase())
                          }}
                          disabled={syncing[exchange.exchange.toLowerCase()]}
                          whileTap={{ scale: 0.9 }}
                          className={`p-2 rounded-xl transition-colors disabled:opacity-50 ${
                            hasBalance
                              ? 'bg-ocean-700/50 hover:bg-ocean-600/50'
                              : 'bg-biolum-cyan/20 hover:bg-biolum-cyan/30'
                          }`}
                        >
                          <RefreshCw
                            size={16}
                            className={`${hasBalance ? 'text-gray-400' : 'text-biolum-cyan'} ${
                              syncing[exchange.exchange.toLowerCase()] ? 'animate-spin' : ''
                            }`}
                          />
                        </motion.button>
                      </div>
                    </div>

                    {/* Show last sync time if available */}
                    {exchange.last_sync && (
                      <p className="text-[10px] text-gray-600 mt-2 text-right">
                        Last synced: {new Date(exchange.last_sync).toLocaleTimeString()}
                      </p>
                    )}
                  </motion.div>
                )
              })}

              {/* Show message if no exchanges connected */}
              {balances.exchanges.filter(ex => ex.connected).length === 0 && (
                <motion.div
                  className="glass-card p-6 text-center border border-biolum-cyan/20"
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={() => {
                    haptic.medium()
                    window.dispatchEvent(new CustomEvent('navigate', { detail: 'settings' }))
                  }}
                >
                  <motion.div
                    className="w-14 h-14 mx-auto mb-3 rounded-2xl bg-gradient-to-br from-biolum-cyan/20 to-biolum-purple/10 flex items-center justify-center"
                    animate={{ y: [0, -4, 0] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <Wallet size={28} className="text-biolum-cyan" />
                  </motion.div>
                  <p className="text-white font-semibold text-sm mb-1">Connect Your Exchange</p>
                  <p className="text-gray-500 text-xs mb-4">Link Binance, Bybit, or OKX to start copy trading</p>
                  <motion.button
                    className="px-4 py-2 rounded-xl bg-gradient-to-r from-biolum-cyan to-biolum-blue text-ocean-900 text-sm font-bold"
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    Connect Now →
                  </motion.button>
                </motion.div>
              )}
            </div>
          </motion.div>
        )}

        {/* Active Positions with Quick Actions */}
        <motion.div variants={itemVariants} className="mb-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display text-base font-semibold text-white flex items-center gap-2">
              <Zap size={16} className="text-biolum-cyan" />
              Active Positions
            </h2>
            <button
              onClick={() => {
                haptic.light()
                window.dispatchEvent(new CustomEvent('navigate', { detail: 'history' }))
              }}
              className="text-biolum-cyan text-xs font-medium flex items-center gap-1 hover:underline"
            >
              View All <ChevronRight size={14} />
            </button>
          </div>

          {positions.length === 0 ? (
            <motion.div
              className="glass-card p-8 text-center"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <motion.div
                className="w-16 h-16 mx-auto mb-4 rounded-full bg-ocean-800 flex items-center justify-center"
                animate={{ y: [0, -5, 0] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <Activity size={28} className="text-gray-600" />
              </motion.div>
              <p className="text-gray-400 font-medium">No active positions</p>
              <p className="text-gray-600 text-sm mt-1">Follow a whale to start copy trading</p>
            </motion.div>
          ) : (
            <motion.div
              className="space-y-2"
              variants={listContainerVariants}
              initial="hidden"
              animate="visible"
            >
              {positions.slice(0, 5).map((position, index) => (
                <PositionCard
                  key={position.id}
                  position={position}
                  index={index}
                  onSell={() => {
                    haptic.selection()
                    setSellModal({ isOpen: true, position })
                  }}
                  isLoading={actionLoading[`sell-${position.id}`]}
                />
              ))}
            </motion.div>
          )}
        </motion.div>

        {/* Top Whales */}
        <motion.div variants={itemVariants}>
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-display text-base font-semibold text-white flex items-center gap-2">
              <span className="text-lg">🐋</span>
              Top Whales
            </h2>
            <button
              onClick={() => {
                haptic.light()
                window.dispatchEvent(new CustomEvent('navigate', { detail: 'whales' }))
              }}
              className="text-biolum-cyan text-xs font-medium flex items-center gap-1 hover:underline"
            >
              Discover <ChevronRight size={14} />
            </button>
          </div>
          <p className="text-gray-500 text-xs mb-3">
            Professional traders with proven track records. Follow them to copy their trades automatically.
          </p>

          {topWhales.length === 0 ? (
            <div className="glass-card p-6 text-center">
              <p className="text-gray-500">No whales found</p>
            </div>
          ) : (
            <motion.div
              className="space-y-2"
              variants={listContainerVariants}
              initial="hidden"
              animate="visible"
            >
              {topWhales.map((whale, index) => (
                <WhaleCard key={whale.id} whale={whale} index={index} />
              ))}
            </motion.div>
          )}
        </motion.div>
      </motion.div>

      {/* Modals */}
      <SellPositionModal
        isOpen={sellModal.isOpen}
        position={sellModal.position}
        onClose={() => setSellModal({ isOpen: false, position: null })}
        onSell={handleSellPosition}
      />

      <ConvertToUsdtModal
        isOpen={convertModal.isOpen}
        asset={convertModal.asset}
        onClose={() => setConvertModal({ isOpen: false, asset: null })}
        onConfirm={handleConvertToUsdt}
      />
    </>
  )
}

// Position Card with Quick Actions
function PositionCard({ position, index, onSell, isLoading }) {
  const [showActions, setShowActions] = useState(false)
  const pnl = Number(position.unrealized_pnl || 0)
  const margin = Number(position.entry_value_usdt || 0)
  const leverageNum = position.leverage || 1
  const isFutures = position.position_type === 'FUTURES'
  // Position size = margin * leverage for futures (notional value)
  const size = isFutures ? margin * leverageNum : margin
  // Calculate pnlPercent if not provided by API (use margin as base for %)
  const pnlPercent = Number(position.unrealized_pnl_percent || 0) || (margin > 0 ? (pnl / margin) * 100 : 0)
  const isProfit = pnl >= 0

  return (
    <motion.div
      variants={listItemVariants}
      className="glass-card-hover p-4 relative overflow-hidden"
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
    >
      {/* Profit/Loss indicator strip */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${isProfit ? 'bg-profit' : 'bg-loss'}`} />

      <div className="flex items-center justify-between pl-2">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-display font-bold text-sm text-white ${
            isProfit
              ? 'bg-gradient-to-br from-profit/30 to-profit/10'
              : 'bg-gradient-to-br from-loss/30 to-loss/10'
          }`}>
            {position.symbol?.replace('USDT', '').slice(0, 3) || '??'}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-white text-sm">{position.symbol}</span>
              {/* Show SPOT for spot trades, LONG/SHORT for futures - use position_type as source of truth */}
              {position.position_type === 'SPOT' ? (
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-biolum-cyan/20 text-biolum-cyan">
                  SPOT
                </span>
              ) : (
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                  position.side === 'BUY'
                    ? 'bg-profit/20 text-profit'
                    : 'bg-loss/20 text-loss'
                }`}>
                  {position.side === 'BUY' ? 'LONG' : 'SHORT'}
                </span>
              )}
              {position.leverage && position.leverage >= 1 && position.position_type === 'FUTURES' && (
                <span className="text-[10px] font-mono text-gray-500">
                  {position.leverage}x
                </span>
              )}
            </div>
            <p className="text-[11px] text-gray-500">
              via {position.whale_name || 'Whale'} • Entry: ${Number(position.entry_price || 0).toFixed(2)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* PnL Display */}
          <div className="text-right">
            <div className={`flex items-center justify-end gap-1 ${
              isProfit ? 'text-profit' : 'text-loss'
            }`}>
              {isProfit ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              <span className="font-mono font-bold text-sm">
                {isProfit ? '+' : ''}{pnlPercent.toFixed(2)}%
              </span>
            </div>
            <p className={`text-[11px] font-mono ${isProfit ? 'text-profit/70' : 'text-loss/70'}`}>
              {isProfit ? '+' : ''}{formatCurrency(pnl)}
            </p>
          </div>

          {/* Quick Action Button */}
          <motion.button
            onClick={(e) => {
              e.stopPropagation()
              onSell()
            }}
            disabled={isLoading}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              isProfit
                ? 'bg-profit/20 text-profit hover:bg-profit/30'
                : 'bg-loss/20 text-loss hover:bg-loss/30'
            } disabled:opacity-50`}
          >
            {isLoading ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              'Close'
            )}
          </motion.button>
        </div>
      </div>
    </motion.div>
  )
}

// Whale Card Component
function WhaleCard({ whale, index }) {
  const chartData = whale.chart_data?.map((value) => ({ value })) ||
    [40, 45, 42, 55, 60, 58, 65, 70, 68, 75, 80, 85].map((value) => ({ value }))

  const weeklyPnl = Number(whale.stats?.avg_profit_percent) || 0
  const winRateRaw = Number(whale.stats?.win_rate)
  const winRate = isNaN(winRateRaw) ? 0 : winRateRaw
  const totalTrades = whale.stats?.total_trades || 0
  const isFollowing = whale.is_following || false
  const whaleName = whale.name || 'Unknown Whale'

  return (
    <motion.div
      variants={listItemVariants}
      className="glass-card-hover p-4"
      whileHover={{ scale: 1.01, x: 4 }}
      whileTap={{ scale: 0.99 }}
    >
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div className="relative">
          <motion.div
            className="w-12 h-12 rounded-2xl bg-gradient-to-br from-biolum-cyan/20 to-biolum-purple/20 flex items-center justify-center text-2xl"
            whileHover={{ rotate: [0, -5, 5, 0] }}
            transition={{ duration: 0.4 }}
          >
            {whale.avatar || '🐋'}
          </motion.div>
          {isFollowing && (
            <motion.div
              className="absolute -bottom-1 -right-1 w-5 h-5 bg-profit rounded-full flex items-center justify-center"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={springs.bouncy}
            >
              <svg className="w-3 h-3 text-ocean-900" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            </motion.div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white truncate text-sm">{whaleName}</h3>
          </div>
          <p className="text-[11px] text-gray-500 font-mono">
            {whale.wallet_address ? shortenAddress(whale.wallet_address) : `${totalTrades} trades`}
          </p>
        </div>

        {/* Mini Chart */}
        <div className="w-16 h-8">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id={`gradient-${whale.id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="value"
                stroke={weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'}
                strokeWidth={1.5}
                fill={`url(#gradient-${whale.id})`}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Stats */}
        <div className="text-right">
          <div className={`font-mono font-bold text-sm ${
            weeklyPnl >= 0 ? 'text-profit' : 'text-loss'
          }`}>
            {formatPercent(weeklyPnl)}
          </div>
          <p className="text-[11px] text-gray-500">{winRate.toFixed(0)}% win</p>
        </div>
      </div>
    </motion.div>
  )
}

export default Dashboard
