/**
 * Live FastAPI bridge (VITE_API_URL = http://localhost:8000/api).
 * Paths are relative to that base — do not prefix with /api again.
 */
import { API_BASE, DEMO_MODE, apiJson } from './apiClient'
import type { Reason, ScoreRow } from './types'
import type { Priority } from '@/theme/tokens'

export const LIVE_API = Boolean(API_BASE) && !DEMO_MODE

export interface StatsSummary {
  total_analyzed_cves: number | null
  ranking_rows: number
  scores_rows: number
  risk_bands: { critical: number; high: number; med: number; low: number }
  token_usage: {
    estimated_tokens_consumed: number | null
    truncate_tokens?: number | null
    provider?: string | null
    model_id?: string | null
    subset?: boolean | null
    n_embedded_this_run?: number | null
    n_unique_texts?: number | null
    dimension?: number | null
    created_utc?: string | null
  }
  comparison?: {
    n_vectors?: number | null
    embeddings_files?: string[]
    folds_present?: string[]
    note?: string | null
  }
  granite_subset?: Record<string, unknown>
  /** Verified claim p6.granite_subset.n_vectors, read by the server at request time; null unless verified. */
  watsonx_subset?: { id: string; value: number; verified_by?: string | null } | null
  multi_model?: {
    gemini_explanations?: number
    granite_summary_coverage?: { current_top100_with_summary?: number; current_top100?: number; note?: string }
  }
  sources?: Record<string, string>
  load_errors?: string[]
}

export interface RankingItem {
  cve_id: string
  rank: number | null
  score: number | null
  priority: string | null
  risk_band?: string | null
  published?: string | null
  snapshot_month?: string | null
  assigner?: string | null
  epss?: number | null
  any_public_exploit?: number | null
  in_top500?: number | null
  reasons?: unknown
}

export interface RankingPage {
  total: number
  page: number
  limit: number
  pages?: number
  items: RankingItem[]
}

export interface ProviderNarrative {
  summary?: string | null
  rationale?: string | null
  executive_summary?: string | null
  why_this_rank?: string | null
  suggested_action?: string | null
  /** "granite" = Granite instruct output; "template" = deterministic fallback, not AI-generated. */
  source?: string | null
  label?: string | null
  audited?: boolean
  provider?: string | null
  model_id?: string | null
  is_ai_generated?: boolean
  grounding_ok?: boolean
  playbook?: Record<string, unknown> | null
  remediation_steps?: { step: string; detail: string }[]
}

export interface ExplanationPayload {
  cve_id: string
  priority?: string | null
  rank?: number | null
  score?: number | null
  epss?: number | null
  any_public_exploit?: number | null
  reasons?: unknown
  model?: 'granite' | 'gemini' | 'both'
  gemini_executive_summary?: string | null
  gemini_triage_playbook?: {
    containment?: string | null
    remediation?: string | null
    verification?: string | null
  } | null
  granite: ProviderNarrative | null
  gemini?: ProviderNarrative | null
  remediation: {
    steps: { step: string; detail: string }[]
    playbook: Record<string, unknown> | null
    is_ai_generated?: boolean
  }
  available: {
    explanation: boolean
    playbook: boolean
    granite?: boolean
    gemini?: boolean
  }
}

export type RefineActionType =
  | 'bash_script'
  | 'business_risk'
  | 'granite_divergence'
  | 'custom_refinement'

export interface RefineActionResponse {
  cve_id: string
  action_type: RefineActionType
  content: string
  format: 'bash' | 'prose'
  cached: boolean
  source: string
  provider: string
  is_ai_generated?: boolean
  label?: string
  role: string
  grounding: string
}

/** Rank-1 featured demo CVE (audited top500). Smoke ID CVE-2026-10001 is refine-cache only. */
export const FEATURED_DEMO_CVE = 'CVE-2026-10523'

export interface ModelsComparison {
  baseline?: string
  granite: Record<string, unknown>
  gemini: Record<string, unknown>
  head_to_head?: Record<string, unknown>
  latency?: Record<string, unknown>
  token_economics?: Record<string, unknown>
  ranking_consistency?: string
  explanation_style?: Record<string, string>
  qualitative_depth?: Record<string, number>
  sources?: string[]
}

function asPriority(p: string | null | undefined): Priority {
  if (p === 'P0' || p === 'P1' || p === 'P2') return p
  return 'P2'
}

function mapReasons(raw: unknown): Reason[] {
  if (!Array.isArray(raw)) return []
  return raw.map((r) => {
    const o = (r ?? {}) as Record<string, unknown>
    const value = o.value
    const impact =
      typeof o.impact === 'number'
        ? o.impact
        : typeof o.value === 'number'
          ? Math.abs(o.value)
          : 0
    const direction = o.direction === 'down' ? 'down' : 'up'
    return {
      signal: String(o.signal ?? 'signal'),
      value: (value as number | string | null) ?? null,
      impact,
      direction,
    }
  })
}

