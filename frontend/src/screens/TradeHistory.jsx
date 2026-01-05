/**
 * TradeHistory - Complete trading activity with position management
 * Enhanced with quick actions, animations, and toast notifications
 */

import React, { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  History,
  TrendingUp,
  TrendingDown,
  Calendar,
  Filter,
  ChevronDown,
  ArrowUpRight,
  ArrowDownRight,
  Clock,
  X,
  Loader2,
  RefreshCw,
  DollarSign,
  Target,
  Zap,
  ExternalLink
} from 'lucide-react'
import { useTrades, usePositions } from '../hooks/useApi'
import { formatCurrency, formatPercent, tradesApi } from '../services/api'
import { useToast } from '../components/Toast'
import { SellPositionModal } from '../components/TradeModal'
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

const filterOptions = [
  { id: 'all', label: 'All Trades', icon: null },
  { id: 'open', label: 'Open', icon: Zap },
  { id: 'closed', label: 'Closed', icon: History },
  { id: 'profit', label: 'Profit', icon: TrendingUp },
  { id: 'loss', label: 'Loss', icon: TrendingDown },
]

const timeFilters = [
  { id: 'today', label: 'Today' },
  { id: 'week', label: '7D' },
  { id: 'month', label: '30D' },
  { id: 'all', label: 'All' },
]

