import { act, create, type ReactTestRenderer } from 'react-test-renderer'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ResultsPage } from './ResultsPage'
import { RESULTS_SNAPSHOT } from '@/lib/results'

// Recharts needs a real layout engine; the page's data wiring is what we test.
vi.mock('recharts', () => {
  const Box = ({ children }: { children?: ReactNode }) => <div>{children}</div>
  const Nothing = () => null
  return {
    ResponsiveContainer: Box,
    BarChart: Box,
    Bar: Box,
    XAxis: Nothing,
    YAxis: Nothing,
    CartesianGrid: Nothing,
    Tooltip: Nothing,
    Cell: Nothing,
    LabelList: Nothing,
  }
})

vi.mock('@/lib/results', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/results')>()
  return { ...actual, fetchResults: vi.fn().mockRejectedValue(new Error('offline')) }
})

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let renderer: ReactTestRenderer | undefined

async function mount() {
  await act(async () => {
    renderer = create(<ResultsPage />)
  })
  await act(async () => {})
  return JSON.stringify(renderer!.toJSON())
}

afterEach(async () => {
  if (renderer) await act(async () => renderer!.unmount())
  renderer = undefined
  vi.clearAllMocks()
})

describe('results evidence sheet', () => {
  it('renders the submitted model and the head-to-head table from the artifact snapshot', async () => {
    const text = await mount()
    const fold1 = RESULTS_SNAPSHOT.folds[0]
    const g2 = fold1.models.find((model) => model.key === 'G2')
    expect(text).toContain('The queue is not a guess')
    expect(text).toContain('G2')
    expect(text).toContain(String(g2?.metrics.auc.value?.toFixed(3)))
    expect(text).toContain('Exploit code, then EPSS')
  })

  it('falls back to the bundled snapshot and says so when the API is unavailable', async () => {
    const text = await mount()
    expect(text).toContain('Bundled snapshot')
    expect(text).toContain('generated')
  })

  it('keeps the no-2026-accuracy and top-500-noise limits visible', async () => {
    const text = await mount()
    expect(text).toContain('No 2026 accuracy')
    expect(text).toContain('Top-500 is noisy')
    expect(text).toContain('G2 is not an improvement')
  })

  it('answers the ensemble question without claiming an unmeasured gain', async () => {
    const text = await mount()
    expect(text).toContain('Would an ensemble be better? Not automatically.')
    expect(text).toContain('Averaging near-duplicates is not an ensemble.')
    expect(text).toContain('research plan, not')
  })
})
