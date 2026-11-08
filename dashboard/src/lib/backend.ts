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
    fold1_delta_auc_granite_minus_tfidf?: number | null
    fold2_delta_auc_granite_minus_tfidf?: number | null
    mean_delta_auc_granite_minus_tfidf?: number | null
    prefer?: string | null
    rule?: string | null
    note?: string | null
  }
  granite_subset?: Record<string, unknown>
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

export interface ExplanationPayload {
  cve_id: string
  priority?: string | null
  rank?: number | null
  granite: {
    summary?: string | null
    rationale?: string | null
    provider?: string | null
    model_id?: string | null
    is_ai_generated?: boolean
    grounding_ok?: boolean
  } | null
  remediation: {
    steps: { step: string; detail: string }[]
    playbook: Record<string, unknown> | null
    is_ai_generated?: boolean
  }
  available: { explanation: boolean; playbook: boolean }
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

export async function fetchExplanation(cveId: string, signal?: AbortSignal): Promise<ExplanationPayload> {
  return apiJson<ExplanationPayload>(`/explanations/${encodeURIComponent(cveId)}`, { signal })
}
