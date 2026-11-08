import Papa from 'papaparse'
import type { Priority } from '@/theme/tokens'
import { assignRanks, dummyScore } from './scoring'
import { CSV_COLUMNS, type Reason, type ScoreRow } from './types'

export type RawRecord = Record<string, unknown>

export class IngestError extends Error {}

const CVE_RE = /^CVE-\d{4}-\d{4,}$/i

/** Read a File as CSV or JSON into plain records. */
export async function readRecords(file: File): Promise<RawRecord[]> {
  const text = await file.text()
  const name = file.name.toLowerCase()
  const looksJson = name.endsWith('.json') || /^\s*[[{]/.test(text)

  if (looksJson) {
    let data: unknown
    try {
      data = JSON.parse(text)
    } catch (e) {
      throw new IngestError(`Invalid JSON: ${(e as Error).message}`)
    }
    const arr = Array.isArray(data)
      ? data
      : data && typeof data === 'object' && Array.isArray((data as { rows?: unknown }).rows)
        ? (data as { rows: unknown[] }).rows
        : null
    if (!arr) throw new IngestError('JSON must be an array of CVE objects or { "rows": [...] }.')
    return arr.filter((r): r is RawRecord => !!r && typeof r === 'object')
  }

  // Tolerate backslash-escaped quotes (\") from hand-written CSVs; RFC 4180 uses "".
  const csvText = text.includes('\\"') ? text.replace(/\\"/g, '""') : text
  const parsed = Papa.parse<RawRecord>(csvText, {
    header: true,
    skipEmptyLines: 'greedy',
    transformHeader: (h) => h.trim().toLowerCase(),
  })
  if (parsed.errors.length && !parsed.data.length) {
    throw new IngestError(`CSV parse error: ${parsed.errors[0].message}`)
  }
  return parsed.data
}

/* ------------------------------------------------------------------------ */

const str = (v: unknown) => (v == null ? '' : String(v).trim())

function num(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = typeof v === 'number' ? v : Number(String(v).trim())
  return Number.isFinite(n) ? n : null
}

const flag = (v: unknown): 0 | 1 => {
  if (typeof v === 'boolean') return v ? 1 : 0
  const s = str(v).toLowerCase()
  return s === '1' || s === 'true' || s === 'yes' ? 1 : 0
}

function parseReasons(v: unknown): Reason[] {
  let arr: unknown = v
  if (typeof v === 'string') {
    if (!v.trim()) return []
    try {
      arr = JSON.parse(v)
    } catch {
      return []
    }
  }
  if (!Array.isArray(arr)) return []
  return arr
    .filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
    .map((r) => ({
      signal: str(r.signal) || 'unknown_signal',
      value: typeof r.value === 'number' || typeof r.value === 'string' ? r.value : null,
      impact: num(r.impact) ?? 0,
      direction: str(r.direction) === 'down' ? 'down' : 'up',
    }))
}

const isPriority = (p: string): p is Priority => p === 'P0' || p === 'P1' || p === 'P2'

function baseRow(raw: RawRecord, i: number): ScoreRow {
  const cve = str(raw.cve_id ?? raw.cve ?? raw.id).toUpperCase()
  if (!cve) throw new IngestError(`Row ${i + 1}: missing cve_id.`)
  const published = str(raw.published ?? raw.published_date).slice(0, 10)
  const flags = {
    exploitdb: flag(raw.exploitdb),
    metasploit: flag(raw.metasploit),
    nuclei: flag(raw.nuclei),
    poc_github: flag(raw.poc_github),
  }
  const anyRaw = raw.any_public_exploit
  const any_public_exploit: 0 | 1 =
    anyRaw == null || anyRaw === ''
      ? ((flags.exploitdb || flags.metasploit || flags.nuclei || flags.poc_github) as 0 | 1)
      : flag(anyRaw)
  const epss = num(raw.epss)
  const prio = str(raw.priority).toUpperCase()

  return {
    cve_id: cve,
    published,
    snapshot_month: str(raw.snapshot_month) || published.slice(0, 7),
    assigner: str(raw.assigner) || 'unknown',
    score: Math.min(1, Math.max(0, num(raw.score) ?? 0)),
    rank: num(raw.rank) ?? 0,
    percentile: num(raw.percentile) ?? 0,
    in_top500: flag(raw.in_top500),
    priority: isPriority(prio) ? prio : 'P2',
    epss: epss == null ? null : Math.min(1, Math.max(0, epss)),
    ...flags,
    any_public_exploit,
    reasons: parseReasons(raw.reasons),
    model_version: str(raw.model_version) || 'v0',
  }
}

export interface IngestSummary {
  rows: ScoreRow[]
  preScored: boolean
  warnings: string[]
}

export function hasScores(records: RawRecord[]) {
  return records.length > 0 && records.every((r) => num(r.score) != null)
}

export interface IngestProgress {
  done: number
  total: number
  /** Current provisional leaders (by score), for the live ranking view. */
  leaders: ScoreRow[]
}

interface IngestState {
  preScored: boolean
  seen: Set<string>
  rows: ScoreRow[]
  warnings: string[]
  missingId: number
  dupes: number
  nonStandard: number
}

function startIngest(records: RawRecord[], mode: 'auto' | 'rescore'): IngestState {
  if (!records.length) throw new IngestError('File contains no rows.')
  return {
    preScored: mode === 'auto' && hasScores(records),
    seen: new Set(),
    rows: [],
    warnings: [],
    missingId: 0,
    dupes: 0,
    nonStandard: 0,
  }
}

function ingestOne(st: IngestState, raw: RawRecord, i: number) {
  let row: ScoreRow
  try {
    row = baseRow(raw, i)
  } catch (e) {
    st.missingId++
    if (st.missingId <= 3) st.warnings.push((e as Error).message)
    return
  }
  if (st.seen.has(row.cve_id)) {
    st.dupes++
    return
  }
  st.seen.add(row.cve_id)
  if (!CVE_RE.test(row.cve_id)) st.nonStandard++
  if (!st.preScored) {
    const { score, reasons } = dummyScore(row)
    row.score = score
    row.reasons = reasons
    row.model_version = 'client-dummy-v0'
  }
  st.rows.push(row)
}

function finishIngest(st: IngestState, records: RawRecord[]): IngestSummary {
  const { rows, warnings } = st
  if (st.missingId > 3) warnings.push(`${st.missingId} rows without cve_id skipped in total.`)
  if (st.dupes > 0) warnings.push(`${st.dupes} duplicate cve_id row(s) skipped.`)
  if (st.nonStandard > 0) warnings.push(`${st.nonStandard} row(s) have a non-standard cve_id format.`)
  if (!rows.length) throw new IngestError('No usable rows: every record was missing cve_id.')
  // A fully pre-ranked file (e.g. outputs/scores_2026.csv or a slice of it) keeps the
  // model's global rank/percentile/priority; anything else is ranked within the file.
  const fullyRanked =
    st.preScored &&
    records.every((r) => num(r.rank) != null && num(r.percentile) != null && isPriority(str(r.priority).toUpperCase())) &&
    new Set(rows.map((r) => r.rank)).size === rows.length
  if (fullyRanked) {
    rows.sort((a, b) => a.rank - b.rank)
    return { rows, preScored: true, warnings }
  }
  const keepPriority = st.preScored && records.every((r) => isPriority(str(r.priority).toUpperCase()))
  assignRanks(rows, { keepPriority })
  return { rows, preScored: st.preScored, warnings }
}

/**
 * Normalise records into ScoreRows.
 *  - mode 'auto': if every record already carries `score`, honour it (and its priority).
 *  - otherwise run the in-browser dummy scorer.
 */
export function normalize(records: RawRecord[], mode: 'auto' | 'rescore' = 'auto'): IngestSummary {
  const st = startIngest(records, mode)
  records.forEach((raw, i) => ingestOne(st, raw, i))
  return finishIngest(st, records)
}

function topN(rows: ScoreRow[], n: number) {
  const out: ScoreRow[] = []
  for (const r of rows) {
    if (out.length < n || r.score > out[out.length - 1].score) {
      out.push(r)
      out.sort((a, b) => b.score - a.score)
      if (out.length > n) out.pop()
    }
  }
  return out
}

/**
 * Same as `normalize`, but yields to the browser between chunks and reports
 * provisional leaders so the UI can render rankings as they form.
 */
export async function normalizeStreaming(
  records: RawRecord[],
  mode: 'auto' | 'rescore',
  onProgress: (p: IngestProgress) => void,
  opts: { chunkSize?: number; signal?: AbortSignal; minFrameMs?: number } = {},
): Promise<IngestSummary> {
  const st = startIngest(records, mode)
  const chunk = opts.chunkSize ?? Math.max(250, Math.ceil(records.length / 40))
  for (let i = 0; i < records.length; i += chunk) {
    if (opts.signal?.aborted) throw new DOMException('aborted', 'AbortError')
    const end = Math.min(records.length, i + chunk)
    for (let j = i; j < end; j++) ingestOne(st, records[j], j)
    onProgress({ done: end, total: records.length, leaders: topN(st.rows, 10) })
    await new Promise((r) => setTimeout(r, opts.minFrameMs ?? 16))
  }
  return finishIngest(st, records)
}

/** Normalise rows coming back from POST /predict. */
export function normalizeApiResponse(data: unknown): ScoreRow[] {
  const arr = Array.isArray(data)
    ? data
    : data && typeof data === 'object'
      ? ((data as { rows?: unknown; predictions?: unknown }).rows ??
        (data as { predictions?: unknown }).predictions)
      : null
  if (!Array.isArray(arr)) throw new IngestError('/predict returned an unexpected payload (expected an array or { rows }).')
  if (!hasScores(arr as RawRecord[])) throw new IngestError('/predict response rows are missing `score`.')
  return normalize(arr as RawRecord[], 'auto').rows
}

/** Serialise rows back to the INTERFACES.md CSV shape (for export). */
export function toCsv(rows: ScoreRow[]) {
  return Papa.unparse(
    rows.map((r) => ({ ...r, epss: r.epss ?? '', reasons: JSON.stringify(r.reasons) })),
    {
      columns: [...CSV_COLUMNS],
    },
  )
}
