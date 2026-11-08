import { lazy, StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { ConfigError } from './components/ConfigError'
import { NotFound } from './components/NotFound'
import { CONFIG_ERROR } from './lib/apiClient'
import { ThemeProvider } from './theme/ThemeContext'
import './index.css'

// Charts are heavy and only /results needs them, so that page is a separate chunk.
const ResultsPage = lazy(() =>
  import('./components/results/ResultsPage').then((module) => ({ default: module.ResultsPage })),
)

// The host rewrites every URL to index.html so deep links load. "/" is the
// kitchen; "/results" is the evidence sheet; anything else is a 404.
const path = window.location.pathname.replace(/\/+$/, '') || '/'
const isHome = path === '/' || path === '/index.html'
const isResults = path === '/results'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      {CONFIG_ERROR ? (
        <ConfigError message={CONFIG_ERROR} />
      ) : isHome ? (
        <App />
      ) : isResults ? (
        <Suspense
          fallback={
            <div className="mx-auto max-w-3xl px-6 py-24 text-sm text-fg-muted">Loading the evidence sheet…</div>
          }
        >
          <ResultsPage />
        </Suspense>
      ) : (
        <NotFound path={window.location.pathname} />
      )}
    </ThemeProvider>
  </StrictMode>,
)

