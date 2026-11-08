import snapshot from '@/data/results_snapshot.json'
import { API_BASE } from './apiClient'

export type MetricKey = 'top500' | 'top250' | 'auc' | 'avg_precision' | 'median_rank'

export interface MetricCell {
  value: number | null
  claim: string
  verified: boolean
}

export interface ModelRow {
  key: string
  label: string
  short: string
  submitted: boolean
  metrics: Record<MetricKey, MetricCell>
}

export interface FoldRow {
  key: string
  label: string
  test_months: string | null
  test_rows: number | null
  positives: number | null
  models: ModelRow[]
}

export interface AblationFold {
  key: string
  auc: number | null
  top500: number | null
  top250: number | null
  avg_precision: number | null
  median_rank: number | null
  verified: boolean
}

export interface AblationRow {
  key: string
  label: string
  note: string
  folds: AblationFold[]
}

export interface BootstrapBlock {
  diff: number | null
  ci95: [number | null, number | null]
  claims: Record<'diff' | 'ci95_lo' | 'ci95_hi', string>
  /** True only when diff and both CI bounds are verified claims (read from the ledger at build/serve time). */
  verified: boolean
}

export interface ResultsPayload {
  generated_at: string
  submitted: {
    model: string
    base: string
    best_granite: string | null
    rule: string | null
    flag: string | null
    mean_auc: Record<string, number>
  }
  folds: FoldRow[]
  ablations: AblationRow[]
  significance: {
    /** Seed set 0, one entry per fold. */
    paired_bootstrap_vs_exploit_then_epss: {
      fold: string
      seed_set: number
      auc: BootstrapBlock
      top500_expected: BootstrapBlock
    }[]
    permutation: {
      fold: string
      mean: number | null
      sd: number | null
      max: number | null
      n_shuffles: number | null
    }
  }
  unseen_assigner: {
    fold: string
    definition: string | null
    rows: number | null
    positives: number | null
    auc: number | null
    top500_rows_from_subset: number | null
    top500_hits_from_subset: number | null
  }
  drift: {
    rows_2025_pool: number | null
    rows_2026_scoreboard: number | null
    assigners_2025: number | null
    assigners_2026: number | null
  }
  sources: { path: string; role: string }[]
  metric_labels: Record<string, string>
}

export const RESULTS_SNAPSHOT = snapshot as unknown as ResultsPayload

export class ResultsUnavailable extends Error {}

/** Same-origin `/api/results`; throws when the page must fall back to its bundled snapshot. */
export async function fetchResults(signal?: AbortSignal): Promise<ResultsPayload> {
  if (!API_BASE) throw new ResultsUnavailable('No API base configured.')
  const res = await fetch(`${API_BASE}/results`, { headers: { Accept: 'application/json' }, signal })
  if (!res.ok) throw new ResultsUnavailable(`/results responded ${res.status}.`)
  return (await res.json()) as ResultsPayload
}

export function cell(row: ModelRow | undefined, key: MetricKey): MetricCell {
  return row?.metrics[key] ?? { value: null, claim: '', verified: false }
}

export function modelOf(fold: FoldRow, key: string): ModelRow | undefined {
  return fold.models.find((model) => model.key === key)
}
