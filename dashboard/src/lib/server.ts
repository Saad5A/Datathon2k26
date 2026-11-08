import type { Priority } from '@/theme/tokens'
import { LIVE_API, fetchRankingPage, rankingItemToScoreRow } from './backend'
import type { ScoreRow } from './types'

/**
 * Server-style query layer. When VITE_API_URL points at the FastAPI backend,
 * pages come from GET /ranking/cves. Otherwise the in-memory demo/upload rows
 * are filtered locally (same contract as before).
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
  source?: 'api' | 'local'
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

async function queryScoresLocal(all: ScoreRow[], q: ScoreQuery, signal?: AbortSignal): Promise<ScorePage> {
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
      if (av == null) return 1
      if (bv == null) return -1
      if (av < bv) return -dir
      if (av > bv) return dir
      return a.rank - b.rank
    })
  } else if (q.sort?.desc) {
    rows = [...rows].reverse()
  }

  const total = rows.length
  const start = q.pageIndex * q.pageSize
  return {
    rows: rows.slice(start, start + q.pageSize),
    total,
    pageCount: Math.max(1, Math.ceil(total / q.pageSize)),
    tookMs: Math.round(performance.now() - t0),
    source: 'local',
  }
}

async function queryScoresApi(q: ScoreQuery, signal?: AbortSignal): Promise<ScorePage> {
  const t0 = performance.now()
  const sortId = q.sort?.id
  const sort =
    sortId === 'score' || sortId === 'cve_id' || sortId === 'rank' ? String(sortId) : 'rank'
  const page = await fetchRankingPage(
    {
      page: q.pageIndex + 1,
      limit: q.pageSize,
      search: q.q || undefined,
      sort,
      order: q.sort?.desc ? 'desc' : 'asc',
    },
    signal,
  )
  let rows = page.items.map((item) => rankingItemToScoreRow(item, page.total || 500))
  // Priority / exploit filters still applied client-side (API ranking page is CVE search + score).
  if (q.priorities.length || q.exploitOnly) {
    rows = filterRows(rows, { q: '', priorities: q.priorities, exploitOnly: q.exploitOnly })
  }
  return {
    rows,
    total: page.total,
    pageCount: Math.max(1, page.pages ?? Math.ceil(page.total / q.pageSize)),
    tookMs: Math.round(performance.now() - t0),
    source: 'api',
  }
}

export async function queryScores(all: ScoreRow[], q: ScoreQuery, signal?: AbortSignal): Promise<ScorePage> {
  // Live API mode never falls back to synthetic/mock rows — fail empty instead.
  if (LIVE_API) {
    try {
      return await queryScoresApi(q, signal)
    } catch (e) {
      if ((e as Error).name === 'AbortError') throw e
      return { rows: [], total: 0, pageCount: 1, tookMs: 0, source: 'api' }
    }
  }
  return queryScoresLocal(all, q, signal)
}
