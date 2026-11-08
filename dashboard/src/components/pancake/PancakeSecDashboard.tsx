import {
  CheckCircle2,
  Copy,
  Download,
  GitCommit,
  Layers,
  MousePointerClick,
  Send,
  ShieldAlert,
  Table2,
  Terminal,
  TrendingDown,
  Wrench,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  fetchExplanation,
  fetchRankingPage,
  fetchStatsSummary,
  refineGeminiAction,
  type ExplanationPayload,
  type RankingItem,
  type StatsSummary,
} from '@/lib/backend'
import { PancakeScene, type StackCve } from './PancakeScene'
import { SimilarCves } from '@/components/dashboard/SimilarCves'
import './pancakesec.css'

type ViewMode = '3d' | 'table'
type TierFilter = 'ALL' | 'P0' | 'P1' | 'P2'
type RefineKind = 'bash_script' | 'business_risk' | 'granite_divergence' | 'custom_refinement'

const STACK_N = 6

function fmtInt(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return '—'
  return Math.round(n).toLocaleString()
}

function fmtDeltaAuc(delta: number | null | undefined) {
  if (delta == null || Number.isNaN(delta)) return '—'
  const pts = delta * 100
  const sign = pts > 0 ? '+' : ''
  return `${sign}${pts.toFixed(2)} pt ΔAUC`
}

function toStackCve(item: RankingItem): StackCve {
  const reasons = Array.isArray(item.reasons) ? item.reasons : []
  const lead = reasons[0] as { signal?: string } | undefined
  const vector = lead?.signal ? String(lead.signal) : 'ranking_signal'
  const assigner = item.assigner?.trim()
  return {
    id: item.cve_id,
    rank: item.rank ?? 0,
    priority: item.priority || 'P2',
    score: item.score ?? 0,
    title: assigner
      ? `${item.cve_id} · ${assigner}`
      : `${item.cve_id} · ranked exploitation priority`,
    publicExploit: item.any_public_exploit === 1,
    vector,
  }
}

function priorityBadgeClass(p: string) {
  if (p === 'P0') return 'bg-red-100 text-red-700 border border-red-200'
  if (p === 'P1') return 'bg-amber-100 text-amber-800 border border-amber-200'
  return 'bg-slate-100 text-slate-700 border border-slate-200'
}

