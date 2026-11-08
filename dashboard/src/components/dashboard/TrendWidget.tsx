import { useId, useState } from 'react'
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useThemeContext } from '@/theme/ThemeContext'
import { cn, fmtCompact, fmtInt, fmtMonth } from '@/lib/utils'
import { ChartTooltipBox } from './ChartTooltip'

export interface TrendSeries {
  key: string
  label: string
  color: string
  /** Short explanation shown under the selector. */
  description?: string
}

export interface TrendWidgetProps<T extends { month: string }> {
  data: T[]
  series: TrendSeries[]
  height?: number
}

function pctChange(xs: number[]) {
  if (xs.length < 2) return null
  const a = xs[xs.length - 2]
  const b = xs[xs.length - 1]
  return a ? ((b - a) / a) * 100 : null
}

/**
 * Series selector with inline sparklines + one focused area chart.
 * Series on very different scales (7k publications vs 50 top-500 entries)
 * get their own y-axis by being viewed one at a time, rather than sharing a
 * misleading dual axis.
 */
export function TrendWidget<T extends { month: string }>({ data, series, height = 220 }: TrendWidgetProps<T>) {
  const { palette } = useThemeContext()
  const [selected, setSelected] = useState(series[0]?.key)
  const gid = `trend${useId().replace(/[^a-zA-Z0-9]/g, '')}`
  const s = series.find((x) => x.key === selected) ?? series[0]
  const get = (row: T, key: string) => Number((row as Record<string, unknown>)[key] ?? 0)

  if (!data.length || !s) {
    return <div className="flex h-40 items-center justify-center text-xs text-fg-subtle">No dated rows</div>
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4" role="tablist" aria-label="Trend series">
        {series.map((x) => {
          const vals = data.map((d) => get(d, x.key))
          const last = vals[vals.length - 1] ?? 0
          const ch = pctChange(vals)
          const on = x.key === s.key
          return (
            <button
              key={x.key}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => setSelected(x.key)}
              className={cn(
                'flex min-w-0 flex-col gap-1 rounded-md border px-3 py-2 text-left transition-colors',
                on ? 'border-line-strong bg-raised' : 'border-line hover:bg-raised/60',
              )}
            >
              <span className="flex items-center gap-1.5 truncate text-xs text-fg-muted">
                <span className="size-2 shrink-0 rounded-sm" style={{ backgroundColor: x.color }} aria-hidden />
                {x.label}
              </span>
              <span className="flex items-end justify-between gap-2">
                <span className="tabular font-mono text-base font-semibold text-fg">{fmtInt(last)}</span>
                <span className="h-6 w-16" aria-hidden>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={vals.map((v, i) => ({ i, v }))}>
                      <YAxis hide domain={['dataMin', 'dataMax']} />
                      <Line type="monotone" dataKey="v" stroke={x.color} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </span>
              </span>
              <span className="tabular font-mono text-[11px] text-fg-subtle">
                {ch == null ? 'n/a' : `${ch > 0 ? '+' : ''}${ch.toFixed(1)}% MoM`}
              </span>
            </button>
          )
        })}
      </div>

      {s.description && <p className="text-xs text-fg-subtle">{s.description}</p>}

      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
            <defs>
              <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.28} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={palette.grid} strokeDasharray="0" vertical={false} />
            <XAxis
              dataKey="month"
              tickFormatter={fmtMonth}
              tickLine={false}
              axisLine={{ stroke: palette.borderStrong }}
              tick={{ fill: palette.fgMuted, fontSize: 12 }}
              minTickGap={12}
            />
            <YAxis
              tickFormatter={(v: number) => fmtCompact(v)}
              tickLine={false}
              axisLine={false}
              tick={{ fill: palette.fgMuted, fontSize: 12 }}
              width={48}
              allowDecimals={false}
            />
            <Tooltip
              cursor={{ stroke: palette.borderStrong }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null
                const row = payload[0].payload as T
                return (
                  <ChartTooltipBox
                    title={`${fmtMonth(String(label))} ${String(label).slice(0, 4)}`}
                    rows={series.map((x) => ({ label: x.label, value: fmtInt(get(row, x.key)), color: x.color }))}
                  />
                )
              }}
            />
            <Area
              type="monotone"
              dataKey={s.key}
              stroke={s.color}
              strokeWidth={2}
              fill={`url(#${gid})`}
              activeDot={{ r: 4, strokeWidth: 2, stroke: palette.surface }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
