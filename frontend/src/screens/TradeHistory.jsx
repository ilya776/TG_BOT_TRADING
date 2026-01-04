import React, { useState } from 'react'
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
  Loader2
} from 'lucide-react'
import { useTrades, usePositions } from '../hooks/useApi'
import { formatCurrency, formatPercent } from '../services/api'

const filterOptions = [
  { id: 'all', label: 'All Trades' },
  { id: 'open', label: 'Open' },
  { id: 'closed', label: 'Closed' },
  { id: 'profit', label: 'Profit' },
  { id: 'loss', label: 'Loss' },
]

const timeFilters = [
  { id: 'today', label: 'Today' },
  { id: 'week', label: '7 Days' },
  { id: 'month', label: '30 Days' },
  { id: 'all', label: 'All Time' },
]

function TradeHistory() {
  const [selectedFilter, setSelectedFilter] = useState('all')
  const [selectedTime, setSelectedTime] = useState('week')
  const [selectedTrade, setSelectedTrade] = useState(null)

  // Fetch trades and positions from API
  const { trades: apiTrades, loading: tradesLoading, error: tradesError } = useTrades({ limit: 50 })
  const { positions, loading: positionsLoading, closePosition } = usePositions()

  // Combine trades and positions into unified list
  const allTrades = React.useMemo(() => {
    const closedTrades = (apiTrades || []).map(trade => ({
      id: trade.id,
      symbol: trade.symbol?.replace('USDT', '') || 'UNKNOWN',
      name: trade.symbol?.replace('USDT', '') || 'Unknown',
      side: trade.side === 'BUY' ? 'LONG' : 'SHORT',
      type: trade.trade_type || 'SPOT',
      leverage: trade.leverage ? `${trade.leverage}x` : null,
      entry: parseFloat(trade.executed_price || trade.requested_price || 0),
      exit: trade.status === 'FILLED' ? parseFloat(trade.executed_price || 0) : null,
      size: parseFloat(trade.trade_value_usdt || 0),
      pnl: 0, // Calculated from position if available
      pnlPercent: 0,
      whale: 'Whale',
      whaleAvatar: '🐋',
      status: trade.status === 'FILLED' ? 'closed' : 'pending',
      openedAt: new Date(trade.created_at).toLocaleString(),
      closedAt: trade.executed_at ? new Date(trade.executed_at).toLocaleString() : null,
    }))

    const openPositions = (positions || []).map(pos => ({
      id: `pos-${pos.id}`,
      positionId: pos.id,
      symbol: pos.symbol?.replace('USDT', '') || 'UNKNOWN',
      name: pos.symbol?.replace('USDT', '') || 'Unknown',
      side: pos.side === 'BUY' ? 'LONG' : 'SHORT',
      type: pos.position_type || 'SPOT',
      leverage: pos.leverage ? `${pos.leverage}x` : null,
      entry: parseFloat(pos.entry_price || 0),
      exit: null,
      size: parseFloat(pos.entry_value_usdt || 0),
      pnl: parseFloat(pos.unrealized_pnl || 0),
      pnlPercent: parseFloat(pos.unrealized_pnl_percent || 0),
      whale: 'Whale',
      whaleAvatar: '🐋',
      status: 'open',
      openedAt: new Date(pos.opened_at).toLocaleString(),
      closedAt: null,
    }))

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
  const profitTrades = filteredTrades.filter(t => t.pnl > 0).length
  const lossTrades = filteredTrades.filter(t => t.pnl < 0).length
  const totalPnl = filteredTrades.reduce((sum, t) => sum + t.pnl, 0)
  const winRate = totalTrades > 0 ? (profitTrades / totalTrades * 100).toFixed(1) : 0

  const loading = tradesLoading || positionsLoading

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
        <h1 className="font-display text-2xl font-bold text-white flex items-center gap-2">
          <History className="text-biolum-cyan" size={24} />
          Trade History
        </h1>
        <p className="text-gray-400 text-sm mt-1">Your copy trading activity</p>
      </motion.div>

      {/* Summary Stats */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass-card p-4 mb-5"
      >
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-gray-400">Summary</p>
          <div className="flex gap-2">
            {timeFilters.map((filter) => (
              <button
                key={filter.id}
                onClick={() => setSelectedTime(filter.id)}
                className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                  selectedTime === filter.id
                    ? 'bg-biolum-cyan/20 text-biolum-cyan'
                    : 'text-gray-500 hover:text-white'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-4 gap-3">
          <div className="text-center">
            <p className="font-display text-xl font-bold text-white">{totalTrades}</p>
            <p className="text-[10px] text-gray-500 uppercase">Trades</p>
          </div>
          <div className="text-center">
            <p className="font-display text-xl font-bold text-profit">{profitTrades}</p>
            <p className="text-[10px] text-gray-500 uppercase">Wins</p>
          </div>
          <div className="text-center">
            <p className="font-display text-xl font-bold text-loss">{lossTrades}</p>
            <p className="text-[10px] text-gray-500 uppercase">Losses</p>
          </div>
          <div className="text-center">
            <p className={`font-display text-xl font-bold ${totalPnl >= 0 ? 'text-profit' : 'text-loss'}`}>
              {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(0)}
            </p>
            <p className="text-[10px] text-gray-500 uppercase">P&L ($)</p>
          </div>
        </div>

        {/* Win Rate Bar */}
        <div className="mt-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-400">Win Rate</span>
            <span className="font-mono text-sm text-profit">{winRate}%</span>
          </div>
          <div className="h-2 bg-ocean-700 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-biolum-cyan to-profit rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${winRate}%` }}
              transition={{ duration: 0.8, delay: 0.3 }}
            />
          </div>
        </div>
      </motion.div>

      {/* Filter Tabs */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
        className="flex gap-2 overflow-x-auto pb-3 mb-4 hide-scrollbar"
      >
        {filterOptions.map((filter) => (
          <button
            key={filter.id}
            onClick={() => setSelectedFilter(filter.id)}
            className={`px-4 py-2 rounded-xl whitespace-nowrap transition-all text-sm font-medium ${
              selectedFilter === filter.id
                ? 'bg-gradient-to-r from-biolum-cyan/20 to-biolum-blue/20 border border-biolum-cyan/30 text-white'
                : 'bg-ocean-700/50 border border-transparent text-gray-400 hover:text-white'
            }`}
          >
            {filter.label}
          </button>
        ))}
      </motion.div>

      {/* Trades List */}
      <div className="space-y-3">
        <AnimatePresence>
          {filteredTrades.map((trade, index) => (
            <TradeCard
              key={trade.id}
              trade={trade}
              index={index}
              onClick={() => setSelectedTrade(trade)}
            />
          ))}
        </AnimatePresence>

        {filteredTrades.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-12"
          >
            <div className="text-4xl mb-3">📊</div>
            <p className="text-gray-400">No trades found</p>
            <p className="text-gray-500 text-sm">
              {allTrades.length === 0
                ? 'Follow whales and start copy trading'
                : 'Try adjusting your filters'}
            </p>
          </motion.div>
        )}
      </div>

      {/* Trade Detail Modal */}
      <AnimatePresence>
        {selectedTrade && (
          <TradeDetailModal
            trade={selectedTrade}
            onClose={() => setSelectedTrade(null)}
            onClosePosition={closePosition}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function TradeCard({ trade, index, onClick }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ delay: 0.05 * index }}
      className="glass-card-hover p-4"
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Token Icon */}
          <div className="relative">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-ocean-600 to-ocean-700 flex items-center justify-center">
              <span className="font-display font-bold text-sm text-white">
                {trade.symbol.slice(0, 3)}
              </span>
            </div>
            {trade.status === 'open' && (
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-profit rounded-full animate-pulse" />
            )}
          </div>

          {/* Trade Info */}
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-white">{trade.symbol}</span>
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                trade.side === 'LONG' ? 'bg-profit/20 text-profit' : 'bg-loss/20 text-loss'
              }`}>
                {trade.side}
              </span>
              {trade.leverage && (
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-biolum-purple/20 text-biolum-purple">
                  {trade.leverage}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xl">{trade.whaleAvatar}</span>
              <span className="text-xs text-gray-500">{trade.whale}</span>
            </div>
          </div>
        </div>

        {/* PnL */}
        <div className="text-right">
          <div className={`flex items-center justify-end gap-1 ${
            trade.pnl >= 0 ? 'text-profit' : 'text-loss'
          }`}>
            {trade.pnl >= 0 ? (
              <ArrowUpRight size={16} />
            ) : (
              <ArrowDownRight size={16} />
            )}
            <span className="font-mono font-bold text-lg">
              {trade.pnl >= 0 ? '+' : ''}{trade.pnlPercent.toFixed(2)}%
            </span>
          </div>
          <p className={`text-sm font-mono ${
            trade.pnl >= 0 ? 'text-profit/70' : 'text-loss/70'
          }`}>
            {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
          </p>
          <p className="text-[10px] text-gray-500 flex items-center justify-end gap-1 mt-1">
            <Clock size={10} />
            {trade.status === 'open' ? 'Open' : 'Closed'}
          </p>
        </div>
      </div>
    </motion.div>
  )
}

function TradeDetailModal({ trade, onClose, onClosePosition }) {
  const [closing, setClosing] = useState(false)

  const handleClosePosition = async () => {
    if (!trade.positionId) return
    setClosing(true)
    try {
      await onClosePosition(trade.positionId)
      onClose()
    } catch (err) {
      console.error('Failed to close position:', err)
    } finally {
      setClosing(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-end justify-center"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal */}
      <motion.div
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="relative w-full max-h-[80vh] overflow-y-auto rounded-t-3xl"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'linear-gradient(180deg, #151d2e 0%, #0a0e17 100%)',
        }}
      >
        {/* Handle */}
        <div className="sticky top-0 pt-3 pb-4 flex justify-center bg-gradient-to-b from-ocean-700 to-transparent">
          <div className="w-10 h-1 rounded-full bg-gray-600" />
        </div>

        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full bg-ocean-700/50 text-gray-400 hover:text-white"
        >
          <X size={20} />
        </button>

        <div className="px-5 pb-8">
          {/* Header */}
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-ocean-600 to-ocean-700 flex items-center justify-center">
              <span className="font-display font-bold text-lg text-white">
                {trade.symbol.slice(0, 3)}
              </span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-display text-2xl font-bold text-white">{trade.symbol}</h2>
                <span className={`text-xs font-bold px-2 py-1 rounded ${
                  trade.side === 'LONG' ? 'bg-profit/20 text-profit' : 'bg-loss/20 text-loss'
                }`}>
                  {trade.side}
                </span>
              </div>
              <p className="text-gray-400">{trade.name}</p>
            </div>
          </div>

          {/* PnL Card */}
          <div className={`glass-card p-6 mb-4 text-center ${
            trade.pnl >= 0 ? 'border-profit/20' : 'border-loss/20'
          }`}>
            <p className="text-sm text-gray-400 mb-2">Profit / Loss</p>
            <p className={`font-display text-4xl font-bold ${
              trade.pnl >= 0 ? 'text-profit' : 'text-loss'
            }`}>
              {trade.pnl >= 0 ? '+' : ''}{trade.pnlPercent.toFixed(2)}%
            </p>
            <p className={`font-mono text-lg ${
              trade.pnl >= 0 ? 'text-profit/70' : 'text-loss/70'
            }`}>
              {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
            </p>
          </div>

          {/* Trade Details */}
          <div className="glass-card p-4 mb-4">
            <div className="space-y-3">
              <div className="flex justify-between items-center py-2 border-b border-ocean-600/50">
                <span className="text-gray-400">Type</span>
                <span className="font-semibold text-white flex items-center gap-2">
                  {trade.type}
                  {trade.leverage && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-biolum-purple/20 text-biolum-purple">
                      {trade.leverage}
                    </span>
                  )}
                </span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-ocean-600/50">
                <span className="text-gray-400">Entry Price</span>
                <span className="font-mono font-semibold text-white">
                  ${trade.entry < 0.01 ? trade.entry.toFixed(8) : trade.entry.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-ocean-600/50">
                <span className="text-gray-400">Exit Price</span>
                <span className="font-mono font-semibold text-white">
                  {trade.exit
                    ? `$${trade.exit < 0.01 ? trade.exit.toFixed(8) : trade.exit.toFixed(2)}`
                    : '-'
                  }
                </span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-ocean-600/50">
                <span className="text-gray-400">Position Size</span>
                <span className="font-mono font-semibold text-white">${trade.size.toFixed(2)}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-ocean-600/50">
                <span className="text-gray-400">Opened</span>
                <span className="text-sm text-white">{trade.openedAt}</span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-gray-400">Closed</span>
                <span className="text-sm text-white">{trade.closedAt || 'Still Open'}</span>
              </div>
            </div>
          </div>

          {/* Whale Info */}
          <div className="glass-card p-4 mb-6">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-3">Copied From</p>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-biolum-cyan/20 to-biolum-purple/20 flex items-center justify-center text-2xl">
                {trade.whaleAvatar}
              </div>
              <div>
                <p className="font-semibold text-white">{trade.whale}</p>
                <p className="text-xs text-gray-500">Whale Trader</p>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          {trade.status === 'open' && trade.positionId && (
            <button
              onClick={handleClosePosition}
              disabled={closing}
              className="w-full py-4 rounded-2xl font-semibold text-lg bg-loss/20 text-loss border border-loss/30 hover:bg-loss/30 transition-all disabled:opacity-50"
            >
              {closing ? 'Closing...' : 'Close Position'}
            </button>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}

export default TradeHistory