function TradeHistory() {
  const toast = useToast()
  const [selectedFilter, setSelectedFilter] = useState('all')
  const [selectedTime, setSelectedTime] = useState('week')
  const [selectedTrade, setSelectedTrade] = useState(null)
  const [sellModal, setSellModal] = useState({ isOpen: false, position: null })
  const [refreshing, setRefreshing] = useState(false)

  // Fetch trades and positions from API with pagination support
  const {
    trades: apiTrades,
    loading: tradesLoading,
    error: tradesError,
    refetch: refetchTrades,
    loadMore,
    hasMore
  } = useTrades({ limit: 20 })
  const { positions, loading: positionsLoading, closePosition, refetch: refetchPositions } = usePositions()
  const [loadingMore, setLoadingMore] = useState(false)

  // Combine trades and positions into unified list
  const allTrades = React.useMemo(() => {
    const closedTrades = (apiTrades || []).map(trade => ({
      id: trade.id,
      symbol: trade.symbol?.replace('USDT', '') || 'UNKNOWN',
      fullSymbol: trade.symbol || 'UNKNOWN',
      name: trade.symbol?.replace('USDT', '') || 'Unknown',
      side: trade.side === 'BUY' ? 'LONG' : 'SHORT',
      type: trade.trade_type || 'SPOT',
      isSpot: !trade.leverage || trade.leverage <= 1 || trade.trade_type === 'SPOT',
      leverage: trade.leverage && trade.leverage > 1 ? `${trade.leverage}x` : null,
      entry: parseFloat(trade.executed_price || trade.requested_price || 0),
      exit: trade.status === 'FILLED' ? parseFloat(trade.executed_price || 0) : null,
      size: parseFloat(trade.trade_value_usdt || 0),
      pnl: parseFloat(trade.realized_pnl || 0),
      pnlPercent: parseFloat(trade.realized_pnl_percent || 0),
      whale: trade.whale_name || 'Whale',
      whaleAvatar: trade.whale_avatar || '🐋',
      status: trade.status === 'FILLED' ? 'closed' : 'pending',
      openedAt: new Date(trade.created_at).toLocaleString(),
      closedAt: trade.executed_at ? new Date(trade.executed_at).toLocaleString() : null,
      exchange: trade.exchange || 'BINANCE',
    }))

    const openPositions = (positions || []).map(pos => {
      const pnl = parseFloat(pos.unrealized_pnl || 0)
      const size = parseFloat(pos.entry_value_usdt || 0)
      // Calculate pnlPercent if not provided
      const pnlPercent = parseFloat(pos.unrealized_pnl_percent || 0) || (size > 0 ? (pnl / size) * 100 : 0)

      return {
        id: `pos-${pos.id}`,
        positionId: pos.id,
        symbol: pos.symbol?.replace('USDT', '') || 'UNKNOWN',
        fullSymbol: pos.symbol || 'UNKNOWN',
        name: pos.symbol?.replace('USDT', '') || 'Unknown',
        side: pos.side === 'BUY' ? 'LONG' : 'SHORT',
        type: pos.position_type || 'SPOT',
        isSpot: !pos.leverage || pos.leverage <= 1 || pos.position_type === 'SPOT' || pos.market_type === 'spot',
        leverage: pos.leverage && pos.leverage > 1 ? `${pos.leverage}x` : null,
        entry: parseFloat(pos.entry_price || 0),
        currentPrice: parseFloat(pos.current_price || pos.entry_price || 0),
        exit: null,
        size,
        pnl,
        pnlPercent,
        whale: pos.whale_name || 'Whale',
        whaleAvatar: pos.whale_avatar || '🐋',
        status: 'open',
        openedAt: new Date(pos.opened_at).toLocaleString(),
        closedAt: null,
        exchange: pos.exchange || 'BINANCE',
      }
    })

    return [...openPositions, ...closedTrades]
  }, [apiTrades, positions])

  const filteredTrades = allTrades.filter(trade => {
    if (selectedFilter === 'open' && trade.status !== 'open') return false
    if (selectedFilter === 'closed' && trade.status !== 'closed') return false
    if (selectedFilter === 'profit' && trade.pnl < 0) return false
    if (selectedFilter === 'loss' && trade.pnl >= 0) return false
    return true
  })

  // Calculate summary stats
  const totalTrades = filteredTrades.length
  const profitTrades = filteredTrades.filter(t => Number(t.pnl) > 0).length
  const lossTrades = filteredTrades.filter(t => Number(t.pnl) < 0).length
  const totalPnlRaw = filteredTrades.reduce((sum, t) => sum + (Number(t.pnl) || 0), 0)
  const totalPnl = isNaN(totalPnlRaw) ? 0 : totalPnlRaw
  const winRateCalc = totalTrades > 0 ? (profitTrades / totalTrades * 100) : 0
  const winRate = isNaN(winRateCalc) ? 0 : winRateCalc

  const loading = tradesLoading || positionsLoading

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    haptic.light()
    setRefreshing(true)
    try {
      await Promise.all([refetchTrades?.(), refetchPositions?.()])
      toast.success('Trades refreshed')
    } catch (err) {
      toast.error('Failed to refresh')
    }
    setRefreshing(false)
  }, [refetchTrades, refetchPositions, toast])

  // Handle quick close position
  const handleQuickClose = useCallback(async (trade) => {
    haptic.selection()
    setSellModal({ isOpen: true, position: {
      id: trade.positionId,
      symbol: trade.fullSymbol,
      unrealized_pnl: trade.pnl,
      unrealized_pnl_percent: trade.pnlPercent,
      side: trade.side === 'LONG' ? 'BUY' : 'SELL',
      entry_price: trade.entry,
      current_price: trade.currentPrice || trade.entry,
      size_usdt: trade.size,
    }})
  }, [])

  // Handle sell confirmation
  const handleSellConfirm = useCallback(async (position, percentage) => {
    const loadingToast = toast.loading(`Closing position...`)
    haptic.medium()

    try {
      await tradesApi.closePosition(position.id)
      toast.dismiss(loadingToast)
      toast.success(`Position closed successfully!`, { title: 'Position Closed' })
      haptic.success()
      await Promise.all([refetchTrades?.(), refetchPositions?.()])
    } catch (err) {
      toast.dismiss(loadingToast)
      toast.error(err.message || 'Failed to close position')
      haptic.error()
    } finally {
      setSellModal({ isOpen: false, position: null })
    }
  }, [toast, refetchTrades, refetchPositions])

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
          <p className="text-gray-500 text-sm">Loading trades...</p>
        </motion.div>
      </div>
    )
  }

  return (
    <>
      <motion.div
        className="px-4 pt-6 pb-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between mb-5"
        >
          <div>
            <h1 className="font-display text-xl font-bold text-white flex items-center gap-2">
              <History className="text-biolum-cyan" size={22} />
              Trade History
            </h1>
            <p className="text-gray-500 text-xs mt-0.5">Your copy trading activity</p>
          </div>
          <motion.button
            onClick={handleRefresh}
            whileTap={{ scale: 0.9 }}
            disabled={refreshing}
            className="p-2.5 rounded-xl bg-ocean-800/50 border border-ocean-700/50 transition-all disabled:opacity-50"
          >
            <RefreshCw size={16} className={`text-gray-400 ${refreshing ? 'animate-spin' : ''}`} />
          </motion.button>
        </motion.div>

        {/* Summary Stats Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card p-4 mb-5 relative overflow-hidden"
        >
          {/* Background Glow */}
          <motion.div
            className="absolute -right-10 -top-10 w-32 h-32 rounded-full blur-3xl"
            style={{ background: `radial-gradient(circle, ${totalPnl >= 0 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'} 0%, transparent 70%)` }}
          />

          <div className="flex items-center justify-between mb-3 relative z-10">
            <p className="text-sm text-gray-400 font-medium">Performance</p>
            <div className="flex gap-1">
              {timeFilters.map((filter) => (
                <motion.button
                  key={filter.id}
                  onClick={() => {
                    setSelectedTime(filter.id)
                    haptic.selection()
                  }}
                  whileTap={{ scale: 0.95 }}
                  className={`px-2 py-1 rounded-lg text-[10px] font-semibold transition-all ${
                    selectedTime === filter.id
                      ? 'bg-biolum-cyan/20 text-biolum-cyan'
                      : 'text-gray-500 hover:text-white'
                  }`}
                >
                  {filter.label}
                </motion.button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-4 gap-2 mb-4 relative z-10">
            {[
              { value: totalTrades, label: 'Trades', color: 'text-white' },
              { value: profitTrades, label: 'Wins', color: 'text-profit' },
              { value: lossTrades, label: 'Losses', color: 'text-loss' },
              { value: `${totalPnl >= 0 ? '+' : ''}${Math.round(totalPnl)}`, label: 'P&L $', color: totalPnl >= 0 ? 'text-profit' : 'text-loss' },
            ].map((stat, i) => (
              <motion.div
                key={stat.label}
                className="text-center"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.05 }}
              >
                <p className={`font-display text-xl font-bold ${stat.color}`}>{stat.value}</p>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">{stat.label}</p>
              </motion.div>
            ))}
          </div>

          {/* Win Rate Bar */}
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] text-gray-400 flex items-center gap-1">
                <Target size={12} />
                Win Rate
              </span>
              <span className={`font-mono text-sm font-bold ${winRate >= 50 ? 'text-profit' : 'text-loss'}`}>
                {winRate.toFixed(1)}%
              </span>
            </div>
            <div className="h-2 bg-ocean-700 rounded-full overflow-hidden">
              <motion.div
                className={`h-full rounded-full ${winRate >= 50 ? 'bg-gradient-to-r from-biolum-cyan to-profit' : 'bg-gradient-to-r from-loss to-amber-500'}`}
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(winRate, 100)}%` }}
                transition={{ duration: 0.8, delay: 0.3, ease: 'easeOut' }}
              />
            </div>
          </div>
        </motion.div>

        {/* Filter Tabs */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="flex gap-2 overflow-x-auto pb-3 mb-4 hide-scrollbar"
        >
          {filterOptions.map((filter) => {
            const count = filter.id === 'all' ? allTrades.length :
                         filter.id === 'open' ? allTrades.filter(t => t.status === 'open').length :
                         filter.id === 'closed' ? allTrades.filter(t => t.status === 'closed').length :
                         filter.id === 'profit' ? allTrades.filter(t => t.pnl > 0).length :
                         allTrades.filter(t => t.pnl < 0).length

            return (
              <motion.button
                key={filter.id}
                onClick={() => {
                  setSelectedFilter(filter.id)
                  haptic.selection()
                }}
                whileTap={{ scale: 0.95 }}
                className={`px-3 py-1.5 rounded-xl whitespace-nowrap transition-all text-xs font-medium flex items-center gap-1.5 ${
                  selectedFilter === filter.id
                    ? 'bg-gradient-to-r from-biolum-cyan/20 to-biolum-blue/20 border border-biolum-cyan/30 text-white'
                    : 'bg-ocean-800/50 border border-transparent text-gray-400 hover:text-white'
                }`}
              >
                {filter.label}
                {count > 0 && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    selectedFilter === filter.id ? 'bg-biolum-cyan/20' : 'bg-ocean-700'
                  }`}>
                    {count}
                  </span>
                )}
              </motion.button>
            )
          })}
        </motion.div>

        {/* Trades List */}
        <motion.div
          className="space-y-2"
          variants={listContainerVariants}
          initial="hidden"
          animate="visible"
        >
          <AnimatePresence mode="popLayout">
            {filteredTrades.map((trade, index) => (
              <TradeCard
                key={trade.id}
                trade={trade}
                index={index}
                onClick={() => setSelectedTrade(trade)}
                onQuickClose={() => handleQuickClose(trade)}
              />
            ))}
          </AnimatePresence>

          {/* Load More Button */}
          {hasMore && filteredTrades.length > 0 && (
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              onClick={async () => {
                setLoadingMore(true);
                haptic.light();
                await loadMore();
                setLoadingMore(false);
              }}
              disabled={loadingMore}
              className="w-full py-3 mt-4 glass-card text-gray-400 hover:text-white hover:bg-ocean-700/50 transition-colors flex items-center justify-center gap-2"
            >
              {loadingMore ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Loading...
                </>
              ) : (
                <>
                  <ChevronDown size={16} />
                  Load More Trades
                </>
              )}
            </motion.button>
          )}

          {filteredTrades.length === 0 && (
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
                📊
              </motion.div>
              <p className="text-gray-400 font-medium">No trades found</p>
              <p className="text-gray-600 text-sm mt-1">
                {allTrades.length === 0
                  ? 'Follow whales and start copy trading'
                  : 'Try adjusting your filters'}
              </p>
            </motion.div>
          )}
        </motion.div>
      </motion.div>

      {/* Trade Detail Modal */}
      <AnimatePresence>
        {selectedTrade && (
          <TradeDetailModal
            trade={selectedTrade}
            onClose={() => setSelectedTrade(null)}
            onClosePosition={handleQuickClose}
          />
        )}
      </AnimatePresence>

      {/* Sell Position Modal */}
      <SellPositionModal
        isOpen={sellModal.isOpen}
        position={sellModal.position}
        onClose={() => setSellModal({ isOpen: false, position: null })}
        onSell={handleSellConfirm}
      />
    </>
  )
}

