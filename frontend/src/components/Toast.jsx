/**
 * Toast Notification System
 * Beautiful, animated notifications with haptic feedback
 */

import React, { createContext, useContext, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  X,
  Loader2,
  Zap
} from 'lucide-react'

const ToastContext = createContext(null)

const TOAST_ICONS = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
  loading: Loader2,
  trade: Zap,
}

const TOAST_COLORS = {
  success: {
    bg: 'from-emerald-500/20 to-emerald-600/10',
    border: 'border-emerald-500/40',
    icon: 'text-emerald-400',
    glow: 'shadow-[0_0_30px_rgba(16,185,129,0.3)]',
  },
  error: {
    bg: 'from-red-500/20 to-red-600/10',
    border: 'border-red-500/40',
    icon: 'text-red-400',
    glow: 'shadow-[0_0_30px_rgba(239,68,68,0.3)]',
  },
  warning: {
    bg: 'from-amber-500/20 to-amber-600/10',
    border: 'border-amber-500/40',
    icon: 'text-amber-400',
    glow: 'shadow-[0_0_30px_rgba(245,158,11,0.3)]',
  },
  info: {
    bg: 'from-blue-500/20 to-blue-600/10',
    border: 'border-blue-500/40',
    icon: 'text-blue-400',
    glow: 'shadow-[0_0_30px_rgba(59,130,246,0.3)]',
  },
  loading: {
    bg: 'from-biolum-cyan/20 to-biolum-blue/10',
    border: 'border-biolum-cyan/40',
    icon: 'text-biolum-cyan',
    glow: 'shadow-[0_0_30px_rgba(0,255,200,0.3)]',
  },
  trade: {
    bg: 'from-biolum-purple/20 to-biolum-pink/10',
    border: 'border-biolum-purple/40',
    icon: 'text-biolum-purple',
    glow: 'shadow-[0_0_30px_rgba(139,92,246,0.3)]',
  },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((toast) => {
    const id = Date.now() + Math.random()
    const newToast = {
      id,
      type: 'info',
      duration: 4000,
      ...toast,
    }

    setToasts(prev => [...prev, newToast])

    // Haptic feedback on mobile
    if (window.Telegram?.WebApp?.HapticFeedback) {
      if (toast.type === 'success') {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred('success')
      } else if (toast.type === 'error') {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred('error')
      } else {
        window.Telegram.WebApp.HapticFeedback.impactOccurred('light')
      }
    }

    // Auto remove (unless it's loading)
    if (newToast.type !== 'loading' && newToast.duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, newToast.duration)
    }

    return id
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const updateToast = useCallback((id, updates) => {
    setToasts(prev => prev.map(t =>
      t.id === id ? { ...t, ...updates } : t
    ))
  }, [])

  // Convenience methods
  const toast = {
    success: (message, options = {}) => addToast({ type: 'success', message, ...options }),
    error: (message, options = {}) => addToast({ type: 'error', message, ...options }),
    warning: (message, options = {}) => addToast({ type: 'warning', message, ...options }),
    info: (message, options = {}) => addToast({ type: 'info', message, ...options }),
    loading: (message, options = {}) => addToast({ type: 'loading', message, duration: 0, ...options }),
    trade: (message, options = {}) => addToast({ type: 'trade', message, ...options }),
    dismiss: removeToast,
    update: updateToast,
  }

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return context
}

function ToastContainer({ toasts, onDismiss }) {
  return (
    <div className="fixed top-4 left-4 right-4 z-[100] pointer-events-none flex flex-col items-center gap-2">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast, index) => (
          <Toast
            key={toast.id}
            toast={toast}
            onDismiss={() => onDismiss(toast.id)}
            index={index}
          />
        ))}
      </AnimatePresence>
    </div>
  )
}

function Toast({ toast, onDismiss, index }) {
  const colors = TOAST_COLORS[toast.type] || TOAST_COLORS.info
  const Icon = TOAST_ICONS[toast.type] || Info

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -50, scale: 0.8 }}
      animate={{
        opacity: 1,
        y: 0,
        scale: 1,
        transition: {
          type: 'spring',
          stiffness: 400,
          damping: 25,
        }
      }}
      exit={{
        opacity: 0,
        y: -30,
        scale: 0.8,
        transition: { duration: 0.2 }
      }}
      className={`
        pointer-events-auto w-full max-w-sm
        bg-gradient-to-r ${colors.bg}
        backdrop-blur-xl border ${colors.border}
        rounded-2xl p-4
        ${colors.glow}
      `}
    >
      <div className="flex items-start gap-3">
        <div className={`flex-shrink-0 ${colors.icon}`}>
          <Icon
            size={22}
            className={toast.type === 'loading' ? 'animate-spin' : ''}
          />
        </div>

        <div className="flex-1 min-w-0">
          {toast.title && (
            <p className="font-semibold text-white text-sm mb-0.5">
              {toast.title}
            </p>
          )}
          <p className="text-gray-200 text-sm leading-relaxed">
            {toast.message}
          </p>
          {toast.action && (
            <button
              onClick={toast.action.onClick}
              className="mt-2 text-sm font-semibold text-biolum-cyan hover:underline"
            >
              {toast.action.label}
            </button>
          )}
        </div>

        {toast.type !== 'loading' && (
          <button
            onClick={onDismiss}
            className="flex-shrink-0 p-1 rounded-full hover:bg-white/10 transition-colors text-gray-400 hover:text-white"
          >
            <X size={16} />
          </button>
        )}
      </div>

      {/* Progress bar for timed toasts */}
      {toast.duration > 0 && toast.type !== 'loading' && (
        <motion.div
          className="absolute bottom-0 left-0 h-0.5 bg-white/30 rounded-full"
          initial={{ width: '100%' }}
          animate={{ width: '0%' }}
          transition={{ duration: toast.duration / 1000, ease: 'linear' }}
          style={{ marginLeft: '1rem', marginRight: '1rem', maxWidth: 'calc(100% - 2rem)' }}
        />
      )}
    </motion.div>
  )
}

export default Toast
