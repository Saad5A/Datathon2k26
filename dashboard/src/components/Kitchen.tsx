import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { Pause, Play } from 'lucide-react'
import { API_BASE } from '@/lib/apiClient'
import { fetchBackendCapabilities } from '@/lib/backend'
import type { KitchenUpload } from '@/hooks/useKitchenUpload'
import type { CookingStep } from '@/lib/cooking'

const Scene = lazy(() => import('./KitchenScene'))
const labels: Record<CookingStep, string> = {
  ready: 'Your next batch starts here.', pouring: 'Pouring the ingredients…', cooking: 'A little patience. Let it cook.',
  flipping: 'Giving the signals a fresh perspective.', plating: 'Putting it all together.', plated: 'Your batch is ready.',
}
export function Kitchen({controller, onUpload, onServed, settled, onReview, hasResults}: {
  controller: KitchenUpload; onUpload: () => void; onServed: (batchId: number) => void;
  settled: boolean; onReview: () => void; hasResults: boolean;
}) {
  const [paused, setPaused] = useState(false)
  const [uploadScoring, setUploadScoring] = useState(Boolean(API_BASE))
  const [step, setStep] = useState<CookingStep>(settled ? 'plated' : 'ready')
  const { phase } = controller
  const busy = phase.kind === 'parsing' || phase.kind === 'scoring'
  useEffect(() => {
    if (!API_BASE) { setUploadScoring(false); return }
    const ac = new AbortController()
    fetchBackendCapabilities(ac.signal).then((response) => {
      const supported = response.capabilities?.upload_scoring
      setUploadScoring(supported === true)
      if (supported === false && controller.engine === 'api') controller.setEngine('client')
    }).catch(() => { if (!ac.signal.aborted) { setUploadScoring(false); if (controller.engine === 'api') controller.setEngine('client') } })
    return () => ac.abort()
  }, [controller.engine, controller.setEngine])
  const active = busy || (phase.kind === 'done' && !settled && step !== 'plated')
  const presentation = useCallback((next: CookingStep) => setStep(next), [])
  const status = phase.kind === 'error' ? 'This batch needs another look.'
    : phase.kind === 'idle' ? 'Your next batch starts here.' : labels[step]
  return <section className="cooking-workspace" aria-label="Interactive cooking station">
    <div className="cooking-stage"><Suspense fallback={<div className="station-loading">Preparing your kitchen…</div>}><Scene stage={phase.kind} batchId={controller.batchId} paused={paused} settled={settled} onUpload={onUpload} onServed={onServed} onStep={presentation}/></Suspense>
      <button className="motion-control" onClick={() => setPaused(value => !value)} aria-label={paused ? 'Resume animation' : 'Pause animation'}>{paused ? <Play size={14}/> : <Pause size={14}/>}<span>{paused ? 'Resume' : 'Pause'}</span></button>
      <span className="orbit-hint">Drag gently to look around</span>
    </div>
    <div className="cooking-status"><p role="status" aria-live="polite"><i className={active && !paused ? 'active' : ''}/>{status}</p>
      {busy && <div className="processing-detail">{phase.kind === 'parsing' ? 'Reading your file' : phase.engine === 'api' ? 'Waiting for the model API' : `${phase.done.toLocaleString()} / ${phase.total.toLocaleString()} rows processed`}<button onClick={controller.reset}>Cancel</button></div>}
      {phase.kind === 'done' && !settled && <button className="results-available" onClick={onReview}>Results are ready · view now →</button>}
      {hasResults && (phase.kind !== 'done' || settled) && <button className="previous-results" onClick={onReview}>Return to your review queue →</button>}
      {phase.kind === 'error' && <div className="inline-kitchen-error" role="alert"><p>{phase.message}</p><div>{phase.file && <button onClick={() => void controller.run(phase.file!)}>Retry batch</button>}{phase.canFallback && phase.file && <button onClick={() => { controller.setEngine('client'); void controller.run(phase.file!, 'client') }}>Use local demo</button>}<button onClick={onUpload}>Choose another file</button></div></div>}
    </div>
    <div className="kitchen-quiet-options"><button className="try-batch" disabled={busy} onClick={() => void controller.trySample()}>Just exploring? Try a sample batch ↗</button><span className="engine-disclosure">{controller.engine === 'api' ? 'Model API · selected files are sent to the configured scoring server' : 'Local demo · files stay in your browser; supplied scores are preserved unless re-scored'}</span>
      <details className="processing-options"><summary>Processing options</summary><div><label htmlFor="engine-choice">Scoring engine</label><select id="engine-choice" disabled={busy} value={controller.engine} onChange={event => controller.setEngine(event.target.value as 'client' | 'api')}><option value="client">Local demo / pre-scored input</option><option value="api" disabled={!API_BASE || !uploadScoring}>Model API{!API_BASE ? ' · unavailable' : !uploadScoring ? ' · no scoring capability' : ''}</option></select>{controller.engine === 'client' && <label className="rescore-option"><input type="checkbox" disabled={busy} checked={controller.rescore} onChange={event => controller.setRescore(event.target.checked)}/> Re-score existing scores with the demo model</label>}</div></details>
    </div>
  </section>
}
