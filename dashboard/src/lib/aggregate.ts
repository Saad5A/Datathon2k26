import type { Priority } from '@/theme/tokens'
import { TOP_K } from './scoring'
import { EXPLOIT_FLAGS, EXPLOIT_FLAG_LABEL, type ScoreRow } from './types'

export interface MonthPoint {
  month: string
  published: number
  flagged: number // in top-500
  exploit: number // any public exploit
  p0: number
}

export interface Summary {
  total: number
  months: MonthPoint[]
  priorityAll: Record<Priority, number>
  priorityTop: Record<Priority, number>
  top500ExploitShare: number
  top500MedianEpss: number | null
  overallExploitShare: number
  topAssigners: { name: string; count: number; share: number }[]
  topSignals: { name: string; count: number }[]
  exploitFlagsTop: { name: string; count: number }[]
}

const median = (xs: number[]) => {
  if (!xs.length) return null
  const s = [...xs].sort((a, b) => a - b)
  const m = s.length >> 1
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

/** One pass over the dataset → everything the overview widgets need. */
export function summarize(rows: ScoreRow[]): Summary {
  const byMonth = new Map<string, MonthPoint>()
  const priorityAll: Record<Priority, number> = { P0: 0, P1: 0, P2: 0 }
  const priorityTop: Record<Priority, number> = { P0: 0, P1: 0, P2: 0 }
  const assigners = new Map<string, number>()
  const signals = new Map<string, number>()
  const flags = new Map<string, number>()
  const topEpss: number[] = []
  let topExploit = 0
  let topN = 0
  let allExploit = 0

  for (const r of rows) {
    const key = r.snapshot_month || 'unknown'
    let mp = byMonth.get(key)
    if (!mp) byMonth.set(key, (mp = { month: key, published: 0, flagged: 0, exploit: 0, p0: 0 }))
    mp.published++
    if (r.any_public_exploit) {
      mp.exploit++
      allExploit++
    }
    if (r.priority === 'P0') mp.p0++
    priorityAll[r.priority]++

    if (r.rank <= TOP_K) {
      topN++
      mp.flagged++
      priorityTop[r.priority]++
      assigners.set(r.assigner, (assigners.get(r.assigner) ?? 0) + 1)
      if (r.any_public_exploit) topExploit++
      if (r.epss != null) topEpss.push(r.epss)
      for (const f of EXPLOIT_FLAGS) if (r[f]) flags.set(f, (flags.get(f) ?? 0) + 1)
      const lead = r.reasons[0]
      if (lead) signals.set(lead.signal, (signals.get(lead.signal) ?? 0) + 1)
    }
  }

  const months = [...byMonth.values()].sort((a, b) => a.month.localeCompare(b.month))

  return {
    total: rows.length,
    months,
    priorityAll,
    priorityTop,
    top500ExploitShare: topN ? (100 * topExploit) / topN : 0,
    top500MedianEpss: median(topEpss),
    overallExploitShare: rows.length ? (100 * allExploit) / rows.length : 0,
    topAssigners: [...assigners.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name, count]) => ({ name, count, share: topN ? count / topN : 0 })),
    topSignals: [...signals.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name, count]) => ({ name, count })),
    exploitFlagsTop: EXPLOIT_FLAGS.map((f) => ({ name: EXPLOIT_FLAG_LABEL[f], count: flags.get(f) ?? 0 })).sort(
      (a, b) => b.count - a.count,
    ),
  }
}
