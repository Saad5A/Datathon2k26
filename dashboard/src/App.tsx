import { Database, Download, Moon, RotateCcw, ShieldAlert, Sun, Upload } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BarWidget } from '@/components/dashboard/BarWidget'
import { DashboardGrid, GridItem } from '@/components/dashboard/DashboardGrid'
import { DonutWidget } from '@/components/dashboard/DonutWidget'
import { ExplanationModal } from '@/components/dashboard/ExplanationModal'
import { JudgeUploadModal } from '@/components/dashboard/JudgeUploadModal'
import { KpiTile } from '@/components/dashboard/KpiTile'
import { ModelComparisonCard } from '@/components/dashboard/ModelComparisonCard'
import { RankedTable, type TableFilters } from '@/components/dashboard/RankedTable'
import { TrendWidget } from '@/components/dashboard/TrendWidget'
import { WidgetCard } from '@/components/dashboard/WidgetCard'
import { ApiStatus } from '@/components/ApiStatus'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem } from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipProvider } from '@/components/ui/tooltip'
import { generateSampleRows } from '@/data/mock'
import { summarize } from '@/lib/aggregate'
import { LIVE_API, fetchRankingPage, fetchStatsSummary, rankingItemToScoreRow, type StatsSummary } from '@/lib/backend'
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

/** Empty placeholder while live API loads — never seeds mock numbers into KPI tiles. */
const pendingApiDataset = (): Dataset => ({
  id: 'api-pending',
  name: 'api/ranking/cves',
  source: 'api',
  rows: [],
  loadedAt: new Date(),
})

const SOURCE_LABEL: Record<Dataset['source'], string> = {
  sample: 'Synthetic sample',
  'upload-client': 'Upload · in-browser scoring',
  'upload-api': 'Upload · model API',
  api: 'Live FastAPI · ranking + Granite',
}

function momDelta(xs: number[]) {
  if (xs.length < 2) return null
  const a = xs[xs.length - 2]
  const b = xs[xs.length - 1]
  return a ? ((b - a) / a) * 100 : null
}

function fmtDeltaAuc(delta: number | null | undefined): string {
  if (delta == null || Number.isNaN(delta)) return '—'
  const pts = delta * 100
  const sign = pts > 0 ? '+' : ''
  return `${sign}${pts.toFixed(2)} pt`
}

