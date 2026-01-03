/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ocean: {
          950: '#040810',
          900: '#0a0e17',
          800: '#0f1522',
          700: '#151d2e',
          600: '#1c2640',
          500: '#253352',
        },
        biolum: {
          cyan: '#00ffc8',
          blue: '#00a8ff',
          purple: '#8b5cf6',
          pink: '#ec4899',
        },
        profit: '#00ffc8',
        loss: '#ff5f6d',
      },
      fontFamily: {
        display: ['Outfit', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        body: ['Inter', 'sans-serif'],
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'glass': 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
        'glow-cyan': 'radial-gradient(ellipse at center, rgba(0,255,200,0.15) 0%, transparent 70%)',
        'glow-purple': 'radial-gradient(ellipse at center, rgba(139,92,246,0.15) 0%, transparent 70%)',
      },
      boxShadow: {
        'glass': '0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05)',
        'glow-sm': '0 0 20px rgba(0,255,200,0.3)',
        'glow-lg': '0 0 40px rgba(0,255,200,0.4)',
        'inner-glow': 'inset 0 0 30px rgba(0,255,200,0.1)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'wave': 'wave 8s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        wave: {
          '0%, 100%': { transform: 'translateX(0) translateY(0)' },
          '25%': { transform: 'translateX(5px) translateY(-3px)' },
          '50%': { transform: 'translateX(0) translateY(-5px)' },
          '75%': { transform: 'translateX(-5px) translateY(-3px)' },
        },
      },
    },
  },
  plugins: [],
}
