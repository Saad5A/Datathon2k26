import { useEffect, useState } from 'react'
import { WidgetCard } from '@/components/dashboard/WidgetCard'
import { fetchModelsComparison, type ModelsComparison } from '@/lib/backend'
import { fmtInt } from '@/lib/utils'

export function ModelComparisonCard() {
  const [data, setData] = useState<ModelsComparison | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const ac = new AbortController()
    fetchModelsComparison(ac.signal)
      .then((payload) => {
        setData(payload)
        setError(null)
      })
      .catch((e) => {
        if ((e as Error).name === 'AbortError') return
        setError((e as Error).message)
      })
    return () => ac.abort()
  }, [])

  const granite = data?.granite ?? {}
  const gemini = data?.gemini ?? {}
  const coverage = (granite.summary_coverage ?? {}) as Record<string, number | undefined>
  const counts = (granite.unaudited_file_counts ?? {}) as Record<string, number | undefined>

  return (
    <WidgetCard
      title="Where IBM Granite is used"
      subtitle="Embeddings in the ranking model; instruct summaries (AI-generated, unaudited)"
      info="Granite embeddings feed the ranking model's text score (submitted model G2), adopted by a pre-registered rule with no measurable gain. Granite instruct, run locally, wrote summaries for an earlier version of the ranking; some are template fallbacks. AI-generated text is unaudited."
    >
      {error && <p className="px-1 text-sm text-sevfg-p0">{error}</p>}
      {!data && !error && <p className="px-1 text-sm text-fg-subtle">Loading model comparison…</p>}
      {data && (
        <div className="grid gap-4 text-sm md:grid-cols-2">
          <div className="rounded-md border border-line p-3">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
              IBM Granite
            </h3>
            <ul className="mt-2 space-y-1 text-fg">
              <li>
                Embeddings (ranking text score):{' '}
                <span className="font-mono text-xs">{String(granite.embedding_model_id ?? '—')}</span>
              </li>
              <li>
                Instruct summaries:{' '}
                <span className="font-mono text-xs">{String(granite.instruct_model_id ?? '—')}</span> · covers{' '}
                {fmtInt(Number(coverage.current_top100_with_summary ?? 0))} of the current top{' '}
                {fmtInt(Number(coverage.current_top100 ?? 0))} (written for an earlier ranking version; file counts
                unaudited: {fmtInt(Number(counts.granite_summaries ?? 0))} AI-generated,{' '}
                {fmtInt(Number(counts.template_fallbacks ?? 0))} template)
              </li>
              <li className="text-xs text-fg-subtle">{String(granite.adoption_note ?? '')}</li>
            </ul>
          </div>
          <div className="rounded-md border border-line p-3">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
              Gemini · executive brief
            </h3>
            {gemini.model_id ? (
              <ul className="mt-2 space-y-1 text-fg">
                <li className="font-mono text-xs text-fg-subtle">{String(gemini.model_id)}</li>
                <li>Role: executive brief from the CVE description and the ranking model&apos;s reasons</li>
                <li>Briefs loaded: {fmtInt(Number(gemini.n_explanations_loaded ?? 0))}</li>
              </ul>
            ) : (
              <p className="mt-2 text-fg-subtle">No live Gemini output is loaded.</p>
            )}
          </div>
          <p className="md:col-span-2 text-xs text-fg-subtle">
            Neither model rewrites the audited top500 / scores files.
          </p>
        </div>
      )}
    </WidgetCard>
  )
}
