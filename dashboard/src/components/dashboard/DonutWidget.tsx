import { useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { useThemeContext } from '@/theme/ThemeContext'
import { fmtInt, fmtPct } from '@/lib/utils'
import { ChartTooltipBox } from './ChartTooltip'

export interface DonutDatum {
  key: string
  label: string
  value: number
  color: string
}

export interface DonutWidgetProps {
  data: DonutDatum[]
  centerLabel: string
  /** Defaults to the sum of values. */
  centerValue?: string
  height?: number
  onSelect?: (key: string) => void
}

/** Ring chart + direct-labelled legend (counts and shares, no colour-only encoding). */
export function DonutWidget({ data, centerLabel, centerValue, height = 180, onSelect }: DonutWidgetProps) {
  const { palette } = useThemeContext()
  const [active, setActive] = useState<string | null>(null)
  const total = data.reduce((s, d) => s + d.value, 0)

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row">
      <div className="relative shrink-0" style={{ width: height, height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="label"
              innerRadius="68%"
              outerRadius="100%"
              paddingAngle={data.filter((d) => d.value > 0).length > 1 ? 1.5 : 0}
              minAngle={3}
              stroke={palette.surface}
              strokeWidth={2}
              startAngle={90}
              endAngle={-270}
              isAnimationActive={false}
              onMouseEnter={(_, i) => setActive(data[i]?.key ?? null)}
              onMouseLeave={() => setActive(null)}
              onClick={(_, i) => data[i] && onSelect?.(data[i].key)}
              cursor={onSelect ? 'pointer' : undefined}
            >
              {data.map((d) => (
                <Cell key={d.key} fill={d.color} opacity={active && active !== d.key ? 0.35 : 1} />
              ))}
            </Pie>
            <Tooltip
              content={({ active: a, payload }) => {
                if (!a || !payload?.length) return null
                const d = payload[0].payload as DonutDatum
                return (
                  <ChartTooltipBox
                    rows={[{ label: d.label, value: `${fmtInt(d.value)} · ${fmtPct(total ? (100 * d.value) / total : 0)}`, color: d.color }]}
                  />
                )
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="tabular font-mono text-2xl font-semibold text-fg">{centerValue ?? fmtInt(total)}</span>
          <span className="text-[11px] uppercase tracking-wider text-fg-subtle">{centerLabel}</span>
        </div>
      </div>

      <ul className="w-full min-w-0 flex-1 space-y-1">
        {data.map((d) => {
          const share = total ? (100 * d.value) / total : 0
          return (
            <li key={d.key}>
              <button
                type="button"
                onMouseEnter={() => setActive(d.key)}
                onMouseLeave={() => setActive(null)}
                onFocus={() => setActive(d.key)}
                onBlur={() => setActive(null)}
                onClick={() => onSelect?.(d.key)}
                disabled={!onSelect}
                className="group flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-raised disabled:cursor-default disabled:hover:bg-transparent"
              >
                <span className="size-2.5 shrink-0 rounded-sm" style={{ backgroundColor: d.color }} aria-hidden />
                <span className="flex-1 truncate text-fg">{d.label}</span>
                <span className="tabular font-mono text-fg">{fmtInt(d.value)}</span>
                <span className="tabular w-12 text-right font-mono text-xs text-fg-subtle">{fmtPct(share)}</span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
