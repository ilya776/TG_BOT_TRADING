/**
 * PremiumBanner - Aggressive upgrade CTA banner for Dashboard
 * Shows animated crown, gradient border, compelling copy
 */

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Crown, Sparkles, Zap, X, ChevronRight, Star, Lock } from 'lucide-react'
import { springs, haptic } from '../utils/animations'

// Premium features to highlight
const PREMIUM_HIGHLIGHTS = [
  { icon: Zap, text: 'Futures trading with 10x leverage' },
  { icon: Crown, text: 'Unlimited whale follows' },
  { icon: Star, text: 'Priority signal alerts' },
]

export function PremiumBanner({
  onUpgrade,
  variant = 'full', // 'full' | 'compact' | 'floating'
  dismissible = true,
  className = ''
}) {
  const [dismissed, setDismissed] = useState(false)
  const [showHighlight, setShowHighlight] = useState(0)

  // Rotate through highlights
  useEffect(() => {
    const interval = setInterval(() => {
      setShowHighlight(prev => (prev + 1) % PREMIUM_HIGHLIGHTS.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  // Check if dismissed recently (24h)
  useEffect(() => {
    const dismissedAt = localStorage.getItem('premium_banner_dismissed')
    if (dismissedAt) {
      const hoursSince = (Date.now() - Number(dismissedAt)) / (1000 * 60 * 60)
      if (hoursSince < 24) {
        setDismissed(true)
      } else {
        localStorage.removeItem('premium_banner_dismissed')
      }
    }
  }, [])

  const handleDismiss = () => {
    haptic.light()
    localStorage.setItem('premium_banner_dismissed', Date.now().toString())
    setDismissed(true)
  }

  const handleUpgrade = () => {
    haptic.medium()
    onUpgrade?.()
  }

  if (dismissed) return null

  // Compact variant for tight spaces
  if (variant === 'compact') {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={`relative overflow-hidden rounded-2xl bg-gradient-to-r from-biolum-purple/20 via-biolum-pink/15 to-biolum-cyan/20 border border-biolum-purple/30 p-3 ${className}`}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <motion.div
              animate={{ rotate: [0, -10, 10, 0], scale: [1, 1.1, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Crown size={18} className="text-yellow-400" />
            </motion.div>
            <span className="text-sm font-medium text-white">Upgrade to Pro</span>
          </div>
          <motion.button
            onClick={handleUpgrade}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-biolum-purple to-biolum-pink text-white text-xs font-bold"
          >
            Unlock
          </motion.button>
        </div>
      </motion.div>
    )
  }

  // Floating variant for periodic popups
  if (variant === 'floating') {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 50 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: 50 }}
        className={`fixed bottom-24 left-4 right-4 z-50 ${className}`}
      >
        <div className="relative overflow-hidden rounded-3xl bg-ocean-800/95 backdrop-blur-xl border border-biolum-purple/40 p-5 shadow-[0_0_60px_rgba(139,92,246,0.3)]">
          {/* Glow effects */}
          <div className="absolute -top-20 -right-20 w-40 h-40 bg-biolum-purple/30 rounded-full blur-3xl" />
          <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-biolum-pink/20 rounded-full blur-3xl" />

          {dismissible && (
            <motion.button
              onClick={handleDismiss}
              whileTap={{ scale: 0.9 }}
              className="absolute top-3 right-3 p-1.5 rounded-full bg-ocean-700/50 text-gray-400 hover:text-white z-10"
            >
              <X size={16} />
            </motion.button>
          )}

          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-3">
              <motion.div
                className="p-2.5 rounded-xl bg-gradient-to-br from-yellow-400/20 to-yellow-600/10 border border-yellow-400/30"
                animate={{
                  rotate: [0, -5, 5, 0],
                  boxShadow: [
                    '0 0 0px rgba(250,204,21,0)',
                    '0 0 20px rgba(250,204,21,0.4)',
                    '0 0 0px rgba(250,204,21,0)',
                  ]
                }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <Crown size={24} className="text-yellow-400" />
              </motion.div>
              <div>
                <h3 className="font-display font-bold text-lg text-white">Unlock Pro Features</h3>
                <p className="text-gray-400 text-sm">Trade smarter, earn more</p>
              </div>
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={showHighlight}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="flex items-center gap-2 mb-4 text-biolum-cyan text-sm"
              >
                {React.createElement(PREMIUM_HIGHLIGHTS[showHighlight].icon, { size: 16 })}
                <span>{PREMIUM_HIGHLIGHTS[showHighlight].text}</span>
              </motion.div>
            </AnimatePresence>

            <motion.button
              onClick={handleUpgrade}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-biolum-purple via-biolum-pink to-biolum-purple bg-[length:200%_100%] text-white font-bold text-base flex items-center justify-center gap-2 shadow-[0_0_30px_rgba(139,92,246,0.4)]"
              animate={{
                backgroundPosition: ['0% center', '100% center', '0% center'],
              }}
              transition={{ duration: 3, repeat: Infinity }}
            >
              <Sparkles size={18} />
              Upgrade Now
              <ChevronRight size={18} />
            </motion.button>
          </div>
        </div>
      </motion.div>
    )
  }

  // Full variant (default) - for Dashboard
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`relative overflow-hidden rounded-3xl bg-gradient-to-br from-ocean-800/90 via-biolum-purple/10 to-ocean-800/90 border border-biolum-purple/30 p-5 ${className}`}
    >
      {/* Animated gradient border effect */}
      <div className="absolute inset-0 rounded-3xl overflow-hidden">
        <motion.div
          className="absolute inset-0 opacity-30"
          style={{
            background: 'linear-gradient(90deg, transparent, rgba(139,92,246,0.5), rgba(236,72,153,0.5), transparent)',
          }}
          animate={{
            x: ['-100%', '100%'],
          }}
          transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
        />
      </div>

      {/* Glow orbs */}
      <motion.div
        className="absolute -top-10 -right-10 w-32 h-32 bg-biolum-purple/30 rounded-full blur-3xl"
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{ duration: 3, repeat: Infinity }}
      />
      <motion.div
        className="absolute -bottom-10 -left-10 w-28 h-28 bg-biolum-pink/20 rounded-full blur-3xl"
        animate={{
          scale: [1.2, 1, 1.2],
          opacity: [0.2, 0.4, 0.2],
        }}
        transition={{ duration: 4, repeat: Infinity }}
      />

      {dismissible && (
        <motion.button
          onClick={handleDismiss}
          whileTap={{ scale: 0.9 }}
          className="absolute top-3 right-3 p-1.5 rounded-full bg-ocean-700/50 text-gray-500 hover:text-white transition-colors z-10"
        >
          <X size={14} />
        </motion.button>
      )}

      <div className="relative z-10">
        {/* Header */}
        <div className="flex items-center gap-4 mb-4">
          <motion.div
            className="p-3 rounded-2xl bg-gradient-to-br from-yellow-400/20 to-yellow-600/10 border border-yellow-400/30"
            animate={{
              rotate: [0, -8, 8, 0],
              boxShadow: [
                '0 0 0px rgba(250,204,21,0)',
                '0 0 30px rgba(250,204,21,0.5)',
                '0 0 0px rgba(250,204,21,0)',
              ]
            }}
            transition={{ duration: 2.5, repeat: Infinity }}
          >
            <Crown size={28} className="text-yellow-400" />
          </motion.div>
          <div>
            <h3 className="font-display font-bold text-xl text-white">Upgrade to Pro</h3>
            <p className="text-gray-400 text-sm">Unlock the full power of whale trading</p>
          </div>
        </div>

        {/* Features */}
        <div className="space-y-2 mb-5">
          {PREMIUM_HIGHLIGHTS.map((feature, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 * index }}
              className="flex items-center gap-2.5 text-gray-300 text-sm"
            >
              <div className="w-5 h-5 rounded-full bg-biolum-cyan/20 flex items-center justify-center">
                <feature.icon size={12} className="text-biolum-cyan" />
              </div>
              <span>{feature.text}</span>
            </motion.div>
          ))}
        </div>

        {/* CTA Button */}
        <motion.button
          onClick={handleUpgrade}
          whileHover={{ scale: 1.02, y: -2 }}
          whileTap={{ scale: 0.98 }}
          className="w-full py-4 rounded-2xl bg-gradient-to-r from-biolum-purple via-biolum-pink to-biolum-purple bg-[length:200%_100%] text-white font-bold text-base flex items-center justify-center gap-2 shadow-[0_0_40px_rgba(139,92,246,0.4)] transition-shadow hover:shadow-[0_0_50px_rgba(139,92,246,0.5)]"
          animate={{
            backgroundPosition: ['0% center', '100% center', '0% center'],
          }}
          transition={{ duration: 4, repeat: Infinity }}
        >
          <Sparkles size={20} />
          Unlock Pro Features
          <ChevronRight size={20} />
        </motion.button>

        {/* Price hint - Marketing best practice: show discount from original */}
        <p className="text-center text-gray-500 text-xs mt-3">
          <span className="line-through text-gray-600">$199</span>{' '}
          <span className="text-biolum-cyan font-bold text-sm">$99/month</span>
          <span className="ml-1.5 px-1.5 py-0.5 rounded bg-loss/20 text-loss text-[10px] font-bold">-50%</span>
        </p>
      </div>
    </motion.div>
  )
}