function TradeCard({ trade, index, onClick, onQuickClose }) {
  const isProfit = trade.pnl >= 0

  return (
    <motion.div
      layout
      variants={listItemVariants}
      exit={{ opacity: 0, x: -50, scale: 0.95 }}
      className="glass-card-hover p-4 relative overflow-hidden"
      onClick={onClick}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
    >
      {/* Status indicator strip */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${
        trade.status === 'open' ? 'bg-biolum-cyan' : isProfit ? 'bg-profit' : 'bg-loss'
      }`} />

      <div className="flex items-center justify-between pl-2">
        <div className="flex items-center gap-3">
          {/* Token Icon */}
          <div className="relative">
            <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${
              isProfit
                ? 'bg-gradient-to-br from-profit/20 to-profit/5'
                : 'bg-gradient-to-br from-loss/20 to-loss/5'
            }`}>
              <span className="font-display font-bold text-sm text-white">
                {trade.symbol.slice(0, 3)}
              </span>
            </div>
            {trade.status === 'open' && (
              <motion.div
                className="absolute -top-1 -right-1 w-3 h-3 bg-biolum-cyan rounded-full"
                animate={{ scale: [1, 1.3, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
            )}
          </div>

          {/* Trade Info */}
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-white text-sm">{trade.symbol}</span>
              {/* Show SPOT for spot trades, LONG/SHORT for futures */}
              {trade.isSpot ? (
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-biolum-cyan/20 text-biolum-cyan">
                  SPOT
                </span>
              ) : (
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                  trade.side === 'LONG' ? 'bg-profit/20 text-profit' : 'bg-loss/20 text-loss'
                }`}>
                  {trade.side}
                </span>
              )}
              {trade.leverage && (
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-biolum-purple/20 text-biolum-purple">
                  {trade.leverage}
                </span>
              )}
            </div>
            <p className="text-[11px] text-gray-500 flex items-center gap-1">
              <span>{trade.whaleAvatar}</span>
              <span>{trade.whale}</span>
              <span>•</span>
              <span className="text-gray-600">${safeFixed(trade.size, 0)}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* PnL */}
          <div className="text-right">
            <div className={`flex items-center justify-end gap-1 ${isProfit ? 'text-profit' : 'text-loss'}`}>
              {isProfit ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              <span className="font-mono font-bold text-sm">
                {isProfit ? '+' : ''}{safeFixed(trade.pnlPercent, 2)}%
              </span>
            </div>
            <p className={`text-[11px] font-mono ${isProfit ? 'text-profit/70' : 'text-loss/70'}`}>
              {isProfit ? '+' : ''}${safeFixed(trade.pnl, 2)}
            </p>
          </div>

          {/* Quick Close Button (for open positions) */}
          {trade.status === 'open' && trade.positionId && (
            <motion.button
              onClick={(e) => {
                e.stopPropagation()
                onQuickClose()
              }}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={`px-2.5 py-1.5 rounded-lg text-[11px] font-semibold ${
                isProfit
                  ? 'bg-profit/20 text-profit hover:bg-profit/30'
                  : 'bg-loss/20 text-loss hover:bg-loss/30'
              }`}
            >
              Close
            </motion.button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function TradeDetailModal({ trade, onClose, onClosePosition }) {
  const toast = useToast()
  const isProfit = trade.pnl >= 0

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-end justify-center"
      onClick={onClose}
    >
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
      />

      {/* Modal */}
      <motion.div
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 400 }}
        className="relative w-full max-h-[85vh] overflow-y-auto rounded-t-3xl"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'linear-gradient(180deg, #151d2e 0%, #0a0e17 100%)',
        }}
      >
        {/* Handle */}
        <div className="sticky top-0 pt-3 pb-4 flex justify-center bg-gradient-to-b from-ocean-800/80 to-transparent z-10">
          <div className="w-10 h-1 rounded-full bg-gray-600" />
        </div>

        {/* Close Button */}
        <motion.button
          onClick={onClose}
          whileTap={{ scale: 0.9 }}
          className="absolute top-4 right-4 p-2 rounded-full bg-ocean-700/50 text-gray-400 hover:text-white z-10"
        >
          <X size={20} />
        </motion.button>

        <div className="px-5 pb-8">
          {/* Header */}
          <div className="flex items-center gap-4 mb-6">
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${
              isProfit ? 'bg-gradient-to-br from-profit/20 to-profit/5' : 'bg-gradient-to-br from-loss/20 to-loss/5'
            }`}>
              <span className="font-display font-bold text-lg text-white">
                {trade.symbol.slice(0, 3)}
              </span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-display text-xl font-bold text-white">{trade.symbol}</h2>
                {/* Show SPOT for spot trades, LONG/SHORT for futures */}
                {trade.isSpot ? (
                  <span className="text-[10px] font-bold px-2 py-1 rounded bg-biolum-cyan/20 text-biolum-cyan">
                    SPOT
                  </span>
                ) : (
                  <span className={`text-[10px] font-bold px-2 py-1 rounded ${
                    trade.side === 'LONG' ? 'bg-profit/20 text-profit' : 'bg-loss/20 text-loss'
                  }`}>
                    {trade.side}
                  </span>
                )}
                {trade.leverage && (
                  <span className="text-[10px] font-bold px-2 py-1 rounded bg-biolum-purple/20 text-biolum-purple">
                    {trade.leverage}
                  </span>
                )}
              </div>
              <p className="text-gray-500 text-sm">{trade.exchange}</p>
            </div>
          </div>

          {/* PnL Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className={`glass-card p-5 mb-4 text-center border ${
              isProfit ? 'border-profit/20' : 'border-loss/20'
            }`}
          >
            <p className="text-sm text-gray-400 mb-1">
              {trade.status === 'open' ? 'Unrealized P&L' : 'Realized P&L'}
            </p>
            <motion.p
              initial={{ scale: 0.9 }}
              animate={{ scale: 1 }}
              className={`font-display text-4xl font-bold ${isProfit ? 'text-profit' : 'text-loss'}`}
            >
              {isProfit ? '+' : ''}{safeFixed(trade.pnlPercent, 2)}%
            </motion.p>
            <p className={`font-mono text-lg mt-1 ${isProfit ? 'text-profit/70' : 'text-loss/70'}`}>
              {isProfit ? '+' : ''}${safeFixed(trade.pnl, 2)}
            </p>
          </motion.div>

          {/* Trade Details */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-4 mb-4"
          >
            <div className="space-y-3">
              {[
                { label: 'Type', value: <span className="flex items-center gap-2">{trade.type} {trade.leverage && <span className="text-xs px-1.5 py-0.5 rounded bg-biolum-purple/20 text-biolum-purple">{trade.leverage}</span>}</span> },
                { label: 'Entry Price', value: `$${Number(trade.entry) < 0.01 ? safeFixed(trade.entry, 8) : safeFixed(trade.entry, 2)}` },
                { label: trade.status === 'open' ? 'Current Price' : 'Exit Price', value: trade.status === 'open' ? `$${safeFixed(trade.currentPrice || trade.entry, 2)}` : (trade.exit ? `$${safeFixed(trade.exit, 2)}` : '-') },
                { label: 'Position Size', value: `$${safeFixed(trade.size, 2)}` },
                { label: 'Opened', value: trade.openedAt },
                { label: trade.status === 'open' ? 'Status' : 'Closed', value: trade.status === 'open' ? <span className="text-biolum-cyan">Open</span> : trade.closedAt },
              ].map((item, i) => (
                <div key={i} className="flex justify-between items-center py-2 border-b border-ocean-600/30 last:border-0">
                  <span className="text-gray-400 text-sm">{item.label}</span>
                  <span className="font-semibold text-white text-sm">{item.value}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Whale Info */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-4 mb-6"
          >
            <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">Copied From</p>
            <div className="flex items-center gap-3">
              <motion.div
                className="w-11 h-11 rounded-xl bg-gradient-to-br from-biolum-cyan/20 to-biolum-purple/20 flex items-center justify-center text-xl"
                whileHover={{ rotate: [0, -5, 5, 0] }}
              >
                {trade.whaleAvatar}
              </motion.div>
              <div>
                <p className="font-semibold text-white text-sm">{trade.whale}</p>
                <p className="text-[11px] text-gray-500">Whale Trader</p>
              </div>
            </div>
          </motion.div>

          {/* Action Buttons */}
          {trade.status === 'open' && trade.positionId && (
            <motion.button
              onClick={() => onClosePosition(trade)}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className={`w-full py-4 rounded-2xl font-semibold text-base ${
                isProfit
                  ? 'bg-profit/20 text-profit border border-profit/30 hover:bg-profit/30'
                  : 'bg-loss/20 text-loss border border-loss/30 hover:bg-loss/30'
              } transition-all`}
            >
              Close Position
            </motion.button>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}

export default TradeHistory
