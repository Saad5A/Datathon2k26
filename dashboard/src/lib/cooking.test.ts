import { describe, expect, it } from 'vitest'
import { advanceCooking, initialCooking, cookingDuration, type CookingTimeline } from './cooking'

describe('continuous cooking presentation', () => {
  it('does not skip pouring when processing finishes instantly', () => {
    const state = advanceCooking(initialCooking(), 1, 'done', .1)
    expect(state.step).toBe('pouring')
  })
  it('plays the entire story after a fast result', () => {
    let state = advanceCooking(initialCooking(), 1, 'done', 0)
    state = advanceCooking(state, 1, 'done', cookingDuration.pouring)
    expect(state.step).toBe('cooking')
    state = advanceCooking(state, 1, 'done', cookingDuration.cooking)
    expect(state.step).toBe('flipping')
    state = advanceCooking(state, 1, 'done', cookingDuration.flipping)
    expect(state.step).toBe('plating')
    state = advanceCooking(state, 1, 'done', cookingDuration.plating)
    expect(state.step).toBe('plated')
  })
  it('waits on the stove for a slow server without claiming completion', () => {
    const state = advanceCooking({ batchId:1, step:'cooking', elapsed:1 }, 1, 'scoring', 30)
    expect(state.step).toBe('cooking')
    expect(advanceCooking(state, 1, 'done', .1).step).toBe('flipping')
  })
  it('pauses presentation but still lets the controller finish independently', () => {
    const state: CookingTimeline = {batchId:1, step:'cooking', elapsed:1}
    expect(advanceCooking(state, 1, 'done', 10, true)).toEqual(state)
  })
  it('returns to a clean station on cancellation or failure', () => {
    const state: CookingTimeline = {batchId:1, step:'flipping', elapsed:.5}
    expect(advanceCooking(state, 2, 'idle', .1).step).toBe('ready')
    expect(advanceCooking(state, 1, 'error', .1).step).toBe('ready')
  })
  it('resets a stale animation for a new batch', () => {
    const state = advanceCooking({batchId:1, step:'plating', elapsed:.5}, 2, 'parsing', .1)
    expect(state.batchId).toBe(2); expect(state.step).toBe('pouring')
  })
  it('serves results immediately with reduced motion and preserves settled batches', () => {
    expect(advanceCooking(initialCooking(), 1, 'done', 0, true, true).step).toBe('plated')
    expect(advanceCooking(initialCooking(1, true), 1, 'done', 10).step).toBe('plated')
  })
})
