import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { useId, type ReactNode } from 'react'
import { Area, AreaChart, ResponsiveContainer } from 'recharts'
import { Tooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

export interface KpiTileProps {
  label: string
  value: ReactNode
  /** Solid accent (severity token). */
  accent: string
  /** Supporting line under the value. */
  hint?: ReactNode
  /** Change vs. previous period, as a percentage. */
  delta?: number | null
  deltaLabel?: string
  /** Whether "up" is bad (risk metrics) or good. Controls delta colour. */
  upIsBad?: boolean
  /** Inline sparkline values, oldest → newest. */
  spark?: number[]
  info?: ReactNode
}

export function KpiTile({ label, value, accent, hint, delta, deltaLabel = 'vs prev. month', upIsBad = true, spark, info }: KpiTileProps) {
  const dir = delta == null || Math.abs(delta) < 0.05 ? 0 : delta > 0 ? 1 : -1
  const bad = dir !== 0 && (dir > 0) === upIsBad
  const Icon = dir > 0 ? ArrowUpRight : dir < 0 ? ArrowDownRight : Minus
  const sparkData = spark?.map((v, i) => ({ i, v }))
  const gid = `spark${useId().replace(/[^a-zA-Z0-9]/g, '')}`

  const body = (
    <div className="relative flex h-full flex-col overflow-hidden rounded-lg border border-line bg-surface p-4 pl-5">
      <span className="absolute inset-y-0 left-0 w-1" style={{ backgroundColor: accent }} aria-hidden />
      <div className="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">{label}</div>
      <div className="mt-2 flex items-end justify-between gap-3">
        <div className="tabular font-mono text-3xl font-semibold leading-none tracking-tight text-fg">{value}</div>
        {sparkData && sparkData.length > 1 && (
          <div className="h-8 w-20 shrink-0" aria-hidden>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkData} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={accent} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={accent} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="v"
                  stroke={accent}
                  strokeWidth={1.5}
                  fill={`url(#${gid})`}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        {delta != null && (
          <span
            className={cn(
              'tabular inline-flex items-center gap-0.5 font-mono font-medium',
              dir === 0 ? 'text-fg-subtle' : bad ? 'text-sev-p0' : 'text-emerald-500',
            )}
          >
            <Icon className="size-3.5" aria-hidden />
            {dir === 0 ? '0.0%' : `${delta > 0 ? '+' : ''}${delta.toFixed(1)}%`}
            <span className="sr-only">{deltaLabel}</span>
          </span>
        )}
        {delta != null && <span className="text-fg-subtle">{deltaLabel}</span>}
        {hint && <span className="w-full text-fg-subtle">{hint}</span>}
      </div>
    </div>
  )

  return info ? (
    <Tooltip content={info}>
      <div className="h-full" tabIndex={0}>
        {body}
      </div>
    </Tooltip>
  ) : (
    body
  )
}
