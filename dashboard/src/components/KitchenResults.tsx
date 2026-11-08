import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { RankedTable, type TableFilters } from '@/components/dashboard/RankedTable'
import { WidgetCard } from '@/components/dashboard/WidgetCard'
import { LIVE_API, fetchBackendSummary, fetchGeminiBrief, type BackendSummary, type GeminiBrief } from '@/lib/backend'
import { ApiError } from '@/lib/apiClient'
import type { Dataset } from '@/lib/types'

function BackendSnapshot() {
  const [data, setData] = useState<BackendSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!LIVE_API) return
    const ac = new AbortController()
    fetchBackendSummary(ac.signal).then(setData).catch((reason) => {
      if ((reason as Error).name !== 'AbortError') setError((reason as Error).message)
    })
    return () => ac.abort()
  }, [])

  if (!LIVE_API) return <p className="backend-note">Connect the FastAPI backend to see its ranking summary and Gemini briefs.</p>
  if (error) return <p className="backend-note" role="status">Backend summary unavailable: {error}</p>
  if (!data) return <p className="backend-note" role="status">Loading backend summary…</p>

  return <div className="backend-snapshot" aria-label="Backend ranking summary">
    <div><span>Reference ranking</span><strong>{data.ranking_rows > 0 ? 'Connected' : 'Not loaded'}</strong></div>
    <div><span>Gemini briefs</span><strong>{(data.multi_model?.gemini_explanations ?? 0) > 0 ? 'Connected' : 'Not loaded'}</strong></div>
    <div><span>Upload scoring</span><strong>{LIVE_API ? 'Model API · enabled' : 'Local demo'}</strong></div>
  </div>
}

function GeminiPanel({ cveId }: { cveId: string | null }) {
  const [brief, setBrief] = useState<GeminiBrief | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!cveId) { setBrief(null); setError(null); return }
    if (!LIVE_API) { setBrief(null); setError('Gemini briefs need the FastAPI backend.'); return }
    const ac = new AbortController()
    setLoading(true); setBrief(null); setError(null)
    fetchGeminiBrief(cveId, ac.signal).then(setBrief).catch((reason) => {
      if ((reason as Error).name === 'AbortError') return
      setError(reason instanceof ApiError && reason.status === 404
        ? `No Gemini brief is available from the backend for ${cveId}.`
        : (reason as Error).message)
    }).finally(() => { if (!ac.signal.aborted) setLoading(false) })
    return () => ac.abort()
  }, [cveId])

  if (!cveId) return <p className="backend-note">Expand a CVE and open its Gemini brief for backend-provided context.</p>
  const gemini = brief?.gemini
  const summary = brief?.gemini_executive_summary || gemini?.executive_summary || gemini?.summary
  const playbook = brief?.gemini_triage_playbook || gemini?.playbook
  const hasGeminiProviderMetadata = gemini?.is_ai_generated === true && Boolean(gemini.provider && gemini.model_id)
  const steps = [
    ['Containment', playbook?.containment],
    ['Remediation', playbook?.remediation],
    ['Verification', playbook?.verification],
  ].filter((step): step is [string, string] => Boolean(step[1]))

  return <div className="gemini-brief" aria-live="polite">
    <div className="gemini-brief-heading"><Sparkles size={16} aria-hidden/><div><strong>{cveId}</strong><span>{hasGeminiProviderMetadata ? `${gemini?.provider} · AI-generated` : 'Source metadata unavailable'}</span></div>
      {gemini?.model_id && <code>{gemini.model_id}</code>}
    </div>
    {loading && <p className="backend-note">Loading brief from backend…</p>}
    {error && !loading && <p className="backend-note" role="status">{error}</p>}
    {brief && !loading && <>
      {summary ? <p className="gemini-summary">{summary}</p> : <p className="backend-note">No executive summary in the backend response.</p>}
      {steps.length > 0 && <ol className="gemini-steps">{steps.map(([label, detail]) => <li key={label}><strong>{label}</strong><span>{detail}</span></li>)}</ol>}
    </>}
  </div>
}

export function KitchenResults({ dataset, warnings }: { dataset: Dataset; warnings: string[] }) {
  const [filters, setFilters] = useState<TableFilters>({ q: '', priorities: [], exploitOnly: false })
  const [selectedCve, setSelectedCve] = useState<string | null>(null)

  return <>
    <BackendSnapshot />
    {warnings.length > 0 && <ul className="batch-warnings" aria-label="Upload warnings">{warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>}
    <div className="results-columns">
      <div className="scroll-mt-20"><WidgetCard title="Review queue" subtitle="Ranked rows from this batch · expand a row for its supplied signals" bodyClassName="px-0">
        <RankedTable rows={dataset.rows} filters={filters} onFiltersChange={setFilters} datasetKey={dataset.id} onSelectCve={setSelectedCve}/>
      </WidgetCard></div>
      <WidgetCard title="Gemini briefing" subtitle="Available summaries are fetched from the backend">
        <GeminiPanel cveId={selectedCve}/>
      </WidgetCard>
    </div>
  </>
}
