import {
  Check,
  Copy,
  Cpu,
  Loader2,
  MessageSquare,
  Radar,
  Shield,
  Sparkles,
  Terminal,
  TrendingUp,
  Wallet,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  FEATURED_DEMO_CVE,
  LIVE_API,
  fetchExplanation,
  fetchSimilarCves,
  refineGeminiAction,
  type ExplanationPayload,
  type RefineActionResponse,
  type RefineActionType,
  type SimilarCvesResponse,
} from '@/lib/backend'
import { ApiError } from '@/lib/apiClient'
import { cn, fmtInt, fmtScore } from '@/lib/utils'
import type { Reason } from '@/lib/types'

export interface CveInspectionDrawerProps {
  cveId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

type UnifiedExplanation = ExplanationPayload

const QUICK_ACTIONS: {
  id: RefineActionType
  label: string
  icon: typeof Terminal
  accent: string
}[] = [
  {
    id: 'bash_script',
    label: 'Generate Bash Containment Script',
    icon: Terminal,
    accent: 'hover:border-sev-low/60 hover:bg-sev-low/10',
  },
  {
    id: 'business_risk',
    label: 'Estimate Business Downtime',
    icon: Wallet,
    accent: 'hover:border-sev-p1/60 hover:bg-sev-p1/10',
  },
  {
    id: 'granite_divergence',
    label: 'Why Granite Overruled CVSS',
    icon: TrendingUp,
    accent: 'hover:border-sev-p0/60 hover:bg-sev-p0/10',
  },
]

function CopyBlock({ content, format }: { content: string; format: 'bash' | 'prose' }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="relative mt-3 overflow-hidden rounded-md border border-line bg-raised/50">
      <div className="flex items-center justify-between border-b border-line px-3 py-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
          {format === 'bash' ? 'Terminal · copy-ready' : 'Gemini response'}
        </span>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-fg-muted hover:bg-surface hover:text-fg"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(content)
              setCopied(true)
              setTimeout(() => setCopied(false), 1400)
            } catch {
              /* ignore */
            }
          }}
        >
          {copied ? <Check className="size-3.5 text-sevfg-low" /> : <Copy className="size-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre
        className={cn(
          'max-h-64 overflow-auto p-3 text-[11px] leading-relaxed text-fg-muted',
          format === 'bash' && 'font-mono',
        )}
      >
        {content}
      </pre>
    </div>
  )
}

