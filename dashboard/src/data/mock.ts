import { assignRanks, dummyScore } from '@/lib/scoring'
import type { ScoreRow } from '@/lib/types'
import { mulberry32 } from '@/lib/utils'

/**
 * Deterministic synthetic 2026 scoring snapshot (72,670 rows) matching
 * docs/INTERFACES.md. Replace with the real `outputs/scores_2026.csv`
 * via the judge upload flow — no code change needed.
 */
export const SAMPLE_SIZE = 72_670
export const SAMPLE_MODEL_VERSION = 'v0'

// [assigner, relative CVE volume]
const ASSIGNERS: [string, number][] = [
  ['mitre', 15], ['VulDB', 14], ['GitHub_M', 11], ['Wordfence', 10], ['patchstack', 9],
  ['Linux', 8], ['redhat', 5], ['microsoft', 4], ['cisco', 2.5], ['adobe', 2],
  ['google', 2], ['apple', 1.6], ['oracle', 1.6], ['fortinet', 1], ['ivanti', 0.6],
  ['vmware', 0.7], ['palo alto networks', 0.4], ['hackerone', 2], ['zdi', 1.8], ['jpcert', 1.2],
]
// Monthly publication weights Jan → Oct 2026 (volume keeps climbing).
const MONTH_WEIGHTS = [0.088, 0.086, 0.095, 0.094, 0.1, 0.098, 0.105, 0.108, 0.111, 0.115]

function pickWeighted<T>(items: [T, number][], r: number): T {
  const total = items.reduce((s, [, w]) => s + w, 0)
  let x = r * total
  for (const [v, w] of items) {
    if ((x -= w) <= 0) return v
  }
  return items[items.length - 1][0]
}

const MODEL_SIGNALS: [string, number | string][] = [
  ['cvss_network_vector', 'AV:N/AC:L/PR:N'],
  ['description_rce_terms', 1],
  ['vendor_kev_history', 0.12],
  ['cwe_kev_rate', 0.034],
  ['auth_bypass_terms', 1],
  ['edge_device_product', 1],
]

let cache: ScoreRow[] | null = null

export function generateSampleRows(): ScoreRow[] {
  if (cache) return cache
  const rand = mulberry32(2026)
  const monthItems = MONTH_WEIGHTS.map((w, i) => [i, w] as [number, number])
  const asOf = new Date(Date.UTC(2026, 10, 1))
  const rows: ScoreRow[] = new Array(SAMPLE_SIZE)

  for (let i = 0; i < SAMPLE_SIZE; i++) {
    const m = pickWeighted(monthItems, rand())
    const day = 1 + Math.floor(rand() * 28)
    const published = `2026-${String(m + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    const assigner = pickWeighted(ASSIGNERS, rand())

    // Exploit evidence is rare, and correlated: one PoC makes others likelier.
    const hot = rand() < 0.012
    const p = hot ? 0.4 : 0.0015
    const exploitdb = (rand() < p ? 1 : 0) as 0 | 1
    const metasploit = (rand() < p * 0.45 ? 1 : 0) as 0 | 1
    const nuclei = (rand() < p * 0.7 ? 1 : 0) as 0 | 1
    const poc_github = (rand() < p * 1.4 ? 1 : 0) as 0 | 1
    const any = (exploitdb || metasploit || nuclei || poc_github ? 1 : 0) as 0 | 1

    // EPSS: heavy-tailed, ~8% not yet scored.
    const epss =
      rand() < 0.08 ? null : Math.min(0.97, Math.round(Math.pow(rand(), hot ? 2.2 : 9) * 10000) / 10000 + 0.0004)

    const { score, reasons } = dummyScore(
      { cve_id: '', published, assigner, epss, exploitdb, metasploit, nuclei, poc_github, any_public_exploit: any },
      asOf,
    )
    // Model noise so ranks aren't a pure function of the visible features.
    const noise = (rand() - 0.5) * 2.6
    const logit = Math.log(score / (1 - score + 1e-9) + 1e-9) + noise
    const noisy = Math.round((1 / (1 + Math.exp(-logit))) * 1e6) / 1e6

    // The noise stands in for features the real model sees but this mock
    // doesn't (CVSS vector, CWE, description text…). Surface it as reasons.
    if (Math.abs(noise) > 0.4) {
      const [signal, value] = MODEL_SIGNALS[Math.floor(rand() * MODEL_SIGNALS.length)]
      reasons.push({
        signal,
        value,
        impact: Math.round(Math.min(0.9, Math.abs(noise) * (0.25 + rand() * 0.35)) * 1000) / 1000,
        direction: noise > 0 ? 'up' : 'down',
      })
      reasons.sort((a, b) => b.impact - a.impact)
      if (reasons.length > 3) reasons.length = 3
    }

    rows[i] = {
      cve_id: `CVE-2026-${String(10_000 + i * 3 + Math.floor(rand() * 3)).padStart(5, '0')}`,
      published,
      snapshot_month: published.slice(0, 7),
      assigner,
      score: noisy,
      rank: 0,
      percentile: 0,
      in_top500: 0,
      priority: 'P2',
      epss,
      exploitdb,
      metasploit,
      nuclei,
      poc_github,
      any_public_exploit: any,
      reasons,
      model_version: SAMPLE_MODEL_VERSION,
    }
  }

  // Normalise to a 0..1 ranking score so the top row reads near 1.0.
  const max = rows.reduce((m, r) => Math.max(m, r.score), 0) || 1
  for (const r of rows) r.score = Math.round((r.score / max) * 1000) / 1000 || 0.001

  cache = assignRanks(rows)
  return cache
}
