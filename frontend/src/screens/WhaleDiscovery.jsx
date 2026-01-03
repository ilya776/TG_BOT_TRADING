import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search,
  Filter,
  TrendingUp,
  TrendingDown,
  Star,
  Users,
  ArrowUpRight,
  Check,
  ChevronDown,
  Wallet,
  X
} from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'

const chains = [
  { id: 'all', name: 'All Chains', icon: '🌐' },
  { id: 'eth', name: 'Ethereum', icon: '⟠' },
  { id: 'bsc', name: 'BSC', icon: '🔶' },
  { id: 'sol', name: 'Solana', icon: '◎' },
  { id: 'arb', name: 'Arbitrum', icon: '🔵' },
]

const sortOptions = [
  { id: 'profit', name: 'Total Profit' },
  { id: 'winrate', name: 'Win Rate' },
  { id: 'weekly', name: '7D Performance' },
  { id: 'followers', name: 'Most Followed' },
]

const mockWhales = [
  {
    id: 1,
    name: 'DeFi Chad',
    address: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
    avatar: '🐋',
    chain: 'eth',
    winRate: 73,
    totalProfit: 2400000,
    totalTrades: 847,
    weeklyPnl: 12.5,
    followers: 2341,
    isFollowing: true,
    isVerified: true,
    tags: ['Memecoin King', 'Early Entry'],
    chartData: [40, 45, 42, 55, 60, 58, 65, 70, 68, 75, 80, 85],
    recentTrades: [
      { token: 'PEPE', profit: 45000, time: '2h ago' },
      { token: 'WIF', profit: 23000, time: '5h ago' },
    ]
  },
  {
    id: 2,
    name: 'Whale Alpha',
    address: '0x89ab78cdef0123456789abcdef0123456789abcd',
    avatar: '🦈',
    chain: 'eth',
    winRate: 68,
    totalProfit: 1800000,
    totalTrades: 523,
    weeklyPnl: 8.3,
    followers: 1876,
    isFollowing: false,
    isVerified: true,
    tags: ['DeFi Expert', 'Low Risk'],
    chartData: [30, 35, 40, 38, 45, 50, 48, 55, 60, 58, 62, 65],
    recentTrades: [
      { token: 'ARB', profit: 12000, time: '1h ago' },
      { token: 'OP', profit: -3500, time: '6h ago' },
    ]
  },
  {
    id: 3,
    name: 'Smart Money',
    address: '0xdef456789abcdef0123456789abcdef01234567',
    avatar: '🐬',
    chain: 'sol',
    winRate: 71,
    totalProfit: 3200000,
    totalTrades: 1203,
    weeklyPnl: 15.2,
    followers: 4521,
    isFollowing: false,
    isVerified: true,
    tags: ['SOL Native', 'High Volume'],
    chartData: [50, 48, 55, 60, 58, 65, 70, 75, 72, 80, 85, 90],
    recentTrades: [
      { token: 'BONK', profit: 67000, time: '30m ago' },
      { token: 'JUP', profit: 34000, time: '3h ago' },
    ]
  },
  {
    id: 4,
    name: 'Degen King',
    address: '0xabc123def456789abc123def456789abc123def4',
    avatar: '👑',
    chain: 'bsc',
    winRate: 62,
    totalProfit: 980000,
    totalTrades: 2156,
    weeklyPnl: -3.2,
    followers: 3245,
    isFollowing: false,
    isVerified: false,
    tags: ['High Risk', 'BSC Degen'],
    chartData: [60, 65, 58, 55, 52, 58, 62, 55, 50, 48, 52, 55],
    recentTrades: [
      { token: 'CAKE', profit: -8000, time: '45m ago' },
      { token: 'BNB', profit: 5600, time: '2h ago' },
    ]
  },
  {
    id: 5,
    name: 'Silent Whale',
    address: '0x999888777666555444333222111000aaabbbccc',
    avatar: '🌊',
    chain: 'arb',
    winRate: 78,
    totalProfit: 1450000,
    totalTrades: 234,
    weeklyPnl: 22.4,
    followers: 987,
    isFollowing: true,
    isVerified: true,
    tags: ['Arbitrum OG', 'Sniper'],
    chartData: [40, 45, 50, 55, 60, 70, 75, 85, 90, 95, 100, 110],
    recentTrades: [
      { token: 'GMX', profit: 89000, time: '15m ago' },
      { token: 'MAGIC', profit: 45000, time: '4h ago' },
    ]
  },
]

