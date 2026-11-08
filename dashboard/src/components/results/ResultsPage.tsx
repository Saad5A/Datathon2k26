import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ArrowLeft, ArrowUpRight, BadgeCheck, CircleAlert, Database, FlaskConical, GitBranch, Layers } from 'lucide-react'
import { ChartTooltipBox } from '@/components/dashboard/ChartTooltip'
import {
  cell,
  fetchResults,
  modelOf,
  RESULTS_SNAPSHOT,
  type FoldRow,
  type MetricCell,
  type ResultsPayload,
} from '@/lib/results'
import './results.css'

const MODEL_KEYS = ['cvss3', 'epss', 'exploit_then_epss', 'C1', 'G2'] as const

const ACCENT = '#8b3a0f'
const ACCENT_SOFT = '#d4a574'
const NEUTRAL = '#d6c7b2'
const INK = '#4a3b30'
const GRID = '#e8dfc8'

const fmtInt = (v: number | null | undefined) => (v == null ? '—' : Math.round(v).toLocaleString('en-US'))
const fmt3 = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(3))
const signed3 = (v: number | null | undefined) => (v == null ? '—' : `${v > 0 ? '+' : '−'}${Math.abs(v).toFixed(3)}`)

/** One line per fold; numbers appear only when every value in the block is a verified claim. */
function PairedLines({
  rows,
  metric,
}: {
  rows: ResultsPayload['significance']['paired_bootstrap_vs_exploit_then_epss']
  metric: 'auc' | 'top500_expected'
}) {
  return (
    <ul>
      {rows.map((row) => {
        const b = row[metric]
        return (
          <li key={row.fold} title={Object.values(b.claims).join(', ')}>
            {row.fold}:{' '}
            {b.verified ? (
              <>
                {signed3(b.diff)} (95% CI {signed3(b.ci95[0])} to {signed3(b.ci95[1])})
              </>
            ) : (
              <span className="rp-unverified">unverified</span>
            )}
          </li>
        )
      })}
    </ul>
  )
}

function MetricValue({ cell: value, format }: { cell: MetricCell; format: (v: number) => string }) {
  if (value.value == null) {
    return (
      <span className="rp-na" title="Not in the registered claim set, so we do not quote it here.">
        —
      </span>
    )
  }
  return (
    <span
      className="rp-metric"
      title={`${value.claim}${value.verified ? ' · verified in results/claims*.json' : ' · artifact value, no separate claim'}`}
    >
      {format(value.value)}
      {value.verified && <span className="rp-vmark" aria-label="verified claim" />}
    </span>
  )
}

