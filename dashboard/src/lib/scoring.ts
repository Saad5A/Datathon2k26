import type { Priority } from '@/theme/tokens'
import type { Reason, ScoreRow } from './types'

/**
 * Ranking rules shared by the sample generator, the client-side dummy scorer
 * and the normaliser for uploaded/API rows. See docs/INTERFACES.md.
 */
export const TOP_K = 500
export const P0_MIN_PERCENTILE = 99.85 // ≈ top 100 of 72,670
export const P1_MIN_PERCENTILE = 90

export function percentileFor(rank: number, n: number) {
  if (n <= 1) return 100
  return Math.round(1000 * (1 - (rank - 1) / n)) / 10
}

export function priorityFor(percentile: number): Priority {
  if (percentile >= P0_MIN_PERCENTILE) return 'P0'
  if (percentile >= P1_MIN_PERCENTILE) return 'P1'
  return 'P2'
}

/**
 * Sort by score desc (ties broken by cve_id for stability) and write
 * rank / percentile / in_top500 / priority. Mutates and returns `rows`.
 */
export function assignRanks(rows: ScoreRow[], opts: { keepPriority?: boolean } = {}) {
  rows.sort((a, b) => b.score - a.score || a.cve_id.localeCompare(b.cve_id))
  const n = rows.length
  rows.forEach((r, i) => {
    r.rank = i + 1
    r.percentile = percentileFor(r.rank, n)
    r.in_top500 = r.rank <= TOP_K ? 1 : 0
    if (!opts.keepPriority) r.priority = priorityFor(r.percentile)
  })
  return rows
}

/* ------------------------------------------------------------------------ */
/* Client-side dummy scorer                                                  */
/* ------------------------------------------------------------------------ */

/**
 * Historical KEV-rate priors for a handful of assigners. Unknown assigners
 * fall back to the global base rate. Illustrative values, not model output.
 */
const ASSIGNER_KEV_RATE: Record<string, number> = {
  microsoft: 0.071,
  cisco: 0.048,
  apple: 0.052,
  google: 0.039,
  fortinet: 0.083,
  'palo alto networks': 0.066,
  ivanti: 0.091,
  vmware: 0.044,
  adobe: 0.031,
  oracle: 0.018,
  mitre: 0.009,
  github_m: 0.006,
  vuldb: 0.003,
  wordfence: 0.002,
  patchstack: 0.001,
  linux: 0.004,
  redhat: 0.012,
}
const BASE_KEV_RATE = 0.005

export interface ScoringInput {
  cve_id: string
  published?: string
  assigner?: string
  epss?: number | null
  exploitdb?: 0 | 1
  metasploit?: 0 | 1
  nuclei?: 0 | 1
  poc_github?: 0 | 1
  any_public_exploit?: 0 | 1
}

const sigmoid = (x: number) => 1 / (1 + Math.exp(-x))
const round3 = (x: number) => Math.round(x * 1000) / 1000

/**
 * Transparent logistic stand-in for the real model so judges can see the
 * end-to-end flow without the Python server. Returns score + top reasons.
 */
export function dummyScore(input: ScoringInput, asOf = new Date()): { score: number; reasons: Reason[] } {
  const prior = ASSIGNER_KEV_RATE[(input.assigner ?? '').toLowerCase()] ?? BASE_KEV_RATE
  const epss = input.epss ?? null
  const anyExploit =
    input.any_public_exploit ??
    ((input.exploitdb || input.metasploit || input.nuclei || input.poc_github ? 1 : 0) as 0 | 1)

  let ageDays = 180
  if (input.published) {
    const t = Date.parse(input.published)
    if (!Number.isNaN(t)) ageDays = Math.max(0, (asOf.getTime() - t) / 86_400_000)
  }

  const terms: { signal: string; value: number; w: number }[] = [
    { signal: 'public_exploit_code', value: anyExploit, w: 1.6 * anyExploit },
    { signal: 'metasploit_module', value: input.metasploit ?? 0, w: 1.3 * (input.metasploit ?? 0) },
    { signal: 'nuclei_template', value: input.nuclei ?? 0, w: 0.9 * (input.nuclei ?? 0) },
    { signal: 'exploitdb_entry', value: input.exploitdb ?? 0, w: 0.6 * (input.exploitdb ?? 0) },
    { signal: 'poc_github_repos', value: input.poc_github ?? 0, w: 0.7 * (input.poc_github ?? 0) },
    { signal: 'epss_score', value: epss ?? 0, w: epss == null ? 0 : 4.2 * Math.sqrt(epss) - 0.4 },
    { signal: 'assigner_kev_rate', value: prior, w: 18 * (prior - BASE_KEV_RATE) },
    { signal: 'days_since_published', value: Math.round(ageDays), w: ageDays < 30 ? 0.35 : ageDays > 365 ? -0.4 : 0 },
  ]

  const logit = -5.2 + terms.reduce((s, t) => s + t.w, 0)
  const score = round3(sigmoid(logit))

  const totalAbs = terms.reduce((s, t) => s + Math.abs(t.w), 0) || 1
  const reasons: Reason[] = terms
    .filter((t) => Math.abs(t.w) > 0.05)
    .sort((a, b) => Math.abs(b.w) - Math.abs(a.w))
    .slice(0, 3)
    .map((t) => ({
      signal: t.signal,
      value: round3(t.value),
      impact: round3(Math.abs(t.w) / totalAbs),
      direction: t.w >= 0 ? 'up' : 'down',
    }))

  return { score, reasons }
}
