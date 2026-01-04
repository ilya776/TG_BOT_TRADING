import React from 'react'
import { motion } from 'framer-motion'
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
  Loader2
} from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'
import { useDashboard } from '../hooks/useApi'
import { formatCurrency, formatPercent, formatLargeNumber, shortenAddress, authApi } from '../services/api'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
}

function Dashboard() {
  const { portfolio, positions, topWhales, loading, error, isDemo } = useDashboard()

  // Calculate stats from portfolio
  const balance = portfolio?.total_value_usdt || portfolio?.total_balance || 0
  const todayPnl = portfolio?.daily_pnl || portfolio?.today_pnl || 0
  const todayPnlPercent = portfolio?.daily_pnl_percent || portfolio?.today_pnl_percent || 0

  const stats = [
    {
      label: 'Positions',
      value: (portfolio?.total_positions || positions?.length || 0).toString(),
      icon: Activity,
      color: 'text-biolum-blue'
    },
    {
      label: 'Win Rate',
      value: `${portfolio?.win_rate || (portfolio?.winning_positions && portfolio?.total_positions ? Math.round((portfolio.winning_positions / portfolio.total_positions) * 100) : 67)}%`,
      icon: TrendingUp,
      color: 'text-profit'
    },
    {
      label: 'Top Whales',
      value: (topWhales?.length || 0).toString(),
      icon: Users,
      color: 'text-biolum-purple'
    },
    {
      label: 'Unrealized',
      value: formatLargeNumber(portfolio?.unrealized_pnl || portfolio?.month_pnl || 0),
      icon: Sparkles,
      color: 'text-biolum-cyan'
    },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 text-biolum-cyan animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 pt-6">
        <div className="glass-card p-4 text-center">
          <p className="text-loss">Failed to load dashboard</p>
          <p className="text-gray-500 text-sm mt-2">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <motion.div
      className="px-4 pt-6 pb-4"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header */}
      <motion.div variants={itemVariants} className="mb-6">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-2xl">🐋</span>
          <h1 className="font-display text-xl font-bold text-white">Whale Trading</h1>
        </div>
        <p className="text-gray-400 text-sm">Copy the best, be the best</p>
      </motion.div>

      {/* Demo Mode Banner */}
      {isDemo && (
        <motion.div
          variants={itemVariants}
          className="mb-5 p-4 rounded-xl bg-gradient-to-r from-biolum-cyan/10 to-biolum-purple/10 border border-biolum-cyan/20"
        >
          <div className="flex items-center gap-3">
            <span className="text-xl">👋</span>
            <div>
              <p className="text-white font-semibold text-sm">Demo Mode</p>
              <p className="text-gray-400 text-xs">
                {authApi.isInTelegram()
                  ? 'Connecting to your account...'
                  : 'Open in Telegram to unlock full features'
                }
              </p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Balance Card */}
      <motion.div variants={itemVariants} className="glass-card p-5 mb-5 relative overflow-hidden">
        {/* Background Glow */}
        <div className="absolute -right-10 -top-10 w-40 h-40 bg-biolum-cyan/10 rounded-full blur-3xl" />
        <div className="absolute -left-10 -bottom-10 w-32 h-32 bg-biolum-purple/10 rounded-full blur-3xl" />

        <div className="relative">
          <p className="text-gray-400 text-sm mb-1">Total Balance</p>
          <div className="flex items-baseline gap-3 mb-3">
            <motion.span
              className="font-display text-4xl font-bold text-white tabular-nums"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              {formatCurrency(balance)}
            </motion.span>
          </div>

          <div className="flex items-center gap-2">
            <div className={`flex items-center gap-1 px-2.5 py-1 rounded-lg ${
              todayPnl >= 0 ? 'bg-profit/10' : 'bg-loss/10'
            }`}>
              {todayPnl >= 0 ? (
                <ArrowUpRight size={14} className="text-profit" />
              ) : (
                <ArrowDownRight size={14} className="text-loss" />
              )}
              <span className={`font-mono text-sm font-semibold ${
                todayPnl >= 0 ? 'text-profit' : 'text-loss'
              }`}>
                {todayPnl >= 0 ? '+' : ''}{formatCurrency(todayPnl)}
              </span>
              <span className={`font-mono text-sm ${
                todayPnl >= 0 ? 'text-profit/70' : 'text-loss/70'
              }`}>
                ({formatPercent(todayPnlPercent)})
              </span>
            </div>
            <span className="text-gray-500 text-xs">Today</span>
          </div>
        </div>
      </motion.div>

      {/* Quick Stats Grid */}
      <motion.div variants={itemVariants} className="grid grid-cols-2 gap-3 mb-5">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <div
              key={stat.label}
              className="glass-card p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <Icon size={16} className={stat.color} />
                <span className="text-gray-400 text-xs">{stat.label}</span>
              </div>
              <span className="font-display text-xl font-bold text-white">
                {stat.value}
              </span>
            </div>
          )
        })}
      </motion.div>

      {/* Active Positions */}
      <motion.div variants={itemVariants} className="mb-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display text-lg font-semibold text-white flex items-center gap-2">
            <Zap size={18} className="text-biolum-cyan" />
            Active Positions
          </h2>
          <button className="text-biolum-cyan text-sm font-medium flex items-center gap-1">
            View All <ChevronRight size={16} />
          </button>
        </div>

        {positions.length === 0 ? (
          <div className="glass-card p-6 text-center">
            <p className="text-gray-500">No active positions</p>
            <p className="text-gray-600 text-sm mt-1">Follow a whale to start copy trading</p>
          </div>
        ) : (
          <div className="space-y-3">
            {positions.slice(0, 3).map((position, index) => (
              <motion.div
                key={position.id}
                className="glass-card-hover p-4"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 * index }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-ocean-600 to-ocean-700 flex items-center justify-center font-display font-bold text-sm text-white">
                      {position.symbol?.slice(0, 2) || '??'}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-white">{position.symbol}</span>
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                          position.side === 'BUY' ? 'bg-profit/20 text-profit' : 'bg-loss/20 text-loss'
                        }`}>
                          {position.side === 'BUY' ? 'LONG' : 'SHORT'}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500">
                        via {position.whale_name || 'Whale'}
                      </p>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className={`flex items-center justify-end gap-1 ${
                      position.unrealized_pnl >= 0 ? 'text-profit' : 'text-loss'
                    }`}>
                      {position.unrealized_pnl >= 0 ? (
                        <TrendingUp size={14} />
                      ) : (
                        <TrendingDown size={14} />
                      )}
                      <span className="font-mono font-semibold">
                        {formatPercent(position.unrealized_pnl_percent || 0)}
                      </span>
                    </div>
                    <p className={`text-xs font-mono ${
                      position.unrealized_pnl >= 0 ? 'text-profit/70' : 'text-loss/70'
                    }`}>
                      {formatCurrency(position.unrealized_pnl || 0)}
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </motion.div>

      {/* Top Whales */}
      <motion.div variants={itemVariants}>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display text-lg font-semibold text-white flex items-center gap-2">
            <span className="text-lg">🐋</span>
            Top Whales
          </h2>
          <button className="text-biolum-cyan text-sm font-medium flex items-center gap-1">
            Discover <ChevronRight size={16} />
          </button>
        </div>

        {topWhales.length === 0 ? (
          <div className="glass-card p-6 text-center">
            <p className="text-gray-500">No whales found</p>
          </div>
        ) : (
          <div className="space-y-3">
            {topWhales.map((whale, index) => (
              <WhaleCard key={whale.id} whale={whale} index={index} />
            ))}
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}

function WhaleCard({ whale, index }) {
  // Generate chart data from whale stats or use placeholder
  const chartData = whale.chart_data?.map((value) => ({ value })) ||
    [40, 45, 42, 55, 60, 58, 65, 70, 68, 75, 80, 85].map((value) => ({ value }))

  // Map backend fields to frontend expectations
  const weeklyPnl = parseFloat(whale.stats?.profit_7d || whale.pnl_percent_7d || whale.pnl_7d_percent || 0)
  const winRate = parseFloat(whale.stats?.win_rate || whale.win_rate || 0)
  const totalTrades = whale.stats?.total_trades || whale.total_trades_7d || 0
  const isFollowing = whale.is_following || false
  const whaleName = whale.name || whale.whale_name || 'Unknown Whale'

  return (
    <motion.div
      className="glass-card-hover p-4"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 * index }}
    >
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div className="relative">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-biolum-cyan/20 to-biolum-purple/20 flex items-center justify-center text-2xl">
            {whale.avatar || '🐋'}
          </div>
          {isFollowing && (
            <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-profit rounded-full flex items-center justify-center">
              <svg className="w-3 h-3 text-ocean-900" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white truncate">{whaleName}</h3>
          </div>
          <p className="text-xs text-gray-500 font-mono">
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
          <div className={`font-mono font-semibold ${
            weeklyPnl >= 0 ? 'text-profit' : 'text-loss'
          }`}>
            {formatPercent(weeklyPnl)}
          </div>
          <p className="text-xs text-gray-500">{winRate.toFixed(0)}% win</p>
        </div>
      </div>
    </motion.div>
  )
}

export default Dashboard
