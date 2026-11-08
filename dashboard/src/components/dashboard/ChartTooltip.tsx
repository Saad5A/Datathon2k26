import type { ReactNode } from 'react'

export interface TooltipRow {
  label: string
  value: ReactNode
  color?: string
}

/** Shared tooltip chrome for every Recharts widget. */
export function ChartTooltipBox({ title, rows }: { title?: ReactNode; rows: TooltipRow[] }) {
  return (
    <div className="min-w-36 rounded-md border border-line-strong bg-surface px-3 py-2 text-xs shadow-lg">
      {title && <div className="mb-1.5 font-medium text-fg">{title}</div>}
      <dl className="space-y-1">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between gap-4">
            <dt className="flex items-center gap-1.5 text-fg-muted">
              {r.color && <span className="size-2 rounded-sm" style={{ backgroundColor: r.color }} aria-hidden />}
              {r.label}
            </dt>
            <dd className="tabular font-mono font-medium text-fg">{r.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
