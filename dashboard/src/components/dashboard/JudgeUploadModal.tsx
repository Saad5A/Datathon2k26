import { AlertTriangle, CheckCircle2, FileUp, FlaskConical, Loader2, Server, Upload, Cpu } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type DragEvent, type ReactNode } from 'react'
import { PriorityBadge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { DEFAULT_PREDICT_URL, predict } from '@/lib/api'
import { IngestError, normalizeStreaming, readRecords, type RawRecord } from '@/lib/parse'
import { TOP_K } from '@/lib/scoring'
import type { Dataset, ScoreRow } from '@/lib/types'
import { cn, fmtInt, fmtScore } from '@/lib/utils'
import { priorityColor } from '@/theme/tokens'

type Engine = 'client' | 'api'
type Phase =
  | { kind: 'idle' }
  | { kind: 'parsing'; file: File }
  | { kind: 'scoring'; file: File; done: number; total: number; leaders: ScoreRow[]; engine: Engine }
  | { kind: 'done'; file: File; rows: ScoreRow[]; warnings: string[]; preScored: boolean; engine: Engine; ms: number }
  | { kind: 'error'; message: string; file?: File; canFallback: boolean }

const MAX_BYTES = 50 * 1024 * 1024
const ACCEPT = '.csv,.json,text/csv,application/json'

export interface JudgeUploadModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onApply: (ds: Dataset) => void
}

