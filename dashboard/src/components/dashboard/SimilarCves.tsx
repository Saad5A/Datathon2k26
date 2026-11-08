import { Loader2, Radar } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ApiError } from '@/lib/apiClient'
import {
  LIVE_API,
  fetchSimilarCves,
  type SimilarCvesResponse,
} from '@/lib/backend'
import { cn, fmtInt } from '@/lib/utils'

/**
 * Retrieval-only evidence panel: nearest CVEs by Granite description similarity.
 * Shared by the classic inspection drawer and the PancakeSec dashboard.
 * Never feeds a score or a ranking decision.
 */
export function SimilarCves({ cveId, className }: { cveId: string; className?: string }) {
  const [data, setData] = useState<SimilarCvesResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!LIVE_API) {
      setData(null)
      setError('The neighbour index needs the Model API (local demo has no server).')
      return
    }
    const ac = new AbortController()
    setLoading(true)
    setError(null)
    setData(null)
    fetchSimilarCves(cveId, 5, ac.signal)
      .then((payload) => {
        setData(payload)
        setLoading(false)
      })
      .catch((e) => {
        if ((e as Error).name === 'AbortError') return
        setError(
          e instanceof ApiError && (e.status === 404 || e.status === 503)
            ? `No indexed neighbours for ${cveId} yet.`
            : (e as Error).message,
        )
        setLoading(false)
      })
    return () => ac.abort()
  }, [cveId])

  return (
    <section className={cn('rounded-md border border-line bg-bg/40 p-3', className)}>
      <div className="mb-1 flex items-center gap-2">
        <Radar className="size-3.5 text-sevfg-low" aria-hidden />
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Nearest neighbours · IBM Granite
        </h3>
      </div>
      <p className="mb-3 text-[10px] leading-relaxed text-fg-subtle">
        Description similarity over the historical pool and the 2026 top 500. This is retrieval evidence, not a
        probability and not part of the submitted score.
      </p>
      {loading && (
        <p className="flex items-center gap-2 text-xs text-fg-muted">
          <Loader2 className="size-3.5 animate-spin" aria-hidden /> Retrieving neighbours…
        </p>
      )}
      {error && !loading && <p className="text-xs text-fg-subtle">{error}</p>}
      {data && !loading && data.similar.length > 0 && (
        <>
          <ul className="space-y-1.5">
            {data.similar.map((row) => (
              <li
                key={row.cve_id}
                className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 border-b border-line/70 pb-1.5 last:border-0 last:pb-0"
              >
                <span className="font-mono text-[11px] text-fg">{row.cve_id}</span>
                <span className="flex items-baseline gap-3 font-mono text-[10px] text-fg-muted">
                  {row.rank != null && <span>#{fmtInt(row.rank)}</span>}
                  <span>{row.published ?? row.scope ?? 'historical'}</span>
                  <span className="tabular text-fg">{row.similarity.toFixed(3)}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[9px] text-fg-subtle">
            {data.note ?? 'Similarity is not a prediction.'}
            {data.index?.model_id ? ` · ${data.index.model_id}` : ''}
            {data.index?.rows ? ` · ${fmtInt(data.index.rows)} vectors` : ''}
          </p>
        </>
      )}
      {data && !loading && data.similar.length === 0 && (
        <p className="text-xs text-fg-subtle">No neighbours returned for this CVE.</p>
      )}
    </section>
  )
}