function WhaleDiscovery() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedChain, setSelectedChain] = useState('all')
  const [selectedSort, setSelectedSort] = useState('profit')
  const [showFilters, setShowFilters] = useState(false)
  const [selectedWhale, setSelectedWhale] = useState(null)

  const filteredWhales = mockWhales
    .filter(whale => {
      if (selectedChain !== 'all' && whale.chain !== selectedChain) return false
      if (searchQuery && !whale.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
          !whale.address.toLowerCase().includes(searchQuery.toLowerCase())) return false
      return true
    })
    .sort((a, b) => {
      switch (selectedSort) {
        case 'profit': return b.totalProfit - a.totalProfit
        case 'winrate': return b.winRate - a.winRate
        case 'weekly': return b.weeklyPnl - a.weeklyPnl
        case 'followers': return b.followers - a.followers
        default: return 0
      }
    })

  return (
    <div className="px-4 pt-6 pb-4">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-5"
      >
        <h1 className="font-display text-2xl font-bold text-white flex items-center gap-2">
          <span className="text-2xl">🐋</span>
          Discover Whales
        </h1>
        <p className="text-gray-400 text-sm mt-1">Find the best traders to copy</p>
      </motion.div>

      {/* Search Bar */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-4"
      >
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" size={18} />
          <input
            type="text"
            placeholder="Search by name or address..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input-field pl-11 pr-12"
          />
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg transition-colors ${
              showFilters ? 'bg-biolum-cyan/20 text-biolum-cyan' : 'text-gray-500 hover:text-white'
            }`}
          >
            <Filter size={18} />
          </button>
        </div>
      </motion.div>

      {/* Chain Filters */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
        className="flex gap-2 overflow-x-auto pb-3 mb-4 hide-scrollbar"
      >
        {chains.map((chain) => (
          <button
            key={chain.id}
            onClick={() => setSelectedChain(chain.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl whitespace-nowrap transition-all ${
              selectedChain === chain.id
                ? 'bg-gradient-to-r from-biolum-cyan/20 to-biolum-blue/20 border border-biolum-cyan/30 text-white'
                : 'bg-ocean-700/50 border border-transparent text-gray-400 hover:text-white'
            }`}
          >
            <span>{chain.icon}</span>
            <span className="text-sm font-medium">{chain.name}</span>
          </button>
        ))}
      </motion.div>

      {/* Sort Options */}
      <AnimatePresence>
        {showFilters && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-4 overflow-hidden"
          >
            <div className="glass-card p-4">
              <p className="text-sm text-gray-400 mb-3">Sort by</p>
              <div className="flex flex-wrap gap-2">
                {sortOptions.map((option) => (
                  <button
                    key={option.id}
                    onClick={() => setSelectedSort(option.id)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                      selectedSort === option.id
                        ? 'bg-biolum-cyan/20 text-biolum-cyan border border-biolum-cyan/30'
                        : 'bg-ocean-700/50 text-gray-400 hover:text-white'
                    }`}
                  >
                    {option.name}
                  </button>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results Count */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="flex items-center justify-between mb-3"
      >
        <p className="text-sm text-gray-400">
          {filteredWhales.length} whale{filteredWhales.length !== 1 ? 's' : ''} found
        </p>
      </motion.div>

      {/* Whale List */}
      <div className="space-y-3">
        {filteredWhales.map((whale, index) => (
          <WhaleDiscoveryCard
            key={whale.id}
            whale={whale}
            index={index}
            onClick={() => setSelectedWhale(whale)}
          />
        ))}
      </div>

      {/* Whale Detail Modal */}
      <AnimatePresence>
        {selectedWhale && (
          <WhaleDetailModal
            whale={selectedWhale}
            onClose={() => setSelectedWhale(null)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function WhaleDiscoveryCard({ whale, index, onClick }) {
  const [isFollowing, setIsFollowing] = useState(whale.isFollowing)
  const chartData = whale.chartData.map((value) => ({ value }))
  const chainInfo = chains.find(c => c.id === whale.chain)

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 * index }}
      className="glass-card-hover p-4"
      onClick={onClick}
    >
      {/* Top Row */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          {/* Avatar */}
          <div className="relative">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-biolum-cyan/20 to-biolum-purple/20 flex items-center justify-center text-3xl">
              {whale.avatar}
            </div>
            {whale.isVerified && (
              <div className="absolute -top-1 -right-1 w-5 h-5 bg-biolum-blue rounded-full flex items-center justify-center">
                <Check size={12} className="text-white" />
              </div>
            )}
          </div>

          {/* Info */}
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-white">{whale.name}</h3>
              <span className="text-xs px-1.5 py-0.5 rounded bg-ocean-600/50 text-gray-400">
                {chainInfo?.icon}
              </span>
            </div>
            <p className="text-xs text-gray-500 font-mono">
              {whale.address.slice(0, 6)}...{whale.address.slice(-4)}
            </p>
            <div className="flex gap-1 mt-1">
              {whale.tags.slice(0, 2).map((tag) => (
                <span
                  key={tag}
                  className="text-[10px] px-1.5 py-0.5 rounded-full bg-biolum-purple/10 text-biolum-purple"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Follow Button */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            setIsFollowing(!isFollowing)
          }}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            isFollowing
              ? 'bg-profit/20 text-profit border border-profit/30'
              : 'bg-biolum-cyan/20 text-biolum-cyan border border-biolum-cyan/30'
          }`}
        >
          {isFollowing ? 'Following' : 'Follow'}
        </button>
      </div>

      {/* Stats Row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wide">Win Rate</p>
            <p className="font-mono font-semibold text-profit">{whale.winRate}%</p>
          </div>
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wide">Total Profit</p>
            <p className="font-mono font-semibold text-white">
              ${(whale.totalProfit / 1000000).toFixed(1)}M
            </p>
          </div>
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wide">Followers</p>
            <p className="font-mono font-semibold text-gray-300">
              {whale.followers.toLocaleString()}
            </p>
          </div>
        </div>

        {/* Mini Chart + Weekly PnL */}
        <div className="flex items-center gap-3">
          <div className="w-16 h-10">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id={`discovery-gradient-${whale.id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={whale.weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={whale.weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke={whale.weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'}
                  strokeWidth={1.5}
                  fill={`url(#discovery-gradient-${whale.id})`}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-gray-500">7D</p>
            <p className={`font-mono font-semibold ${
              whale.weeklyPnl >= 0 ? 'text-profit' : 'text-loss'
            }`}>
              {whale.weeklyPnl >= 0 ? '+' : ''}{whale.weeklyPnl}%
            </p>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

function WhaleDetailModal({ whale, onClose }) {
  const [isFollowing, setIsFollowing] = useState(whale.isFollowing)
  const [copySettings, setCopySettings] = useState({
    tradeSize: 100,
    autoCopy: true,
    maxLoss: 10,
  })

  const chartData = whale.chartData.map((value) => ({ value }))

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
        className="relative w-full max-h-[85vh] overflow-y-auto rounded-t-3xl"
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
            <div className="relative">
              <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-biolum-cyan/20 to-biolum-purple/20 flex items-center justify-center text-5xl">
                {whale.avatar}
              </div>
              {whale.isVerified && (
                <div className="absolute -bottom-1 -right-1 w-7 h-7 bg-biolum-blue rounded-full flex items-center justify-center">
                  <Check size={16} className="text-white" />
                </div>
              )}
            </div>

            <div className="flex-1">
              <h2 className="font-display text-2xl font-bold text-white">{whale.name}</h2>
              <p className="text-sm text-gray-500 font-mono flex items-center gap-2">
                <Wallet size={14} />
                {whale.address.slice(0, 10)}...{whale.address.slice(-6)}
              </p>
              <div className="flex gap-2 mt-2">
                {whale.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs px-2 py-1 rounded-full bg-biolum-purple/10 text-biolum-purple"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Performance Chart */}
          <div className="glass-card p-4 mb-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm text-gray-400">7 Day Performance</p>
              <p className={`font-mono font-bold ${
                whale.weeklyPnl >= 0 ? 'text-profit' : 'text-loss'
              }`}>
                {whale.weeklyPnl >= 0 ? '+' : ''}{whale.weeklyPnl}%
              </p>
            </div>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="modal-gradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={whale.weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0.4} />
                      <stop offset="100%" stopColor={whale.weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={whale.weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'}
                    strokeWidth={2}
                    fill="url(#modal-gradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="glass-card p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Win Rate</p>
              <p className="font-display text-2xl font-bold text-profit">{whale.winRate}%</p>
            </div>
            <div className="glass-card p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Total Profit</p>
              <p className="font-display text-2xl font-bold text-white">
                ${(whale.totalProfit / 1000000).toFixed(2)}M
              </p>
            </div>
            <div className="glass-card p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Total Trades</p>
              <p className="font-display text-2xl font-bold text-gray-300">
                {whale.totalTrades.toLocaleString()}
              </p>
            </div>
            <div className="glass-card p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Followers</p>
              <p className="font-display text-2xl font-bold text-biolum-blue">
                {whale.followers.toLocaleString()}
              </p>
            </div>
          </div>

          {/* Recent Trades */}
          <div className="glass-card p-4 mb-6">
            <p className="text-sm text-gray-400 mb-3">Recent Trades</p>
            <div className="space-y-2">
              {whale.recentTrades.map((trade, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between py-2 border-b border-ocean-600/50 last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-ocean-600 flex items-center justify-center font-mono text-xs font-bold">
                      {trade.token.slice(0, 2)}
                    </div>
                    <div>
                      <p className="font-semibold text-white">{trade.token}</p>
                      <p className="text-xs text-gray-500">{trade.time}</p>
                    </div>
                  </div>
                  <p className={`font-mono font-semibold ${
                    trade.profit >= 0 ? 'text-profit' : 'text-loss'
                  }`}>
                    {trade.profit >= 0 ? '+' : ''}${Math.abs(trade.profit).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Copy Settings */}
          {isFollowing && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-4 mb-4"
            >
              <p className="text-sm text-gray-400 mb-4">Copy Settings</p>

              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm text-white">Trade Size</label>
                    <span className="font-mono text-biolum-cyan">${copySettings.tradeSize}</span>
                  </div>
                  <input
                    type="range"
                    min="10"
                    max="1000"
                    step="10"
                    value={copySettings.tradeSize}
                    onChange={(e) => setCopySettings({ ...copySettings, tradeSize: Number(e.target.value) })}
                    className="w-full accent-biolum-cyan"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-sm text-white">Auto-Copy</label>
                  <button
                    onClick={() => setCopySettings({ ...copySettings, autoCopy: !copySettings.autoCopy })}
                    className={`w-12 h-6 rounded-full transition-colors ${
                      copySettings.autoCopy ? 'bg-biolum-cyan' : 'bg-ocean-600'
                    }`}
                  >
                    <div
                      className={`w-5 h-5 rounded-full bg-white transition-transform ${
                        copySettings.autoCopy ? 'translate-x-6' : 'translate-x-0.5'
                      }`}
                    />
                  </button>
                </div>
              </div>
            </motion.div>
          )}

          {/* Action Button */}
          <button
            onClick={() => setIsFollowing(!isFollowing)}
            className={`w-full py-4 rounded-2xl font-semibold text-lg transition-all ${
              isFollowing
                ? 'bg-ocean-600 text-white border border-ocean-500'
                : 'btn-primary'
            }`}
          >
            {isFollowing ? 'Stop Following' : 'Start Copying'}
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

export default WhaleDiscovery
