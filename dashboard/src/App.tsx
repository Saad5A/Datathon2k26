import { Database, Download, Moon, RotateCcw, ShieldAlert, Sun, Upload } from 'lucide-react'
import { useCallback, useMemo, useRef, useState } from 'react'
import { BarWidget } from '@/components/dashboard/BarWidget'
import { DashboardGrid, GridItem } from '@/components/dashboard/DashboardGrid'
import { DonutWidget } from '@/components/dashboard/DonutWidget'
import { JudgeUploadModal } from '@/components/dashboard/JudgeUploadModal'
import { KpiTile } from '@/components/dashboard/KpiTile'
import { RankedTable, type TableFilters } from '@/components/dashboard/RankedTable'
import { TrendWidget } from '@/components/dashboard/TrendWidget'
import { WidgetCard } from '@/components/dashboard/WidgetCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem } from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipProvider } from '@/components/ui/tooltip'
import { generateSampleRows } from '@/data/mock'
import { summarize } from '@/lib/aggregate'
import { toCsv } from '@/lib/parse'
import { P0_MIN_PERCENTILE, P1_MIN_PERCENTILE, TOP_K } from '@/lib/scoring'
import type { Dataset } from '@/lib/types'
import { fmtInt, fmtPct, humanizeSignal } from '@/lib/utils'
import { useThemeContext } from '@/theme/ThemeContext'
import { priorityColor, priorityLabel, severity, type Priority } from '@/theme/tokens'

const sampleDataset = (): Dataset => ({
  id: 'sample',
  name: 'sample_scores_2026',
  source: 'sample',
  rows: generateSampleRows(),
  loadedAt: new Date(),
})

const SOURCE_LABEL: Record<Dataset['source'], string> = {
  sample: 'Synthetic sample',
  'upload-client': 'Upload · in-browser scoring',
  'upload-api': 'Upload · model API',
}

function momDelta(xs: number[]) {
  if (xs.length < 2) return null
  const a = xs[xs.length - 2]
  const b = xs[xs.length - 1]
  return a ? ((b - a) / a) * 100 : null
}

