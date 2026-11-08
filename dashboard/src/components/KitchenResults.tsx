import { useEffect, useState } from 'react'
import { RankedTable, type TableFilters } from '@/components/dashboard/RankedTable'
import { CveInspectionDrawer } from '@/components/dashboard/CveInspectionDrawer'
import { WidgetCard } from '@/components/dashboard/WidgetCard'
import { LIVE_API, fetchExplanation, type ExplanationPayload } from '@/lib/backend'
import type { Dataset, ScoreRow } from '@/lib/types'

function SignalPanel({ row }: { row: ScoreRow | null }) {
  if (!row) {
    return <p className="backend-note">Select a CVE in the review queue to inspect the signals supplied with its ranking.</p>
  }
  return <div className="signal-panel" aria-live="polite">
    <div className="signal-heading"><div><strong>{row.cve_id}</strong><span>Rank {row.rank} · {row.priority} · score {row.score.toFixed(3)}</span></div><code>{row.model_version}</code></div>
    <p className="signal-note">Signals are supplied with the ranking row. They explain ordering, not a probability of exploitation.</p>
    {row.reasons.length > 0 ? <ol className="signal-reasons">{row.reasons.map((reason, i) => <li key={i}><strong>{reason.signal.replace(/_/g, ' ')}</strong><span>{reason.direction === 'up' ? 'raises priority' : 'lowers priority'}{reason.value != null ? ` · ${String(reason.value)}` : ''}</span><i style={{ width: `${Math.max(4, Math.round(reason.impact * 100))}%` }} /></li>)}</ol> : <p className="backend-note">This row was pre-scored; no signal breakdown was supplied.</p>}
  </div>
}

function GraniteNote({ cveId }: { cveId: string | null }) {
  const [payload, setPayload] = useState<ExplanationPayload | null>(null)
  const [missing, setMissing] = useState(false)
  useEffect(() => {
    if (!cveId || !LIVE_API) { setPayload(null); setMissing(false); return }
    const ac = new AbortController()
    setMissing(false)
    fetchExplanation(cveId, ac.signal, 'granite').then((response) => {
      if (response.granite) setPayload(response)
      else { setPayload(null); setMissing(true) }
    }).catch((error) => {
      if ((error as Error).name === 'AbortError') return
      setPayload(null); setMissing(true)
    })
    return () => ac.abort()
  }, [cveId])
  if (!cveId) return null
  if (!LIVE_API) return null
  if (missing) return <p className="backend-note">No IBM Granite note is available for this CVE.</p>
  if (!payload?.granite) return null
  const g = payload.granite
  return <div className="granite-note" aria-live="polite">
    <div className="granite-note-heading"><strong>IBM Granite technical note</strong><span>{g.provider || 'Granite'} · {g.model_id || 'model id unavailable'}</span></div>
    {g.grounding_ok === false && <p className="backend-note">Grounding check reported a warning; use the source record.</p>}
    <p>{g.summary || 'No summary was supplied in the Granite artifact.'}</p>
  </div>
}

export function KitchenResults({ dataset, warnings }: { dataset: Dataset; warnings: string[] }) {
  const [filters, setFilters] = useState<TableFilters>({ q: '', priorities: [], exploitOnly: false })
  const [selectedCve, setSelectedCve] = useState<string | null>(null)
  const [inspectOpen, setInspectOpen] = useState(false)

  return <>
    {warnings.length > 0 && <ul className="batch-warnings" aria-label="Upload warnings">{warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>}
    <div className="results-columns">
      <div className="scroll-mt-20"><WidgetCard title="Review queue" subtitle="Ranked rows from this batch · expand a row for its supplied signals" bodyClassName="px-0">
        <RankedTable rows={dataset.rows} filters={filters} onFiltersChange={setFilters} datasetKey={dataset.id} onSelectCve={setSelectedCve}/>
      </WidgetCard></div>
      <WidgetCard title="Signal rationale" subtitle="Why this row sits where it does">
        <SignalPanel row={dataset.rows.find((row) => row.cve_id === selectedCve) ?? null}/>
        <GraniteNote cveId={selectedCve}/>
        {selectedCve && <button type="button" className="mt-3 text-left text-[10px] font-semibold uppercase tracking-wider text-[#426b54] underline underline-offset-4" onClick={() => setInspectOpen(true)}>Inspect full brief →</button>}
      </WidgetCard>
    </div>
    <CveInspectionDrawer cveId={selectedCve} open={inspectOpen} onOpenChange={setInspectOpen}/>
  </>
}
