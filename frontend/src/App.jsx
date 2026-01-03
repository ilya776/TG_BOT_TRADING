import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard,
  Search,
  History,
  Bell,
  Settings,
  Waves
} from 'lucide-react'

import Dashboard from './screens/Dashboard'
import WhaleDiscovery from './screens/WhaleDiscovery'
import TradeHistory from './screens/TradeHistory'
import LiveAlerts from './screens/LiveAlerts'
import SettingsScreen from './screens/Settings'

const tabs = [
  { id: 'dashboard', icon: LayoutDashboard, label: 'Home' },
  { id: 'whales', icon: Search, label: 'Whales' },
  { id: 'history', icon: History, label: 'History' },
  { id: 'alerts', icon: Bell, label: 'Alerts', badge: 3 },
  { id: 'settings', icon: Settings, label: 'Settings' },
]

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Simulate initial loading
    const timer = setTimeout(() => setIsLoading(false), 1500)
    return () => clearTimeout(timer)
  }, [])

  const renderScreen = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard />
      case 'whales':
        return <WhaleDiscovery />
      case 'history':
        return <TradeHistory />
      case 'alerts':
        return <LiveAlerts />
      case 'settings':
        return <SettingsScreen />
      default:
        return <Dashboard />
    }
  }

  if (isLoading) {
    return <LoadingScreen />
  }

  return (
    <div className="min-h-screen flex flex-col relative">
      {/* Animated Ocean Background */}
      <div className="ocean-bg" />

      {/* Floating Light Orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <motion.div
          className="absolute w-96 h-96 rounded-full opacity-20"
          style={{
            background: 'radial-gradient(circle, rgba(0,255,200,0.3) 0%, transparent 70%)',
            left: '-10%',
            top: '20%',
          }}
          animate={{
            x: [0, 30, 0],
            y: [0, -20, 0],
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
        <motion.div
          className="absolute w-72 h-72 rounded-full opacity-15"
          style={{
            background: 'radial-gradient(circle, rgba(139,92,246,0.4) 0%, transparent 70%)',
            right: '-5%',
            top: '50%',
          }}
          animate={{
            x: [0, -20, 0],
            y: [0, 30, 0],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto overflow-x-hidden pb-24">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
            className="min-h-full"
          >
            {renderScreen()}
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 z-50">
        <div className="absolute inset-0 bg-gradient-to-t from-ocean-950 via-ocean-950/95 to-transparent pointer-events-none" style={{ height: '120%', bottom: 0 }} />
        <div className="relative glass-card rounded-t-3xl border-b-0 mx-2 mb-0">
          <div className="flex items-center justify-around py-2 px-2">
            {tabs.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id

              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className="relative flex flex-col items-center gap-1 py-2 px-4 rounded-xl transition-all duration-300"
                >
                  {isActive && (
                    <motion.div
                      layoutId="activeTab"
                      className="absolute inset-0 rounded-xl"
                      style={{
                        background: 'linear-gradient(135deg, rgba(0,255,200,0.15) 0%, rgba(0,168,255,0.1) 100%)',
                        boxShadow: '0 0 20px rgba(0,255,200,0.2)',
                      }}
                      transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }}
                    />
                  )}
                  <div className="relative">
                    <Icon
                      size={22}
                      className={`transition-colors duration-300 ${
                        isActive ? 'text-biolum-cyan' : 'text-gray-500'
                      }`}
                    />
                    {tab.badge && (
                      <span className="absolute -top-1 -right-1 w-4 h-4 bg-loss rounded-full text-[10px] font-bold flex items-center justify-center text-white">
                        {tab.badge}
                      </span>
                    )}
                  </div>
                  <span className={`text-[10px] font-medium transition-colors duration-300 ${
                    isActive ? 'text-biolum-cyan' : 'text-gray-500'
                  }`}>
                    {tab.label}
                  </span>
                </button>
              )
            })}
          </div>
          <div className="h-safe-area-inset-bottom" />
        </div>
      </nav>
    </div>
  )
}

function LoadingScreen() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden">
      <div className="ocean-bg" />

      {/* Animated Whale */}
      <motion.div
        className="relative"
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <motion.div
          animate={{
            y: [0, -10, 0],
            rotate: [0, 2, -2, 0],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          className="text-7xl"
        >
          🐋
        </motion.div>

        {/* Glow Effect */}
        <div className="absolute inset-0 blur-2xl opacity-50">
          <div className="w-full h-full bg-gradient-to-r from-biolum-cyan to-biolum-purple rounded-full" />
        </div>
      </motion.div>

      {/* Loading Text */}
      <motion.div
        className="mt-8 flex flex-col items-center gap-3"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <h1 className="font-display text-2xl font-bold bg-gradient-to-r from-biolum-cyan via-biolum-blue to-biolum-purple bg-clip-text text-transparent">
          Whale Trading
        </h1>

        {/* Loading Bar */}
        <div className="w-48 h-1 bg-ocean-700 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-biolum-cyan to-biolum-blue"
            initial={{ width: '0%' }}
            animate={{ width: '100%' }}
            transition={{ duration: 1.2, ease: 'easeInOut' }}
          />
        </div>

        <p className="text-gray-500 text-sm">Connecting to the deep...</p>
      </motion.div>

      {/* Floating Bubbles */}
      {[...Array(5)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-2 h-2 bg-biolum-cyan/30 rounded-full"
          style={{
            left: `${20 + i * 15}%`,
            bottom: '20%',
          }}
          animate={{
            y: [-20, -100],
            opacity: [0.6, 0],
            scale: [1, 1.5],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            delay: i * 0.3,
            ease: 'easeOut',
          }}
        />
      ))}
    </div>
  )
}

export default App