// Premium Popup - Shows periodically for free users
export function PremiumPopup({ isOpen, onClose, onUpgrade }) {
  if (!isOpen) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-ocean-900/80 backdrop-blur-sm"
        />

        {/* Modal */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 30 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 30 }}
          transition={springs.bouncy}
          onClick={e => e.stopPropagation()}
          className="relative w-full max-w-sm"
        >
          <div className="relative overflow-hidden rounded-3xl bg-ocean-800 border border-biolum-purple/40 p-6 shadow-[0_0_80px_rgba(139,92,246,0.3)]">
            {/* Decorative elements */}
            <div className="absolute -top-20 -right-20 w-48 h-48 bg-biolum-purple/20 rounded-full blur-3xl" />
            <div className="absolute -bottom-20 -left-20 w-40 h-40 bg-biolum-pink/15 rounded-full blur-3xl" />

            <motion.button
              onClick={onClose}
              whileTap={{ scale: 0.9 }}
              className="absolute top-4 right-4 p-2 rounded-full bg-ocean-700/50 text-gray-400 hover:text-white z-10"
            >
              <X size={18} />
            </motion.button>

            <div className="relative z-10 text-center">
              {/* Crown icon */}
              <motion.div
                className="w-20 h-20 mx-auto mb-4 rounded-3xl bg-gradient-to-br from-yellow-400/20 to-yellow-600/10 border border-yellow-400/30 flex items-center justify-center"
                animate={{
                  rotate: [0, -5, 5, 0],
                  boxShadow: [
                    '0 0 0px rgba(250,204,21,0)',
                    '0 0 40px rgba(250,204,21,0.5)',
                    '0 0 0px rgba(250,204,21,0)',
                  ]
                }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <Crown size={40} className="text-yellow-400" />
              </motion.div>

              <h2 className="font-display font-bold text-2xl text-white mb-2">
                Go Pro Today!
              </h2>
              <p className="text-gray-400 mb-6">
                You're missing out on powerful features that could boost your profits.
              </p>

              {/* Feature list */}
              <div className="space-y-3 mb-6 text-left">
                {[
                  'Trade futures with up to 10x leverage',
                  'Follow unlimited top whales',
                  'Priority access to whale signals',
                  'Advanced risk management tools',
                ].map((feature, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 * i }}
                    className="flex items-center gap-3 text-sm text-gray-300"
                  >
                    <div className="w-5 h-5 rounded-full bg-profit/20 flex items-center justify-center flex-shrink-0">
                      <svg className="w-3 h-3 text-profit" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <span>{feature}</span>
                  </motion.div>
                ))}
              </div>

              {/* CTA */}
              <motion.button
                onClick={() => {
                  haptic.medium()
                  onUpgrade?.()
                }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="w-full py-4 rounded-2xl bg-gradient-to-r from-biolum-purple via-biolum-pink to-biolum-purple bg-[length:200%_100%] text-white font-bold text-lg flex items-center justify-center gap-2 shadow-[0_0_40px_rgba(139,92,246,0.5)]"
                animate={{
                  backgroundPosition: ['0% center', '100% center', '0% center'],
                }}
                transition={{ duration: 3, repeat: Infinity }}
              >
                <Sparkles size={22} />
                Upgrade Now
              </motion.button>

              <button
                onClick={onClose}
                className="mt-3 text-gray-500 text-sm hover:text-gray-400 transition-colors"
              >
                Maybe later
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

export default PremiumBanner