export default function App() {
  const { mode, toggle, palette } = useThemeContext()
  const [dataset, setDataset] = useState<Dataset>(sampleDataset)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [donutScope, setDonutScope] = useState<'top' | 'all'>('top')
  const [filters, setFilters] = useState<TableFilters>({ q: '', priorities: [], exploitOnly: false })
  const tableRef = useRef<HTMLDivElement>(null)

  const s = useMemo(() => summarize(dataset.rows), [dataset])
  const models = useMemo(() => [...new Set(dataset.rows.map((r) => r.model_version))].join(', '), [dataset])

  const focusTable = useCallback((next: Partial<TableFilters>) => {
    setFilters((f) => ({ ...f, ...next }))
    tableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const loadDataset = (ds: Dataset) => {
    setDataset(ds)
    setFilters({ q: '', priorities: [], exploitOnly: false })
  }

  const exportCsv = () => {
    const blob = new Blob([toCsv(dataset.rows)], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${dataset.name.replace(/\.(csv|json)$/i, '')}_ranked.csv`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const monthly = s.months
  const prioritySrc = donutScope === 'top' ? s.priorityTop : s.priorityAll
  const donutData = (['P0', 'P1', 'P2'] as Priority[]).map((p) => ({
    key: p,
    label: `${p} · ${priorityLabel[p]}`,
    value: prioritySrc[p],
    color: priorityColor[p],
  }))
  const latestMonth = monthly[monthly.length - 1]?.month

  return (
    <TooltipProvider>
      <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col px-4 pb-12 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="sticky top-0 z-30 -mx-4 mb-6 flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-line bg-bg/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <div className="flex items-center gap-3">
            <span className="flex size-8 items-center justify-center rounded-md bg-sev-p0 text-white">
              <ShieldAlert className="size-4.5" aria-hidden />
            </span>
            <div>
              <h1 className="text-base font-semibold leading-tight tracking-tight">Before the Breach</h1>
              <p className="text-xs text-fg-subtle">CVE exploitation triage · Sheridan Datathon 2026</p>
            </div>
          </div>

          <div className="flex min-w-0 flex-1 items-center gap-2">
            <Tooltip
              content={
                <span>
                  {SOURCE_LABEL[dataset.source]} · loaded {dataset.loadedAt.toLocaleTimeString()}
                  <br />
                  Model: <span className="font-mono">{models}</span>
                </span>
              }
            >
              <span className="flex min-w-0 items-center gap-2 rounded-md border border-line px-2.5 py-1.5 text-xs">
                <Database className="size-3.5 shrink-0 text-fg-subtle" aria-hidden />
                <span className="truncate font-mono text-fg">{dataset.name}</span>
                <span className="tabular shrink-0 font-mono text-fg-subtle">{fmtInt(dataset.rows.length)} rows</span>
                {dataset.source !== 'sample' && <Badge className="border-sev-low/50 text-sev-low">judge</Badge>}
              </span>
            </Tooltip>
            {dataset.source !== 'sample' && (
              <Button variant="ghost" size="sm" onClick={() => loadDataset(sampleDataset())}>
                <RotateCcw /> Sample
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={exportCsv}>
              <Download /> Export CSV
            </Button>
            <Button variant="danger" size="sm" onClick={() => setUploadOpen(true)}>
              <Upload /> Evaluate dataset
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={toggle}
              aria-label={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {mode === 'dark' ? <Sun /> : <Moon />}
            </Button>
          </div>
        </header>

        <main className="flex flex-col gap-4">
          {/* KPIs */}
          <DashboardGrid>
            <GridItem span={12} sm={6} xl={3}>
              <KpiTile
                label="CVEs scored"
                value={fmtInt(s.total)}
                accent={palette.neutral}
                spark={monthly.map((m) => m.published)}
                delta={momDelta(monthly.map((m) => m.published))}
                upIsBad={false}
                hint={latestMonth ? `Through ${latestMonth}` : undefined}
                info="Every CVE in the active dataset, ranked once. Trend shows publications per snapshot month."
              />
            </GridItem>
            <GridItem span={12} sm={6} xl={3}>
              <KpiTile
                label="P0 · Critical"
                value={fmtInt(s.priorityAll.P0)}
                accent={severity.critical}
                spark={monthly.map((m) => m.p0)}
                delta={momDelta(monthly.map((m) => m.p0))}
                hint={`Percentile ≥ ${P0_MIN_PERCENTILE}; patch first`}
                info={`P0 = percentile ≥ ${P0_MIN_PERCENTILE}. P1 = percentile ≥ ${P1_MIN_PERCENTILE}. P2 = everything else.`}
              />
            </GridItem>
            <GridItem span={12} sm={6} xl={3}>
              <KpiTile
                label={`Top ${TOP_K} · public exploit`}
                value={fmtPct(s.top500ExploitShare)}
                accent={severity.high}
                spark={monthly.map((m) => m.exploit)}
                hint={`vs ${fmtPct(s.overallExploitShare)} across all CVEs`}
                info="Share of the top-500 review queue with any public exploit code (Exploit-DB, Metasploit, Nuclei or GitHub PoC)."
              />
            </GridItem>
            <GridItem span={12} sm={6} xl={3}>
              <KpiTile
                label={`Top ${TOP_K} · median EPSS`}
                value={s.top500MedianEpss == null ? '—' : s.top500MedianEpss.toFixed(3)}
                accent={severity.medium}
                hint="EPSS is an input signal, not the target"
                info="Median EPSS probability among top-500 CVEs that have an EPSS score. Rows without EPSS are excluded."
              />
            </GridItem>
          </DashboardGrid>

          {/* Trend + priority mix */}
          <DashboardGrid>
            <GridItem span={12} lg={8}>
              <WidgetCard
                title="Publication rate vs. review queue"
                subtitle="Per snapshot month · select a series"
                info="Series sit on very different scales, so each is charted on its own axis. The dataset schema has no KEV-added date; top-500 entries are the model's forecast of KEV-bound CVEs."
              >
                <TrendWidget
                  data={monthly}
                  series={[
                    { key: 'published', label: 'Published', color: palette.neutral, description: 'New CVEs published per month.' },
                    { key: 'flagged', label: `In top ${TOP_K}`, color: severity.critical, description: `CVEs from each month that land in the top-${TOP_K} review queue (forecast KEV additions).` },
                    { key: 'p0', label: 'P0 critical', color: severity.critical, description: 'P0 CVEs per publication month.' },
                    { key: 'exploit', label: 'Public exploit', color: severity.high, description: 'CVEs per month with any public exploit evidence.' },
                  ]}
                />
              </WidgetCard>
            </GridItem>
            <GridItem span={12} lg={4}>
              <WidgetCard
                title="Priority mix"
                subtitle={donutScope === 'top' ? `Top ${fmtInt(TOP_K)} review queue` : `All ${fmtInt(s.total)} CVEs`}
                info="Click a slice or row to filter the ranked table."
                menu={
                  <>
                    <DropdownMenuLabel>Scope</DropdownMenuLabel>
                    <DropdownMenuRadioGroup value={donutScope} onValueChange={(v) => setDonutScope(v as 'top' | 'all')}>
                      <DropdownMenuRadioItem value="top">Top {TOP_K}</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem value="all">All CVEs</DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>
                  </>
                }
              >
                <DonutWidget
                  data={donutData}
                  centerLabel={donutScope === 'top' ? `top ${TOP_K}` : 'CVEs'}
                  onSelect={(k) => focusTable({ priorities: [k as Priority] })}
                />
              </WidgetCard>
            </GridItem>
          </DashboardGrid>

          {/* Breakdown bars */}
          <DashboardGrid>
            <GridItem span={12} md={6} xl={4}>
              <WidgetCard title="Top assigners" subtitle={`CVEs in the top ${TOP_K}`} info="Click a bar to search the table for that assigner.">
                <BarWidget
                  data={s.topAssigners.map((a) => ({ name: a.name, value: a.count, note: `${fmtPct(a.share * 100)} of top ${TOP_K}` }))}
                  valueLabel={`In top ${TOP_K}`}
                  onSelect={(name) => focusTable({ q: name, priorities: [] })}
                />
              </WidgetCard>
            </GridItem>
            <GridItem span={12} md={6} xl={4}>
              <WidgetCard title="Driving signals" subtitle={`Lead reason across the top ${TOP_K}`} info="The highest-impact entry in each row's `reasons` array.">
                <BarWidget
                  data={s.topSignals.map((x) => ({ name: x.name, value: x.count }))}
                  color={severity.low}
                  valueLabel="Rows led by signal"
                  labelFormat={humanizeSignal}
                  labelWidth={148}
                  onSelect={(name) => focusTable({ q: name, priorities: [] })}
                />
              </WidgetCard>
            </GridItem>
            <GridItem span={12} md={12} xl={4}>
              <WidgetCard title="Exploit evidence" subtitle={`Sources present in the top ${TOP_K}`} info="A CVE can appear in several sources.">
                <BarWidget data={s.exploitFlagsTop.map((x) => ({ name: x.name, value: x.count }))} color={severity.high} valueLabel="CVEs" />
              </WidgetCard>
            </GridItem>
          </DashboardGrid>

          {/* Ranked table */}
          <div ref={tableRef} className="scroll-mt-20">
            <WidgetCard
              title="Ranked CVEs"
              subtitle="Sorted by model rank · expand a row for its signal explanation"
              bodyClassName="px-0"
            >
              <RankedTable rows={dataset.rows} filters={filters} onFiltersChange={setFilters} datasetKey={dataset.id} />
            </WidgetCard>
          </div>
        </main>
      </div>

      <JudgeUploadModal open={uploadOpen} onOpenChange={setUploadOpen} onApply={loadDataset} />
    </TooltipProvider>
  )
}