export function PancakeSecDashboard() {
  const [view, setView] = useState<ViewMode>('3d')
  const [tier, setTier] = useState<TierFilter>('ALL')
  const [summary, setSummary] = useState<StatsSummary | null>(null)
  const [rows, setRows] = useState<RankingItem[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [brief, setBrief] = useState<ExplanationPayload | null>(null)
  const [briefLoading, setBriefLoading] = useState(false)
  const [briefError, setBriefError] = useState<string | null>(null)
  const [tableQ, setTableQ] = useState('')
  const [tablePri, setTablePri] = useState<TierFilter | 'ALL'>('ALL')
  const [actionBusy, setActionBusy] = useState(false)
  const [actionTitle, setActionTitle] = useState('')
  const [actionBody, setActionBody] = useState('')
  const [actionOpen, setActionOpen] = useState(false)
  const [followUp, setFollowUp] = useState('')

  useEffect(() => {
    const ac = new AbortController()
    ;(async () => {
      try {
        setLoading(true)
        const [stats, page] = await Promise.all([
          fetchStatsSummary(ac.signal),
          fetchRankingPage({ page: 1, limit: 50, sort: 'rank', order: 'asc' }, ac.signal),
        ])
        setSummary(stats)
        setRows(page.items)
        setLoadError(null)
        if (page.items[0]?.cve_id) setSelectedId(page.items[0].cve_id)
      } catch (e) {
        if ((e as Error).name === 'AbortError') return
        setLoadError((e as Error).message)
      } finally {
        setLoading(false)
      }
    })()
    return () => ac.abort()
  }, [])

  const stack = useMemo(() => rows.slice(0, STACK_N).map(toStackCve), [rows])
  const selectedStack = useMemo(
    () => stack.find((c) => c.id === selectedId) || rows.map(toStackCve).find((c) => c.id === selectedId) || null,
    [stack, rows, selectedId],
  )

  useEffect(() => {
    if (!selectedId) {
      setBrief(null)
      return
    }
    const ac = new AbortController()
    setBriefLoading(true)
    setBriefError(null)
    setActionOpen(false)
    fetchExplanation(selectedId, ac.signal, 'both')
      .then((p) => {
        setBrief(p)
        setBriefLoading(false)
      })
      .catch((e) => {
        if ((e as Error).name === 'AbortError') return
        setBrief(null)
        setBriefError((e as Error).message)
        setBriefLoading(false)
      })
    return () => ac.abort()
  }, [selectedId])

  const graniteText =
    brief?.granite_technical_rationale || brief?.granite?.summary || brief?.granite?.rationale || null
  const geminiExec =
    brief?.gemini_executive_summary || brief?.gemini?.executive_summary || brief?.gemini?.summary || null
  const playbook = brief?.gemini_triage_playbook || brief?.gemini?.playbook || null

  const runRefine = useCallback(
    async (kind: RefineKind, userContext?: string, title?: string) => {
      if (!selectedId) return
      setActionBusy(true)
      setActionOpen(true)
      setActionTitle(title || '✨ Gemini synthesizing Granite vector context…')
      setActionBody('Gemini synthesizing Granite vector context…')
      try {
        const res = await refineGeminiAction({
          cve_id: selectedId,
          action_type: kind,
          granite_rationale: graniteText || undefined,
          user_context: userContext,
        })
        setActionTitle(title || `✨ Gemini · ${kind}`)
        setActionBody(res.content)
      } catch (e) {
        setActionBody((e as Error).message)
      } finally {
        setActionBusy(false)
      }
    },
    [selectedId, graniteText],
  )

  const filteredTable = useMemo(() => {
    const q = tableQ.trim().toLowerCase()
    return rows.filter((r) => {
      const pri = r.priority || 'P2'
      if (tablePri !== 'ALL' && pri !== tablePri) return false
      if (!q) return true
      const hay = `${r.cve_id} ${r.assigner || ''}`.toLowerCase()
      return hay.includes(q)
    })
  }, [rows, tableQ, tablePri])

  const downloadTop500 = async () => {
    try {
      const page = await fetchRankingPage({ page: 1, limit: 500, sort: 'rank', order: 'asc' })
      const lines = ['rank,cve_id,priority,score,any_public_exploit']
      for (const item of page.items) {
        lines.push(
          `${item.rank ?? ''},${item.cve_id},${item.priority ?? ''},${item.score ?? ''},${item.any_public_exploit ?? 0}`,
        )
      }
      const blob = new Blob([lines.join('\n') + '\n'], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'top500_export.csv'
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) {
      setLoadError((e as Error).message)
    }
  }

  const onFollowUp = (e: FormEvent) => {
    e.preventDefault()
    const q = followUp.trim()
    if (!q) return
    void runRefine('custom_refinement', q, `✨ Gemini Analysis: "${q}"`)
    setFollowUp('')
  }

  const p0Count = summary?.risk_bands.critical ?? null
  const rankingRows = summary?.ranking_rows ?? rows.length

  return (
    <div className="pancakesec-root">
      <header className="sticky top-0 z-40 border-b border-[#E8DFC8]/80 bg-[#FAF7F2]/90 px-6 py-3.5 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1700px] items-center justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#8B3A0F] to-[#451A03] text-xl shadow-md shadow-[#8B3A0F]/20">
              🥞
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-lg font-extrabold tracking-tight text-[#1E1611]">PancakeSec</h1>
                <span className="rounded-full border border-[#8B3A0F]/20 bg-[#8B3A0F]/10 px-2 py-0.5 text-xs font-semibold text-[#8B3A0F]">
                  The Vulnerability Stack
                </span>
              </div>
              <p className="text-xs font-medium text-[#7A6B5D]">
                CVE Exploitation Prioritization · Sheridan Datathon 2026
              </p>
            </div>
          </div>

          <div className="hidden items-center space-x-6 rounded-2xl border border-[#E8DFC8] bg-white/80 px-5 py-2 shadow-sm xl:flex">
            <div className="flex items-center space-x-2.5">
              <div className="h-2 w-2 animate-ping rounded-full bg-emerald-500" />
              <div className="text-xs">
                <div className="font-medium text-[#8A7968]">Audit Corpus</div>
                <div className="mono font-bold text-[#1E1611]">
                  {fmtInt(summary?.total_analyzed_cves ?? summary?.scores_rows)} CVEs
                </div>
              </div>
            </div>
            <div className="h-6 w-px bg-[#E8DFC8]" />
            <div className="text-xs">
              <div className="font-medium text-[#8A7968]">Watsonx Embeddings</div>
              <div className="mono font-bold text-[#0F62FE]">
                {fmtInt(summary?.token_usage.estimated_tokens_consumed)} tokens
              </div>
            </div>
            <div className="h-6 w-px bg-[#E8DFC8]" />
            <div className="text-xs">
              <div className="font-medium text-[#8A7968]">Granite Lift vs TF-IDF</div>
              <div className="mono font-bold text-emerald-700">
                {fmtDeltaAuc(summary?.comparison?.mean_delta_auc_granite_minus_tfidf)}
              </div>
            </div>
            <div className="h-6 w-px bg-[#E8DFC8]" />
            <div className="text-xs">
              <div className="font-medium text-[#8A7968]">P0 Critical Tier</div>
              <div className="mono font-bold text-[#8B3A0F]">
                {fmtInt(p0Count)} / {fmtInt(rankingRows)}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div className="flex rounded-xl bg-[#EFE7D8] p-1 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setView('3d')}
                className={`flex items-center space-x-1.5 rounded-lg px-3 py-1.5 transition ${
                  view === '3d' ? 'bg-white text-[#1E1611] shadow-sm' : 'text-[#7A6B5D] hover:text-[#1E1611]'
                }`}
              >
                <Layers className="h-3.5 w-3.5 text-[#8B3A0F]" />
                <span>3D Stack</span>
              </button>
              <button
                type="button"
                onClick={() => setView('table')}
                className={`flex items-center space-x-1.5 rounded-lg px-3 py-1.5 transition ${
                  view === 'table' ? 'bg-white text-[#1E1611] shadow-sm' : 'text-[#7A6B5D] hover:text-[#1E1611]'
                }`}
              >
                <Table2 className="h-3.5 w-3.5" />
                <span>Table ({fmtInt(rankingRows)})</span>
              </button>
            </div>
            <a
              href="/results"
              className="rounded-xl border border-[#E8DFC8] bg-white px-3 py-2 text-xs font-semibold text-[#451A03] shadow-sm transition hover:bg-[#F7EFE2]"
            >
              Evidence
            </a>
            <button
              type="button"
              onClick={() => void downloadTop500()}
              className="flex items-center space-x-1.5 rounded-xl border border-[#E8DFC8] bg-white px-3 py-2 text-xs font-semibold text-[#451A03] shadow-sm transition hover:bg-[#F7EFE2]"
            >
              <Download className="h-3.5 w-3.5" />
              <span>top500.csv</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-[1700px] flex-1 flex-col gap-6 p-6">
        {loadError && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{loadError}</div>
        )}
        {loading && <div className="text-sm text-[#7A6B5D]">Loading live ranking from FastAPI…</div>}

        <section className="glass-card flex flex-col items-center justify-between gap-4 rounded-2xl border border-[#E8DFC8] p-4 md:flex-row">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">🥞</span>
            <div>
              <h2 className="text-sm font-bold text-[#1E1611]">The Biggest Risks Rise to the Top</h2>
              <p className="text-xs text-[#7A6B5D]">
                Interactive CVE stack from live `/api/ranking/cves` · Granite technical → Gemini triage
              </p>
            </div>
          </div>
          <div className="flex w-full items-center gap-3 md:w-auto">
            <div className="flex flex-1 items-center space-x-2.5 rounded-xl border border-[#0F62FE]/20 bg-[#0F62FE]/10 px-3 py-1.5 md:flex-initial">
              <div className="h-2.5 w-2.5 rounded-full bg-[#0F62FE]" />
              <div className="text-xs">
                <span className="font-bold text-[#0F62FE]">IBM Granite</span>
                <span className="ml-1 hidden text-[#5B6B82] sm:inline">· Vector Prioritization</span>
              </div>
            </div>
            <span className="text-xs font-bold text-[#A89886]">→</span>
            <div className="flex flex-1 items-center space-x-2.5 rounded-xl border border-[#6929C4]/20 bg-[#6929C4]/10 px-3 py-1.5 md:flex-initial">
              <div className="h-2.5 w-2.5 rounded-full bg-[#6929C4]" />
              <div className="text-xs">
                <span className="font-bold text-[#6929C4]">Google Gemini</span>
                <span className="ml-1 hidden text-[#6D5D80] sm:inline">· Triage & Playbooks</span>
              </div>
            </div>
          </div>
        </section>

        {view === '3d' ? (
          <div className="grid min-h-[700px] flex-1 grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="glass-card relative flex flex-col overflow-hidden rounded-3xl border border-[#E8DFC8] p-5 lg:col-span-7">
              <div className="absolute left-6 top-6 z-10 flex flex-wrap items-center gap-2">
                <div className="mr-2 text-xs font-bold uppercase tracking-wider text-[#7A6B5D]">Filter Tiers:</div>
                {(['ALL', 'P0', 'P1', 'P2'] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTier(t)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                      tier === t
                        ? 'bg-[#451A03] text-white shadow-sm'
                        : 'border border-[#E8DFC8] bg-white/90 text-[#7A6B5D] hover:bg-[#FAF4EB]'
                    }`}
                  >
                    {t === 'ALL' ? `All Tiers (${stack.length})` : t}
                  </button>
                ))}
              </div>
              <div className="absolute right-6 top-6 z-10 text-right">
                <div className="flex items-center space-x-1.5 rounded-full border border-[#E8DFC8] bg-[#FAF4EB] px-2.5 py-1 text-[11px] font-semibold text-[#8B3A0F]">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#8B3A0F]" />
                  <span>Real-time Viscous Maple Syrup Simulation</span>
                </div>
              </div>

              <div className="mt-12 flex-1">
                {stack.length > 0 ? (
                  <PancakeScene
                    stack={stack}
                    selectedId={selectedId}
                    filterTier={tier}
                    onSelect={setSelectedId}
                  />
                ) : (
                  <div className="flex h-[520px] items-center justify-center text-sm text-[#7A6B5D]">
                    Waiting for ranking rows…
                  </div>
                )}
              </div>

              <div className="mt-3 flex items-center justify-between border-t border-[#E8DFC8]/60 pt-3 text-xs text-[#7A6B5D]">
                <div className="flex items-center space-x-2">
                  <MousePointerClick className="h-3.5 w-3.5 text-[#8B3A0F]" />
                  <span>
                    Move cursor to tilt. Hover to lift. <strong>Click to triage.</strong>
                  </span>
                </div>
                <div className="mono text-[11px] text-[#A89886]">Grade A Dark Maple Viscosity · IOR 1.49</div>
              </div>
            </div>

            <div className="flex flex-col gap-5 lg:col-span-5">
              <div className="glass-card flex flex-1 flex-col rounded-3xl border border-[#E8DFC8] p-6">
                <div className="flex items-start justify-between border-b border-[#E8DFC8] pb-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`mono rounded-lg px-2.5 py-1 text-xs font-bold uppercase ${priorityBadgeClass(
                          selectedStack?.priority || brief?.priority || 'P2',
                        )}`}
                      >
                        {selectedStack?.priority || brief?.priority || '—'} ·{' '}
                        {(selectedStack?.priority || brief?.priority) === 'P0'
                          ? 'Critical'
                          : (selectedStack?.priority || brief?.priority) === 'P1'
                            ? 'High'
                            : 'Medium'}
                      </span>
                      <span className="mono text-base font-extrabold text-[#1E1611]">
                        {selectedId || 'Select a CVE'}
                      </span>
                      {selectedStack?.publicExploit && (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-800">
                          Public Exploit Active
                        </span>
                      )}
                    </div>
                    <h3 className="mt-1.5 text-sm font-semibold text-[#4A3B30]">
                      {selectedStack?.title || 'Click a pancake layer or table row'}
                    </h3>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] font-bold uppercase text-[#8A7968]">Exploit Score</div>
                    <div className="mono text-xl font-extrabold text-[#8B3A0F]">
                      {selectedStack?.score != null ? selectedStack.score.toFixed(3) : '—'}
                    </div>
                  </div>
                </div>

                <div className="custom-scroll flex flex-1 flex-col gap-4 overflow-y-auto py-4 pr-1">
                  {briefLoading && <p className="text-xs text-[#7A6B5D]">Loading Granite + Gemini briefing…</p>}
                  {briefError && !briefLoading && (
                    <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                      {briefError}
                    </p>
                  )}

                  <div className="relative rounded-2xl border border-[#C9DEFF] bg-[#F0F5FF] p-4">
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <div className="flex h-3 w-3 items-center justify-center rounded bg-[#0F62FE] text-[8px] font-bold text-white">
                          G
                        </div>
                        <span className="text-xs font-bold text-[#0F62FE]">IBM Granite Core (watsonx.ai)</span>
                      </div>
                      <span className="mono rounded-md border border-[#D0E2FF] bg-white px-2 py-0.5 text-[10px] text-[#587399]">
                        granite-embedding-278m
                      </span>
                    </div>
                    <div className="text-xs leading-relaxed text-[#243552]">
                      {graniteText || 'No Granite technical rationale for this CVE yet.'}
                    </div>
                  </div>

                  <div className="relative rounded-2xl border border-[#E8D9FF] bg-[#FAF5FF] p-4">
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <div className="flex h-3 w-3 items-center justify-center rounded bg-[#6929C4] text-[8px] text-white">
                          ✨
                        </div>
                        <span className="text-xs font-bold text-[#6929C4]">
                          Google Gemini · Executive Synthesis
                        </span>
                      </div>
                    </div>
                    <div className="mb-3 text-xs font-medium leading-relaxed text-[#3E275C]">
                      <strong>Executive Brief:</strong>{' '}
                      {geminiExec || 'No Gemini executive synthesis for this CVE yet.'}
                    </div>
                    <div className="mb-2 text-[10px] font-bold uppercase tracking-wide text-[#512F7A]">
                      Automated Triage Playbook
                    </div>
                    <div className="space-y-1.5">
                      {[
                        {
                          icon: ShieldAlert,
                          label: 'Containment',
                          detail: playbook && 'containment' in playbook ? playbook.containment : null,
                        },
                        {
                          icon: Wrench,
                          label: 'Hotfix',
                          detail: playbook && 'remediation' in playbook ? playbook.remediation : null,
                        },
                        {
                          icon: CheckCircle2,
                          label: 'Verification',
                          detail: playbook && 'verification' in playbook ? playbook.verification : null,
                        },
                      ].map((step) =>
                        step.detail ? (
                          <div key={step.label} className="flex items-start space-x-2 text-xs text-[#3E275C]">
                            <step.icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-purple-700" />
                            <span>
                              <strong>{step.label}:</strong> {String(step.detail)}
                            </span>
                          </div>
                        ) : null,
                      )}
                      {!playbook?.containment && !playbook?.remediation && !playbook?.verification && (
                        <p className="text-xs text-[#7A6B5D]">No triage steps available.</p>
                      )}
                    </div>
                  </div>

                  {selectedId && (
                    <SimilarCves
                      key={selectedId}
                      cveId={selectedId}
                      className="rounded-2xl border-[#E8DFC8] bg-white/80 p-4"
                    />
                  )}

                  <div className="rounded-2xl border border-[#E8DFC8] bg-white/80 p-3.5">
                    <div className="mb-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-[#7A6B5D]">
                      <span>⚡ Interactive Gemini Actions</span>
                      <span className="font-normal text-[#A89886]">Live refine-action</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <button
                        type="button"
                        disabled={actionBusy || !selectedId}
                        onClick={() =>
                          void runRefine('bash_script', undefined, `🛠️ Bash Containment (${selectedId})`)
                        }
                        className="group rounded-xl border border-[#E8DFC8] p-2 text-left transition hover:border-[#8B3A0F] hover:bg-[#FAF4EB] disabled:opacity-50"
                      >
                        <div className="flex items-center space-x-1 text-xs font-bold text-[#451A03]">
                          <Terminal className="h-3.5 w-3.5 text-[#8B3A0F]" />
                          <span>Bash Script</span>
                        </div>
                        <div className="mt-0.5 text-[10px] text-[#8A7968]">Instant mitigation</div>
                      </button>
                      <button
                        type="button"
                        disabled={actionBusy || !selectedId}
                        onClick={() =>
                          void runRefine('business_risk', undefined, '💸 Business Impact & Downtime')
                        }
                        className="group rounded-xl border border-[#E8DFC8] p-2 text-left transition hover:border-[#8B3A0F] hover:bg-[#FAF4EB] disabled:opacity-50"
                      >
                        <div className="flex items-center space-x-1 text-xs font-bold text-[#451A03]">
                          <TrendingDown className="h-3.5 w-3.5 text-amber-700" />
                          <span>Risk Impact</span>
                        </div>
                        <div className="mt-0.5 text-[10px] text-[#8A7968]">Downtime & blast radius</div>
                      </button>
                      <button
                        type="button"
                        disabled={actionBusy || !selectedId}
                        onClick={() =>
                          void runRefine('granite_divergence', undefined, '🥊 Why Granite Overruled CVSS')
                        }
                        className="group rounded-xl border border-[#E8DFC8] p-2 text-left transition hover:border-[#8B3A0F] hover:bg-[#FAF4EB] disabled:opacity-50"
                      >
                        <div className="flex items-center space-x-1 text-xs font-bold text-[#451A03]">
                          <GitCommit className="h-3.5 w-3.5 text-purple-700" />
                          <span>Why Granite?</span>
                        </div>
                        <div className="mt-0.5 text-[10px] text-[#8A7968]">Model vs CVSS</div>
                      </button>
                    </div>

                    {actionOpen && (
                      <div className="relative mt-3 rounded-xl bg-[#241A14] p-3 font-mono text-xs text-white">
                        <div className="mb-1.5 flex items-center justify-between border-b border-[#3D2C22] pb-1 text-[11px] text-[#C4A482]">
                          <span>{actionBusy ? 'Gemini synthesizing Granite vector context…' : actionTitle}</span>
                          <button
                            type="button"
                            className="flex items-center space-x-1 text-[#F5A623] hover:underline"
                            onClick={() => void navigator.clipboard.writeText(actionBody)}
                          >
                            <Copy className="h-3 w-3" />
                            <span>Copy</span>
                          </button>
                        </div>
                        <pre className="whitespace-pre-wrap leading-relaxed text-[#F0E6D8]">{actionBody}</pre>
                      </div>
                    )}
                  </div>

                  <form onSubmit={onFollowUp} className="flex items-center space-x-2 pt-1">
                    <input
                      value={followUp}
                      onChange={(e) => setFollowUp(e.target.value)}
                      placeholder="Ask Gemini follow-up (e.g. 'What if we can't patch before Monday?')…"
                      className="flex-1 rounded-xl border border-[#E8DFC8] bg-white px-3.5 py-2.5 text-xs transition focus:border-[#8B3A0F] focus:outline-none"
                    />
                    <button
                      type="submit"
                      disabled={!followUp.trim() || actionBusy || !selectedId}
                      className="flex items-center space-x-1 rounded-xl bg-[#451A03] px-3.5 py-2.5 text-xs font-bold text-white transition hover:bg-[#682705] disabled:opacity-50"
                    >
                      <span>Ask</span>
                      <Send className="h-3 w-3" />
                    </button>
                  </form>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="glass-card flex min-h-[600px] flex-col rounded-3xl border border-[#E8DFC8] p-6">
            <div className="flex flex-col items-center justify-between gap-4 border-b border-[#E8DFC8] pb-4 sm:flex-row">
              <div>
                <h2 className="text-base font-extrabold text-[#1E1611]">Audited CVE Exploitation Ranking</h2>
                <p className="text-xs text-[#7A6B5D]">
                  Live from <code className="mono">GET /api/ranking/cves</code> (top500 ⨝ scores)
                </p>
              </div>
              <div className="flex w-full items-center space-x-3 sm:w-auto">
                <input
                  value={tableQ}
                  onChange={(e) => setTableQ(e.target.value)}
                  placeholder="Search CVE ID or assigner…"
                  className="w-full rounded-xl border border-[#E8DFC8] bg-white px-3.5 py-2 text-xs focus:border-[#8B3A0F] focus:outline-none sm:w-64"
                />
                <select
                  value={tablePri}
                  onChange={(e) => setTablePri(e.target.value as TierFilter | 'ALL')}
                  className="rounded-xl border border-[#E8DFC8] bg-white px-3 py-2 text-xs font-semibold focus:outline-none"
                >
                  <option value="ALL">All Priorities</option>
                  <option value="P0">P0 Only</option>
                  <option value="P1">P1 Only</option>
                  <option value="P2">P2 Only</option>
                </select>
              </div>
            </div>
            <div className="custom-scroll mt-4 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#E8DFC8] text-[11px] uppercase tracking-wider text-[#7A6B5D]">
                    <th className="px-3 py-3">Rank</th>
                    <th className="px-3 py-3">CVE ID</th>
                    <th className="px-3 py-3">Priority</th>
                    <th className="px-3 py-3">Exploit Score</th>
                    <th className="px-3 py-3">Public Weaponization</th>
                    <th className="px-3 py-3">Primary Vector</th>
                    <th className="px-3 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E8DFC8]/60 text-[#2D241E]">
                  {filteredTable.map((item) => {
                    const row = toStackCve(item)
                    return (
                      <tr
                        key={item.cve_id}
                        className="cursor-pointer transition hover:bg-[#FAF4EB]/80"
                        onClick={() => {
                          setSelectedId(item.cve_id)
                          setView('3d')
                        }}
                      >
                        <td className="mono px-3 py-3 font-bold text-[#8B3A0F]">#{row.rank}</td>
                        <td className="mono px-3 py-3 font-extrabold text-[#1E1611]">{row.id}</td>
                        <td className="px-3 py-3">
                          <span
                            className={`mono rounded px-2 py-0.5 text-[10px] font-bold uppercase ${
                              row.priority === 'P0'
                                ? 'bg-red-100 text-red-700'
                                : row.priority === 'P1'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-slate-100 text-slate-700'
                            }`}
                          >
                            {row.priority}
                          </span>
                        </td>
                        <td className="mono px-3 py-3 font-bold">{row.score.toFixed(3)}</td>
                        <td className="px-3 py-3">
                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              row.publicExploit
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-slate-100 text-slate-500'
                            }`}
                          >
                            {row.publicExploit ? 'Weaponized' : 'None Detected'}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-[#5A4B40]">{row.vector}</td>
                        <td className="px-3 py-3 text-right">
                          <span className="rounded-lg border border-[#E8DFC8] bg-[#FAF4EB] px-2.5 py-1 text-[11px] font-bold text-[#8B3A0F]">
                            Triage →
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
