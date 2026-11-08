import type { Priority } from '@/theme/tokens'
import type { ScoreRow } from './types'

/**
 * Server-style query layer. The table never touches the full row array:
 * it asks for one page at a time with sort + filter applied here, exactly as
 * it would against a REST endpoint (`GET /scores?page=…&sort=…&q=…`).
 * Swap the body of `queryScores` for a fetch() when a real API exists.
 */
export interface ScoreQuery {
  pageIndex: number
  pageSize: number
  sort: { id: keyof ScoreRow; desc: boolean } | null
  q: string
  priorities: Priority[]
  exploitOnly: boolean
}

export interface ScorePage {
  rows: ScoreRow[]
  total: number
  pageCount: number
  tookMs: number
}

const LATENCY_MS = 120

export function filterRows(all: ScoreRow[], q: Pick<ScoreQuery, 'q' | 'priorities' | 'exploitOnly'>) {
  const needle = q.q.trim().toLowerCase()
  const prio = new Set(q.priorities)
  if (!needle && prio.size === 0 && !q.exploitOnly) return all
  return all.filter(
    (r) =>
      (prio.size === 0 || prio.has(r.priority)) &&
      (!q.exploitOnly || r.any_public_exploit === 1) &&
      (!needle ||
        r.cve_id.toLowerCase().includes(needle) ||
        r.assigner.toLowerCase().includes(needle) ||
        r.reasons.some((x) => x.signal.includes(needle))),
  )
}

export async function queryScores(all: ScoreRow[], q: ScoreQuery, signal?: AbortSignal): Promise<ScorePage> {
  const t0 = performance.now()
  await new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, LATENCY_MS)
    signal?.addEventListener('abort', () => {
      clearTimeout(t)
      reject(new DOMException('aborted', 'AbortError'))
    })
  })

  let rows = filterRows(all, q)

  if (q.sort && q.sort.id !== 'rank') {
    const { id, desc } = q.sort
    const dir = desc ? -1 : 1
    rows = [...rows].sort((a, b) => {
      const av = a[id]
      const bv = b[id]
      if (av == null && bv == null) return a.rank - b.rank
      if (av == null) return 1 // nulls last regardless of direction
      if (bv == null) return -1
      if (av < bv) return -dir
      if (av > bv) return dir
      return a.rank - b.rank
    })
  } else if (q.sort?.desc) {
    rows = [...rows].reverse() // source is already rank-ascending
  }

  const total = rows.length
  const start = q.pageIndex * q.pageSize
  return {
    rows: rows.slice(start, start + q.pageSize),
    total,
    pageCount: Math.max(1, Math.ceil(total / q.pageSize)),
    tookMs: Math.round(performance.now() - t0),
  }
}
