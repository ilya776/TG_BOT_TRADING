import React, { useState, useEffect } from 'react'
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
  Sparkles
} from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'

// Mock data
const mockPositions = [
  {
    id: 1,
    symbol: 'PEPE',
    name: 'Pepe',
    side: 'LONG',
    entry: 0.00001234,
    current: 0.00001456,
    size: 150,
    pnl: 27.35,
    pnlPercent: 18.23,
    whale: 'DeFi Chad',
  },
  {
    id: 2,
    symbol: 'ARB',
    name: 'Arbitrum',
    side: 'LONG',
    entry: 1.24,
    current: 1.18,
    size: 200,
    pnl: -9.68,
    pnlPercent: -4.84,
    whale: 'Whale Alpha',
  },
  {
    id: 3,
    symbol: 'SOL',
    name: 'Solana',
    side: 'LONG',
    entry: 98.50,
    current: 105.20,
    size: 300,
    pnl: 20.41,
    pnlPercent: 6.80,
    whale: 'Smart Money',
  },
]

const mockWhales = [
  {
    id: 1,
    name: 'DeFi Chad',
    address: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
    avatar: '🐋',
    winRate: 73,
    totalProfit: 2400000,
    weeklyPnl: 12.5,
    isFollowing: true,
    chartData: [40, 45, 42, 55, 60, 58, 65, 70, 68, 75, 80, 85],
  },
  {
    id: 2,
    name: 'Whale Alpha',
    address: '0x89ab78cdef0123456789abcdef0123456789abcd',
    avatar: '🦈',
    winRate: 68,
    totalProfit: 1800000,
    weeklyPnl: 8.3,
    isFollowing: true,
    chartData: [30, 35, 40, 38, 45, 50, 48, 55, 60, 58, 62, 65],
  },
  {
    id: 3,
    name: 'Smart Money',
    address: '0xdef456789abcdef0123456789abcdef01234567',
    avatar: '🐬',
    winRate: 71,
    totalProfit: 3200000,
    weeklyPnl: 15.2,
    isFollowing: false,
    chartData: [50, 48, 55, 60, 58, 65, 70, 75, 72, 80, 85, 90],
  },
]

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
  const [balance, setBalance] = useState(12847.53)
  const [todayPnl, setTodayPnl] = useState(387.24)
  const [todayPnlPercent, setTodayPnlPercent] = useState(3.11)

  const stats = [
    { label: 'Total Trades', value: '247', icon: Activity, color: 'text-biolum-blue' },
    { label: 'Win Rate', value: '68%', icon: TrendingUp, color: 'text-profit' },
    { label: 'Active Whales', value: '5', icon: Users, color: 'text-biolum-purple' },
    { label: 'This Month', value: '+$2.4K', icon: Sparkles, color: 'text-biolum-cyan' },
  ]

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
              ${balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
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
                {todayPnl >= 0 ? '+' : ''}${Math.abs(todayPnl).toFixed(2)}
              </span>
              <span className={`font-mono text-sm ${
                todayPnl >= 0 ? 'text-profit/70' : 'text-loss/70'
              }`}>
                ({todayPnl >= 0 ? '+' : ''}{todayPnlPercent.toFixed(2)}%)
              </span>
            </div>
            <span className="text-gray-500 text-xs">Today</span>
          </div>
        </div>
      </motion.div>

      {/* Quick Stats Grid */}
      <motion.div variants={itemVariants} className="grid grid-cols-2 gap-3 mb-5">
        {stats.map((stat, index) => {
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

        <div className="space-y-3">
          {mockPositions.map((position, index) => (
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
                    {position.symbol.slice(0, 2)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white">{position.symbol}</span>
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        position.side === 'LONG' ? 'bg-profit/20 text-profit' : 'bg-loss/20 text-loss'
                      }`}>
                        {position.side}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500">via {position.whale}</p>
                  </div>
                </div>

                <div className="text-right">
                  <div className={`flex items-center justify-end gap-1 ${
                    position.pnl >= 0 ? 'text-profit' : 'text-loss'
                  }`}>
                    {position.pnl >= 0 ? (
                      <TrendingUp size={14} />
                    ) : (
                      <TrendingDown size={14} />
                    )}
                    <span className="font-mono font-semibold">
                      {position.pnl >= 0 ? '+' : ''}{position.pnlPercent.toFixed(2)}%
                    </span>
                  </div>
                  <p className={`text-xs font-mono ${
                    position.pnl >= 0 ? 'text-profit/70' : 'text-loss/70'
                  }`}>
                    {position.pnl >= 0 ? '+' : ''}${position.pnl.toFixed(2)}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
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

        <div className="space-y-3">
          {mockWhales.map((whale, index) => (
            <WhaleCard key={whale.id} whale={whale} index={index} />
          ))}
        </div>
      </motion.div>
    </motion.div>
  )
}

function WhaleCard({ whale, index }) {
  const chartData = whale.chartData.map((value, i) => ({ value }))

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
            {whale.avatar}
          </div>
          {whale.isFollowing && (
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
            <h3 className="font-semibold text-white truncate">{whale.name}</h3>
          </div>
          <p className="text-xs text-gray-500 font-mono">
            {whale.address.slice(0, 6)}...{whale.address.slice(-4)}
          </p>
        </div>

        {/* Mini Chart */}
        <div className="w-16 h-8">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id={`gradient-${whale.id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={whale.weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={whale.weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="value"
                stroke={whale.weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'}
                strokeWidth={1.5}
                fill={`url(#gradient-${whale.id})`}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Stats */}
        <div className="text-right">
          <div className={`font-mono font-semibold ${
            whale.weeklyPnl >= 0 ? 'text-profit' : 'text-loss'
          }`}>
            {whale.weeklyPnl >= 0 ? '+' : ''}{whale.weeklyPnl}%
          </div>
          <p className="text-xs text-gray-500">{whale.winRate}% win</p>
        </div>
      </div>
    </motion.div>
  )
}

export default Dashboard
