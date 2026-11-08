import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useThemeContext } from '@/theme/ThemeContext'
import { fmtInt } from '@/lib/utils'
import { ChartTooltipBox } from './ChartTooltip'

export interface BarDatum {
  name: string
  value: number
  /** Optional per-bar override (e.g. severity). */
  color?: string
  /** Extra line in the tooltip. */
  note?: string
}

export interface BarWidgetProps {
  data: BarDatum[]
  color?: string
  valueLabel?: string
  format?: (v: number) => string
  labelFormat?: (name: string) => string
  /** px per bar row */
  rowHeight?: number
  labelWidth?: number
  onSelect?: (name: string) => void
}

/** Horizontal ranked bars: long category names stay readable, values are direct-labelled. */
export function BarWidget({
  data,
  color,
  valueLabel = 'Count',
  format = fmtInt,
  labelFormat = (s) => s,
  rowHeight = 30,
  labelWidth = 128,
  onSelect,
}: BarWidgetProps) {
  const { palette } = useThemeContext()
  const fill = color ?? palette.neutral

  if (!data.length) {
    return <div className="flex h-40 items-center justify-center text-xs text-fg-subtle">No data in scope</div>
  }

  return (
    <div style={{ height: data.length * rowHeight + 8 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 48, bottom: 0, left: 0 }} barCategoryGap={6}>
          <XAxis type="number" hide domain={[0, 'dataMax']} />
          <YAxis
            type="category"
            dataKey="name"
            width={labelWidth}
            tickLine={false}
            axisLine={false}
            interval={0}
            tick={{ fill: palette.fgMuted, fontSize: 12 }}
            tickFormatter={(v: string) => {
              const s = labelFormat(v)
              return s.length > 20 ? `${s.slice(0, 19)}…` : s
            }}
          />
          <Tooltip
            cursor={{ fill: palette.surfaceRaised, opacity: 0.6 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload as BarDatum
              return (
                <ChartTooltipBox
                  title={labelFormat(d.name)}
                  rows={[
                    { label: valueLabel, value: format(d.value), color: d.color ?? fill },
                    ...(d.note ? [{ label: 'Note', value: d.note }] : []),
                  ]}
                />
              )
            }}
          />
          <Bar
            dataKey="value"
            radius={[0, 3, 3, 0]}
            isAnimationActive={false}
            onClick={(d: BarDatum) => onSelect?.(d.name)}
            cursor={onSelect ? 'pointer' : undefined}
          >
            {data.map((d) => (
              <Cell key={d.name} fill={d.color ?? fill} />
            ))}
            <LabelList
              dataKey="value"
              position="right"
              formatter={(v: number) => format(v)}
              style={{ fill: palette.fg, fontSize: 12, fontFamily: 'IBM Plex Mono, monospace' }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