export function JudgeUploadModal({ open, onOpenChange, onApply }: JudgeUploadModalProps) {
  const [engine, setEngine] = useState<Engine>('client')
  const [endpoint, setEndpoint] = useState(DEFAULT_PREDICT_URL)
  const [rescore, setRescore] = useState(false)
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!open) {
      abortRef.current?.abort()
      setPhase({ kind: 'idle' })
      setDragging(false)
    }
  }, [open])

  const run = useCallback(
    async (file: File, eng: Engine = engine) => {
      abortRef.current?.abort()
      const ac = new AbortController()
      abortRef.current = ac
      const t0 = performance.now()

      if (file.size > MAX_BYTES) {
        setPhase({ kind: 'error', message: `File is ${(file.size / 1e6).toFixed(1)} MB; the limit is 50 MB.`, file, canFallback: false })
        return
      }

      try {
        setPhase({ kind: 'parsing', file })
        const records: RawRecord[] = await readRecords(file)
        if (!records.length) throw new IngestError('File contains no rows.')

        if (eng === 'api') {
          setPhase({ kind: 'scoring', file, done: 0, total: records.length, leaders: [], engine: eng })
          const rows = await predict(endpoint, records, ac.signal)
          // Reveal the server's ranking progressively so the leaderboard animates in.
          for (let i = 1; i <= Math.min(10, rows.length); i++) {
            if (ac.signal.aborted) return
            setPhase({ kind: 'scoring', file, done: Math.round((i / 10) * rows.length), total: rows.length, leaders: rows.slice(0, i), engine: eng })
            await new Promise((r) => setTimeout(r, 40))
          }
          setPhase({ kind: 'done', file, rows, warnings: [], preScored: true, engine: eng, ms: performance.now() - t0 })
          return
        }

        const summary = await normalizeStreaming(
          records,
          rescore ? 'rescore' : 'auto',
          (p) => setPhase({ kind: 'scoring', file, engine: eng, ...p }),
          { signal: ac.signal },
        )
        setPhase({ kind: 'done', file, engine: eng, ms: performance.now() - t0, ...summary })
      } catch (e) {
        if ((e as Error).name === 'AbortError') return
        setPhase({
          kind: 'error',
          message: e instanceof IngestError ? e.message : `Unexpected error: ${(e as Error).message}`,
          file,
          canFallback: eng === 'api',
        })
      }
    },
    [engine, endpoint, rescore],
  )

  const pick = (files: FileList | null) => {
    const f = files?.[0]
    if (f) void run(f)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    pick(e.dataTransfer.files)
  }

  const trySample = async () => {
    try {
      const res = await fetch('/sample_judge_input.csv')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      void run(new File([blob], 'sample_judge_input.csv', { type: 'text/csv' }))
    } catch (e) {
      setPhase({ kind: 'error', message: `Could not load the bundled sample: ${(e as Error).message}`, canFallback: false })
    }
  }

  const apply = () => {
    if (phase.kind !== 'done') return
    onApply({
      id: `${phase.file.name}-${Date.now()}`,
      name: phase.file.name,
      source: phase.engine === 'api' ? 'upload-api' : 'upload-client',
      rows: phase.rows,
      loadedAt: new Date(),
    })
    onOpenChange(false)
  }

  const busy = phase.kind === 'parsing' || phase.kind === 'scoring'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="judge-desc">
        <div className="border-b border-line px-6 py-4 pr-12">
          <DialogTitle>Evaluate a dataset</DialogTitle>
          <DialogDescription id="judge-desc">
            Upload CVEs as CSV or JSON. Rows are scored, ranked and loaded into every widget on the dashboard.
          </DialogDescription>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">
          {/* Engine */}
          <fieldset disabled={busy}>
            <legend className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">Scoring engine</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              <EngineOption
                active={engine === 'client'}
                onClick={() => setEngine('client')}
                icon={<Cpu />}
                title="In-browser"
                body="Transparent logistic stand-in. No server needed; nothing leaves this machine."
              />
              <EngineOption
                active={engine === 'api'}
                onClick={() => setEngine('api')}
                icon={<Server />}
                title="Model API"
                body="POST rows to the trained model and render its ranking."
              />
            </div>
            {engine === 'api' ? (
              <label className="mt-3 flex items-center gap-2 text-xs text-fg-muted">
                Endpoint
                <input
                  value={endpoint}
                  onChange={(e) => setEndpoint(e.target.value)}
                  className="h-8 flex-1 rounded-md border border-line-strong bg-bg px-2 font-mono text-xs text-fg"
                  spellCheck={false}
                />
              </label>
            ) : (
              <label className="mt-3 flex items-center gap-2 text-xs text-fg-muted">
                <input type="checkbox" checked={rescore} onChange={(e) => setRescore(e.target.checked)} className="accent-sev-low" />
                Re-score even if the file already has a <code className="font-mono text-fg">score</code> column
              </label>
            )}
          </fieldset>

          {/* Drop zone / progress */}
          {phase.kind === 'idle' || phase.kind === 'error' ? (
            <>
              <div
                onDragOver={(e) => {
                  e.preventDefault()
                  setDragging(true)
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={cn(
                  'flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors',
                  dragging ? 'border-sev-low bg-sev-low/10' : 'border-line-strong',
                )}
              >
                <FileUp className={cn('size-8', dragging ? 'text-sev-low' : 'text-fg-subtle')} aria-hidden />
                <div>
                  <p className="font-medium text-fg">Drop a .csv or .json file</p>
                  <p className="mt-1 text-xs text-fg-subtle">
                    Needs <code className="font-mono">cve_id</code>. Uses <code className="font-mono">published, assigner, epss, exploitdb, metasploit, nuclei, poc_github</code> when present. Up to 50 MB.
                  </p>
                </div>
                <div className="flex flex-wrap justify-center gap-2">
                  <Button variant="primary" size="sm" onClick={() => inputRef.current?.click()}>
                    <Upload /> Choose file
                  </Button>
                  <Button variant="outline" size="sm" onClick={trySample}>
                    <FlaskConical /> Try sample input
                  </Button>
                </div>
                <input
                  ref={inputRef}
                  type="file"
                  accept={ACCEPT}
                  className="sr-only"
                  onChange={(e) => {
                    pick(e.target.files)
                    e.target.value = ''
                  }}
                />
              </div>
              {phase.kind === 'error' && (
                <div role="alert" className="flex gap-3 rounded-md border border-sev-p0/40 bg-sev-p0/10 p-3 text-sm">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-sev-p0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-fg">{phase.message}</p>
                    {phase.canFallback && phase.file && (
                      <Button
                        className="mt-2"
                        size="sm"
                        onClick={() => {
                          setEngine('client')
                          void run(phase.file!, 'client')
                        }}
                      >
                        Score in browser instead
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <LiveRanking phase={phase} />
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-line px-6 py-3">
          <p className="text-xs text-fg-subtle">
            {phase.kind === 'done'
              ? `${fmtInt(phase.rows.length)} CVEs ranked in ${Math.round(phase.ms)} ms`
              : 'Files are processed locally unless Model API is selected.'}
          </p>
          <div className="flex gap-2">
            {phase.kind === 'done' && (
              <Button variant="ghost" size="sm" onClick={() => setPhase({ kind: 'idle' })}>
                Upload another
              </Button>
            )}
            {busy && (
              <Button variant="ghost" size="sm" onClick={() => { abortRef.current?.abort(); setPhase({ kind: 'idle' }) }}>
                Cancel
              </Button>
            )}
            <Button variant="danger" size="sm" disabled={phase.kind !== 'done'} onClick={apply}>
              Load into dashboard
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function EngineOption({ active, onClick, icon, title, body }: { active: boolean; onClick: () => void; icon: ReactNode; title: string; body: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'flex gap-3 rounded-md border p-3 text-left transition-colors [&>svg]:mt-0.5 [&>svg]:size-4 [&>svg]:shrink-0',
        active ? 'border-fg/60 bg-raised' : 'border-line-strong hover:bg-raised/60',
      )}
    >
      {icon}
      <span>
        <span className="block font-medium text-fg">{title}</span>
        <span className="block text-xs text-fg-muted">{body}</span>
      </span>
    </button>
  )
}

function LiveRanking({ phase }: { phase: Extract<Phase, { kind: 'parsing' | 'scoring' | 'done' }> }) {
  const leaders = phase.kind === 'scoring' ? phase.leaders : phase.kind === 'done' ? phase.rows.slice(0, 10) : []
  const pct = phase.kind === 'scoring' ? (100 * phase.done) / Math.max(1, phase.total) : phase.kind === 'done' ? 100 : 0
  const label =
    phase.kind === 'parsing'
      ? 'Parsing file…'
      : phase.kind === 'scoring'
        ? phase.engine === 'api'
          ? phase.leaders.length ? 'Receiving ranking…' : 'Waiting for model server…'
          : `Scoring ${fmtInt(phase.done)} / ${fmtInt(phase.total)}`
        : 'Ranking complete'

  const counts =
    phase.kind === 'done'
      ? phase.rows.reduce(
          (acc, r) => ({ ...acc, [r.priority]: acc[r.priority] + 1, top: acc.top + (r.rank <= TOP_K ? 1 : 0) }),
          { P0: 0, P1: 0, P2: 0, top: 0 },
        )
      : null

  return (
    <div className="space-y-4">
      <div>
        <div className="mb-1.5 flex items-center justify-between text-xs">
          <span className="flex items-center gap-2 font-medium text-fg">
            {phase.kind === 'done' ? (
              <CheckCircle2 className="size-4 text-emerald-500" />
            ) : (
              <Loader2 className="size-4 animate-spin text-fg-muted" />
            )}
            {label}
          </span>
          <span className="max-w-[50%] truncate font-mono text-fg-subtle">{phase.file.name}</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-raised" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
          <div
            className={cn('h-full rounded-full bg-sev-low transition-[width] duration-150', phase.kind === 'parsing' && 'w-1/3 animate-pulse')}
            style={phase.kind === 'parsing' ? undefined : { width: `${pct}%` }}
          />
        </div>
      </div>

      {counts && (
        <div className="grid grid-cols-4 gap-2">
          {(['P0', 'P1', 'P2'] as const).map((p) => (
            <div key={p} className="rounded-md border border-line px-3 py-2">
              <PriorityBadge priority={p} />
              <div className="tabular mt-1 font-mono text-lg font-semibold">{fmtInt(counts[p])}</div>
            </div>
          ))}
          <div className="rounded-md border border-line px-3 py-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">Top {TOP_K}</span>
            <div className="tabular mt-1 font-mono text-lg font-semibold">{fmtInt(counts.top)}</div>
          </div>
        </div>
      )}

      <div>
        <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          {phase.kind === 'done' ? 'Top 10' : 'Provisional leaders'}
        </h3>
        <ol className="divide-y divide-line overflow-hidden rounded-md border border-line">
          {leaders.length === 0 &&
            Array.from({ length: 5 }).map((_, i) => (
              <li key={i} className="h-10 px-3 py-3">
                <div className="h-4 animate-pulse rounded bg-raised" style={{ width: `${80 - i * 10}%` }} />
              </li>
            ))}
          {leaders.map((r, i) => (
            <li key={r.cve_id} className="flex h-10 animate-row-in items-center gap-3 px-3" style={{ animationDelay: `${i * 15}ms` }}>
              <span className="tabular w-6 font-mono text-xs text-fg-subtle">{i + 1}</span>
              <span className="flex-1 truncate font-mono text-sm font-medium text-fg">{r.cve_id}</span>
              <span className="hidden truncate text-xs text-fg-muted sm:block sm:max-w-[160px]">{r.assigner}</span>
              <span className="h-1.5 w-16 overflow-hidden rounded-full bg-raised" aria-hidden>
                <span className="block h-full rounded-full" style={{ width: `${r.score * 100}%`, backgroundColor: phase.kind === 'done' ? priorityColor[r.priority] : 'currentColor' }} />
              </span>
              <span className="tabular w-12 text-right font-mono text-xs text-fg">{fmtScore(r.score)}</span>
              {phase.kind === 'done' && <PriorityBadge priority={r.priority} />}
            </li>
          ))}
        </ol>
      </div>

      {phase.kind === 'done' && (phase.warnings.length > 0 || phase.preScored) && (
        <ul className="space-y-1 text-xs text-fg-muted">
          {phase.preScored && phase.engine === 'client' && (
            <li>• File already contained scores; ranking uses them as-is. Tick “Re-score” to run the in-browser model instead.</li>
          )}
          {phase.warnings.map((w) => (
            <li key={w} className="text-sev-p2">• {w}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

