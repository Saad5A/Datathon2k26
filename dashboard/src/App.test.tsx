import { act, create, type ReactTestRenderer } from 'react-test-renderer'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('@/components/pancake/PancakeSecDashboard', () => ({
  PancakeSecDashboard: () => <div data-testid="pancakesec" />,
}))

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let renderer: ReactTestRenderer

afterEach(async () => {
  if (renderer) await act(async () => renderer.unmount())
})

describe('home entry', () => {
  it('renders the PancakeSec dashboard', async () => {
    await act(async () => {
      renderer = create(<App />)
    })
    expect(renderer.root.findAllByProps({ 'data-testid': 'pancakesec' })).toHaveLength(1)
  })
})
