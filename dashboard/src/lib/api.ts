import { apiJson } from './apiClient'
import { normalizeApiResponse, type RawRecord } from './parse'
import type { ScoreRow } from './types'

/**
 * POST raw CVE records to the model server.
 * Request:  { "rows": [ { cve_id, published, assigner, epss, exploitdb, … } ] }
 * Response: [ ScoreRow-shaped objects ]  or  { "rows": [...] }
 */
export async function predict(records: RawRecord[], signal?: AbortSignal): Promise<ScoreRow[]> {
  const data = await apiJson<unknown>('/predict', {
    method: 'POST',
    body: JSON.stringify({ rows: records }),
    signal,
    timeoutMs: 60_000, // large uploads legitimately take a while
  })
  return normalizeApiResponse(data)
}