export default function App() {
  const { mode, toggle, palette } = useThemeContext()
  const [dataset, setDataset] = useState<Dataset>(() => (LIVE_API ? pendingApiDataset() : sampleDataset()))
  const [uploadOpen, setUploadOpen] = useState(false)
  const [donutScope, setDonutScope] = useState<'top' | 'all'>('top')
  const [filters, setFilters] = useState<TableFilters>({ q: '', priorities: [], exploitOnly: false })
  const [apiSummary, setApiSummary] = useState<StatsSummary | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [explainCve, setExplainCve] = useState<string | null>(null)
  const tableRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!LIVE_API) return
    const ac = new AbortController()
    ;(async () => {
      try {
        const summary = await fetchStatsSummary(ac.signal)
        const limit = Math.max(summary.ranking_rows || 500, 1)
        const page = await fetchRankingPage(
          { page: 1, limit, sort: 'rank', order: 'asc' },
          ac.signal,
        )
        setApiSummary(summary)
        setApiError(null)
        setDataset({
          id: 'api-ranking',
          name: 'results/top500.csv ∩ scores_2026.csv',
          source: 'api',
          rows: page.items.map((item) => rankingItemToScoreRow(item, page.total || limit)),
          loadedAt: new Date(),
        })
        setFilters({ q: '', priorities: [], exploitOnly: false })
      } catch (e) {
        setApiError((e as Error).message)
        // Do not inject mock rows when the live API is configured.
        setDataset(pendingApiDataset())
        setApiSummary(null)
      }
    })()
    return () => ac.abort()
  }, [])

  const s = useMemo(() => summarize(dataset.rows), [dataset])
  const models = useMemo(
    () =>
      apiSummary?.token_usage.model_id ||
      [...new Set(dataset.rows.map((r) => r.model_version))].join(', ') ||
      '—',
    [apiSummary, dataset],
  )

  const live = dataset.source === 'api' && apiSummary != null
  const cvesAnalyzed = live ? (apiSummary.total_analyzed_cves ?? 0) : s.total
  const tokensExact = live ? apiSummary.token_usage.estimated_tokens_consumed : null
  const meanDelta = live ? apiSummary.comparison?.mean_delta_auc_granite_minus_tfidf : null
  const p0Count = live ? apiSummary.risk_bands.critical : s.priorityAll.P0

  const focusTable = useCallback((next: Partial<TableFilters>) => {
    setFilters((f) => ({ ...f, ...next }))
    tableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const loadDataset = (ds: Dataset) => {
    setDataset(ds)
    if (ds.source !== 'api') setApiSummary(null)
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
  const donutData = useMemo(() => {
    if (live) {
      const bands = apiSummary.risk_bands
      return [
        { key: 'P0' as Priority, label: `P0 · ${priorityLabel.P0}`, value: bands.critical, color: priorityColor.P0 },
        { key: 'P1' as Priority, label: `P1 · ${priorityLabel.P1}`, value: bands.high, color: priorityColor.P1 },
        { key: 'P2' as Priority, label: `P2 · ${priorityLabel.P2}`, value: bands.med + bands.low, color: priorityColor.P2 },
      ]
    }
    const prioritySrc = donutScope === 'top' ? s.priorityTop : s.priorityAll
    return (['P0', 'P1', 'P2'] as Priority[]).map((p) => ({
      key: p,
      label: `${p} · ${priorityLabel[p]}`,
      value: prioritySrc[p],
      color: priorityColor[p],
    }))
  }, [live, apiSummary, donutScope, s])
  const latestMonth = monthly[monthly.length - 1]?.month

  return (
    <TooltipProvider>
      <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col px-4 pb-12 sm:px-6 lg:px-8">
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

          <div className="flex min-w-0 basis-full items-center gap-2 sm:flex-1 sm:basis-0">
            <Tooltip
              content={
                <span>
                  {SOURCE_LABEL[dataset.source]} · loaded {dataset.loadedAt.toLocaleTimeString()}
                  <br />
                  Model: <span className="font-mono">{models}</span>
                  {apiError ? (
                    <>
                      <br />
                      API error: {apiError}
                    </>
                  ) : null}
                </span>
              }
            >
              <span className="flex min-w-0 max-w-full items-center gap-2 rounded-md border border-line px-2.5 py-1.5 text-xs">
                <Database className="size-3.5 shrink-0 text-fg-subtle" aria-hidden />
                <span className="truncate font-mono text-fg">{dataset.name}</span>
                <span className="tabular shrink-0 font-mono text-fg-subtle">{fmtInt(dataset.rows.length)} rows</span>
                {dataset.source === 'sample' ? (
                  <Badge className="border-sev-p2/60 text-sevfg-p2">demo data</Badge>
                ) : dataset.source === 'api' ? (
                  <Badge className="border-sev-low/50 text-sevfg-low">results/</Badge>
                ) : (
                  <Badge className="border-sev-low/50 text-sevfg-low">judge</Badge>
                )}
              </span>
            </Tooltip>
            {!LIVE_API && dataset.source !== 'sample' && (
              <Button variant="ghost" size="sm" onClick={() => loadDataset(sampleDataset())}>
                <RotateCcw /> Sample
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={exportCsv} disabled={dataset.rows.length === 0}>
              <Download /> Export CSV
            </Button>
            {!LIVE_API && (
              <Button variant="danger" size="sm" onClick={() => setUploadOpen(true)}>
                <Upload /> Evaluate dataset
              </Button>
            )}
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
          <DashboardGrid>
            <GridItem span={12} sm={6} xl={3}>
              <KpiTile
                label={live ? 'CVEs analyzed' : 'CVEs scored'}
                value={live && apiSummary.total_analyzed_cves == null ? '—' : fmtInt(cvesAnalyzed)}
                accent={palette.neutral}
                spark={live ? undefined : monthly.map((m) => m.published)}
                delta={live ? null : momDelta(monthly.map((m) => m.published))}
                upIsBad={false}
                hint={
                  live
                    ? `ranking_rows=${fmtInt(apiSummary.ranking_rows)} · scores_rows=${fmtInt(apiSummary.scores_rows)}`
                    : latestMonth
                      ? `Through ${latestMonth}`
                      : undefined
                }
                info={
                  live
                    ? 'Bound to summary.total_analyzed_cves ← data_cache/granite_embeddings_watsonx_subset.meta.json n_rows'
                    : 'Every CVE in the active dataset, ranked once.'
                }
              />
            </GridItem>
            <GridItem span={12} sm={6} xl={3}>
              <KpiTile
                label="P0 · Critical"
                value={fmtInt(p0Count)}
                accent={severity.critical}
                spark={live ? undefined : monthly.map((m) => m.p0)}
                delta={live ? null : momDelta(monthly.map((m) => m.p0))}
                hint={live ? `risk_bands.critical from top500 priorities` : `Percentile ≥ ${P0_MIN_PERCENTILE}; patch first`}
                info={
                  live
                    ? 'Bound to summary.risk_bands.critical ← results/top500.csv ⨝ scores_2026.csv priority=P0'
                    : `P0 = percentile ≥ ${P0_MIN_PERCENTILE}. P1 = percentile ≥ ${P1_MIN_PERCENTILE}.`
                }
              />
            </GridItem>
            <GridItem span={12} sm={6} xl={3}>
              <KpiTile
                label={live ? 'Granite ΔAUC vs TF-IDF' : `Top ${TOP_K} · public exploit`}
                value={live ? fmtDeltaAuc(meanDelta) : fmtPct(s.top500ExploitShare)}
                accent={severity.high}
                spark={live ? undefined : monthly.map((m) => m.exploit)}
                hint={
                  live
                    ? `prefer ${apiSummary.comparison?.prefer ?? '—'} · folds ${(apiSummary.comparison?.folds_present ?? []).join(',')}`
                    : `vs ${fmtPct(s.overallExploitShare)} across all CVEs`
                }
                info={
                  live
                    ? 'Bound to summary.comparison.mean_delta_auc_granite_minus_tfidf ← results/granite_subset_comparison.json'
                    : 'Share of the top-500 review queue with any public exploit code.'
                }
              />
            </GridItem>
            <GridItem span={12} sm={6} xl={3}>
              <KpiTile
                label={live ? 'Watsonx tokens used' : `Top ${TOP_K} · median EPSS`}
                value={
                  live
                    ? tokensExact == null
                      ? '—'
                      : fmtInt(tokensExact)
                    : s.top500MedianEpss == null
                      ? '—'
                      : s.top500MedianEpss.toFixed(3)
                }
                accent={severity.medium}
                hint={
                  live
                    ? `${apiSummary.token_usage.provider ?? '—'} · ${apiSummary.token_usage.model_id ?? '—'}`
                    : 'EPSS is an input signal, not the target'
                }
                info={
                  live
                    ? 'Bound to summary.token_usage.estimated_tokens_consumed ← meta.estimated_tokens_this_run (exact integer)'
                    : 'Median EPSS among top-500 CVEs with an EPSS score.'
                }
              />
            </GridItem>
          </DashboardGrid>

          {live && (
            <DashboardGrid>
              <GridItem span={12}>
                <ModelComparisonCard />
              </GridItem>
            </DashboardGrid>
          )}

          <DashboardGrid>
            <GridItem span={12} lg={8}>
              <WidgetCard
                title="Publication rate vs. review queue"
                subtitle={live ? 'Derived from live ranking rows (results/scores_2026.csv fields)' : 'Per snapshot month · select a series'}
                info="Series sit on very different scales, so each is charted on its own axis."
              >
                <TrendWidget
                  data={monthly}
                  series={[
                    { key: 'published', label: 'Published', color: palette.neutral, description: 'New CVEs published per month.' },
                    { key: 'flagged', label: `In top ${TOP_K}`, color: severity.critical, description: `CVEs from each month in the top-${TOP_K} review queue.` },
                    { key: 'p0', label: 'P0 critical', color: severity.critical, description: 'P0 CVEs per publication month.' },
                    { key: 'exploit', label: 'Public exploit', color: severity.high, description: 'CVEs per month with any public exploit evidence.' },
                  ]}
                />
              </WidgetCard>
            </GridItem>
            <GridItem span={12} lg={4}>
              <WidgetCard
                title="Priority mix"
                subtitle={
                  live
                    ? `Top ${fmtInt(apiSummary.ranking_rows)} from API risk_bands`
                    : donutScope === 'top'
                      ? `Top ${fmtInt(TOP_K)} review queue`
                      : `All ${fmtInt(s.total)} CVEs`
                }
                info="Click a slice or row to filter the ranked table."
                menu={
                  live ? undefined : (
                    <>
                      <DropdownMenuLabel>Scope</DropdownMenuLabel>
                      <DropdownMenuRadioGroup value={donutScope} onValueChange={(v) => setDonutScope(v as 'top' | 'all')}>
                        <DropdownMenuRadioItem value="top">Top {TOP_K}</DropdownMenuRadioItem>
                        <DropdownMenuRadioItem value="all">All CVEs</DropdownMenuRadioItem>
                      </DropdownMenuRadioGroup>
                    </>
                  )
                }
              >
                <DonutWidget
                  data={donutData}
                  centerLabel={live ? `top ${apiSummary.ranking_rows}` : donutScope === 'top' ? `top ${TOP_K}` : 'CVEs'}
                  onSelect={(k) => focusTable({ priorities: [k as Priority] })}
                />
              </WidgetCard>
            </GridItem>
          </DashboardGrid>

          <DashboardGrid>
            <GridItem span={12} md={6} xl={4}>
              <WidgetCard title="Top assigners" subtitle={`CVEs in the top ${TOP_K}`} info="From loaded ranking rows (assigner may be empty if not joined).">
                <BarWidget
                  data={s.topAssigners.map((a) => ({ name: a.name, value: a.count, note: `${fmtPct(a.share * 100)} of top ${TOP_K}` }))}
                  valueLabel={`In top ${TOP_K}`}
                  onSelect={(name) => focusTable({ q: name, priorities: [] })}
                />
              </WidgetCard>
            </GridItem>
            <GridItem span={12} md={6} xl={4}>
              <WidgetCard title="Driving signals" subtitle={`Lead reason across the top ${TOP_K}`} info="Highest-impact entry in each row's reasons array from scores_2026.csv.">
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
              <WidgetCard title="Exploit evidence" subtitle={`any_public_exploit in top ${TOP_K}`} info="From scores_2026.csv any_public_exploit flag on ranking rows.">
                <BarWidget
                  data={[
                    {
                      name: 'any_public_exploit',
                      value: dataset.rows.filter((r) => r.any_public_exploit === 1).length,
                    },
                    {
                      name: 'none',
                      value: dataset.rows.filter((r) => r.any_public_exploit !== 1).length,
                    },
                  ]}
                  color={severity.high}
                  valueLabel="CVEs"
                />
              </WidgetCard>
            </GridItem>
          </DashboardGrid>

          <div ref={tableRef} className="scroll-mt-20">
            <WidgetCard
              title="Ranked CVEs"
              subtitle="GET /api/ranking/cves · click a CVE for Granite text from results/granite_explanations_top100.json"
              bodyClassName="px-0"
            >
              <RankedTable
                rows={dataset.rows}
                filters={filters}
                onFiltersChange={setFilters}
                datasetKey={dataset.id}
                onSelectCve={(id) => setExplainCve(id)}
              />
            </WidgetCard>
          </div>
        </main>

        <footer className="mt-10 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-line pt-4 text-xs text-fg-subtle">
          <p>Before the Breach · Sheridan Datathon 2026 · Live numbers from results/ and data_cache/ only.</p>
          <ApiStatus />
        </footer>
      </div>

      {!LIVE_API && <JudgeUploadModal open={uploadOpen} onOpenChange={setUploadOpen} onApply={loadDataset} />}
      <ExplanationModal
        cveId={explainCve}
        open={explainCve != null}
        onOpenChange={(o) => {
          if (!o) setExplainCve(null)
        }}
      />
    </TooltipProvider>
  )
}
