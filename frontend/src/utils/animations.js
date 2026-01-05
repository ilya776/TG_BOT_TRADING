/**
 * Animation Utilities for Whale Trading Bot
 * Reusable motion variants and spring configurations
 */

// ==================== SPRING CONFIGS ====================

export const springs = {
  // Snappy for buttons and interactive elements
  snappy: { type: 'spring', stiffness: 500, damping: 30 },
  // Smooth for page transitions
  smooth: { type: 'spring', stiffness: 300, damping: 30 },
  // Bouncy for fun elements
  bouncy: { type: 'spring', stiffness: 400, damping: 15, mass: 1 },
  // Gentle for subtle animations
  gentle: { type: 'spring', stiffness: 200, damping: 25 },
  // Quick for micro-interactions
  quick: { type: 'spring', stiffness: 700, damping: 35 },
  // Slow for dramatic reveals
  slow: { type: 'spring', stiffness: 100, damping: 20 },
}

// ==================== PAGE TRANSITIONS ====================

export const pageVariants = {
  initial: {
    opacity: 0,
    y: 20,
    scale: 0.98,
  },
  animate: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      ...springs.smooth,
      staggerChildren: 0.05,
    }
  },
  exit: {
    opacity: 0,
    y: -10,
    scale: 0.98,
    transition: { duration: 0.2 }
  }
}

// ==================== CARD ANIMATIONS ====================

export const cardVariants = {
  hidden: {
    opacity: 0,
    y: 30,
    scale: 0.95,
  },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: springs.smooth
  },
  hover: {
    scale: 1.02,
    y: -4,
    transition: springs.snappy
  },
  tap: {
    scale: 0.98,
    transition: springs.quick
  }
}

// ==================== LIST ANIMATIONS ====================

export const listContainerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.1,
    }
  }
}

export const listItemVariants = {
  hidden: {
    opacity: 0,
    x: -20,
    scale: 0.95,
  },
  visible: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: springs.smooth
  },
  exit: {
    opacity: 0,
    x: 20,
    scale: 0.95,
    transition: { duration: 0.2 }
  }
}

// ==================== MODAL ANIMATIONS ====================

export const overlayVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: 0.2 }
  },
  exit: {
    opacity: 0,
    transition: { duration: 0.15, delay: 0.1 }
  }
}

export const slideUpVariants = {
  hidden: {
    y: '100%',
    opacity: 0.5,
  },
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

export const scaleVariants = {
  hidden: {
    scale: 0.8,
    opacity: 0,
  },
  visible: {
    scale: 1,
    opacity: 1,
    transition: springs.bouncy
  },
  exit: {
    scale: 0.8,
    opacity: 0,
    transition: { duration: 0.15 }
  }
}

// ==================== BUTTON ANIMATIONS ====================

export const buttonVariants = {
  idle: { scale: 1 },
  hover: {
    scale: 1.02,
    transition: springs.snappy
  },
  tap: {
    scale: 0.95,
    transition: springs.quick
  },
  disabled: {
    opacity: 0.5,
    scale: 1,
  }
}

export const pulseVariants = {
  animate: {
    scale: [1, 1.02, 1],
    opacity: [1, 0.8, 1],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: 'easeInOut',
    }
  }
}

// ==================== GLOW EFFECTS ====================

export const glowVariants = {
  idle: {
    boxShadow: '0 0 0px rgba(0, 255, 200, 0)',
  },
  active: {
    boxShadow: '0 0 30px rgba(0, 255, 200, 0.4)',
    transition: springs.gentle
  },
  success: {
    boxShadow: '0 0 40px rgba(16, 185, 129, 0.5)',
    transition: springs.gentle
  },
  error: {
    boxShadow: '0 0 40px rgba(239, 68, 68, 0.5)',
    transition: springs.gentle
  }
}

// ==================== NUMBER ANIMATIONS ====================

export const countUpConfig = {
  duration: 1.5,
  ease: [0.22, 1, 0.36, 1], // Smooth ease-out
}

// ==================== SKELETON LOADING ====================

export const skeletonVariants = {
  animate: {
    backgroundPosition: ['200% 0', '-200% 0'],
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: 'linear',
    }
  }
}

// ==================== FLOATING ANIMATION ====================

export const floatVariants = {
  animate: {
    y: [0, -10, 0],
    transition: {
      duration: 3,
      repeat: Infinity,
      ease: 'easeInOut',
    }
  }
}

// ==================== RIPPLE EFFECT ====================

export const rippleVariants = {
  initial: {
    scale: 0,
    opacity: 0.6,
  },
  animate: {
    scale: 4,
    opacity: 0,
    transition: {
      duration: 0.6,
      ease: 'easeOut',
    }
  }
}

// ==================== NOTIFICATION DOT ====================

export const notificationDotVariants = {
  initial: { scale: 0 },
  animate: {
    scale: 1,
    transition: springs.bouncy
  },
  pulse: {
    scale: [1, 1.2, 1],
    transition: {
      duration: 1,
      repeat: Infinity,
    }
  }
}

// ==================== PRICE CHANGE FLASH ====================

export const priceFlashVariants = {
  positive: {
    backgroundColor: ['rgba(16, 185, 129, 0.3)', 'rgba(16, 185, 129, 0)'],
    transition: { duration: 0.5 }
  },
  negative: {
    backgroundColor: ['rgba(239, 68, 68, 0.3)', 'rgba(239, 68, 68, 0)'],
    transition: { duration: 0.5 }
  }
}

// ==================== STAGGER DELAYS ====================

export const stagger = {
  fast: 0.03,
  medium: 0.06,
  slow: 0.1,
}

// ==================== HELPER FUNCTIONS ====================

/**
 * Create staggered children animation with custom delay
 */
export const createStaggerContainer = (staggerDelay = 0.05, delayStart = 0) => ({
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: staggerDelay,
      delayChildren: delayStart,
    }
  }
})

/**
 * Create fade in animation from direction
 */
export const fadeInFrom = (direction = 'bottom', distance = 20) => {
  const directions = {
    top: { y: -distance },
    bottom: { y: distance },
    left: { x: -distance },
    right: { x: distance },
  }

  return {
    hidden: {
      opacity: 0,
      ...directions[direction]
    },
    visible: {
      opacity: 1,
      x: 0,
      y: 0,
      transition: springs.smooth
    }
  }
}

/**
 * Animate presence wrapper for conditional rendering
 */
export const presenceAnimation = {
  initial: 'hidden',
  animate: 'visible',
  exit: 'exit',
}

// ==================== HAPTIC FEEDBACK ====================

export const haptic = {
  light: () => {
    window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('light')
  },
  medium: () => {
    window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('medium')
  },
  heavy: () => {
    window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('heavy')
  },
  success: () => {
    window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('success')
  },
  warning: () => {
    window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('warning')
  },
  error: () => {
    window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('error')
  },
  selection: () => {
    window.Telegram?.WebApp?.HapticFeedback?.selectionChanged()
  },
}

export default {
  springs,
  pageVariants,
  cardVariants,
  listContainerVariants,
  listItemVariants,
  overlayVariants,
  slideUpVariants,
  scaleVariants,
  buttonVariants,
  pulseVariants,
  glowVariants,
  skeletonVariants,
  floatVariants,
  rippleVariants,
  notificationDotVariants,
  priceFlashVariants,
  stagger,
  createStaggerContainer,
  fadeInFrom,
  presenceAnimation,
  haptic,
}
