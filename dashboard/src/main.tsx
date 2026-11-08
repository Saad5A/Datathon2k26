import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { ConfigError } from './components/ConfigError'
import { NotFound } from './components/NotFound'
import { CONFIG_ERROR } from './lib/apiClient'
import { ThemeProvider } from './theme/ThemeContext'
import './index.css'

// The app is a single view at "/". Any other path (the host rewrites every URL
// to index.html so deep links load) gets the 404 screen.
const path = window.location.pathname.replace(/\/+$/, '') || '/'
const isHome = path === '/' || path === '/index.html'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      {CONFIG_ERROR ? <ConfigError message={CONFIG_ERROR} /> : isHome ? <App /> : <NotFound path={window.location.pathname} />}
    </ThemeProvider>
  </StrictMode>,
)