/** Map a FastAPI ranking item into the dashboard ScoreRow shape. */
export function rankingItemToScoreRow(item: RankingItem, totalHint = 500): ScoreRow {
  const rank = item.rank ?? 0
  const score = item.score ?? 0
  const percentile = totalHint > 1 && rank > 0 ? Math.max(0, 100 * (1 - (rank - 1) / totalHint)) : 0
  return {
    cve_id: item.cve_id,
    published: item.published ?? '',
    snapshot_month: item.snapshot_month ?? '',
    assigner: item.assigner ?? '',
    score,
    rank,
    percentile,
    in_top500: item.in_top500 === 1 || (rank > 0 && rank <= 500) ? 1 : 0,
    priority: asPriority(item.priority),
    epss: item.epss ?? null,
    exploitdb: 0,
    metasploit: 0,
    nuclei: 0,
    poc_github: 0,
    any_public_exploit: item.any_public_exploit === 1 ? 1 : 0,
    reasons: mapReasons(item.reasons),
    model_version: 'results/scores_2026.csv',
  }
}

export async function fetchStatsSummary(signal?: AbortSignal): Promise<StatsSummary> {
  return apiJson<StatsSummary>('/stats/summary', { signal })
}

export async function fetchRankingPage(
  opts: {
    page?: number
    limit?: number
    search?: string
    min_score?: number
    sort?: string
    order?: 'asc' | 'desc'
  },
  signal?: AbortSignal,
): Promise<RankingPage> {
  const qs = new URLSearchParams()
  qs.set('page', String(opts.page ?? 1))
  qs.set('limit', String(opts.limit ?? 50))
  if (opts.search?.trim()) qs.set('search', opts.search.trim())
  if (opts.min_score != null) qs.set('min_score', String(opts.min_score))
  if (opts.sort) qs.set('sort', opts.sort)
  if (opts.order) qs.set('order', opts.order)
  return apiJson<RankingPage>(`/ranking/cves?${qs}`, { signal })
}

export async function fetchExplanation(
  cveId: string,
  signal?: AbortSignal,
  model: 'granite' | 'gemini' | 'both' = 'both',
): Promise<ExplanationPayload> {
  const qs = new URLSearchParams({ model })
  return apiJson<ExplanationPayload>(`/explanations/${encodeURIComponent(cveId)}?${qs}`, { signal })
}

export async function fetchModelsComparison(signal?: AbortSignal): Promise<ModelsComparison> {
  return apiJson<ModelsComparison>('/models/comparison', { signal })
}

/* ------------------------------------------------------------------ */
/* Retrieval neighbours (description similarity, not a prediction)    */
/* ------------------------------------------------------------------ */

export interface SimilarCve {
  cve_id: string
  similarity: number
  score?: number | null
  rank?: number | null
  published?: string | null
  scope?: string
}

export interface SimilarCvesResponse {
  cve_id: string
  top_k: number
  similar: SimilarCve[]
  index?: {
    model_id?: string | null
    dimension?: number | null
    rows?: number | null
    purpose?: string | null
  }
  note?: string
}

export function fetchSimilarCves(
  cveId: string,
  topK = 5,
  signal?: AbortSignal,
): Promise<SimilarCvesResponse> {
  return apiJson<SimilarCvesResponse>(
    `/ranking/similar/${encodeURIComponent(cveId)}?top_k=${topK}`,
    { signal },
  )
}

/* ------------------------------------------------------------------ */
/* Kitchen bridge aliases (used by the pancake upload/results flow)   */
/* ------------------------------------------------------------------ */

export type BackendSummary = StatsSummary

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

export function fetchBackendSummary(signal?: AbortSignal): Promise<BackendSummary> {
  return apiJson<BackendSummary>('/stats/summary', { signal })
}

export function fetchBackendCapabilities(signal?: AbortSignal): Promise<{ capabilities?: BackendCapabilities }> {
  return apiJson<{ capabilities?: BackendCapabilities }>('/health', { signal })
}

export function fetchGeminiBrief(cveId: string, signal?: AbortSignal): Promise<GeminiBrief> {
  const query = new URLSearchParams({ model: 'gemini' })
  return apiJson<GeminiBrief>(`/explanations/${encodeURIComponent(cveId)}?${query}`, { signal })
}

export async function refineGeminiAction(
  body: {
    cve_id: string
    action_type: RefineActionType
    user_context?: string
  },
  signal?: AbortSignal,
): Promise<RefineActionResponse> {
  return apiJson<RefineActionResponse>('/gemini/refine-action', {
    method: 'POST',
    body: JSON.stringify(body),
    signal,
    timeoutMs: 20_000,
  })
}
