import { apiJson, API_BASE, DEMO_MODE } from '@/lib/apiClient'

export const LIVE_API = Boolean(API_BASE) && !DEMO_MODE

export interface BackendSummary {
  total_analyzed_cves: number | null
  ranking_rows: number
  risk_bands: { critical: number; high: number; med: number; low: number }
  multi_model?: { gemini_explanations?: number }
  load_errors?: string[]
}

export interface BackendCapabilities {
  upload_scoring?: boolean
  ranking?: boolean
  gemini_explanations?: boolean
}

export interface GeminiBrief {
  cve_id: string
  priority?: string | null
  rank?: number | null
  gemini?: {
    executive_summary?: string | null
    summary?: string | null
    model_id?: string | null
    provider?: string | null
    is_ai_generated?: boolean
    playbook?: {
      containment?: string | null
      remediation?: string | null
      verification?: string | null
    } | null
  } | null
  gemini_executive_summary?: string | null
  gemini_triage_playbook?: {
    containment?: string | null
    remediation?: string | null
    verification?: string | null
  } | null
  available?: { gemini?: boolean }
}

export function fetchBackendSummary(signal?: AbortSignal) {
  return apiJson<BackendSummary>('/stats/summary', { signal })
}

export function fetchBackendCapabilities(signal?: AbortSignal) {
  return apiJson<{ capabilities?: BackendCapabilities }>('/health', { signal })
}

export function fetchGeminiBrief(cveId: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ model: 'gemini' })
  return apiJson<GeminiBrief>(`/explanations/${encodeURIComponent(cveId)}?${query}`, { signal })
}
