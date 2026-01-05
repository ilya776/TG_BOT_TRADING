/**
 * Trade Modal Components
 * Sell Position, Convert to USDT, Quick Trade actions
 */

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Loader2,
  AlertTriangle,
  Check,
  RefreshCw,
  DollarSign,
  Percent
} from 'lucide-react'
import { formatCurrency } from '../services/api'

// Backdrop animation
const backdropVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
}

// Modal slide-up animation
const modalVariants = {
  hidden: { y: '100%', opacity: 0.5 },
  visible: {
    y: 0,
    opacity: 1,
    transition: {
      type: 'spring',
      damping: 30,
      stiffness: 400,
    }
  },
  exit: {
    y: '100%',
    opacity: 0,
    transition: { duration: 0.2 }
  }
}

// ================== SELL POSITION MODAL ==================
export function SellPositionModal({ isOpen, onClose, position, onSell }) {
  const [sellPercent, setSellPercent] = useState(100)
  const [closeMode, setCloseMode] = useState('close') // 'close' or 'convert'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Calculate values - handle both quantity and size_usdt formats
  const currentPrice = Number(position?.current_price || position?.mark_price || 0)
  const sizeUsdt = Number(position?.size_usdt || position?.entry_value_usdt || position?.notional || 0)
  const quantity = Number(position?.quantity) || (currentPrice > 0 ? sizeUsdt / currentPrice : 0)

  const sellAmount = quantity * sellPercent / 100
  const sellValue = sizeUsdt * sellPercent / 100

  const handleSell = async () => {
    setLoading(true)
    setError(null)

    try {
      // Pass both position, percent, and whether to convert to USDT
      await onSell(position, sellPercent, closeMode === 'convert')
      onClose()
    } catch (err) {
      setError(err.message || 'Failed to close position')
    } finally {
      setLoading(false)
    }
  }

  if (!position) return null

  const pnl = Number(position.unrealized_pnl || position.pnl || 0)
  const pnlPercent = Number(position.unrealized_pnl_percent || position.pnl_percent || 0)
  const isProfit = pnl >= 0
  // Calculate pnlPercent if not provided but we have pnl and size_usdt
  const calculatedPnlPercent = pnlPercent || (sizeUsdt > 0 ? (pnl / sizeUsdt) * 100 : 0)

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center"
          initial="hidden"
          animate="visible"
          exit="hidden"
        >
          <motion.div
            variants={backdropVariants}
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={onClose}
          />

          <motion.div
            variants={modalVariants}
            className="relative w-full max-w-lg bg-gradient-to-b from-ocean-800 to-ocean-900 rounded-t-3xl overflow-hidden"
          >
            {/* Glow effect */}
            <div className={`absolute top-0 left-1/2 -translate-x-1/2 w-64 h-32 rounded-full blur-3xl opacity-30 ${
              isProfit ? 'bg-profit' : 'bg-loss'
            }`} />

            {/* Handle */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-12 h-1.5 rounded-full bg-gray-600" />
            </div>

            {/* Close button */}
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-2 rounded-full bg-ocean-700/80 text-gray-400 hover:text-white hover:bg-ocean-600 transition-all"
            >
              <X size={20} />
            </button>

            <div className="px-6 pb-8 pt-2 relative">
              {/* Header */}
              <div className="text-center mb-6">
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-ocean-700/50 border border-ocean-600/50 mb-4">
                  <span className="font-display font-bold text-xl text-white">
                    {position.symbol}
                  </span>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                    position.side === 'BUY' ? 'bg-profit/20 text-profit' : 'bg-loss/20 text-loss'
                  }`}>
                    {position.side === 'BUY' ? 'LONG' : 'SHORT'}
                  </span>
                </div>

                <h2 className="font-display text-2xl font-bold text-white mb-1">
                  Close Position
                </h2>
                <p className="text-gray-400 text-sm">
                  Select how much to sell
                </p>
              </div>

              {/* Current PnL */}
              <div className={`rounded-2xl p-5 mb-6 border ${
                isProfit
                  ? 'bg-profit/5 border-profit/20'
                  : 'bg-loss/5 border-loss/20'
              }`}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm mb-1">Current P&L</p>
                    <div className="flex items-center gap-2">
                      {isProfit ? (
                        <TrendingUp className="text-profit" size={24} />
                      ) : (
                        <TrendingDown className="text-loss" size={24} />
                      )}
                      <span className={`font-display text-3xl font-bold ${
                        isProfit ? 'text-profit' : 'text-loss'
                      }`}>
                        {isProfit ? '+' : ''}{formatCurrency(pnl)}
                      </span>
                    </div>
                  </div>
                  <div className={`text-right px-4 py-2 rounded-xl ${
                    isProfit ? 'bg-profit/10' : 'bg-loss/10'
                  }`}>
                    <span className={`font-mono text-xl font-bold ${
                      isProfit ? 'text-profit' : 'text-loss'
                    }`}>
                      {isProfit ? '+' : ''}{Number(calculatedPnlPercent || 0).toFixed(2)}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Sell Percentage Slider */}
              <div className="mb-6">
                <div className="flex justify-between items-center mb-3">
                  <span className="text-gray-400">Sell Amount</span>
                  <span className="font-mono font-bold text-biolum-cyan text-lg">
                    {sellPercent}%
                  </span>
                </div>

                {/* Quick Select Buttons */}
                <div className="grid grid-cols-4 gap-2 mb-4">
                  {[25, 50, 75, 100].map((pct) => (
                    <button
                      key={pct}
                      onClick={() => setSellPercent(pct)}
                      className={`py-2.5 rounded-xl font-semibold text-sm transition-all ${
                        sellPercent === pct
                          ? 'bg-biolum-cyan text-ocean-900 shadow-glow-sm'
                          : 'bg-ocean-700/50 text-gray-300 hover:bg-ocean-600/50'
                      }`}
                    >
                      {pct}%
                    </button>
                  ))}
                </div>

                {/* Slider */}
                <input
                  type="range"
                  min="1"
                  max="100"
                  value={sellPercent}
                  onChange={(e) => setSellPercent(Number(e.target.value))}
                  className="w-full h-2 rounded-full appearance-none cursor-pointer accent-biolum-cyan"
                  style={{
                    background: `linear-gradient(to right, #00ffc8 0%, #00ffc8 ${sellPercent}%, #1c2640 ${sellPercent}%, #1c2640 100%)`
                  }}
                />
              </div>

              {/* Close Mode Selection */}
              <div className="mb-6">
                <p className="text-gray-400 text-sm mb-3">Close Option</p>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => setCloseMode('close')}
                    className={`p-4 rounded-xl border-2 transition-all text-left ${
                      closeMode === 'close'
                        ? 'border-biolum-cyan bg-biolum-cyan/10'
                        : 'border-ocean-600 bg-ocean-700/30 hover:border-ocean-500'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                        closeMode === 'close' ? 'border-biolum-cyan bg-biolum-cyan' : 'border-gray-500'
                      }`}>
                        {closeMode === 'close' && <Check size={10} className="text-ocean-900" />}
                      </div>
                      <span className={`font-semibold ${closeMode === 'close' ? 'text-white' : 'text-gray-400'}`}>
                        Close Only
                      </span>
                    </div>
                    <p className="text-xs text-gray-500">Keep received asset in wallet</p>
                  </button>
                  <button
                    onClick={() => setCloseMode('convert')}
                    className={`p-4 rounded-xl border-2 transition-all text-left ${
                      closeMode === 'convert'
                        ? 'border-profit bg-profit/10'
                        : 'border-ocean-600 bg-ocean-700/30 hover:border-ocean-500'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                        closeMode === 'convert' ? 'border-profit bg-profit' : 'border-gray-500'
                      }`}>
                        {closeMode === 'convert' && <Check size={10} className="text-ocean-900" />}
                      </div>
                      <span className={`font-semibold ${closeMode === 'convert' ? 'text-white' : 'text-gray-400'}`}>
                        Close + USDT
                      </span>
                    </div>
                    <p className="text-xs text-gray-500">Convert to USDT after close</p>
                  </button>
                </div>
              </div>

              {/* Sell Summary */}
              <div className="glass-card p-4 mb-6">
                <div className="flex justify-between items-center py-2 border-b border-ocean-600/30">
                  <span className="text-gray-400">Quantity</span>
                  <span className="font-mono text-white">
                    {Number(sellAmount || 0).toFixed(6)} {position.symbol?.replace('USDT', '')}
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-ocean-600/30">
                  <span className="text-gray-400">Est. Value</span>
                  <span className="font-mono font-semibold text-white">
                    {formatCurrency(sellValue)}
                  </span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-ocean-600/30">
                  <span className="text-gray-400">Est. P&L</span>
                  <span className={`font-mono font-bold ${isProfit ? 'text-profit' : 'text-loss'}`}>
                    {isProfit ? '+' : ''}{formatCurrency(pnl * sellPercent / 100)}
                  </span>
                </div>
                <div className="flex justify-between items-center py-2">
                  <span className="text-gray-400">You Receive</span>
                  <span className="font-mono font-bold text-biolum-cyan">
                    {closeMode === 'convert' ? '~USDT' : position.symbol?.replace('USDT', '')}
                  </span>
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="mb-4 p-3 rounded-xl bg-loss/10 border border-loss/20 flex items-center gap-2">
                  <AlertTriangle size={18} className="text-loss" />
                  <span className="text-loss text-sm">{error}</span>
                </div>
              )}

              {/* Action Button */}
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleSell}
                disabled={loading}
                className={`w-full py-4 rounded-2xl font-bold text-lg flex items-center justify-center gap-2 transition-all ${
                  closeMode === 'convert'
                    ? 'bg-gradient-to-r from-profit to-emerald-400 text-ocean-900 shadow-[0_0_30px_rgba(0,255,200,0.4)]'
                    : isProfit
                      ? 'bg-gradient-to-r from-biolum-cyan to-biolum-blue text-ocean-900 shadow-[0_0_30px_rgba(0,168,255,0.4)]'
                      : 'bg-gradient-to-r from-loss to-red-400 text-white shadow-[0_0_30px_rgba(255,95,109,0.4)]'
                } disabled:opacity-50`}
              >
                {loading ? (
                  <Loader2 size={22} className="animate-spin" />
                ) : (
                  <>
                    {closeMode === 'convert' ? <RefreshCw size={22} /> : <DollarSign size={22} />}
                    {closeMode === 'convert'
                      ? `Close & Convert to USDT`
                      : `Close ${sellPercent}%`}
                  </>
                )}
              </motion.button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// ================== CONVERT TO USDT MODAL ==================