function SimilarCves({ cveId }: { cveId: string }) {
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
    <section className="rounded-md border border-line bg-bg/40 p-3">
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

export function CveInspectionDrawer({ cveId, open, onOpenChange }: CveInspectionDrawerProps) {
  const [data, setData] = useState<UnifiedExplanation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [showRawGranite, setShowRawGranite] = useState(false)
  const [refineLoading, setRefineLoading] = useState<RefineActionType | null>(null)
  const [refineResult, setRefineResult] = useState<RefineActionResponse | null>(null)
  const [refineError, setRefineError] = useState<string | null>(null)
  const [followUp, setFollowUp] = useState('')

  useEffect(() => {
    if (!open || !cveId) {
      setData(null)
      setError(null)
      setShowRawGranite(false)
      setRefineResult(null)
      setRefineError(null)
      setFollowUp('')
      setRefineLoading(null)
      return
    }
    const ac = new AbortController()
    setLoading(true)
    setError(null)
    setData(null)
    setShowRawGranite(false)
    setRefineResult(null)
    setRefineError(null)
    setFollowUp('')
    fetchExplanation(cveId, ac.signal, 'both')
      .then((payload) => {
        setData(payload)
        setLoading(false)
      })
      .catch((e) => {
        if ((e as Error).name === 'AbortError') return
        const msg =
          e instanceof ApiError && e.status === 404
            ? `No Granite/Gemini synthesis for ${cveId} yet.`
            : (e as Error).message
        setError(msg)
        setLoading(false)
      })
    return () => ac.abort()
  }, [open, cveId])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  const rawTech =
    data?.granite_technical_rationale || data?.granite?.summary || data?.granite?.rationale || null
  const techSummary = data?.gemini_technical_summary || data?.gemini?.technical_summary || null
  const executive =
    data?.gemini_executive_summary || data?.gemini?.executive_summary || data?.gemini?.summary || null
  const playbook = data?.gemini_triage_playbook || data?.gemini?.playbook || null
  const steps = [
    { step: 'Containment', detail: (playbook as { containment?: string } | null)?.containment },
    { step: 'Hotfix', detail: (playbook as { remediation?: string } | null)?.remediation },
    { step: 'Verification', detail: (playbook as { verification?: string } | null)?.verification },
  ].filter((s) => Boolean(s.detail)) as { step: string; detail: string }[]

  const reasons: Reason[] = useMemo(() => {
    const raw = data?.reasons
    if (!Array.isArray(raw)) return []
    return raw.map((r) => {
      const o = (r ?? {}) as Record<string, unknown>
      return {
        signal: String(o.signal ?? 'signal'),
        value: (o.value as number | string | null) ?? null,
        impact: typeof o.impact === 'number' ? o.impact : typeof o.value === 'number' ? Math.abs(o.value) : 0,
        direction: o.direction === 'down' ? 'down' : 'up',
      }
    })
  }, [data?.reasons])

  const runRefine = async (action: RefineActionType, userContext?: string) => {
    if (!cveId) return
    setRefineLoading(action)
    setRefineError(null)
    try {
      const res = await refineGeminiAction({
        cve_id: cveId,
        action_type: action,
        granite_rationale: rawTech ?? undefined,
        user_context: userContext,
      })
      setRefineResult(res)
    } catch (e) {
      setRefineError((e as Error).message)
    } finally {
      setRefineLoading(null)
    }
  }

  const onFollowUp = (e: FormEvent) => {
    e.preventDefault()
    const q = followUp.trim()
    if (!q) return
    void runRefine('custom_refinement', q)
  }

  if (!open) return null

  const featured = cveId === FEATURED_DEMO_CVE || cveId === 'CVE-2026-10001'

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
      <button
        type="button"
        className="absolute inset-0 animate-fade-in bg-black/60 backdrop-blur-[2px]"
        aria-label="Close inspection drawer"
        onClick={() => onOpenChange(false)}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="cve-drawer-title"
        className="relative z-10 flex h-full w-full max-w-xl animate-drawer-in flex-col border-l border-line-strong bg-surface shadow-2xl sm:max-w-2xl"
      >
        <header className="flex shrink-0 items-start gap-3 border-b border-line px-4 py-3">
          <span className="mt-0.5 flex size-9 items-center justify-center rounded-md bg-sev-p0/15 text-sevfg-p0">
            <Sparkles className="size-4" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id="cve-drawer-title" className="font-mono text-base font-semibold text-fg">
                {cveId ?? 'CVE'}
              </h2>
              {data?.priority && <Badge className="shrink-0">{data.priority}</Badge>}
              {featured && (
                <span className="rounded border border-sev-p0/50 bg-sev-p0/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sevfg-p0">
                  Featured Demo
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-fg-subtle">
              CVE Triage Workstation · Granite technical core → Gemini executive orchestration
            </p>
            {data?.rank != null && (
              <p className="mt-1 font-mono text-[11px] text-fg-muted">
                Rank #{fmtInt(data.rank)}
                {data.score != null ? ` · score ${fmtScore(data.score)}` : ''}
                {data.epss != null ? ` · EPSS ${data.epss.toFixed(3)}` : ''}
                {data.any_public_exploit === 1 ? ' · public exploit' : ''}
              </p>
            )}
          </div>
          <Button variant="ghost" size="icon" aria-label="Close" onClick={() => onOpenChange(false)}>
            <X className="size-4" />
          </Button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          {loading && (
            <p className="flex items-center gap-2 text-sm text-fg-muted">
              <Loader2 className="size-4 animate-spin" aria-hidden /> Loading dual-provider briefing…
            </p>
          )}
          {error && !loading && (
            <p className="rounded-md border border-sev-p0/40 bg-sev-p0/10 px-3 py-2 text-sm text-sevfg-p0">
              {error}
            </p>
          )}

          {cveId && <SimilarCves key={cveId} cveId={cveId} />}

          {data && !loading && (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                {/* Card A — IBM Granite */}
                <section className="rounded-md border border-line bg-bg/40 p-3">
                  <div className="mb-2 flex items-center gap-2">
                    <Cpu className="size-3.5 text-sevfg-low" aria-hidden />
                    <h3 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                      IBM Granite · watsonx
                    </h3>
                  </div>
                  <dl className="mb-2 grid grid-cols-2 gap-2 text-[11px]">
                    <div className="rounded border border-line px-2 py-1.5">
                      <dt className="text-fg-subtle">Exploit score</dt>
                      <dd className="font-mono text-fg">{data.score != null ? fmtScore(data.score) : '—'}</dd>
                    </div>
                    <div className="rounded border border-line px-2 py-1.5">
                      <dt className="text-fg-subtle">Public exploit</dt>
                      <dd className="font-mono text-fg">{data.any_public_exploit === 1 ? 'Yes' : 'No'}</dd>
                    </div>
                  </dl>
                  {reasons.length > 0 && (
                    <div className="mb-2">
                      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                        Latent attribution
                      </p>
                      <ul className="space-y-1">
                        {reasons.slice(0, 4).map((r) => (
                          <li key={r.signal} className="flex justify-between gap-2 font-mono text-[10px] text-fg-muted">
                            <span className="truncate">{r.signal}</span>
                            <span>{String(r.value ?? '∅')}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {techSummary && (
                    <p className="mb-2 text-xs leading-relaxed text-fg">{techSummary}</p>
                  )}
                  {rawTech ? (
                    <div>
                      <button
                        type="button"
                        className="text-[11px] font-medium text-fg-muted underline-offset-2 hover:text-fg hover:underline"
                        onClick={() => setShowRawGranite((v) => !v)}
                        aria-expanded={showRawGranite}
                      >
                        {showRawGranite ? 'Hide' : 'Show'} raw Granite rationale
                      </button>
                      {showRawGranite && (
                        <p className="mt-2 rounded border border-line bg-raised/40 p-2 font-mono text-[10px] leading-relaxed text-fg-muted">
                          {rawTech}
                        </p>
                      )}
                    </div>
                  ) : (
                    !techSummary && <p className="text-xs text-fg-subtle">No Granite rationale for this CVE.</p>
                  )}
                </section>

                {/* Card B — Gemini Executive */}
                <section className="rounded-md border border-line bg-bg/40 p-3">
                  <div className="mb-2 flex items-center gap-2">
                    <Shield className="size-3.5 text-sevfg-p1" aria-hidden />
                    <h3 className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                      Gemini · executive synthesis
                    </h3>
                  </div>
                  {executive ? (
                    <p className="mb-3 text-xs leading-relaxed text-fg">{executive}</p>
                  ) : (
                    <p className="mb-3 text-xs text-fg-subtle">No Gemini executive brief yet.</p>
                  )}
                  <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                    Triage checklist
                  </p>
                  {steps.length === 0 ? (
                    <p className="text-xs text-fg-subtle">No triage steps available.</p>
                  ) : (
                    <ol className="list-decimal space-y-2 pl-4 text-xs">
                      {steps.map((s) => (
                        <li key={s.step}>
                          <span className="font-medium text-fg">{s.step}</span>
                          <p className="mt-0.5 text-fg-muted">{s.detail}</p>
                        </li>
                      ))}
                    </ol>
                  )}
                </section>
              </div>

              {/* Quick-action engine */}
              <section className="rounded-md border border-line bg-bg/40 p-3">
                <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                  Interactive Gemini quick-actions
                </h3>
                <p className="mb-3 text-[11px] text-fg-subtle">
                  Contextual Triage Orchestrator — refinements grounded in Granite vectors (cached for demo
                  latency).
                </p>
                <div className="grid gap-2 sm:grid-cols-3">
                  {QUICK_ACTIONS.map((a) => {
                    const Icon = a.icon
                    const busy = refineLoading === a.id
                    return (
                      <button
                        key={a.id}
                        type="button"
                        disabled={Boolean(refineLoading)}
                        onClick={() => void runRefine(a.id)}
                        className={cn(
                          'group flex min-h-[4.5rem] flex-col items-start gap-1.5 rounded-md border border-line-strong bg-surface px-3 py-2.5 text-left transition-all duration-200',
                          'hover:-translate-y-0.5 hover:shadow-md disabled:opacity-60',
                          a.accent,
                        )}
                      >
                        <Icon className="size-4 text-fg-muted transition-colors group-hover:text-fg" />
                        <span className="text-[11px] font-medium leading-snug text-fg">
                          {busy ? 'Synthesizing…' : a.label}
                        </span>
                      </button>
                    )
                  })}
                </div>

                {refineLoading && (
                  <p className="mt-3 flex items-center gap-2 text-xs text-fg-muted animate-pulse-soft">
                    <Loader2 className="size-3.5 animate-spin" aria-hidden />
                    Gemini synthesizing Granite vector context…
                  </p>
                )}
                {refineError && (
                  <p className="mt-3 rounded border border-sev-p0/40 bg-sev-p0/10 px-2 py-1.5 text-xs text-sevfg-p0">
                    {refineError}
                  </p>
                )}
                {refineResult && !refineLoading && (
                  <CopyBlock
                    content={refineResult.content}
                    format={refineResult.format === 'bash' ? 'bash' : 'prose'}
                  />
                )}
                {refineResult?.cached && (
                  <p className="mt-1.5 text-[10px] text-fg-subtle">Served from refine cache · 0 ms demo path</p>
                )}

                <form onSubmit={onFollowUp} className="mt-4 flex gap-2">
                  <label className="relative min-w-0 flex-1">
                    <span className="sr-only">Ask Gemini follow-up</span>
                    <MessageSquare className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-fg-subtle" />
                    <input
                      value={followUp}
                      onChange={(e) => setFollowUp(e.target.value)}
                      placeholder="Ask Gemini follow-up… e.g. What if we can’t patch before Monday?"
                      className="h-9 w-full rounded-md border border-line-strong bg-bg pl-8 pr-2 text-xs text-fg placeholder:text-fg-subtle"
                    />
                  </label>
                  <Button type="submit" size="sm" disabled={!followUp.trim() || Boolean(refineLoading)}>
                    Ask
                  </Button>
                </form>
              </section>
            </>
          )}
        </div>
      </aside>
    </div>
  )
}
