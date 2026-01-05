/**
 * FeatureGate - Lock overlay for premium features
 * Wraps components with blur and "Pro Required" badge
 */

import React from 'react'
import { motion } from 'framer-motion'
import { Lock, Crown, Sparkles } from 'lucide-react'
import { haptic } from '../utils/animations'

export function FeatureGate({
  children,
  isLocked = false,
  featureName = 'This feature',
  onUpgrade,
  variant = 'overlay', // 'overlay' | 'inline' | 'disabled'
  className = ''
}) {
  if (!isLocked) {
    return children
  }

  const handleUpgrade = (e) => {
    e.stopPropagation()
    haptic.medium()
    onUpgrade?.()
  }

  // Inline variant - shows lock badge inline
  if (variant === 'inline') {
    return (
      <div className={`relative ${className}`}>
        {/* Content with reduced opacity */}
        <div className="opacity-40 grayscale pointer-events-none select-none">
          {children}
        </div>

        {/* Lock badge */}
        <motion.button
          onClick={handleUpgrade}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-biolum-purple to-biolum-pink text-white text-sm font-bold shadow-[0_0_30px_rgba(139,92,246,0.4)]"
        >
          <Crown size={16} className="text-yellow-400" />
          Pro Only
        </motion.button>
      </div>
    )
  }

  // Disabled variant - shows as disabled with tooltip
  if (variant === 'disabled') {
    return (
      <div
        className={`relative opacity-50 cursor-not-allowed ${className}`}
        onClick={handleUpgrade}
        title={`${featureName} requires Pro`}
      >
        <div className="pointer-events-none grayscale">
          {children}
        </div>
        <div className="absolute top-2 right-2 flex items-center gap-1 px-2 py-0.5 rounded-lg bg-biolum-purple/30 border border-biolum-purple/50">
          <Lock size={10} className="text-biolum-purple" />
          <span className="text-[10px] font-bold text-biolum-purple">PRO</span>
        </div>
      </div>
    )
  }

  // Overlay variant (default) - full blur overlay
  return (
    <div className={`relative ${className}`}>
      {/* Content with blur */}
      <div className="opacity-30 blur-[2px] grayscale pointer-events-none select-none">
        {children}
      </div>

      {/* Lock overlay */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="absolute inset-0 flex flex-col items-center justify-center bg-ocean-900/40 backdrop-blur-[1px] rounded-2xl"
      >
        {/* Lock icon with glow */}
        <motion.div
          className="w-16 h-16 mb-4 rounded-2xl bg-gradient-to-br from-biolum-purple/20 to-biolum-pink/10 border border-biolum-purple/40 flex items-center justify-center"
          animate={{
            boxShadow: [
              '0 0 0px rgba(139,92,246,0)',
              '0 0 30px rgba(139,92,246,0.5)',
              '0 0 0px rgba(139,92,246,0)',
            ]
          }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          <Lock size={28} className="text-biolum-purple" />
        </motion.div>

        {/* Text */}
        <p className="text-white font-semibold mb-1">{featureName}</p>
        <p className="text-gray-400 text-sm mb-4">Requires Pro subscription</p>

        {/* Upgrade button */}
        <motion.button
          onClick={handleUpgrade}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-biolum-purple to-biolum-pink text-white text-sm font-bold shadow-[0_0_25px_rgba(139,92,246,0.4)]"
        >
          <Crown size={16} className="text-yellow-400" />
          Upgrade to Pro
        </motion.button>
      </motion.div>
    </div>
  )
}

// Premium Badge - Small badge for buttons/cards
export function PremiumBadge({
  size = 'md', // 'sm' | 'md' | 'lg'
  variant = 'solid', // 'solid' | 'outline' | 'glow'
  className = ''
}) {
  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-[9px]',
    md: 'px-2 py-0.5 text-[10px]',
    lg: 'px-2.5 py-1 text-xs',
  }

  const iconSizes = {
    sm: 8,
    md: 10,
    lg: 12,
  }

  const variantClasses = {
    solid: 'bg-gradient-to-r from-biolum-purple to-biolum-pink text-white',
    outline: 'bg-transparent border border-biolum-purple text-biolum-purple',
    glow: 'bg-biolum-purple/20 border border-biolum-purple/50 text-biolum-purple shadow-[0_0_15px_rgba(139,92,246,0.3)]',
  }

  return (
    <span className={`inline-flex items-center gap-1 rounded-lg font-bold ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}>
      <Crown size={iconSizes[size]} className={variant === 'solid' ? 'text-yellow-400' : ''} />
      PRO
    </span>
  )
}

// Locked Option Card - For settings options that require Pro
export function LockedOptionCard({
  title,
  description,
  icon: Icon,
  onUpgrade,
  isSelected = false,
  className = ''
}) {
  return (
    <motion.div
      onClick={() => {
        haptic.medium()
        onUpgrade?.()
      }}
      whileTap={{ scale: 0.98 }}
      className={`relative overflow-hidden rounded-2xl border cursor-pointer transition-all ${
        isSelected
          ? 'border-biolum-purple/50 bg-biolum-purple/10'
          : 'border-ocean-700/50 bg-ocean-800/30 hover:border-biolum-purple/30'
      } ${className}`}
    >
      {/* Locked overlay pattern */}
      <div className="absolute inset-0 opacity-5" style={{
        backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(139,92,246,0.1) 10px, rgba(139,92,246,0.1) 20px)',
      }} />

      <div className="relative p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-ocean-700/50">
              {Icon && <Icon size={18} className="text-gray-400" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white text-sm">{title}</span>
                <PremiumBadge size="sm" variant="glow" />
              </div>
              <p className="text-gray-500 text-xs mt-0.5">{description}</p>
            </div>
          </div>

          <motion.div
            className="p-1.5 rounded-lg bg-biolum-purple/20"
            animate={{
              boxShadow: [
                '0 0 0px rgba(139,92,246,0)',
                '0 0 15px rgba(139,92,246,0.4)',
                '0 0 0px rgba(139,92,246,0)',
              ]
            }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            <Lock size={14} className="text-biolum-purple" />
          </motion.div>
        </div>

        {/* Upgrade hint */}
        <div className="mt-3 pt-3 border-t border-ocean-700/50 flex items-center justify-center gap-2 text-biolum-purple text-xs font-medium">
          <Sparkles size={12} />
          <span>Tap to upgrade</span>
        </div>
      </div>
    </motion.div>
  )
}

export default FeatureGate
