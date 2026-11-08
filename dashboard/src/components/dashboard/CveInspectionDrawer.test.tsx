import { act, create, type ReactTestRenderer } from 'react-test-renderer'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CveInspectionDrawer } from './CveInspectionDrawer'

vi.mock('@/lib/backend', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/backend')>()
  return {
    ...actual,
    LIVE_API: true,
    fetchExplanation: vi.fn().mockResolvedValue({
      available: { explanation: true, playbook: false, granite: true, gemini: false },
      granite: {
        summary: 'Grounded Granite note.',
        provider: 'IBM',
        model_id: 'granite-test',
        grounding_ok: true,
      },
      remediation: { steps: [], playbook: null, is_ai_generated: false },
    }),
    fetchSimilarCves: vi.fn().mockResolvedValue({
      cve_id: 'CVE-2026-10523',
      top_k: 5,
      similar: [
        {
          cve_id: 'CVE-2021-44228',
          similarity: 0.91,
          rank: null,
          published: null,
          scope: 'historical pool',
        },
      ],
      index: {
        model_id: 'ibm-granite/granite-embedding-small-english-r2',
        dimension: 384,
        rows: 2000,
        purpose: 'retrieval only',
      },
      note: 'Description-similarity neighbours. Retrieval evidence only.',
    }),
    refineGeminiAction: vi.fn(),
  }
})

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let renderer: ReactTestRenderer | undefined

beforeEach(() => {
  vi.stubGlobal('window', { addEventListener: vi.fn(), removeEventListener: vi.fn() })
})

afterEach(async () => {
  if (renderer) await act(async () => renderer!.unmount())
  renderer = undefined
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('CVE drawer retrieval panel', () => {
  it('shows nearest neighbours with the retrieval-only disclaimer', async () => {
    await act(async () => {
      renderer = create(<CveInspectionDrawer cveId="CVE-2026-10523" open onOpenChange={() => {}} />)
    })
    await act(async () => {})
    const text = JSON.stringify(renderer!.toJSON())
    expect(text).toContain('Nearest neighbours')
    expect(text).toContain('CVE-2021-44228')
    expect(text).toContain('retrieval evidence, not a')
    expect(text).toContain('0.910')
    expect(text).toContain('granite-embedding-small-english-r2')
  })

  it('stays quiet when the drawer is closed', async () => {
    await act(async () => {
      renderer = create(<CveInspectionDrawer cveId="CVE-2026-10523" open={false} onOpenChange={() => {}} />)
    })
    expect(renderer!.toJSON()).toBeNull()
  })
})
