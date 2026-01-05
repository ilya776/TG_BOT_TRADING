import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { ToastProvider } from './components/Toast'
import './index.css'

// Error Boundary Component
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('React Error Boundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0a0e17',
          color: '#fff',
          padding: '20px',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '64px', marginBottom: '20px' }}>🐋</div>
          <p style={{ color: '#888', maxWidth: '300px' }}>
            Something went wrong. Please reload the app.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: '20px',
              padding: '12px 24px',
              background: 'linear-gradient(135deg, #00ffc8, #00a8ff)',
              border: 'none',
              borderRadius: '12px',
              color: '#0a0e17',
              fontWeight: '600',
              cursor: 'pointer'
            }}
          >
            Reload
          </button>
          <p style={{ fontSize: '10px', marginTop: '20px', color: '#555' }}>
            {this.state.error?.message || 'Unknown error'}
          </p>
        </div>
      )
    }

    return this.props.children
  }
}

// Initialize Telegram WebApp safely
try {
  if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
    const tg = window.Telegram.WebApp
    tg.ready()
    tg.expand()

    // These methods might not exist in older versions
    if (typeof tg.enableClosingConfirmation === 'function') {
      tg.enableClosingConfirmation()
    }
    if (typeof tg.setHeaderColor === 'function') {
      tg.setHeaderColor('#0a0e17')
    }
    if (typeof tg.setBackgroundColor === 'function') {
      tg.setBackgroundColor('#0a0e17')
    }

    console.log('Telegram WebApp initialized successfully')
  } else {
    console.log('Telegram WebApp not available')
  }
} catch (e) {
  console.error('Error initializing Telegram WebApp:', e)
}

// Render app with error boundary
try {
  const root = document.getElementById('root')
  if (root) {
    ReactDOM.createRoot(root).render(
      <React.StrictMode>
        <ToastProvider>
          <ErrorBoundary>
            <App />
          </ErrorBoundary>
        </ToastProvider>
      </React.StrictMode>,
    )
  } else {
    console.error('Root element not found')
  }
} catch (e) {
  console.error('Error rendering app:', e)
}
