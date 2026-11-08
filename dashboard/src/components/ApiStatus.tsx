import { useCallback, useEffect, useState } from 'react'
import { API_BASE, apiJson } from '@/lib/apiClient'
import { cn } from '@/lib/utils'

type State =
  | { kind: 'checking' }
  | { kind: 'online'; ms: number }
  | { kind: 'offline'; reason: string }
  | { kind: 'demo' }

const POLL_MS = 60_000

/** Footer indicator: GET {VITE_API_URL}/health. Colour is paired with text, never alone. */
export function ApiStatus() {
  const [state, setState] = useState<State>(API_BASE ? { kind: 'checking' } : { kind: 'demo' })

  const check = useCallback(async (signal?: AbortSignal) => {
    if (!API_BASE) return
    setState({ kind: 'checking' })
    const t0 = performance.now()
    try {
      await apiJson('/health', { signal, timeoutMs: 5_000, parse: 'none' })
      setState({ kind: 'online', ms: Math.round(performance.now() - t0) })
    } catch (e) {
      if ((e as Error).name === 'AbortError') return
      setState({ kind: 'offline', reason: (e as Error).message })
    }
  }, [])

  useEffect(() => {
    const ac = new AbortController()
    void check(ac.signal)
    const id = setInterval(() => void check(ac.signal), POLL_MS)
    return () => {
      ac.abort()
      clearInterval(id)
    }
  }, [check])

  const dot =
    state.kind === 'online' ? 'bg-emerald-500' : state.kind === 'offline' ? 'bg-sev-p0' : 'bg-sev-neutral'
  const label =
    state.kind === 'online'
      ? `API online · ${state.ms} ms`
      : state.kind === 'offline'
        ? 'API unreachable'
        : state.kind === 'checking'
          ? 'Checking API…'
          : 'Demo mode · no backend'
  const detail =
    state.kind === 'offline'
      ? `${state.reason} Click to retry.`
      : state.kind === 'demo'
        ? 'Running on sample data with in-browser scoring.'
        : 'Click to re-check now.'

  return (
    <button
      type="button"
      onClick={() => void check()}
      disabled={state.kind === 'demo' || state.kind === 'checking'}
      title={detail}
      aria-label={`${label}. ${detail}`}
      className="inline-flex items-center gap-2 rounded-md px-2 py-1 text-xs text-fg-muted hover:bg-raised disabled:cursor-default disabled:hover:bg-transparent"
    >
      <span className={cn('size-2 rounded-full', dot, state.kind === 'checking' && 'animate-pulse')} aria-hidden />
      <span role="status" aria-live="polite">
        {label}
      </span>
    </button>
  )
}
