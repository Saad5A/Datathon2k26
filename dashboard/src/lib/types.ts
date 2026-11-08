import type { Priority } from '@/theme/tokens'

/** One explanation entry inside the `reasons` JSON column. */
export interface Reason {
  signal: string
  value: number | string | null
  impact: number
  direction: 'up' | 'down'
}

/** Mirrors docs/INTERFACES.md column-for-column. */
export interface ScoreRow {
  cve_id: string
  published: string // YYYY-MM-DD
  snapshot_month: string // YYYY-MM
  assigner: string
  score: number // 0..1, uncalibrated
  rank: number // 1..N, unique
  percentile: number // 0..100
  in_top500: 0 | 1
  priority: Priority
  epss: number | null
  exploitdb: 0 | 1
  metasploit: 0 | 1
  nuclei: 0 | 1
  poc_github: 0 | 1
  any_public_exploit: 0 | 1
  reasons: Reason[] // parsed from the JSON string column
  model_version: string
}

export const CSV_COLUMNS = [
  'cve_id',
  'published',
  'snapshot_month',
  'assigner',
  'score',
  'rank',
  'percentile',
  'in_top500',
  'priority',
  'epss',
  'exploitdb',
  'metasploit',
  'nuclei',
  'poc_github',
  'any_public_exploit',
  'reasons',
  'model_version',
] as const

export const EXPLOIT_FLAGS = ['exploitdb', 'metasploit', 'nuclei', 'poc_github'] as const
export type ExploitFlag = (typeof EXPLOIT_FLAGS)[number]

export const EXPLOIT_FLAG_LABEL: Record<ExploitFlag, string> = {
  exploitdb: 'Exploit-DB',
  metasploit: 'Metasploit',
  nuclei: 'Nuclei',
  poc_github: 'GitHub PoC',
}

export interface Dataset {
  id: string
  name: string
<<<<<<< HEAD
  source: 'sample' | 'upload-client' | 'upload-api'
=======
  source: 'sample' | 'upload-client' | 'upload-api' | 'api'
>>>>>>> origin/feat/dashboard-backend
  rows: ScoreRow[]
  loadedAt: Date
}