export function ConvertToUsdtModal({ isOpen, onClose, asset, onConvert }) {
  const [convertPercent, setConvertPercent] = useState(100)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const convertAmount = asset ? (parseFloat(asset.quantity) * convertPercent / 100) : 0
  const convertValue = asset ? (parseFloat(asset.value_usdt) * convertPercent / 100) : 0

  const handleConvert = async () => {
    setLoading(true)
    setError(null)

    try {
      await onConvert(asset.symbol, convertPercent)
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!asset) return null

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center"
          initial="hidden"
          animate="visible"
          exit="hidden"
        >
          <motion.div
            variants={backdropVariants}
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={onClose}
          />

          <motion.div
            variants={modalVariants}
            className="relative w-full max-w-lg bg-gradient-to-b from-ocean-800 to-ocean-900 rounded-t-3xl overflow-hidden"
          >
            {/* Glow effect */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-64 h-32 rounded-full blur-3xl opacity-30 bg-biolum-cyan" />

            {/* Handle */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-12 h-1.5 rounded-full bg-gray-600" />
            </div>

            {/* Close button */}
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-2 rounded-full bg-ocean-700/80 text-gray-400 hover:text-white hover:bg-ocean-600 transition-all"
            >
              <X size={20} />
            </button>

            <div className="px-6 pb-8 pt-2 relative">
              {/* Header */}
              <div className="text-center mb-6">
                <div className="inline-flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-ocean-600 to-ocean-700 flex items-center justify-center">
                    <span className="font-display font-bold text-sm text-white">
                      {asset.symbol?.slice(0, 3)}
                    </span>
                  </div>
                  <ArrowRight className="text-biolum-cyan" size={24} />
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-profit/20 to-profit/10 flex items-center justify-center border border-profit/30">
                    <DollarSign className="text-profit" size={24} />
                  </div>
                </div>

                <h2 className="font-display text-2xl font-bold text-white mb-1">
                  Convert to USDT
                </h2>
                <p className="text-gray-400 text-sm">
                  Sell {asset.symbol} for USDT
                </p>
              </div>

              {/* Current Holdings */}
              <div className="rounded-2xl p-5 mb-6 bg-ocean-700/30 border border-ocean-600/30">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-400 text-sm mb-1">You Have</p>
                    <p className="font-display text-2xl font-bold text-white">
                      {parseFloat(asset.quantity).toFixed(6)} {asset.symbol}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-gray-400 text-sm mb-1">Value</p>
                    <p className="font-mono text-xl font-semibold text-biolum-cyan">
                      {formatCurrency(parseFloat(asset.value_usdt))}
                    </p>
                  </div>
                </div>
              </div>

              {/* Convert Percentage */}
              <div className="mb-6">
                <div className="flex justify-between items-center mb-3">
                  <span className="text-gray-400">Convert Amount</span>
                  <span className="font-mono font-bold text-biolum-cyan text-lg">
                    {convertPercent}%
                  </span>
                </div>

                <div className="grid grid-cols-4 gap-2 mb-4">
                  {[25, 50, 75, 100].map((pct) => (
                    <button
                      key={pct}
                      onClick={() => setConvertPercent(pct)}
                      className={`py-2.5 rounded-xl font-semibold text-sm transition-all ${
                        convertPercent === pct
                          ? 'bg-biolum-cyan text-ocean-900 shadow-glow-sm'
                          : 'bg-ocean-700/50 text-gray-300 hover:bg-ocean-600/50'
                      }`}
                    >
                      {pct}%
                    </button>
                  ))}
                </div>

                <input
                  type="range"
                  min="1"
                  max="100"
                  value={convertPercent}
                  onChange={(e) => setConvertPercent(Number(e.target.value))}
                  className="w-full h-2 rounded-full appearance-none cursor-pointer"
                  style={{
                    background: `linear-gradient(to right, #00ffc8 0%, #00ffc8 ${convertPercent}%, #1c2640 ${convertPercent}%, #1c2640 100%)`
                  }}
                />
              </div>

              {/* Summary */}
              <div className="glass-card p-4 mb-6">
                <div className="flex justify-between items-center py-2 border-b border-ocean-600/30">
                  <span className="text-gray-400">Sell</span>
                  <span className="font-mono text-white">
                    {convertAmount.toFixed(6)} {asset.symbol}
                  </span>
                </div>
                <div className="flex justify-between items-center py-2">
                  <span className="text-gray-400">Receive (est.)</span>
                  <span className="font-mono font-bold text-profit text-lg">
                    ~{formatCurrency(convertValue)}
                  </span>
                </div>
              </div>

              {error && (
                <div className="mb-4 p-3 rounded-xl bg-loss/10 border border-loss/20 flex items-center gap-2">
                  <AlertTriangle size={18} className="text-loss" />
                  <span className="text-loss text-sm">{error}</span>
                </div>
              )}

              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleConvert}
                disabled={loading}
                className="w-full py-4 rounded-2xl font-bold text-lg flex items-center justify-center gap-2 bg-gradient-to-r from-biolum-cyan to-biolum-blue text-ocean-900 shadow-[0_0_30px_rgba(0,255,200,0.4)] disabled:opacity-50 transition-all"
              >
                {loading ? (
                  <Loader2 size={22} className="animate-spin" />
                ) : (
                  <>
                    <RefreshCw size={22} />
                    Convert to ~{formatCurrency(convertValue)}
                  </>
                )}
              </motion.button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// ================== CONFIRMATION MODAL ==================
export function ConfirmModal({ isOpen, onClose, onConfirm, title, message, confirmText = 'Confirm', type = 'danger' }) {
  const [loading, setLoading] = useState(false)

  const handleConfirm = async () => {
    setLoading(true)
    try {
      await onConfirm()
      onClose()
    } finally {
      setLoading(false)
    }
  }

  const colors = {
    danger: 'from-loss to-red-400',
    success: 'from-profit to-emerald-400',
    warning: 'from-amber-500 to-yellow-400',
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial="hidden"
          animate="visible"
          exit="hidden"
        >
          <motion.div
            variants={backdropVariants}
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={onClose}
          />

          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 400 }}
            className="relative w-full max-w-sm bg-gradient-to-b from-ocean-800 to-ocean-900 rounded-3xl p-6 border border-ocean-600/30"
          >
            <div className="text-center mb-6">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-loss/20 flex items-center justify-center">
                <AlertTriangle size={32} className="text-loss" />
              </div>
              <h3 className="font-display text-xl font-bold text-white mb-2">
                {title}
              </h3>
              <p className="text-gray-400 text-sm">
                {message}
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="flex-1 py-3 rounded-xl font-semibold bg-ocean-700/50 text-gray-300 hover:bg-ocean-600/50 transition-all"
              >
                Cancel
              </button>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleConfirm}
                disabled={loading}
                className={`flex-1 py-3 rounded-xl font-semibold bg-gradient-to-r ${colors[type]} text-white disabled:opacity-50 transition-all`}
              >
                {loading ? (
                  <Loader2 size={18} className="animate-spin mx-auto" />
                ) : (
                  confirmText
                )}
              </motion.button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default { SellPositionModal, ConvertToUsdtModal, ConfirmModal }
