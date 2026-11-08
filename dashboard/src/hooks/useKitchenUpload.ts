import { useCallback, useEffect, useRef, useState } from 'react'
import { predict } from '@/lib/api'
import { API_BASE, ApiError } from '@/lib/apiClient'
import { IngestError, normalizeStreaming, readRecords } from '@/lib/parse'
import type { Dataset, ScoreRow } from '@/lib/types'

export type Engine = 'client' | 'api'
export type UploadPhase =
  | { kind: 'idle' }
  | { kind: 'parsing'; file: File }
  | { kind: 'scoring'; file: File; done: number; total: number; leaders: ScoreRow[]; engine: Engine }
  | { kind: 'done'; file: File; rows: ScoreRow[]; warnings: string[]; preScored: boolean; engine: Engine; ms: number }
  | { kind: 'error'; message: string; file?: File; canFallback: boolean }

export function useKitchenUpload(onApply: (dataset: Dataset) => void) {
  const [batchId, setBatchId] = useState(0)
  const [phase, setPhase] = useState<UploadPhase>({ kind: 'idle' })
  const [engine, setEngine] = useState<Engine>('client')
  const [rescore, setRescore] = useState(false)
  const abort = useRef<AbortController | null>(null)
  const onApplyRef = useRef(onApply)
  onApplyRef.current = onApply
  useEffect(() => () => abort.current?.abort(), [])
  const reset = useCallback(() => { abort.current?.abort(); setBatchId(id => id + 1); setPhase({ kind: 'idle' }) }, [])
  const processFile = useCallback(async (file: File, selectedEngine: Engine, newBatch: boolean, isSample = false) => {
    abort.current?.abort()
    const ac = new AbortController(); abort.current = ac
    if (newBatch) setBatchId(id => id + 1)
    const start = performance.now()
    if (file.size > 50 * 1024 * 1024) {
      setPhase({kind:'error', message:'File exceeds the upload limit of 50 MB.', file, canFallback:false}); return
    }
    try {
      setPhase({ kind:'parsing', file })
      const records = await readRecords(file)
      if (ac.signal.aborted) return
      if (!records.length) throw new IngestError('File contains no rows.')
      let result: { rows: ScoreRow[]; warnings: string[]; preScored: boolean }
      if (selectedEngine === 'api') {
        if (!API_BASE) throw new IngestError('No model API is configured. Select the local demo engine.')
        setPhase({ kind:'scoring', file, done:0, total:records.length, leaders:[], engine:selectedEngine })
        result = { rows:await predict(records, ac.signal), warnings:[], preScored:true }
      } else {
        result = await normalizeStreaming(records, rescore ? 'rescore' : 'auto', progress => {
          if (!ac.signal.aborted) setPhase({kind:'scoring', file, engine:selectedEngine, ...progress})
        }, {signal:ac.signal})
      }
      if (ac.signal.aborted) return
      setPhase({kind:'done', file, engine:selectedEngine, ms:performance.now()-start, ...result})
      onApplyRef.current({isSample, id:`${file.name}-${Date.now()}`, name:file.name, source:selectedEngine==='api'?'upload-api':'upload-client', rows:result.rows, loadedAt:new Date()})
    } catch (error) {
      if (ac.signal.aborted) return
      setPhase({ kind:'error', message:error instanceof IngestError || error instanceof ApiError ? error.message : `Unexpected error: ${(error as Error).message}`, file, canFallback:selectedEngine==='api' })
    }
  }, [rescore])
  const run = useCallback((file: File, selectedEngine: Engine = engine) => processFile(file, selectedEngine, true), [engine, processFile])
  const trySample = useCallback(async () => {
    abort.current?.abort()
    const ac = new AbortController(); abort.current = ac
    setBatchId(id => id + 1)
    setPhase({kind:'parsing', file:new File([], 'sample_judge_input.csv', {type:'text/csv'})})
    try {
      const response = await fetch('/sample_judge_input.csv', {signal:ac.signal})
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const blob = await response.blob()
      if (!ac.signal.aborted) void processFile(new File([blob], 'sample_judge_input.csv', {type:'text/csv'}), engine, false, true)
    } catch (error) {
      if (!ac.signal.aborted) setPhase({kind:'error', message:`Could not load sample: ${(error as Error).message}`,canFallback:false})
    }
  }, [engine, processFile])
  return {batchId, phase, engine, setEngine, rescore, setRescore, run, reset, trySample}
}
export type KitchenUpload = ReturnType<typeof useKitchenUpload>
