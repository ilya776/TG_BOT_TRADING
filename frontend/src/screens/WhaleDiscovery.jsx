import React, { useState, useCallback } from 'react'
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
  X,
  Loader2
} from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'
import { useWhales, useFollowingWhales } from '../hooks/useApi'
import { formatCurrency, formatLargeNumber, shortenAddress } from '../services/api'

const chains = [
  { id: 'all', name: 'All Chains', icon: '🌐' },
  { id: 'ETHEREUM', name: 'Ethereum', icon: '⟠' },
  { id: 'BSC', name: 'BSC', icon: '🔶' },
]

const sortOptions = [
  { id: 'score', name: 'Score' },
  { id: 'win_rate', name: 'Win Rate' },
  { id: 'pnl_7d', name: '7D Performance' },
  { id: 'followers', name: 'Most Followed' },
]

function WhaleDiscovery() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedChain, setSelectedChain] = useState('all')
  const [selectedSort, setSelectedSort] = useState('score')
  const [showFilters, setShowFilters] = useState(false)
  const [selectedWhale, setSelectedWhale] = useState(null)

  const { whales, loading, error, refetch } = useWhales({
    chain: selectedChain !== 'all' ? selectedChain : undefined,
    sortBy: selectedSort,
    search: searchQuery || undefined,
  })

  const { whales: followingWhales, followWhale, unfollowWhale, updateFollow } = useFollowingWhales()
  const followedIds = new Set(followingWhales.map(w => w.whale_id))

  const filteredWhales = whales.map(whale => ({
    ...whale,
    isFollowing: followedIds.has(whale.id)
  }))

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

      {/* Error State */}
      {error && (
        <div className="glass-card p-4 mb-4 text-center">
          <p className="text-loss">{error}</p>
          <button onClick={refetch} className="text-biolum-cyan text-sm mt-2">Try again</button>
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredWhales.length === 0 && (
        <div className="glass-card p-8 text-center">
          <p className="text-2xl mb-2">🐋</p>
          <p className="text-gray-400">No whales found</p>
          <p className="text-gray-500 text-sm mt-1">Try adjusting your filters</p>
        </div>
      )}

      {/* Whale List */}
      <div className="space-y-3">
        {filteredWhales.map((whale, index) => (
          <WhaleDiscoveryCard
            key={whale.id}
            whale={whale}
            index={index}
            onClick={() => setSelectedWhale(whale)}
            onFollow={() => followWhale(whale.id)}
            onUnfollow={() => unfollowWhale(whale.id)}
          />
        ))}
      </div>

      {/* Whale Detail Modal */}
      <AnimatePresence>
        {selectedWhale && (
          <WhaleDetailModal
            whale={selectedWhale}
            onClose={() => setSelectedWhale(null)}
            onFollow={() => followWhale(selectedWhale.id)}
            onUnfollow={() => unfollowWhale(selectedWhale.id)}
            onUpdateFollow={(settings) => updateFollow(selectedWhale.id, settings)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function WhaleDiscoveryCard({ whale, index, onClick, onFollow, onUnfollow }) {
  const [isFollowing, setIsFollowing] = useState(whale.isFollowing)
  const chartData = whale.chart_data?.map((value) => ({ value })) ||
    [40, 45, 42, 55, 60, 58, 65, 70, 68, 75, 80, 85].map(v => ({ value: v }))

  // Map backend fields - API returns strings, convert to numbers safely
  // Use avg_profit_percent for ROI percentage (profit_7d is USD value)
  const weeklyPnlRaw = Number(whale.stats?.avg_profit_percent)
  const weeklyPnl = isNaN(weeklyPnlRaw) ? 0 : weeklyPnlRaw
  const winRateRaw = Number(whale.stats?.win_rate)
  const winRate = isNaN(winRateRaw) ? 0 : winRateRaw
  const totalProfit = Number(whale.stats?.total_profit_usd) || Number(whale.stats?.avg_profit_percent) * 100 || 0
  const followers = whale.followers_count || 0

  // Parse tags - backend returns null or string "tag1,tag2"
  const tags = whale.tags && typeof whale.tags === 'string'
    ? whale.tags.split(',').map(t => t.trim()).filter(Boolean)
    : []

  const handleFollowClick = async (e) => {
    e.stopPropagation()
    const previousState = isFollowing
    // Optimistic update
    setIsFollowing(!isFollowing)
    try {
      if (previousState) {
        await onUnfollow()
      } else {
        await onFollow()
      }
    } catch (err) {
      // Rollback on error
      setIsFollowing(previousState)
      console.error('Follow error:', err)
    }
  }

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
              🐋
            </div>
            {whale.is_verified && (
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
                {whale.chain === 'ETHEREUM' ? '⟠' : '🔶'}
              </span>
            </div>
            <p className="text-xs text-gray-500 font-mono">
              {shortenAddress(whale.wallet_address)}
            </p>
            {tags.length > 0 && (
              <div className="flex gap-1 mt-1">
                {tags.slice(0, 2).map((tag) => (
                  <span
                    key={tag}
                    className="text-[10px] px-1.5 py-0.5 rounded-full bg-biolum-purple/10 text-biolum-purple"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Follow Button */}
        <button
          onClick={handleFollowClick}
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
            <p className="font-mono font-semibold text-profit">{winRate.toFixed(1)}%</p>
          </div>
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wide">Total Profit</p>
            <p className="font-mono font-semibold text-white">
              {formatLargeNumber(totalProfit)}
            </p>
          </div>
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wide">Followers</p>
            <p className="font-mono font-semibold text-gray-300">
              {followers.toLocaleString()}
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
                    <stop offset="0%" stopColor={weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke={weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'}
                  strokeWidth={1.5}
                  fill={`url(#discovery-gradient-${whale.id})`}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-gray-500">7D</p>
            <p className={`font-mono font-semibold ${
              weeklyPnl >= 0 ? 'text-profit' : 'text-loss'
            }`}>
              {weeklyPnl >= 0 ? '+' : ''}{weeklyPnl.toFixed(1)}%
            </p>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

function WhaleDetailModal({ whale, onClose, onFollow, onUnfollow, onUpdateFollow }) {
  const [isFollowing, setIsFollowing] = useState(whale.isFollowing)
  const [copySettings, setCopySettings] = useState({
    tradeSize: 100,
    autoCopy: false,
    maxLoss: 10,
  })
  const [isLoading, setIsLoading] = useState(false)

  const chartData = whale.chart_data?.map((value) => ({ value })) ||
    [40, 45, 42, 55, 60, 58, 65, 70, 68, 75, 80, 85].map(v => ({ value: v }))

  // Map backend fields - API returns strings, convert to numbers safely
  // Use avg_profit_percent for ROI percentage (profit_7d is USD value)
  const weeklyPnlRaw = Number(whale.stats?.avg_profit_percent)
  const weeklyPnl = isNaN(weeklyPnlRaw) ? 0 : weeklyPnlRaw
  const winRateRaw = Number(whale.stats?.win_rate)
  const winRate = isNaN(winRateRaw) ? 0 : winRateRaw
  const totalProfit = Number(whale.stats?.total_profit_usd) || Number(whale.stats?.avg_profit_percent) * 100 || 0
  const totalTrades = whale.stats?.total_trades || 0
  const followers = whale.followers_count || 0

  // Parse tags - backend returns null or string "tag1,tag2"
  const tags = whale.tags && typeof whale.tags === 'string'
    ? whale.tags.split(',').map(t => t.trim()).filter(Boolean)
    : []

  const handleAction = async () => {
    setIsLoading(true)
    const previousState = isFollowing
    // Optimistic update
    setIsFollowing(!isFollowing)
    try {
      if (previousState) {
        await onUnfollow()
      } else {
        await onFollow()
      }
    } catch (err) {
      // Rollback on error
      setIsFollowing(previousState)
      console.error('Action error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSettingsChange = async (key, value) => {
    const previousSettings = { ...copySettings }
    const newSettings = { ...copySettings, [key]: value }
    setCopySettings(newSettings)
    if (isFollowing) {
      try {
        await onUpdateFollow({
          auto_copy_enabled: newSettings.autoCopy,
          trade_size_usdt: newSettings.tradeSize,
        })
      } catch (err) {
        // Rollback on error
        setCopySettings(previousSettings)
        console.error('Update settings error:', err)
      }
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
                🐋
              </div>
              {whale.is_verified && (
                <div className="absolute -bottom-1 -right-1 w-7 h-7 bg-biolum-blue rounded-full flex items-center justify-center">
                  <Check size={16} className="text-white" />
                </div>
              )}
            </div>

            <div className="flex-1">
              <h2 className="font-display text-2xl font-bold text-white">{whale.name}</h2>
              <p className="text-sm text-gray-500 font-mono flex items-center gap-2">
                <Wallet size={14} />
                {shortenAddress(whale.wallet_address)}
              </p>
              {tags.length > 0 && (
                <div className="flex gap-2 mt-2">
                  {tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-xs px-2 py-1 rounded-full bg-biolum-purple/10 text-biolum-purple"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Performance Chart */}
          <div className="glass-card p-4 mb-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm text-gray-400">7 Day Performance</p>
              <p className={`font-mono font-bold ${
                weeklyPnl >= 0 ? 'text-profit' : 'text-loss'
              }`}>
                {weeklyPnl >= 0 ? '+' : ''}{weeklyPnl.toFixed(1)}%
              </p>
            </div>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="modal-gradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0.4} />
                      <stop offset="100%" stopColor={weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={weeklyPnl >= 0 ? '#00ffc8' : '#ff5f6d'}
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
              <p className="font-display text-2xl font-bold text-profit">{winRate.toFixed(1)}%</p>
            </div>
            <div className="glass-card p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Total Profit</p>
              <p className="font-display text-2xl font-bold text-white">
                {formatLargeNumber(totalProfit)}
              </p>
            </div>
            <div className="glass-card p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Total Trades</p>
              <p className="font-display text-2xl font-bold text-gray-300">
                {totalTrades.toLocaleString()}
              </p>
            </div>
            <div className="glass-card p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Followers</p>
              <p className="font-display text-2xl font-bold text-biolum-blue">
                {followers.toLocaleString()}
              </p>
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
                    onChange={(e) => handleSettingsChange('tradeSize', Number(e.target.value))}
                    className="w-full accent-biolum-cyan"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-sm text-white">Auto-Copy</label>
                  <button
                    onClick={() => handleSettingsChange('autoCopy', !copySettings.autoCopy)}
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
            onClick={handleAction}
            disabled={isLoading}
            className={`w-full py-4 rounded-2xl font-semibold text-lg transition-all ${
              isFollowing
                ? 'bg-ocean-600 text-white border border-ocean-500'
                : 'btn-primary'
            }`}
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin mx-auto" />
            ) : isFollowing ? (
              'Stop Following'
            ) : (
              'Start Copying'
            )}
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

export default WhaleDiscovery
