import { Loader2, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { fetchExplanation, type ExplanationPayload, type ProviderNarrative } from '@/lib/backend'
import { ApiError } from '@/lib/apiClient'
import { cn, fmtInt } from '@/lib/utils'

export interface ExplanationModalProps {
  cveId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

type ProviderTab = 'granite' | 'gemini'

function narrativeText(n: ProviderNarrative | null | undefined): string | null {
  if (!n) return null
  return n.summary || n.rationale || n.executive_summary || null
}

export function ExplanationModal({ cveId, open, onOpenChange }: ExplanationModalProps) {
  const [data, setData] = useState<ExplanationPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState<ProviderTab>('granite')

  useEffect(() => {
    if (!open || !cveId) {
      setData(null)
      setError(null)
      return
    }
    const ac = new AbortController()
    setLoading(true)
    setError(null)
    setData(null)
    fetchExplanation(cveId, ac.signal, 'both')
      .then((payload) => {
        setData(payload)
        // Prefer a tab that actually has content for this CVE.
        if (payload.available?.granite || payload.granite) setTab('granite')
        else if (payload.available?.gemini || payload.gemini) setTab('gemini')
        setLoading(false)
      })
      .catch((e) => {
        if ((e as Error).name === 'AbortError') return
        const msg =
          e instanceof ApiError && e.status === 404
            ? `No Granite or Gemini explanation/playbook for ${cveId} yet.`
            : (e as Error).message
        setError(msg)
        setLoading(false)
      })
    return () => ac.abort()
  }, [open, cveId])

  const active: ProviderNarrative | null = useMemo(() => {
    if (!data) return null
    return tab === 'granite' ? data.granite : data.gemini ?? null
  }, [data, tab])

  const steps =
    tab === 'gemini' && active?.remediation_steps?.length
      ? active.remediation_steps
      : data?.remediation.steps ?? []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex size-8 items-center justify-center rounded-md bg-sev-p0/15 text-sevfg-p0">
              <Sparkles className="size-4" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <DialogTitle className="font-mono text-base">{cveId ?? 'CVE'}</DialogTitle>
              <DialogDescription>
                Dual-provider risk rationale — toggle IBM Granite (watsonx) vs Gemini.
              </DialogDescription>
            </div>
            {data?.priority && <Badge className="shrink-0">{data.priority}</Badge>}
          </div>

          <div className="flex gap-1 rounded-md border border-line bg-raised/40 p-1" role="tablist" aria-label="Model provider">
            {(
              [
                { id: 'granite' as const, label: 'IBM Granite (Watsonx)', ready: Boolean(data?.granite || data?.available?.granite) },
                { id: 'gemini' as const, label: 'Gemini', ready: Boolean(data?.gemini || data?.available?.gemini) },
              ] as const
            ).map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  'flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors',
                  tab === t.id ? 'bg-surface text-fg shadow-sm' : 'text-fg-muted hover:text-fg',
                )}
              >
                {t.label}
                {!loading && data && !t.ready ? <span className="ml-1 text-fg-subtle">(n/a)</span> : null}
              </button>
            ))}
          </div>

          {loading && (
            <p className="flex items-center gap-2 text-sm text-fg-muted">
              <Loader2 className="size-4 animate-spin" aria-hidden /> Loading explanation…
            </p>
          )}

          {error && !loading && (
            <p className="rounded-md border border-sev-p0/40 bg-sev-p0/10 px-3 py-2 text-sm text-sevfg-p0">{error}</p>
          )}

          {data && !loading && (
            <div className="space-y-4 text-sm">
              {data.rank != null && (
                <p className="text-xs text-fg-subtle">
                  Rank #{fmtInt(data.rank)}
                  {active?.provider ? ` · provider ${active.provider}` : ''}
                  {active?.model_id ? ` · ${active.model_id}` : ''}
                </p>
              )}

              <section>
                <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                  {tab === 'granite' ? 'Granite risk summary' : 'Gemini risk rationale'}
                </h3>
                {narrativeText(active) ? (
                  <p className="leading-relaxed text-fg">{narrativeText(active)}</p>
                ) : (
                  <p className="text-fg-subtle">
                    {tab === 'granite'
                      ? 'No Granite narrative for this CVE.'
                      : 'No Gemini playbook for this CVE (smoke suite covers CVE-2026-10001…10005).'}
                  </p>
                )}
              </section>

              <section>
                <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                  Remediation steps
                </h3>
                {steps.length === 0 ? (
                  <p className="text-fg-subtle">No playbook steps available for this provider/CVE.</p>
                ) : (
                  <ol className="list-decimal space-y-2 pl-4">
                    {steps.map((s) => (
                      <li key={s.step}>
                        <span className="font-medium text-fg">{s.step.replace(/_/g, ' ')}</span>
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
