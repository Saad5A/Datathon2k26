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
  const geminiEval = (gemini.eval as Record<string, unknown> | undefined) ?? {}

  return (
    <WidgetCard
      title="Division of labor · Granite → Gemini"
      subtitle="Technical prioritization & embeddings vs executive synthesis & triage automation"
      info="Granite owns dense risk representation and technical rationale. Gemini ingests that output to produce executive briefs and containment playbooks. Audited ranking files stay read-only."
    >
      {error && <p className="px-1 text-sm text-sevfg-p0">{error}</p>}
      {!data && !error && <p className="px-1 text-sm text-fg-subtle">Loading model comparison…</p>}
      {data && (
        <div className="grid gap-4 text-sm md:grid-cols-2">
          <div className="rounded-md border border-line p-3">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
              IBM Granite · technical layer
            </h3>
            <p className="mt-1 font-mono text-xs text-fg-subtle">{String(granite.model_id ?? 'ibm/granite-embedding…')}</p>
            <ul className="mt-2 space-y-1 text-fg">
              <li>Role: embeddings + technical risk rationale</li>
              <li>Explanations: {fmtInt(Number(granite.n_explanations_loaded ?? 0))}</li>
              <li>Embedding tokens: {granite.embedding_tokens != null ? fmtInt(Number(granite.embedding_tokens)) : '—'}</li>
              <li>
                ΔAUC vs TF-IDF:{' '}
                {granite.mean_delta_auc_vs_tfidf != null
                  ? `${(Number(granite.mean_delta_auc_vs_tfidf) * 100).toFixed(2)} pt`
                  : '—'}
              </li>
            </ul>
          </div>
          <div className="rounded-md border border-line p-3">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
              Gemini · executive synthesis
            </h3>
            <p className="mt-1 font-mono text-xs text-fg-subtle">{String(gemini.model_id ?? 'gemini-2.5-flash')}</p>
            <ul className="mt-2 space-y-1 text-fg">
              <li>Role: executive brief + triage playbooks from Granite</li>
              <li>Linked syntheses: {fmtInt(Number(gemini.n_explanations_loaded ?? 0))}</li>
              <li>Eval pass rate: {geminiEval.overall_pass_rate != null ? `${geminiEval.overall_pass_rate}%` : '—'}</li>
              <li>
                Patch URL hallucination:{' '}
                {geminiEval.patch_url_hallucination_rate != null ? `${geminiEval.patch_url_hallucination_rate}%` : '—'}
              </li>
            </ul>
          </div>
          <p className="md:col-span-2 text-xs text-fg-subtle">
            {data.ranking_consistency ||
              'Both layers consume ML priority tiers; neither rewrites audited top500/scores baselines.'}
          </p>
        </div>
      )}
    </WidgetCard>
  )
}
