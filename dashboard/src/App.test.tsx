import { act, create, type ReactTestRenderer } from 'react-test-renderer'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { ScoreRow } from '@/lib/types'

const mocked = vi.hoisted(() => ({kitchen: null as unknown, read:vi.fn(), normalize:vi.fn()}))
vi.mock('@/components/Kitchen', () => ({Kitchen:(props:unknown) => {mocked.kitchen=props; return <div data-testid="kitchen"/>}}))
vi.mock('@/components/KitchenResults', () => ({KitchenResults:() => <div data-testid="results"/>}))
vi.mock('@/components/ApiStatus', () => ({ApiStatus:() => null}))
vi.mock('@/components/ui/tooltip', () => ({TooltipProvider:({children}:{children:React.ReactNode}) => children}))
vi.mock('@/lib/parse', () => ({IngestError:class extends Error {}, readRecords:mocked.read, normalizeStreaming:mocked.normalize, toCsv:vi.fn()}))
vi.mock('@/lib/apiClient', () => ({API_BASE:'',ApiError:class extends Error {}}))
vi.mock('@/lib/api', () => ({predict:vi.fn()}))
;(globalThis as {IS_REACT_ACT_ENVIRONMENT?:boolean}).IS_REACT_ACT_ENVIRONMENT=true
let renderer:ReactTestRenderer
interface KitchenProps {controller:{batchId:number};onServed:(id:number)=>void;onReview:()=>void;settled:boolean}
const kitchen = () => mocked.kitchen as KitchenProps
async function mount() { vi.stubGlobal('window',{scrollTo:vi.fn()}); await act(async()=>{renderer=create(<App/>)}) }
async function upload() {
  mocked.read.mockResolvedValue([{}]); mocked.normalize.mockResolvedValue({rows:[{cve_id:'CVE-2026-12345',priority:'P0'} as ScoreRow],warnings:[],preScored:true})
  const input=renderer.root.findByType('input')
  await act(async()=>{input.props.onChange({target:{files:[new File(['[]'],'input.json')],value:'input.json'}})})
  // Flush completion after readRecords has resolved.
  await act(async()=>{})
}
afterEach(async()=>{if(renderer)await act(async()=>renderer.unmount());vi.clearAllMocks();vi.unstubAllGlobals()})
describe('kitchen to results navigation',()=>{
  it('starts with only the kitchen, without synthetic result metrics',async()=>{
    await mount();expect(renderer.root.findAllByProps({'data-testid':'kitchen'})).toHaveLength(1)
    expect(renderer.root.findAllByProps({'data-testid':'results'})).toHaveLength(0)
  })
  it('makes completed data available before the animation ends',async()=>{
    await mount();await upload()
    expect(renderer.root.findAllByProps({'data-testid':'results'})).toHaveLength(0)
    await act(async()=>kitchen().onReview())
    expect(renderer.root.findAllByProps({'data-testid':'results'})).toHaveLength(1)
  })
  it('ignores stale animation completion and accepts the current batch',async()=>{
    await mount();await upload();const id=kitchen().controller.batchId
    await act(async()=>kitchen().onServed(id-1));expect(renderer.root.findAllByProps({'data-testid':'results'})).toHaveLength(0)
    await act(async()=>kitchen().onServed(id));expect(renderer.root.findAllByProps({'data-testid':'results'})).toHaveLength(1)
  })
  it('returns to a settled kitchen without replaying the sequence',async()=>{
    await mount();await upload();await act(async()=>kitchen().onReview())
    const back=renderer.root.findAllByType('button').find(button=>button.children.some(child=>typeof child==='string'&&child.includes('Back to kitchen')))!
    await act(async()=>back.props.onClick());expect(kitchen().settled).toBe(true)
  })
})