function AucChart({ fold1, fold2 }: { fold1: FoldRow; fold2: FoldRow }) {
  const data = useMemo(
    () =>
      MODEL_KEYS.map((key) => {
        const row = modelOf(fold1, key)
        return {
          key,
          name: row?.short ?? key,
          fold1: modelOf(fold1, key)?.metrics.auc.value ?? null,
          fold2: modelOf(fold2, key)?.metrics.auc.value ?? null,
          submitted: key === 'G2',
        }
      }),
    [fold1, fold2],
  )
  return (
    <div className="rp-chart" role="img" aria-label="ROC AUC by method, both backtest folds, axis starts at 0.6">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 12, right: 8, bottom: 4, left: -14 }} barGap={4}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="name" tickLine={false} axisLine={{ stroke: GRID }} tick={{ fill: '#7a6b5d', fontSize: 11 }} interval={0} />
          <YAxis
            domain={[0.6, 0.92]}
            ticks={[0.6, 0.7, 0.8, 0.9]}
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#7a6b5d', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}
          />
          <Tooltip
            cursor={{ fill: '#f7efe2', opacity: 0.7 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const row = payload[0].payload as { name: string; fold1: number | null; fold2: number | null }
              return (
                <ChartTooltipBox
                  title={row.name}
                  rows={[
                    { label: 'Fold 1 AUC', value: fmt3(row.fold1), color: ACCENT_SOFT },
                    { label: 'Fold 2 AUC', value: fmt3(row.fold2), color: ACCENT },
                  ]}
                />
              )
            }}
          />
          <Bar dataKey="fold1" fill={ACCENT_SOFT} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="fold2" fill={ACCENT} radius={[3, 3, 0, 0]} isAnimationActive={false}>
            <LabelList
              dataKey="fold2"
              position="top"
              formatter={(v: number) => (v ? v.toFixed(3) : '')}
              style={{ fill: INK, fontSize: 9, fontFamily: 'JetBrains Mono, monospace' }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function RankChart({ fold }: { fold: FoldRow }) {
  const data = MODEL_KEYS.map((key) => {
    const row = modelOf(fold, key)
    return {
      key,
      name: row?.short ?? key,
      rank: row?.metrics.median_rank.value ?? null,
      color: key === 'G2' ? ACCENT : key === 'C1' ? '#d4a574' : key === 'exploit_then_epss' ? '#c4a482' : NEUTRAL,
    }
  })
  return (
    <div className="rp-chart rp-chart-short" role="img" aria-label="Median rank of exploited CVEs in fold 1, lower is better, log scale">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 62, bottom: 4, left: 4 }} barCategoryGap={7}>
          <XAxis
            type="number"
            scale="log"
            domain={[400, 9000]}
            ticks={[500, 1000, 2000, 4000, 8000]}
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#7a6b5d', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}
            tickFormatter={(v: number) => fmtInt(v)}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={104}
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#4a3b30', fontSize: 11 }}
            interval={0}
          />
          <Tooltip
            cursor={{ fill: '#f7efe2', opacity: 0.7 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const row = payload[0].payload as { name: string; rank: number | null }
              return <ChartTooltipBox title={row.name} rows={[{ label: 'Median rank', value: fmtInt(row.rank) }]} />
            }}
          />
          <Bar dataKey="rank" isAnimationActive={false} radius={[0, 3, 3, 0]}>
            {data.map((row) => (
              <Cell key={row.key} fill={row.color} />
            ))}
            <LabelList
              dataKey="rank"
              position="right"
              formatter={(v: number) => fmtInt(v)}
              style={{ fill: INK, fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function AblationChart({ folds, baseline }: { folds: ResultsPayload['ablations']; baseline: FoldRow[] }) {
  const full = baseline.map((fold) => modelOf(fold, 'C1')?.metrics.auc.value ?? null)
  const short: Record<string, string> = {
    drop_signals: 'Signals',
    drop_text: 'Text',
    drop_assigner: 'Assigner',
    unmasked_text: 'Unmasked',
  }
  const data = [
    { key: 'full', name: 'Full C1', fold1: full[0], fold2: full[1] },
    ...folds.map((row) => ({
      key: row.key,
      name: short[row.key] ?? row.label,
      fold1: row.folds[0]?.auc ?? null,
      fold2: row.folds[1]?.auc ?? null,
    })),
  ]
  return (
    <div className="rp-chart" role="img" aria-label="AUC after removing one signal family at a time">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 8, bottom: 4, left: -14 }} barGap={4}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="name" tickLine={false} axisLine={{ stroke: GRID }} tick={{ fill: '#7a6b5d', fontSize: 9.5 }} interval={0} />
          <YAxis
            domain={[0.75, 0.9]}
            ticks={[0.75, 0.8, 0.85, 0.9]}
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#7a6b5d', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}
          />
          <Tooltip
            cursor={{ fill: '#f7efe2', opacity: 0.7 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const row = payload[0].payload as { name: string; fold1: number | null; fold2: number | null }
              return (
                <ChartTooltipBox
                  title={row.name}
                  rows={[
                    { label: 'Fold 1 AUC', value: fmt3(row.fold1), color: ACCENT_SOFT },
                    { label: 'Fold 2 AUC', value: fmt3(row.fold2), color: ACCENT },
                  ]}
                />
              )
            }}
          />
          <Bar dataKey="fold1" fill={ACCENT_SOFT} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="fold2" fill={ACCENT} radius={[3, 3, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function HeadlineTable({ folds }: { folds: FoldRow[] }) {
  return (
    <div className="rp-table-wrap">
      <table className="rp-table">
        <thead>
          <tr>
            <th rowSpan={2} className="rp-th-method">
              Method
            </th>
            <th colSpan={2}>Top-500 hits</th>
            <th colSpan={2}>ROC AUC</th>
            <th colSpan={2}>Average precision</th>
            <th colSpan={2}>Median rank</th>
          </tr>
          <tr>
            <th>Fold 1</th>
            <th>Fold 2</th>
            <th>Fold 1</th>
            <th>Fold 2</th>
            <th>Fold 1</th>
            <th>Fold 2</th>
            <th>Fold 1</th>
            <th>Fold 2</th>
          </tr>
        </thead>
        <tbody>
          {MODEL_KEYS.map((key) => {
            const row = modelOf(folds[0], key)
            const row2 = modelOf(folds[1], key)
            return (
              <tr key={key} className={key === 'G2' ? 'rp-row-submitted' : key === 'C1' ? 'rp-row-ours' : undefined}>
                <th scope="row">
                  <span>{row?.label ?? key}</span>
                  {key === 'G2' && <em>submitted</em>}
                  {key === 'C1' && <em className="rp-em-quiet">base</em>}
                </th>
                <td><MetricValue cell={cell(row, 'top500')} format={fmtInt} /></td>
                <td><MetricValue cell={cell(row2, 'top500')} format={fmtInt} /></td>
                <td><MetricValue cell={cell(row, 'auc')} format={fmt3} /></td>
                <td><MetricValue cell={cell(row2, 'auc')} format={fmt3} /></td>
                <td><MetricValue cell={cell(row, 'avg_precision')} format={fmt3} /></td>
                <td><MetricValue cell={cell(row2, 'avg_precision')} format={fmt3} /></td>
                <td><MetricValue cell={cell(row, 'median_rank')} format={fmtInt} /></td>
                <td><MetricValue cell={cell(row2, 'median_rank')} format={fmtInt} /></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function AblationTable({ rows, baseline }: { rows: ResultsPayload['ablations']; baseline: FoldRow[] }) {
  const fullAuc = baseline.map((fold) => modelOf(fold, 'C1')?.metrics.auc.value ?? null)
  const fullTop = baseline.map((fold) => modelOf(fold, 'C1')?.metrics.top500.value ?? null)
  return (
    <div className="rp-table-wrap">
      <table className="rp-table rp-table-ablation">
        <thead>
          <tr>
            <th rowSpan={2}>Feature set</th>
            <th colSpan={2}>AUC</th>
            <th colSpan={2}>Δ AUC vs full</th>
            <th colSpan={2}>Top-500 hits</th>
          </tr>
          <tr>
            <th>Fold 1</th>
            <th>Fold 2</th>
            <th>Fold 1</th>
            <th>Fold 2</th>
            <th>Fold 1</th>
            <th>Fold 2</th>
          </tr>
        </thead>
        <tbody>
          <tr className="rp-row-submitted">
            <th scope="row">Full C1</th>
            <td>{fmt3(fullAuc[0])}</td>
            <td>{fmt3(fullAuc[1])}</td>
            <td>—</td>
            <td>—</td>
            <td>{fmtInt(fullTop[0])}</td>
            <td>{fmtInt(fullTop[1])}</td>
          </tr>
          {rows.map((row) => (
            <tr key={row.key}>
              <th scope="row">
                <span>{row.label}</span>
                <em className="rp-em-quiet">{row.note}</em>
              </th>
              <td>{fmt3(row.folds[0]?.auc)}</td>
              <td>{fmt3(row.folds[1]?.auc)}</td>
              <td>{row.folds[0]?.auc != null && fullAuc[0] != null ? signed3(row.folds[0].auc - fullAuc[0]) : '—'}</td>
              <td>{row.folds[1]?.auc != null && fullAuc[1] != null ? signed3(row.folds[1].auc - fullAuc[1]) : '—'}</td>
              <td>{fmtInt(row.folds[0]?.top500)}</td>
              <td>{fmtInt(row.folds[1]?.top500)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Kpi({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rp-kpi">
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{note}</p>
    </div>
  )
}

function SectionHead({ step, eyebrow, title, children }: { step: string; eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <header className="rp-section-head">
      <span className="rp-step">{step}</span>
      <div>
        <span className="rp-eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
        {children && <p>{children}</p>}
      </div>
    </header>
  )
}

export function ResultsPage() {
  const [data, setData] = useState<ResultsPayload>(RESULTS_SNAPSHOT)
  const [live, setLive] = useState(false)
  const [liveError, setLiveError] = useState(false)

  useEffect(() => {
    const ac = new AbortController()
    fetchResults(ac.signal)
      .then((payload) => {
        setData(payload)
        setLive(true)
      })
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setLiveError(true)
      })
    return () => ac.abort()
  }, [])

  const [fold1, fold2] = data.folds
  const g2 = modelOf(fold1, 'G2')
  const cvss = modelOf(fold1, 'cvss3')
  const epss = modelOf(fold1, 'epss')
  const exploit = modelOf(fold1, 'exploit_then_epss')
  const mean = data.submitted.mean_auc

  const bootstrap = data.significance.paired_bootstrap_vs_exploit_then_epss
  const permutation = data.significance.permutation
  const unseen = data.unseen_assigner
  const ablation = (key: string) => data.ablations.find((row) => row.key === key)
  const signalDrop = ablation('drop_signals')
  const textDrop = ablation('drop_text')
  const assignerDrop = ablation('drop_assigner')

  const delta = (row: typeof signalDrop, index: number) => {
    const full = modelOf(data.folds[index], 'C1')?.metrics.auc.value
    const value = row?.folds[index]?.auc
    return full != null && value != null ? value - full : null
  }
  const deltaText = (row: typeof signalDrop, index: number) => {
    const value = delta(row, index)
    return value == null ? '—' : signed3(value)
  }

  return (
    <div className="rp-app">
      <header className="rp-top">
        <a className="rp-brand" href="/">
          <img src="/pancakess-mark.svg" alt="" />
          <span>
            <strong>pancakess</strong>
            <small>
              Predictive Analytics Network for Cybersecurity Assessment,
              <br />
              Knowledge, and Exploitation Software System
            </small>
          </span>
        </a>
        <nav aria-label="Results sections">
          <a href="#head-to-head">Head-to-head</a>
          <a href="#signal">Signal ablations</a>
          <a href="#limits">Limits</a>
          <a href="#ensembles">Ensembles</a>
          <a href="#verify">Verify</a>
        </nav>
        <a className="rp-back" href="/">
          <ArrowLeft size={14} aria-hidden /> Kitchen
        </a>
      </header>

      <main>
        <section className="rp-hero">
          <div>
            <span className="rp-eyebrow">2025 backtest · 2026 submission · no 2026 labels</span>
            <h1>
              The queue is not a guess.
              <br />
              It is a measured ordering.
            </h1>
            <p className="rp-lede">
              Every number on this page is read from the audited artifacts in <code>results/</code> and tied to a claim in
              the ledger. The submitted model is <strong>G2</strong>: gradient boosting over time-safe exploit signals,
              assigner history and masked description text, plus an IBM Granite text score. It was adopted by a
              pre-registered tie-break — not because it beat its own baseline.
            </p>
            <div className="rp-hero-actions">
              <a className="rp-button rp-button-solid" href="#head-to-head">
                See the head-to-head <ArrowUpRight size={15} aria-hidden />
              </a>
              <a className="rp-button" href="/evolve/">
                Evolution observatory <GitBranch size={15} aria-hidden />
              </a>
            </div>
            <p className="rp-source-line">
              {live ? 'Live artifacts · /api/results' : 'Bundled snapshot · /api/results offline'}
              {liveError && !live ? ' · using the generated snapshot' : ''} · generated {data.generated_at.slice(0, 10)}
            </p>
          </div>

          <aside className="rp-verdict" aria-label="Pre-registered selection verdict">
            <span className="rp-verdict-label">
              <BadgeCheck size={14} aria-hidden /> Pre-registered verdict
            </span>
            <strong className="rp-verdict-model">{data.submitted.model}</strong>
            <p className="rp-verdict-rule">{data.submitted.rule}</p>
            <dl className="rp-verdict-rows">
              <div>
                <dt>Tie-break candidate</dt>
                <dd>{data.submitted.best_granite}</dd>
              </div>
              <div>
                <dt>C1 mean AUC</dt>
                <dd>{fmt3(mean.C1)}</dd>
              </div>
              <div>
                <dt>G2 mean AUC</dt>
                <dd>{fmt3(mean.G2)}</dd>
              </div>
              <div>
                <dt>Final flag</dt>
                <dd>
                  <code>{data.submitted.flag}</code>
                </dd>
              </div>
            </dl>
          </aside>
        </section>

        <section className="rp-kpis" aria-label="Headline metrics">
          <Kpi
            label="Mean AUC · 2 folds"
            value={fmt3(mean.G2)}
            note={`G2 ${fmt3(mean.G2)} vs C1 ${fmt3(mean.C1)}. No measurable gain; the tie-break decided.`}
          />
          <Kpi
            label="Median rank · fold 1"
            value={fmtInt(g2?.metrics.median_rank.value)}
            note={`CVSS3 ${fmtInt(cvss?.metrics.median_rank.value)} · EPSS ${fmtInt(epss?.metrics.median_rank.value)}. Lower is better.`}
          />
          <Kpi
            label={`Top-500 hits · fold 1`}
            value={fmtInt(g2?.metrics.top500.value)}
            note={`of ${fold1?.positives ?? '—'} exploited CVEs. Exploit→EPSS ${fmtInt(exploit?.metrics.top500.value)} · CVSS3 ${fmtInt(cvss?.metrics.top500.value)}.`}
          />
          <Kpi
            label="2026 queue"
            value={fmtInt(data.drift.rows_2026_scoreboard)}
            note="CVEs ranked for the judges. No 2026 labels exist, so we claim no 2026 accuracy."
          />
        </section>

        <section className="rp-section" id="head-to-head">
          <SectionHead step="01" eyebrow="Head-to-head" title="The ordering, against the signals a scanner already has.">
            Same folds, same positives, same seeds. CVSS3 and EPSS are the severity and probability scores most teams
            already sort by; “exploit code → EPSS” is the strongest simple rule we could build. G2 is judged on the full
            queue, not on a hand-picked slice.
          </SectionHead>

          <div className="rp-two-col">
            <div className="rp-card">
              <div className="rp-card-head">
                <h3>ROC AUC by method</h3>
                <span className="rp-legend">
                  <span><i style={{ background: ACCENT_SOFT }} /> Fold 1</span>
                  <span><i style={{ background: ACCENT }} /> Fold 2</span>
                </span>
              </div>
              <AucChart fold1={fold1} fold2={fold2} />
              <p className="rp-caption">
                Axis starts at 0.6 so the gap is visible; a coin flip is 0.5. Higher is better. Hover a bar for both
                folds.
              </p>
            </div>
            <div className="rp-card">
              <div className="rp-card-head">
                <h3>Median rank of exploited CVEs</h3>
                <span className="rp-mono rp-muted">fold 1 · lower is better</span>
              </div>
              <RankChart fold={fold1} />
              <p className="rp-caption">
                Log scale. The typical exploited CVE sits around rank {fmtInt(g2?.metrics.median_rank.value)} with G2,
                versus {fmtInt(cvss?.metrics.median_rank.value)} for CVSS3 — a shorter review queue before the typical
                dangerous CVE is reached.
              </p>
            </div>
          </div>

          <HeadlineTable folds={data.folds} />
          <div className="rp-notes-row">
            <span>
              <i className="rp-dot" /> Fold 1: {fmtInt(fold1?.test_rows)} rows, {fmtInt(fold1?.positives)} positives
              ({fold1?.test_months}).
            </span>
            <span>
              <i className="rp-dot" /> Fold 2: {fmtInt(fold2?.test_rows)} rows, {fmtInt(fold2?.positives)} positives
              ({fold2?.test_months}).
            </span>
            <span>
              <i className="rp-dot" /> Green dot = the claim is verified in <code>results/claims*.json</code>; hover any
              value for its claim id.
            </span>
          </div>
        </section>

        <section className="rp-section" id="signal">
          <SectionHead step="02" eyebrow="Signal ablations" title="Where the ordering comes from.">
            One feature family removed at a time, with the same folds and seeds. This is the honest answer to “what is
            doing the work?” — exploit evidence and description text carry the lift; assigner history is a small, mixed
            prior.
          </SectionHead>

          <div className="rp-two-col rp-two-col-wide">
            <div className="rp-card">
              <div className="rp-card-head">
                <h3>AUC after removing one signal family</h3>
                <span className="rp-legend">
                  <span><i style={{ background: ACCENT_SOFT }} /> Fold 1</span>
                  <span><i style={{ background: ACCENT }} /> Fold 2</span>
                </span>
              </div>
              <AblationChart folds={data.ablations} baseline={data.folds} />
              <p className="rp-caption">Full C1 is the reference. Every ablation is a real retrain, not a correlation.</p>
            </div>
            <div className="rp-signal-cards">
              <article className="rp-signal-card">
                <span className="rp-signal-icon">
                  <FlaskConical size={16} aria-hidden />
                </span>
                <h3>Exploit signals at the snapshot month</h3>
                <p>{signalDrop?.note}</p>
                <strong>
                  Δ AUC {deltaText(signalDrop, 0)} / {deltaText(signalDrop, 1)}
                </strong>
                <small>
                  Top-500 falls from {fmtInt(modelOf(fold1, 'C1')?.metrics.top500.value)} to{' '}
                  {fmtInt(signalDrop?.folds[0]?.top500)} in fold 1, and from{' '}
                  {fmtInt(modelOf(fold2, 'C1')?.metrics.top500.value)} to {fmtInt(signalDrop?.folds[1]?.top500)} in fold
                  2.
                </small>
              </article>
              <article className="rp-signal-card">
                <span className="rp-signal-icon">
                  <Layers size={16} aria-hidden />
                </span>
                <h3>Masked description text</h3>
                <p>{textDrop?.note}</p>
                <strong>
                  Δ AUC {deltaText(textDrop, 0)} / {deltaText(textDrop, 1)}
                </strong>
                <small>
                  Top-500 falls from {fmtInt(modelOf(fold1, 'C1')?.metrics.top500.value)} to{' '}
                  {fmtInt(textDrop?.folds[0]?.top500)} in fold 1, and from{' '}
                  {fmtInt(modelOf(fold2, 'C1')?.metrics.top500.value)} to {fmtInt(textDrop?.folds[1]?.top500)} in fold 2.
                </small>
              </article>
              <article className="rp-signal-card rp-signal-card-quiet">
                <span className="rp-signal-icon">
                  <Database size={16} aria-hidden />
                </span>
                <h3>Assigner history</h3>
                <p>{assignerDrop?.note}</p>
                <strong>
                  Δ AUC {deltaText(assignerDrop, 0)} / {deltaText(assignerDrop, 1)}
                </strong>
                <small>
                  Small and mixed. It is kept as a prior; the unseen-assigner test below covers assigners with no
                  earlier KEV entry, which remain a known weak spot.
                </small>
              </article>
            </div>
          </div>

          <AblationTable rows={data.ablations} baseline={data.folds} />

          <div className="rp-unseen">
            <div>
              <span className="rp-eyebrow">Unseen-assigner stress test · fold 1</span>
              <h3>No KEV history? Ranked on exploit signals and text; this is a known weak spot.</h3>
              <p>
                {fmtInt(unseen.rows)} test rows came from assigners with zero prior KEV rows — {fmtInt(unseen.positives)}{' '}
                of them exploited. Within that subset the model reaches AUC {fmt3(unseen.auc)} and places{' '}
                {fmtInt(unseen.top500_hits_from_subset)} of {fmtInt(unseen.positives)} positives in the top 500 using{' '}
                {fmtInt(unseen.top500_rows_from_subset)} slots. That is the check that stops “assigner memorisation”
                from being the whole story.
              </p>
            </div>
            <div className="rp-unseen-stat">
              <strong>{fmt3(unseen.auc)}</strong>
              <span>AUC with no assigner history</span>
            </div>
          </div>
        </section>

        <section className="rp-section" id="checks">
          <SectionHead step="03" eyebrow="Could it be luck, or leakage?" title="The checks that could have killed it.">
            Strong numbers are cheap. These are the tests we ran to try to break our own result — and what they actually
            support.
          </SectionHead>
          <div className="rp-check-grid">
            <article className="rp-check">
              <span className="rp-check-label">Label shuffle</span>
              <strong>{fmt3(permutation.mean)}</strong>
              <p>
                Mean AUC with labels shuffled across {fmtInt(permutation.n_shuffles)} permutations; the best shuffle
                reached {fmt3(permutation.max)}. The real folds are {fmt3(modelOf(fold1, 'C1')?.metrics.auc.value)} and{' '}
                {fmt3(modelOf(fold2, 'C1')?.metrics.auc.value)}. The signal is not a label leak.
              </p>
            </article>
            <article className="rp-check">
              <span className="rp-check-label">Paired bootstrap · AUC vs exploit→EPSS · seed set 0</span>
              <PairedLines rows={bootstrap} metric="auc" />
              <p>Model minus exploit→EPSS. Suggestive, not conclusive: the interval includes zero.</p>
            </article>
            <article className="rp-check">
              <span className="rp-check-label">Paired bootstrap · top-500 · seed set 0</span>
              <PairedLines rows={bootstrap} metric="top500_expected" />
              <p>
                Expected top-500 hits, model minus exploit→EPSS. This is the least stable result on this page and the
                interval includes zero. We do not sell it as a win.
              </p>
            </article>
            <article className="rp-check">
              <span className="rp-check-label">Exploitation wording</span>
              <strong>{fmt3(ablation('unmasked_text')?.folds[0]?.auc)}</strong>
              <p>
                Leaving “actively exploited” language in the description changes AUC only marginally (
                {fmt3(ablation('unmasked_text')?.folds[0]?.auc)} / {fmt3(ablation('unmasked_text')?.folds[1]?.auc)}).
                Masking is not hiding the answer.
              </p>
            </article>
          </div>
        </section>

        <section className="rp-section" id="limits">
          <SectionHead step="04" eyebrow="What we refuse to claim" title="The limits are part of the result.">
            A ranking page that hides its error bars is a sales page. These are the claims we will not make, even though
            they would look better on a slide.
          </SectionHead>
          <div className="rp-limit-grid">
            <article>
              <CircleAlert size={17} aria-hidden />
              <h3>No 2026 accuracy</h3>
              <p>
                {fmtInt(data.drift.rows_2026_scoreboard)} CVEs are ranked for 2026. None has an outcome we can see. We
                claim a distribution and a ranking, never an accuracy.
              </p>
            </article>
            <article>
              <CircleAlert size={17} aria-hidden />
              <h3>Top-500 is noisy</h3>
              <p>
                Fold 1 has {fmtInt(fold1?.positives)} positives, so one hit is roughly 2% of the test. Fold 2 has{' '}
                {fmtInt(fold2?.positives)}. A one- or two-hit difference between methods is not a result.
              </p>
            </article>
            <article>
              <CircleAlert size={17} aria-hidden />
              <h3>G2 is not an improvement</h3>
              <p>
                G2’s mean AUC is {fmt3(mean.G2)} against C1’s {fmt3(mean.C1)}. It was adopted because the IBM tie-break
                was declared in advance, not because Granite lifted the score.
              </p>
            </article>
            <article>
              <CircleAlert size={17} aria-hidden />
              <h3>KEV is a proxy</h3>
              <p>
                The labels are CISA KEV additions. That is confirmed exploitation, not every attack. A CVE that is
                attacked but never listed counts as a negative.
              </p>
            </article>
          </div>
        </section>

        <section className="rp-section rp-ensemble" id="ensembles">
          <SectionHead step="05" eyebrow="One model or several?" title="Would an ensemble be better? Not automatically.">
            This is the question every “add more models” pitch skips. An ensemble buys variance reduction when its
            members make <em>different</em> mistakes. It costs latency, maintenance and explainability — and it needs
            its own pre-registered test before it can replace the submission.
          </SectionHead>
          <div className="rp-ensemble-grid">
            <div className="rp-ensemble-main">
              <h3>Averaging near-duplicates is not an ensemble.</h3>
              <p>
                C1 and G2 are the same model family: G2 is C1 with a Granite text feature added. Their mean AUC is{' '}
                {fmt3(mean.C1)} versus {fmt3(mean.G2)} — a difference of {signed3((mean.G2 ?? 0) - (mean.C1 ?? 0))}. The
                errors are almost the same, so a blend has nothing new to cancel. G1, which replaces TF-IDF with Granite
                text, is worse at {fmt3(mean.G1)}. There is no diverse second opinion in this family to average.
              </p>
              <h3>The strong baselines are already inputs.</h3>
              <p>
                EPSS and the exploit signals are features inside C1. A “C1 + exploit→EPSS” blend would re-weight
                information the model has already seen, not add a new view of the problem.
              </p>
              <h3>Fifty-two positives do not support a meta-learner.</h3>
              <p>
                Stacking needs out-of-fold predictions and enough positives to fit a second level. Fold 1 has{' '}
                {fmtInt(fold1?.positives)} positives and fold 2 has {fmtInt(fold2?.positives)}. A meta-model trained on
                that would mostly learn noise, and it would need its own audit before we could quote it.
              </p>
              <h3>What would change our mind.</h3>
              <p>
                A genuinely different signal — vendor advisories, internet-exposure telemetry, or a second model with
                measured error decorrelation — plus a pre-registered backtest on both folds. That is a research plan, not
                a claim we can put on this page today.
              </p>
            </div>
            <aside className="rp-ensemble-side">
              <span className="rp-eyebrow">The ensemble we already have</span>
              <p className="rp-ensemble-big">
                Three signal families, one calibrated ranking.
              </p>
              <ul>
                <li>
                  <strong>Exploit evidence</strong> at the snapshot month
                </li>
                <li>
                  <strong>Publisher history</strong> from assigner KEV rates
                </li>
                <li>
                  <strong>Language</strong> from masked descriptions and Granite embeddings
                </li>
              </ul>
              <p className="rp-ensemble-foot">
                The combination is the model. Adding another estimator on top would be a new experiment, not a free
                upgrade — and this page only quotes what has been audited.
              </p>
            </aside>
          </div>
        </section>

        <section className="rp-section" id="verify">
          <SectionHead step="06" eyebrow="Reproduce it" title="Every figure has a file and a command.">
            The page reads the same artifacts the audits read. If a number here is wrong, the artifact is wrong — and
            you can rerun it.
          </SectionHead>
          <div className="rp-verify-grid">
            <div className="rp-card">
              <h3>Artifacts</h3>
              <ul className="rp-source-list">
                {data.sources.map((source) => (
                  <li key={source.path}>
                    <code>{source.path}</code>
                    <span>{source.role}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="rp-card">
              <h3>Commands</h3>
              <pre className="rp-code">
                <code>{`.venv/bin/python -m server.services.results_service
.venv/bin/python run_all.py
.venv/bin/python tools/check_claims.py docs/RESULTS.md
curl -s https://pancakess.work/api/results | head`}</code>
              </pre>
              <div className="rp-links">
                <a href="/api/docs">
                  API docs <ArrowUpRight size={13} aria-hidden />
                </a>
                <a href="/evolve/">
                  Evolution <ArrowUpRight size={13} aria-hidden />
                </a>
                <a href="/pancakess_test_upload.csv">
                  Test CSV <ArrowUpRight size={13} aria-hidden />
                </a>
                <a href="/">
                  Back to kitchen <ArrowUpRight size={13} aria-hidden />
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="rp-footer">
        <p>
          <strong>pancakess</strong> · Before the Breach. Labelled metrics are 2025 backtests; the 2026 scoreboard has no
          outcomes we can see. Priority scores rank review urgency; they are not exploit probabilities.
        </p>
        <p className="rp-footer-mono">
          {data.submitted.model} · {data.submitted.flag} · snapshot {data.generated_at.slice(0, 10)}
        </p>
      </footer>
    </div>
  )
}
