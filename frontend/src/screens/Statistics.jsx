/**
 * Statistics - Comprehensive trading performance analytics
 * Performance overview, trading stats, whale analytics, portfolio breakdown
 */

import React, { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  TrendingUp,
  TrendingDown,
  Target,
  Award,
  Users,
  PieChart as PieChartIcon,
  BarChart2,
  Calendar,
  ChevronRight,
  Loader2,
  RefreshCw,
  Trophy,
  Flame,
  Zap,
  DollarSign,
  Activity
} from 'lucide-react'
import {
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'
import { useDashboard, useTrades } from '../hooks/useApi'
import { formatCurrency, formatPercent } from '../services/api'
import { springs, haptic, cardVariants } from '../utils/animations'

// Date range options
const DATE_RANGES = [
  { id: '7d', label: '7D', days: 7 },
  { id: '30d', label: '30D', days: 30 },
  { id: '90d', label: '90D', days: 90 },
  { id: 'all', label: 'All', days: 365 },
]

// Chart colors
const CHART_COLORS = {
  profit: '#00ffc8',
  loss: '#ff5f6d',
  primary: '#00a8ff',
  secondary: '#8b5cf6',
  tertiary: '#ec4899',
  neutral: '#64748b',
}

const PIE_COLORS = ['#00ffc8', '#00a8ff', '#8b5cf6', '#ec4899', '#f59e0b', '#64748b']

// Page animation
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

function Statistics() {
  const { portfolio, positions, topWhales, loading, error, refetch, isDemo } = useDashboard()
  const { trades } = useTrades()
  const [dateRange, setDateRange] = useState('30d')
  const [refreshing, setRefreshing] = useState(false)

  // Calculate statistics from trades
  const stats = useMemo(() => {
    if (!trades || trades.length === 0) {
      return {
        totalPnl: 0,
        totalPnlPercent: 0,
        winRate: 0,
        totalTrades: 0,
        winningTrades: 0,
        losingTrades: 0,
        avgWin: 0,
        avgLoss: 0,
        bestTrade: null,
        worstTrade: null,
        avgTradeSize: 0,
        profitFactor: 0,
      }
    }

    const closedTrades = trades.filter(t => t.status === 'closed')
    const winners = closedTrades.filter(t => (t.pnl || 0) > 0)
    const losers = closedTrades.filter(t => (t.pnl || 0) < 0)

    const totalPnl = closedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0)
    const totalWin = winners.reduce((sum, t) => sum + (t.pnl || 0), 0)
    const totalLoss = Math.abs(losers.reduce((sum, t) => sum + (t.pnl || 0), 0))

    const sortedByPnl = [...closedTrades].sort((a, b) => (b.pnl || 0) - (a.pnl || 0))

    return {
      totalPnl,
      totalPnlPercent: portfolio?.total_value ? (totalPnl / portfolio.total_value * 100) : 0,
      winRate: closedTrades.length > 0 ? (winners.length / closedTrades.length * 100) : 0,
      totalTrades: closedTrades.length,
      winningTrades: winners.length,
      losingTrades: losers.length,
      avgWin: winners.length > 0 ? totalWin / winners.length : 0,
      avgLoss: losers.length > 0 ? totalLoss / losers.length : 0,
      bestTrade: sortedByPnl[0] || null,
      worstTrade: sortedByPnl[sortedByPnl.length - 1] || null,
      avgTradeSize: closedTrades.length > 0
        ? closedTrades.reduce((sum, t) => sum + (t.size_usdt || 0), 0) / closedTrades.length
        : 0,
      profitFactor: totalLoss > 0 ? totalWin / totalLoss : totalWin > 0 ? Infinity : 0,
    }
  }, [trades, portfolio])

  // Generate PnL chart data
  const pnlChartData = useMemo(() => {
    if (!trades || trades.length === 0) {
      // Return empty array - no fake data
      return []
    }

    // Group trades by date
    const tradesByDate = {}
    trades.forEach(trade => {
      const date = new Date(trade.executed_at || trade.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      if (!tradesByDate[date]) {
        tradesByDate[date] = 0
      }
      tradesByDate[date] += trade.pnl || 0
    })

    let cumulative = 0
    return Object.entries(tradesByDate).map(([date, pnl]) => {
      cumulative += pnl
      return { date, pnl, cumulative }
    })
  }, [trades, dateRange])

  // Portfolio allocation pie chart data
  const allocationData = useMemo(() => {
    if (!positions || positions.length === 0) {
      // Return empty array - no fake data
      return []
    }

    const positionsBySymbol = {}
    positions.forEach(pos => {
      const symbol = pos.symbol?.replace('USDT', '') || 'Unknown'
      positionsBySymbol[symbol] = (positionsBySymbol[symbol] || 0) + (pos.size_usdt || 0)
    })

    const total = Object.values(positionsBySymbol).reduce((a, b) => a + b, 0)
    return Object.entries(positionsBySymbol)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([name, value], i) => ({
        name,
        value: total > 0 ? (value / total * 100) : 0,
        color: PIE_COLORS[i % PIE_COLORS.length],
      }))
  }, [positions])

  // Whale performance data
  const whalePerformance = useMemo(() => {
    if (!topWhales || topWhales.length === 0) {
      // Return empty array - no fake data
      return []
    }

    return topWhales.slice(0, 5).map(whale => ({
      name: whale.name?.slice(0, 10) || 'Unknown',
      pnl: Number(whale.stats?.total_profit_usd) || Number(whale.stats?.total_pnl) || 0,
      winRate: Number(whale.stats?.win_rate) || 0,
    }))
  }, [topWhales])

  const handleRefresh = async () => {
    setRefreshing(true)
    haptic.light()
    await refetch()
    setRefreshing(false)
  }

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
          <p className="text-gray-500 text-sm">Loading statistics...</p>
        </motion.div>
      </div>
    )
  }

  return (
    <motion.div
      className="px-4 pt-6 pb-4"
      variants={pageVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header */}
      <motion.div variants={itemVariants} className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-gradient-to-br from-biolum-purple/20 to-biolum-pink/10 border border-biolum-purple/30">
            <BarChart2 size={20} className="text-biolum-purple" />
          </div>
          <div>
            <h1 className="font-display text-xl font-bold text-white">Statistics</h1>
            <p className="text-gray-500 text-xs">Your trading performance</p>
          </div>
        </div>
        <motion.button
          onClick={handleRefresh}
          whileTap={{ scale: 0.9 }}
          className="p-2.5 rounded-xl bg-ocean-800/50 hover:bg-ocean-700/50 border border-ocean-700/50 transition-all"
        >
          <RefreshCw size={18} className={`text-gray-400 ${refreshing ? 'animate-spin' : ''}`} />
        </motion.button>
      </motion.div>

      {/* Date Range Selector */}
      <motion.div variants={itemVariants} className="flex gap-2 mb-5">
        {DATE_RANGES.map((range) => (
          <motion.button
            key={range.id}
            onClick={() => {
              haptic.selection()
              setDateRange(range.id)
            }}
            whileTap={{ scale: 0.95 }}
            className={`flex-1 py-2 rounded-xl text-sm font-semibold transition-all ${
              dateRange === range.id
                ? 'bg-biolum-cyan/20 text-biolum-cyan border border-biolum-cyan/30'
                : 'bg-ocean-800/50 text-gray-400 border border-ocean-700/50 hover:border-ocean-600'
            }`}
          >
            {range.label}
          </motion.button>
        ))}
      </motion.div>

      {/* Performance Overview - Hero Stats */}
      <motion.div variants={itemVariants} className="grid grid-cols-2 gap-3 mb-5">
        {/* Total PnL */}
        <div className={`glass-card p-4 relative overflow-hidden ${
          stats.totalPnl >= 0
            ? 'bg-gradient-to-br from-profit/10 to-profit/5'
            : 'bg-gradient-to-br from-loss/10 to-loss/5'
        }`}>
          <div className="absolute -right-4 -bottom-4 opacity-10">
            <DollarSign size={64} className={stats.totalPnl >= 0 ? 'text-profit' : 'text-loss'} />
          </div>
          <p className="text-gray-400 text-xs mb-1">Total PnL</p>
          <p className={`font-display text-2xl font-bold ${
            stats.totalPnl >= 0 ? 'text-profit' : 'text-loss'
          }`}>
            {stats.totalPnl >= 0 ? '+' : ''}{formatCurrency(stats.totalPnl)}
          </p>
          <p className={`text-xs font-mono ${
            (stats.totalPnlPercent ?? 0) >= 0 ? 'text-profit/70' : 'text-loss/70'
          }`}>
            {(stats.totalPnlPercent ?? 0) >= 0 ? '+' : ''}{Number(stats.totalPnlPercent || 0).toFixed(2)}%
          </p>
        </div>

        {/* Win Rate */}
        <div className="glass-card p-4 relative overflow-hidden bg-gradient-to-br from-biolum-cyan/10 to-biolum-blue/5">
          <div className="absolute -right-4 -bottom-4 opacity-10">
            <Target size={64} className="text-biolum-cyan" />
          </div>
          <p className="text-gray-400 text-xs mb-1">Win Rate</p>
          <p className="font-display text-2xl font-bold text-white">
            {Number(stats.winRate || 0).toFixed(1)}%
          </p>
          <p className="text-xs text-gray-500">
            {stats.winningTrades}W / {stats.losingTrades}L
          </p>
        </div>

        {/* Total Trades */}
        <div className="glass-card p-4 relative overflow-hidden">
          <div className="absolute -right-4 -bottom-4 opacity-10">
            <Activity size={64} className="text-biolum-purple" />
          </div>
          <p className="text-gray-400 text-xs mb-1">Total Trades</p>
          <p className="font-display text-2xl font-bold text-white">
            {stats.totalTrades}
          </p>
          <p className="text-xs text-gray-500">
            Avg: {formatCurrency(stats.avgTradeSize)}
          </p>
        </div>

        {/* Profit Factor */}
        <div className="glass-card p-4 relative overflow-hidden">
          <div className="absolute -right-4 -bottom-4 opacity-10">
            <Flame size={64} className="text-biolum-pink" />
          </div>
          <p className="text-gray-400 text-xs mb-1">Profit Factor</p>
          <p className="font-display text-2xl font-bold text-white">
            {stats.profitFactor === Infinity ? '∞' : Number(stats.profitFactor || 0).toFixed(2)}
          </p>
          <p className="text-xs text-gray-500">
            Risk/Reward Ratio
          </p>
        </div>
      </motion.div>

      {/* PnL Chart */}
      <motion.div variants={itemVariants} className="glass-card p-4 mb-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-semibold text-white flex items-center gap-2">
            <TrendingUp size={16} className="text-profit" />
            PnL Over Time
          </h2>
        </div>
        {pnlChartData.length === 0 ? (
          <div className="h-48 flex items-center justify-center">
            <div className="text-center">
              <Activity size={32} className="mx-auto text-gray-600 mb-2" />
              <p className="text-gray-500 text-sm">No trading data yet</p>
              <p className="text-gray-600 text-xs">Start trading to see your PnL chart</p>
            </div>
          </div>
        ) : (
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={pnlChartData}>
              <defs>
                <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART_COLORS.profit} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={CHART_COLORS.profit} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="date"
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(value) => `$${value}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1a2235',
                  border: '1px solid #2d3748',
                  borderRadius: '12px',
                  fontSize: '12px',
                }}
                labelStyle={{ color: '#64748b' }}
                formatter={(value) => [`$${Number(value || 0).toFixed(2)}`, 'PnL']}
              />
              <Area
                type="monotone"
                dataKey="cumulative"
                stroke={CHART_COLORS.profit}
                strokeWidth={2}
                fill="url(#pnlGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        )}
      </motion.div>

      {/* Best & Worst Trades */}
      <motion.div variants={itemVariants} className="grid grid-cols-2 gap-3 mb-5">
        {/* Best Trade */}
        <div className="glass-card p-4 border-profit/20">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-lg bg-profit/20 flex items-center justify-center">
              <Trophy size={16} className="text-profit" />
            </div>
            <span className="text-xs text-gray-400">Best Trade</span>
          </div>
          {stats.bestTrade ? (
            <>
              <p className="font-semibold text-white text-sm">{stats.bestTrade.symbol}</p>
              <p className="font-mono text-lg text-profit font-bold">
                +{formatCurrency(stats.bestTrade.pnl || 0)}
              </p>
            </>
          ) : (
            <p className="text-gray-500 text-sm">No trades yet</p>
          )}
        </div>

        {/* Worst Trade */}
        <div className="glass-card p-4 border-loss/20">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-lg bg-loss/20 flex items-center justify-center">
              <TrendingDown size={16} className="text-loss" />
            </div>
            <span className="text-xs text-gray-400">Worst Trade</span>
          </div>
          {stats.worstTrade && stats.worstTrade.pnl < 0 ? (
            <>
              <p className="font-semibold text-white text-sm">{stats.worstTrade.symbol}</p>
              <p className="font-mono text-lg text-loss font-bold">
                {formatCurrency(stats.worstTrade.pnl || 0)}
              </p>
            </>
          ) : (
            <p className="text-gray-500 text-sm">No losing trades</p>
          )}
        </div>
      </motion.div>

      {/* Portfolio Allocation */}
      <motion.div variants={itemVariants} className="glass-card p-4 mb-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-semibold text-white flex items-center gap-2">
            <PieChartIcon size={16} className="text-biolum-purple" />
            Portfolio Allocation
          </h2>
        </div>
        {allocationData.length === 0 ? (
          <div className="h-32 flex items-center justify-center">
            <div className="text-center">
              <PieChartIcon size={32} className="mx-auto text-gray-600 mb-2" />
              <p className="text-gray-500 text-sm">No positions yet</p>
              <p className="text-gray-600 text-xs">Open positions to see allocation</p>
            </div>
          </div>
        ) : (
        <div className="flex items-center gap-4">
          <div className="w-32 h-32">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={allocationData}
                  cx="50%"
                  cy="50%"
                  innerRadius={35}
                  outerRadius={55}
                  dataKey="value"
                  stroke="none"
                >
                  {allocationData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex-1 space-y-2">
            {allocationData.map((item, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-sm text-gray-300">{item.name}</span>
                </div>
                <span className="text-sm font-mono text-white">{Number(item.value || 0).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
        )}
      </motion.div>

      {/* Whale Performance */}
      <motion.div variants={itemVariants} className="glass-card p-4 mb-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-semibold text-white flex items-center gap-2">
            <span className="text-lg">🐋</span>
            Whale Performance
          </h2>
          <button className="text-biolum-cyan text-xs flex items-center gap-1 hover:underline">
            View All <ChevronRight size={14} />
          </button>
        </div>
        {whalePerformance.length === 0 ? (
          <div className="h-40 flex items-center justify-center">
            <div className="text-center">
              <span className="text-3xl mb-2 block">🐋</span>
              <p className="text-gray-500 text-sm">No whales followed yet</p>
              <p className="text-gray-600 text-xs">Follow whales to see their performance</p>
            </div>
          </div>
        ) : (
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={whalePerformance} layout="vertical">
              <XAxis
                type="number"
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(value) => `$${value}`}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fill: '#fff', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={70}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1a2235',
                  border: '1px solid #2d3748',
                  borderRadius: '12px',
                  fontSize: '12px',
                }}
                formatter={(value, name) => [
                  name === 'pnl' ? `$${Number(value || 0).toFixed(2)}` : `${Number(value || 0).toFixed(1)}%`,
                  name === 'pnl' ? 'PnL' : 'Win Rate'
                ]}
              />
              <Bar dataKey="pnl" fill={CHART_COLORS.profit} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        )}
      </motion.div>

      {/* Quick Stats Grid */}
      <motion.div variants={itemVariants} className="grid grid-cols-3 gap-2">
        <div className="glass-card p-3 text-center">
          <p className="text-xs text-gray-500 mb-1">Avg Win</p>
          <p className="font-mono text-sm font-bold text-profit">
            +{formatCurrency(stats.avgWin)}
          </p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className="text-xs text-gray-500 mb-1">Avg Loss</p>
          <p className="font-mono text-sm font-bold text-loss">
            -{formatCurrency(stats.avgLoss)}
          </p>
        </div>
        <div className="glass-card p-3 text-center">
          <p className="text-xs text-gray-500 mb-1">Open Pos</p>
          <p className="font-mono text-sm font-bold text-white">
            {positions?.length || 0}
          </p>
        </div>
      </motion.div>
    </motion.div>
  )
}

export default Statistics
