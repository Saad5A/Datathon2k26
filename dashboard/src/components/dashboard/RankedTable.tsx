import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type PaginationState,
  type SortingState,
} from '@tanstack/react-table'
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  ChevronRight as Caret,
  Loader2,
  Search,
  TrendingDown,
  TrendingUp,
  X,
} from 'lucide-react'
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { PriorityBadge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/tooltip'
import { queryScores, type ScorePage } from '@/lib/server'
import { EXPLOIT_FLAGS, EXPLOIT_FLAG_LABEL, type Reason, type ScoreRow } from '@/lib/types'
import { cn, fmtInt, fmtScore, humanizeSignal } from '@/lib/utils'
import { priorityColor, priorityText, severity, type Priority } from '@/theme/tokens'

export interface TableFilters {
  q: string
  priorities: Priority[]
  exploitOnly: boolean
}

export interface RankedTableProps {
  rows: ScoreRow[]
  filters: TableFilters
  onFiltersChange: (f: TableFilters) => void
  /** Bumps when the dataset changes so pagination resets. */
  datasetKey: string
  /** Open Granite explanation modal for a CVE (live API). */
  onSelectCve?: (cveId: string) => void
}

const PAGE_SIZES = [10, 25, 50, 100]
const FLAG_SHORT: Record<(typeof EXPLOIT_FLAGS)[number], string> = {
  exploitdb: 'EDB',
  metasploit: 'MSF',
  nuclei: 'NUC',
  poc_github: 'GH',
}

function useDebounced<T>(value: T, ms: number) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

function SortIcon({ dir }: { dir: false | 'asc' | 'desc' }) {
  if (dir === 'asc') return <ArrowUp className="size-3" />
  if (dir === 'desc') return <ArrowDown className="size-3" />
  return <ArrowUpDown className="size-3 opacity-40" />
}

function ReasonsPanel({ row }: { row: ScoreRow }) {
  const max = Math.max(0.0001, ...row.reasons.map((r) => r.impact))
  return (
    <div className="grid gap-4 border-t border-line bg-bg/60 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div>
        <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Why it ranks #{fmtInt(row.rank)}
        </h3>
        {row.reasons.length === 0 ? (
          <p className="text-xs text-fg-subtle">No signals above the explanation threshold. The score sits near the base rate.</p>
        ) : (
          <ol className="space-y-2">
            {row.reasons.map((r: Reason, i) => {
              const Icon = r.direction === 'up' ? TrendingUp : TrendingDown
              const c = r.direction === 'up' ? severity.critical : severity.low
              return (
                <li key={`${r.signal}-${i}`} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1">
                  <span className="flex min-w-0 items-center gap-1.5 text-fg">
                    <Icon className="size-3.5 shrink-0" style={{ color: c }} aria-label={r.direction === 'up' ? 'raises risk' : 'lowers risk'} />
                    <span className="truncate">{humanizeSignal(r.signal)}</span>
                    <span className="font-mono text-xs text-fg-subtle">= {String(r.value ?? '∅')}</span>
                  </span>
                  <span className="tabular font-mono text-xs text-fg-muted">{r.impact.toFixed(2)}</span>
                  <span className="col-span-2 h-1.5 overflow-hidden rounded-full bg-raised">
                    <span className="block h-full rounded-full" style={{ width: `${(100 * r.impact) / max}%`, backgroundColor: c }} />
                  </span>
                </li>
              )
            })}
          </ol>
        )}
        <dl className="mt-4 grid grid-cols-3 gap-2 text-xs">
          {[
            ['Published', row.published || '—'],
            ['Snapshot', row.snapshot_month || '—'],
            ['Model', row.model_version],
          ].map(([k, v]) => (
            <div key={k} className="rounded border border-line px-2 py-1.5">
              <dt className="text-fg-subtle">{k}</dt>
              <dd className="truncate font-mono text-fg">{v}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="min-w-0">
        <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">reasons (raw JSON)</h3>
        <pre className="max-h-56 overflow-auto rounded-md border border-line bg-surface p-3 font-mono text-[11px] leading-relaxed text-fg-muted">
          {JSON.stringify(row.reasons, null, 2)}
        </pre>
      </div>
    </div>
  )
}

export function RankedTable({ rows, filters, onFiltersChange, datasetKey, onSelectCve }: RankedTableProps) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'rank', desc: false }])
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 25 })
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [search, setSearch] = useState(filters.q)
  const [page, setPage] = useState<ScorePage | null>(null)
  const [loading, setLoading] = useState(true)
  const debouncedQ = useDebounced(search, 250)
  const lastExternalQ = useRef(filters.q)

  // External filter changes (e.g. clicking a chart) → sync the search box.
  useEffect(() => {
    if (filters.q !== lastExternalQ.current) {
      lastExternalQ.current = filters.q
      setSearch(filters.q)
    }
  }, [filters.q])

  useEffect(() => {
    if (debouncedQ !== filters.q) {
      lastExternalQ.current = debouncedQ
      onFiltersChange({ ...filters, q: debouncedQ })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ])

  // Reset to page 1 whenever the result set changes shape.
  useEffect(() => {
    setPagination((p) => (p.pageIndex === 0 ? p : { ...p, pageIndex: 0 }))
    setExpanded({})
  }, [filters.q, filters.priorities, filters.exploitOnly, sorting, datasetKey])

  useEffect(() => {
    const ac = new AbortController()
    setLoading(true)
    const s = sorting[0]
    queryScores(
      rows,
      {
        pageIndex: pagination.pageIndex,
        pageSize: pagination.pageSize,
        sort: s ? { id: s.id as keyof ScoreRow, desc: s.desc } : null,
        q: filters.q,
        priorities: filters.priorities,
        exploitOnly: filters.exploitOnly,
      },
      ac.signal,
    )
      .then((p) => {
        setPage(p)
        setLoading(false)
      })
      .catch((e) => {
        if (e.name !== 'AbortError') setLoading(false)
      })
    return () => ac.abort()
  }, [rows, pagination, sorting, filters.q, filters.priorities, filters.exploitOnly])

  const columns = useMemo<ColumnDef<ScoreRow>[]>(
    () => [
      {
        id: 'expand',
        header: () => <span className="sr-only">Expand</span>,
        enableSorting: false,
        size: 32,
        cell: ({ row }) => (
          <button
            type="button"
            onClick={row.getToggleExpandedHandler()}
            aria-expanded={row.getIsExpanded()}
            aria-label={`${row.getIsExpanded() ? 'Hide' : 'Show'} signals for ${row.original.cve_id}`}
            className="rounded p-0.5 text-fg-subtle hover:bg-raised hover:text-fg"
          >
            <Caret className={cn('size-4 transition-transform', row.getIsExpanded() && 'rotate-90')} />
          </button>
        ),
      },
      {
        accessorKey: 'rank',
        header: 'Rank',
        size: 72,
        cell: ({ getValue }) => <span className="tabular font-mono text-fg-muted">#{fmtInt(getValue<number>())}</span>,
      },
      {
        accessorKey: 'cve_id',
        header: 'CVE',
        size: 150,
        cell: ({ row }) => (
          <button
            type="button"
            onClick={() => onSelectCve?.(row.original.cve_id)}
            className="text-left font-mono font-medium text-fg underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sev-p0/50"
            title="Open Granite risk explanation"
          >
            {row.original.cve_id}
            {row.original.in_top500 === 1 && (
              <Tooltip content="Inside the top-500 review queue">
                <span className="ml-1.5 align-middle text-[10px] font-semibold text-sevfg-p0">TOP</span>
              </Tooltip>
            )}
          </button>
        ),
      },
      {
        accessorKey: 'priority',
        header: 'Priority',
        size: 80,
        cell: ({ getValue }) => <PriorityBadge priority={getValue<Priority>()} />,
      },
      {
        accessorKey: 'score',
        header: 'Score',
        size: 160,
        cell: ({ row }) => {
          const r = row.original
          return (
            <div className="flex items-center gap-2">
              <div className="h-1.5 w-20 overflow-hidden rounded-full bg-raised" aria-hidden>
                <div
                  className="h-full rounded-full"
                  style={{ width: `${Math.max(2, r.score * 100)}%`, backgroundColor: priorityColor[r.priority] }}
                />
              </div>
              <span className="tabular font-mono text-fg">{fmtScore(r.score)}</span>
            </div>
          )
        },
      },
      {
        accessorKey: 'percentile',
        header: 'Pctl',
        size: 64,
        cell: ({ getValue }) => <span className="tabular font-mono text-fg-muted">{getValue<number>().toFixed(1)}</span>,
      },
      {
        accessorKey: 'epss',
        header: 'EPSS',
        size: 72,
        cell: ({ getValue }) => {
          const v = getValue<number | null>()
          return v == null ? (
            <span className="text-fg-subtle">—</span>
          ) : (
            <span className="tabular font-mono text-fg-muted">{v.toFixed(3)}</span>
          )
        },
      },
      {
        id: 'exploits',
        accessorKey: 'any_public_exploit',
        header: 'Public exploit',
        size: 160,
        cell: ({ row }) => {
          const r = row.original
          const on = EXPLOIT_FLAGS.filter((f) => r[f])
          if (!r.any_public_exploit) return <span className="text-fg-subtle">none</span>
          return (
            <span className="flex flex-wrap gap-1">
              {on.length === 0 && <span className="text-xs text-sevfg-p1">yes</span>}
              {on.map((f) => (
                <Tooltip key={f} content={EXPLOIT_FLAG_LABEL[f]}>
                  <span className="rounded border border-sev-p1/50 bg-sev-p1/10 px-1 font-mono text-[10px] font-semibold leading-4 text-sevfg-p1">
                    {FLAG_SHORT[f]}
                  </span>
                </Tooltip>
              ))}
            </span>
          )
        },
      },
      {
        accessorKey: 'assigner',
        header: 'Assigner',
        size: 140,
        cell: ({ getValue }) => <span className="block max-w-[140px] truncate text-fg-muted">{getValue<string>()}</span>,
      },
      {
        accessorKey: 'published',
        header: 'Published',
        size: 100,
        cell: ({ getValue }) => <span className="tabular font-mono text-xs text-fg-muted">{getValue<string>() || '—'}</span>,
      },
    ],
    [onSelectCve],
  )

  const table = useReactTable({
    data: page?.rows ?? [],
    columns,
    state: { sorting, pagination, expanded },
    getRowId: (r) => r.cve_id,
    getRowCanExpand: () => true,
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    onExpandedChange: (u) => setExpanded((prev) => (typeof u === 'function' ? (u(prev) as Record<string, boolean>) : (u as Record<string, boolean>))),
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    manualSorting: true,
    manualFiltering: true,
    enableSortingRemoval: false,
    sortDescFirst: false,
    pageCount: page?.pageCount ?? -1,
    rowCount: page?.total,
  })

  const togglePriority = (p: Priority) => {
    const has = filters.priorities.includes(p)
    onFiltersChange({ ...filters, priorities: has ? filters.priorities.filter((x) => x !== p) : [...filters.priorities, p] })
  }
  const anyFilter = filters.q || filters.priorities.length || filters.exploitOnly
  const total = page?.total ?? 0
  const from = total ? pagination.pageIndex * pagination.pageSize + 1 : 0
  const to = Math.min(total, (pagination.pageIndex + 1) * pagination.pageSize)

  return (
    <div className="flex flex-col">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 px-4 pb-3">
        <label className="relative min-w-0 flex-1 basis-56">
          <span className="sr-only">Search CVE, assigner or signal</span>
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search CVE ID, assigner, signal…"
            className="h-9 w-full rounded-md border border-line-strong bg-bg pl-8 pr-8 text-sm text-fg placeholder:text-fg-subtle"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-fg-subtle hover:text-fg"
              aria-label="Clear search"
            >
              <X className="size-3.5" />
            </button>
          )}
        </label>
        <div className="flex items-center gap-1" role="group" aria-label="Filter by priority">
          {(['P0', 'P1', 'P2'] as Priority[]).map((p) => {
            const on = filters.priorities.includes(p)
            return (
              <button
                key={p}
                type="button"
                aria-pressed={on}
                onClick={() => togglePriority(p)}
                className={cn(
                  'flex h-9 items-center gap-1.5 rounded-md border px-2.5 font-mono text-xs font-semibold transition-colors',
                  on ? 'border-transparent' : 'border-line-strong text-fg-muted hover:bg-raised',
                )}
                style={on ? { backgroundColor: priorityColor[p], color: priorityText[p] } : undefined}
              >
                {!on && <span className="size-2 rounded-sm" style={{ backgroundColor: priorityColor[p] }} aria-hidden />}
                {p}
              </button>
            )
          })}
        </div>
        <button
          type="button"
          aria-pressed={filters.exploitOnly}
          onClick={() => onFiltersChange({ ...filters, exploitOnly: !filters.exploitOnly })}
          className={cn(
            'h-9 rounded-md border px-3 text-xs font-medium transition-colors',
            filters.exploitOnly ? 'border-sev-p1 bg-sev-p1/15 text-sevfg-p1' : 'border-line-strong text-fg-muted hover:bg-raised',
          )}
        >
          Public exploit only
        </button>
        {anyFilter ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setSearch('')
              onFiltersChange({ q: '', priorities: [], exploitOnly: false })
            }}
          >
            Reset
          </Button>
        ) : null}
      </div>

      {/* Table */}
      <div className="relative overflow-x-auto border-y border-line">
        <table className="w-full min-w-[960px] border-collapse text-sm">
          <thead className="bg-bg/50">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => {
                  const canSort = h.column.getCanSort()
                  const dir = h.column.getIsSorted()
                  return (
                    <th
                      key={h.id}
                      style={{ width: h.getSize() }}
                      aria-sort={dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : undefined}
                      className="h-9 whitespace-nowrap px-3 text-left text-[11px] font-semibold uppercase tracking-wider text-fg-muted"
                    >
                      {canSort ? (
                        <button
                          type="button"
                          onClick={h.column.getToggleSortingHandler()}
                          className={cn('inline-flex items-center gap-1 hover:text-fg', dir && 'text-fg')}
                        >
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          <SortIcon dir={dir} />
                        </button>
                      ) : (
                        flexRender(h.column.columnDef.header, h.getContext())
                      )}
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody className={cn('transition-opacity', loading && page && 'opacity-50')}>
            {!page && (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-t border-line">
                  <td colSpan={columns.length} className="px-3 py-3">
                    <div className="h-4 animate-pulse rounded bg-raised" style={{ width: `${90 - i * 6}%` }} />
                  </td>
                </tr>
              ))
            )}
            {page && page.rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-3 py-12 text-center text-fg-muted">
                  No CVEs match these filters.
                </td>
              </tr>
            )}
            {table.getRowModel().rows.map((row) => (
              <Fragment key={row.id}>
                <tr
                  className={cn(
                    'border-t border-line transition-colors hover:bg-raised/50',
                    row.getIsExpanded() && 'bg-raised/40',
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="h-11 whitespace-nowrap px-3">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
                {row.getIsExpanded() && (
                  <tr>
                    <td colSpan={columns.length} className="p-0">
                      <ReasonsPanel row={row.original} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
        {loading && page && (
          <Loader2 className="absolute right-3 top-2.5 size-4 animate-spin text-fg-subtle" aria-label="Loading" />
        )}
      </div>

      {/* Pagination */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-3 text-xs text-fg-muted">
        <div className="tabular font-mono">
          {fmtInt(from)}–{fmtInt(to)} of {fmtInt(total)}
          {page && <span className="ml-2 text-fg-subtle">· {page.tookMs} ms</span>}
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5">
            Rows
            <select
              value={pagination.pageSize}
              onChange={(e) => setPagination({ pageIndex: 0, pageSize: Number(e.target.value) })}
              className="h-8 rounded-md border border-line-strong bg-bg px-2 text-xs text-fg"
            >
              {PAGE_SIZES.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <span className="tabular font-mono">
            Page {fmtInt(pagination.pageIndex + 1)} / {fmtInt(page?.pageCount ?? 1)}
          </span>
          <div className="flex gap-1">
            <Button size="icon" variant="ghost" onClick={() => table.setPageIndex(0)} disabled={!table.getCanPreviousPage()} aria-label="First page">
              <ChevronsLeft />
            </Button>
            <Button size="icon" variant="ghost" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()} aria-label="Previous page">
              <ChevronLeft />
            </Button>
            <Button size="icon" variant="ghost" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()} aria-label="Next page">
              <ChevronRight />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              onClick={() => table.setPageIndex((page?.pageCount ?? 1) - 1)}
              disabled={!table.getCanNextPage()}
              aria-label="Last page"
            >
              <ChevronsRight />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
