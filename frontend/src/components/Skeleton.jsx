/**
 * Skeleton - Beautiful loading placeholders with shimmer effect
 */

import React from 'react'
import { motion } from 'framer-motion'

export function Skeleton({ className = '', variant = 'default', ...props }) {
  const variants = {
    default: 'h-4 bg-ocean-800/50',
    text: 'h-3 bg-ocean-800/40',
    title: 'h-6 bg-ocean-800/50',
    circle: 'rounded-full bg-ocean-800/50',
    card: 'h-32 bg-ocean-800/30 rounded-2xl',
    stat: 'h-24 bg-ocean-800/30 rounded-xl',
  }

  return (
    <motion.div
      className={`relative overflow-hidden rounded-lg ${variants[variant]} ${className}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      {...props}
    >
      {/* Shimmer effect */}
      <motion.div
        className="absolute inset-0 bg-gradient-to-r from-transparent via-ocean-700/30 to-transparent"
        animate={{
          x: ['-100%', '200%'],
        }}
        transition={{
          repeat: Infinity,
          duration: 1.5,
          ease: 'linear',
        }}
      />
    </motion.div>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="px-4 pt-6 pb-4 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Skeleton className="w-8 h-8" variant="circle" />
          <div className="space-y-2">
            <Skeleton className="w-32 h-5" />
            <Skeleton className="w-40 h-3" />
          </div>
        </div>
        <Skeleton className="w-10 h-10 rounded-xl" />
      </div>

      {/* Balance Card */}
      <Skeleton className="h-40 rounded-2xl" />

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3">
        <Skeleton variant="stat" />
        <Skeleton variant="stat" />
        <Skeleton variant="stat" />
        <Skeleton variant="stat" />
      </div>

      {/* Positions */}
      <div className="space-y-2">
        <Skeleton className="w-32 h-5" />
        <Skeleton className="h-20 rounded-xl" />
        <Skeleton className="h-20 rounded-xl" />
        <Skeleton className="h-20 rounded-xl" />
      </div>
    </div>
  )
}

export function WhaleCardSkeleton() {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-3">
        <Skeleton className="w-12 h-12 rounded-2xl" />
        <div className="flex-1 space-y-2">
          <Skeleton className="w-32 h-4" />
          <Skeleton className="w-24 h-3" />
        </div>
        <div className="space-y-2">
          <Skeleton className="w-16 h-4" />
          <Skeleton className="w-16 h-3" />
        </div>
      </div>
    </div>
  )
}

export function PositionCardSkeleton() {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="w-10 h-10 rounded-xl" />
          <div className="space-y-2">
            <Skeleton className="w-24 h-4" />
            <Skeleton className="w-32 h-3" />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="space-y-2 text-right">
            <Skeleton className="w-16 h-4" />
            <Skeleton className="w-12 h-3" />
          </div>
          <Skeleton className="w-16 h-8 rounded-lg" />
        </div>
      </div>
    </div>
  )
}

export function SignalCardSkeleton() {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Skeleton className="w-8 h-8 rounded-full" />
          <div className="space-y-1">
            <Skeleton className="w-24 h-4" />
            <Skeleton className="w-16 h-3" />
          </div>
        </div>
        <Skeleton className="w-20 h-6 rounded-full" />
      </div>
      <div className="flex items-center gap-2">
        <Skeleton className="w-16 h-8 rounded-lg" />
        <Skeleton className="w-24 h-4" />
      </div>
    </div>
  )
}
