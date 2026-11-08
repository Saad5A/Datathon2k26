/**
 * The single place the frontend talks to the backend.
 *
 * Base URL comes from VITE_API_URL (inlined by Vite at BUILD time, so changing
 * it on the host requires a redeploy). Special value `demo` runs without a
 * backend: sample data only, in-browser scoring.
 */

export type ApiErrorKind = 'timeout' | 'network' | 'http' | 'parse' | 'unconfigured'

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status?: number

  constructor(message: string, kind: ApiErrorKind, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
  }
}

const raw = (import.meta.env.VITE_API_URL ?? '').trim()

export const DEMO_MODE = raw.toLowerCase() === 'demo'

function resolveBase(): { base: string | null; error: string | null } {
  if (!raw) return { base: null, error: 'VITE_API_URL is not set.' }
  if (DEMO_MODE) return { base: null, error: null }
  try {
    const u = new URL(raw)
    if (u.protocol !== 'http:' && u.protocol !== 'https:') throw new Error('protocol')
    return { base: raw.replace(/\/+$/, ''), error: null }
  } catch {
    return { base: null, error: `VITE_API_URL must be an absolute http(s) URL or "demo" (got "${raw.slice(0, 80)}").` }
  }
}

const resolved = resolveBase()

/** Backend origin without trailing slash, or null in demo mode / misconfiguration. */
export const API_BASE: string | null = resolved.base
/** Non-null when the app must not start (shown as a full-screen error). */
export const CONFIG_ERROR: string | null = resolved.error

export interface ApiRequest {
  method?: 'GET' | 'POST'
  body?: string
  signal?: AbortSignal
  /** Covers connect + headers + body. Default 15 s. */
  timeoutMs?: number
  /** `none` accepts any 2xx without reading a JSON body (health checks). */
  parse?: 'json' | 'none'
}

export async function apiJson<T = unknown>(path: string, opts: ApiRequest = {}): Promise<T> {
  if (!API_BASE) throw new ApiError('No backend is configured (demo mode).', 'unconfigured')
  const { method = 'GET', body, signal, timeoutMs = 15_000, parse = 'json' } = opts

  const ac = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    ac.abort()
  }, timeoutMs)
  const relay = () => ac.abort()
  signal?.addEventListener('abort', relay)

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body,
      signal: ac.signal,
    })
    if (!res.ok) {
      const detail = await res.text().catch(() => '')
      throw new ApiError(
        `${path} responded ${res.status}${detail ? `: ${detail.slice(0, 160)}` : ''}`,
        'http',
        res.status,
      )
    }
    if (parse === 'none') return undefined as T
    if (!(res.headers.get('content-type') ?? '').includes('json')) {
      throw new ApiError(`${path} did not return JSON.`, 'parse')
    }
    return (await res.json()) as T
  } catch (e) {
    if (e instanceof ApiError) throw e
    if (timedOut) throw new ApiError(`${path} timed out after ${Math.round(timeoutMs / 1000)} s.`, 'timeout')
    if ((e as Error).name === 'AbortError') throw e
    if (e instanceof SyntaxError) throw new ApiError(`${path} returned malformed JSON.`, 'parse')
    throw new ApiError(`Could not reach the backend at ${API_BASE}.`, 'network')
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', relay)
  }
}
