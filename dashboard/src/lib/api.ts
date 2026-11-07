import { IngestError, normalizeApiResponse, type RawRecord } from './parse'
import type { ScoreRow } from './types'

/** Default predict endpoint; overridable at build time with VITE_PREDICT_URL. */
export const DEFAULT_PREDICT_URL: string = import.meta.env.VITE_PREDICT_URL ?? '/predict'

/**
 * POST raw CVE records to the model server.
 * Request:  { "rows": [ { cve_id, published, assigner, epss, exploitdb, … } ] }
 * Response: [ ScoreRow-shaped objects ]  or  { "rows": [...] }
 */
export async function predict(url: string, records: RawRecord[], signal?: AbortSignal): Promise<ScoreRow[]> {
  let res: Response
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ rows: records }),
      signal,
    })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new IngestError(`Could not reach ${url}. Is the model server running?`)
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new IngestError(`${url} responded ${res.status} ${res.statusText}${detail ? ` — ${detail.slice(0, 160)}` : ''}`)
  }
  const ct = res.headers.get('content-type') ?? ''
  if (!ct.includes('json')) throw new IngestError(`${url} did not return JSON (content-type: ${ct || 'none'}).`)
  return normalizeApiResponse(await res.json())
}
