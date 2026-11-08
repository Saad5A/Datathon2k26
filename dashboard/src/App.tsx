import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, Download } from 'lucide-react'
import { Kitchen } from '@/components/Kitchen'
import { KitchenResults } from '@/components/KitchenResults'
import { ApiStatus } from '@/components/ApiStatus'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useKitchenUpload } from '@/hooks/useKitchenUpload'
import { toCsv } from '@/lib/parse'
import type { Dataset } from '@/lib/types'
import './kitchen.css'

export default function App() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [view, setView] = useState<'kitchen' | 'results'>('kitchen')
  const [servedBatch, setServedBatch] = useState(-1)
  const heading = useRef<HTMLHeadingElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const upload = useKitchenUpload(setDataset)
  const current = useRef({ batchId: upload.batchId, phase: upload.phase.kind, view })
  current.current = { batchId: upload.batchId, phase: upload.phase.kind, view }
  useEffect(() => { heading.current?.focus(); window.scrollTo({ top: 0, behavior: 'instant' }) }, [view])
  useEffect(() => { if (upload.phase.kind === 'done') setWarnings(upload.phase.warnings) }, [upload.phase])

  const showResults = () => {
    if (!dataset) return
    if (upload.phase.kind === 'done') setServedBatch(upload.batchId)
    setView('results')
  }
  const served = useCallback((batchId: number) => {
    const state = current.current
    if (state.batchId !== batchId || state.phase !== 'done' || state.view !== 'kitchen') return
    setServedBatch(batchId)
    setView('results')
  }, [])
  const anotherBatch = () => { upload.reset(); setView('kitchen') }
  const exportCsv = () => {
    if (!dataset) return
    const url = URL.createObjectURL(new Blob([toCsv(dataset.rows)], { type: 'text/csv' }))
    const link = document.createElement('a'); link.href = url
    link.download = `${dataset.name.replace(/\.(csv|json)$/i, '')}_ranked.csv`; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const source = dataset?.isSample
    ? dataset.source === 'upload-api' ? 'Synthetic input · model API · unaudited' : 'Synthetic sample · local demo'
    : dataset?.source === 'upload-api' ? 'Model API · unaudited' : 'Local upload · unaudited'

  return <TooltipProvider><div className="story-app">
    <header className="story-header"><a href="#" onClick={event => { event.preventDefault(); setView('kitchen') }} className="story-brand"><img src="/pancakess-mark.svg" alt=""/><span><strong>pancakess</strong><small>Predictive Analytics Network for Cybersecurity Assessment,<br/>Knowledge, and Exploitation Software System</small></span></a>
      {view !== 'kitchen' && <button onClick={() => setView('kitchen')}><ArrowLeft size={14}/> Back to kitchen</button>}
    </header>
    <main>
      {view === 'kitchen' ? <>
        <h1 className="sr-only" ref={heading} tabIndex={-1}>pancakess — Predictive Analytics Network for Cybersecurity Assessment, Knowledge, and Exploitation Software System</h1>
        <Kitchen controller={upload} onUpload={() => fileInput.current?.click()} onServed={served} settled={servedBatch === upload.batchId} onReview={showResults} hasResults={!!dataset}/>
      </> : dataset && <section className="results-screen">
        <div className="results-title"><div className="served-mark" aria-hidden="true"><span/></div><div><span className="story-eyebrow">YOUR BATCH, SERVED.</span><h1 ref={heading} tabIndex={-1}>Ready for a closer look.</h1><p>{dataset.name} <span>· {source}</span></p></div><div className="result-actions"><button onClick={exportCsv}><Download size={15}/> Export ranking</button><button className="cook-again" onClick={anotherBatch}>Cook another batch ↗</button></div></div>
        <KitchenResults key={dataset.id} dataset={dataset} warnings={warnings}/>
      </section>}
    </main>
    <footer className="story-footer"><span>Priority scores rank review urgency; they are not exploit probabilities.</span><ApiStatus/></footer>
    <input ref={fileInput} type="file" accept=".csv,.json,text/csv,application/json" hidden aria-label="Upload CVE dataset" onChange={event => {
      const file = event.target.files?.[0]
      if (file) { setView('kitchen'); void upload.run(file) }
      event.target.value = ''
    }}/>
  </div></TooltipProvider>
}
