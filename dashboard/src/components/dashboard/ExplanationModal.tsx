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

export function ExplanationModal({ cveId, open, onOpenChange }: ExplanationModalProps) {
  const [data, setData] = useState<ExplanationPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

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
    fetchExplanation(cveId, ac.signal)
      .then((payload) => {
        setData(payload)
        setLoading(false)
      })
      .catch((e) => {
        if ((e as Error).name === 'AbortError') return
        const msg =
          e instanceof ApiError && e.status === 404
            ? `No Granite explanation or playbook for ${cveId} yet.`
            : (e as Error).message
        setError(msg)
        setLoading(false)
      })
    return () => ac.abort()
  }, [open, cveId])

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
                IBM Granite risk rationale and remediation (watsonx.ai / offline template).
              </DialogDescription>
            </div>
            {data?.priority && <Badge className="shrink-0">{data.priority}</Badge>}
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
                  {data.granite?.provider ? ` · provider ${data.granite.provider}` : ''}
                  {data.granite?.model_id ? ` · ${data.granite.model_id}` : ''}
                </p>
              )}

              <section>
                <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                  Granite risk summary
                </h3>
                {data.granite?.summary || data.granite?.rationale ? (
                  <p className="leading-relaxed text-fg">{data.granite.summary || data.granite.rationale}</p>
                ) : (
                  <p className="text-fg-subtle">No Granite narrative for this CVE.</p>
                )}
              </section>

              <section>
                <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
                  Remediation steps
                </h3>
                {data.remediation.steps.length === 0 ? (
                  <p className="text-fg-subtle">No playbook steps available for this CVE.</p>
                ) : (
                  <ol className="list-decimal space-y-2 pl-4">
                    {data.remediation.steps.map((s) => (
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
