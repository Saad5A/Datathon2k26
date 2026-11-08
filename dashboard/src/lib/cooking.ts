import type { UploadPhase } from '@/hooks/useKitchenUpload'

export type CookingStep = 'ready' | 'pouring' | 'cooking' | 'flipping' | 'plating' | 'plated'
export interface CookingTimeline { batchId: number; step: CookingStep; elapsed: number }
export const cookingDuration = { pouring: 2.1, cooking: 1.6, flipping: 1.45, plating: .6 }
export const initialCooking = (batchId = 0, plated = false): CookingTimeline => ({batchId, step: plated ? 'plated' : 'ready', elapsed: 0})

/** Presentation time is independent of processing time; it never delays data. */
export function advanceCooking(previous: CookingTimeline, batchId: number, phase: UploadPhase['kind'], delta: number, paused = false, reducedMotion = false): CookingTimeline {
  if (phase === 'idle' || phase === 'error') return initialCooking(batchId)
  let state = previous.batchId !== batchId || previous.step === 'ready'
    ? {batchId, step: 'pouring' as CookingStep, elapsed: 0}
    : {...previous}
  if (reducedMotion) return {batchId, step: phase === 'done' ? 'plated' : phase === 'parsing' ? 'pouring' : 'cooking', elapsed: 0}
  if (paused || state.step === 'plated') return state
  state.elapsed += Math.max(0, delta)
  if (state.step === 'pouring' && state.elapsed >= cookingDuration.pouring) state = {batchId, step:'cooking', elapsed:0}
  if (state.step === 'cooking' && state.elapsed >= cookingDuration.cooking && phase === 'done') state = {batchId, step:'flipping', elapsed:0}
  if (state.step === 'flipping' && state.elapsed >= cookingDuration.flipping) state = {batchId, step:'plating', elapsed:0}
  if (state.step === 'plating' && state.elapsed >= cookingDuration.plating) state = {batchId, step:'plated', elapsed:0}
  return state
}
export const smooth = (value: number) => { const t = Math.min(1,Math.max(0,value)); return t*t*(3-2*t) }
