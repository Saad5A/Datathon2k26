import { Loader2, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { fetchExplanation, type ExplanationPayload } from '@/lib/backend'
import { ApiError } from '@/lib/apiClient'
import { fmtInt } from '@/lib/utils'

export interface ExplanationModalProps {
  cveId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Unified payload may include top-level linked fields from the dual-provider API. */
type UnifiedExplanation = ExplanationPayload & {
  granite_technical_rationale?: string | null
  gemini_technical_summary?: string | null
  gemini_executive_summary?: string | null
  gemini_triage_playbook?: {
    containment?: string | null
    remediation?: string | null
    verification?: string | null
  } | null
  gemini?: ExplanationPayload['gemini'] & { technical_summary?: string | null }
}

export function ExplanationModal({ cveId, open, onOpenChange }: ExplanationModalProps) {
  const [data, setData] = useState<UnifiedExplanation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [showRawGranite, setShowRawGranite] = useState(false)

  useEffect(() => {
    if (!open || !cveId) {
      setData(null)
      setError(null)
      setShowRawGranite(false)
      return
    }
    const ac = new AbortController()
    setLoading(true)
    setError(null)
    setData(null)
    setShowRawGranite(false)
    fetchExplanation(cveId, ac.signal, 'both')
      .then((payload) => {
        setData(payload as UnifiedExplanation)
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

  const rawTech =
    data?.granite_technical_rationale || data?.granite?.summary || data?.granite?.rationale || null
  const techSummary =
    data?.gemini_technical_summary || data?.gemini?.technical_summary || null
  const executive =
    data?.gemini_executive_summary || data?.gemini?.executive_summary || data?.gemini?.summary || null
  const playbook = data?.gemini_triage_playbook || data?.gemini?.playbook || null
  const steps = [
    { step: 'containment', detail: playbook?.containment },
    { step: 'remediation', detail: playbook?.remediation },
    { step: 'verification', detail: playbook?.verification },
  ].filter((s) => Boolean(s.detail)) as { step: string; detail: string }[]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex size-8 items-center justify-center rounded-md bg-sev-p0/15 text-sevfg-p0">
              <Sparkles className="size-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <DialogTitle className="font-mono text-base">{cveId ?? 'CVE'}</DialogTitle>
              <DialogDescription>
                Granite technical risk → Gemini technical summary + executive triage
              </DialogDescription>
            </div>
            {data?.priority && <Badge className="shrink-0">{data.priority}</Badge>}
          </div>

          {loading && (
            <p className="flex items-center gap-2 text-sm text-fg-muted">
              <Loader2 className="size-4 animate-spin" aria-hidden /> Loading dual-provider briefing…
            </p>
          )}

          {error && !loading && (
            <p className="rounded-md border border-sev-p0/40 bg-sev-p0/10 px-3 py-2 text-sm text-sevfg-p0">{error}</p>
          )}

          {data && !loading && (
            <div className="space-y-4 text-sm">
              {data.rank != null && (
                <p className="text-xs text-fg-subtle">Rank #{fmtInt(data.rank)}</p>
              )}

              {/* Tier 1 — Granite + Gemini technical summary */}
              <section className="rounded-md border border-line bg-surface p-3">
                <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                  Tier 1 · IBM Granite technical risk analysis
                </h3>
                <p className="mb-2 text-[11px] text-fg-subtle">
                  Gemini summarizes Granite&apos;s watsonx signal-grounded rationale for operators.
                </p>

                {techSummary ? (
                  <div className="mb-3">
                    <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-sevfg-p1">
                      Gemini technical summary
                    </h4>
                    <p className="leading-relaxed text-fg">{techSummary}</p>
                  </div>
                ) : (
                  <p className="mb-3 text-fg-subtle">No Gemini technical summary for this CVE yet.</p>
                )}

                {rawTech && (
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
                      <p className="mt-2 rounded border border-line bg-raised/40 p-2 font-mono text-[11px] leading-relaxed text-fg-muted">
                        {rawTech}
                      </p>
                    )}
                  </div>
                )}
                {!rawTech && !techSummary && (
                  <p className="text-fg-subtle">No Granite technical rationale for this CVE.</p>
                )}
              </section>

              {/* Tier 2 — Gemini executive */}
              <section className="rounded-md border border-line bg-surface p-3">
                <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                  Tier 2 · Gemini executive synthesis & triage
                </h3>
                <p className="mb-2 text-[11px] text-fg-subtle">
                  Business-facing brief and containment / remediation / verification steps (no invented
                  patch URLs).
                </p>
                {executive ? (
                  <p className="mb-3 leading-relaxed text-fg">{executive}</p>
                ) : (
                  <p className="mb-3 text-fg-subtle">No Gemini executive brief for this CVE.</p>
                )}
                <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                  Triage playbook
                </h4>
                {steps.length === 0 ? (
                  <p className="text-fg-subtle">No triage steps available.</p>
                ) : (
                  <ol className="list-decimal space-y-2 pl-4">
                    {steps.map((s) => (
                      <li key={s.step}>
                        <span className="font-medium capitalize text-fg">{s.step}</span>
                        <p className="mt-0.5 text-fg-muted">{s.detail}</p>
                      </li>
                    ))}
                  </ol>
                )}
              </section>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
