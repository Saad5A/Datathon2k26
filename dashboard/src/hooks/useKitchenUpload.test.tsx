import { act, create, type ReactTestRenderer } from 'react-test-renderer'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useKitchenUpload, type KitchenUpload } from './useKitchenUpload'
import type { ScoreRow } from '@/lib/types'

const mocks=vi.hoisted(()=>({read:vi.fn(),normalize:vi.fn(),predict:vi.fn()}))
vi.mock('@/lib/parse',()=>({IngestError:class extends Error {},readRecords:mocks.read,normalizeStreaming:mocks.normalize}))
vi.mock('@/lib/api',()=>({predict:mocks.predict}))
vi.mock('@/lib/apiClient',()=>({API_BASE:'https://model.test',ApiError:class extends Error {}}))
;(globalThis as {IS_REACT_ACT_ENVIRONMENT?:boolean}).IS_REACT_ACT_ENVIRONMENT=true
const row={cve_id:'CVE-2026-12345',priority:'P0',rank:1,score:.5} as ScoreRow
const result={rows:[row],warnings:['Preserved warning'],preScored:true}
const file=()=>new File(['[]'],'batch.json',{type:'application/json'})
let renderer:ReactTestRenderer
let controller:KitchenUpload
async function mount(){const apply=vi.fn();function Harness(){controller=useKitchenUpload(apply);return null}await act(async()=>{renderer=create(<Harness/>)});return apply}
const deferred=<T,>()=>{let resolve!:(value:T)=>void;const promise=new Promise<T>(r=>{resolve=r});return {promise,resolve}}
afterEach(async()=>{if(renderer)await act(async()=>renderer.unmount());vi.resetAllMocks();vi.unstubAllGlobals()})
describe('kitchen upload lifecycle',()=>{
 it('applies completed local results immediately with warnings and source',async()=>{
  mocks.read.mockResolvedValue([{}]);mocks.normalize.mockResolvedValue(result);const apply=await mount()
  await act(async()=>controller.run(file()))
  expect(controller.phase).toMatchObject({kind:'done',warnings:result.warnings,preScored:true})
  expect(apply).toHaveBeenCalledWith(expect.objectContaining({rows:[row],source:'upload-client'}))
 })
 it('does not apply a cancelled parse',async()=>{
  const pending=deferred<Record<string,unknown>[]>();mocks.read.mockReturnValue(pending.promise);const apply=await mount()
  let running!:Promise<void>;await act(async()=>{running=controller.run(file())})
  await act(async()=>controller.reset());await act(async()=>{pending.resolve([{}]);await running})
  expect(controller.phase.kind).toBe('idle');expect(apply).not.toHaveBeenCalled()
 })
 it('does not apply scoring that resolves after cancellation',async()=>{
  const pending=deferred<typeof result>();mocks.read.mockResolvedValue([{}]);mocks.normalize.mockReturnValue(pending.promise);const apply=await mount()
  let running!:Promise<void>;await act(async()=>{running=controller.run(file())});await act(async()=>controller.reset())
  await act(async()=>{pending.resolve(result);await running});expect(apply).not.toHaveBeenCalled();expect(controller.phase.kind).toBe('idle')
 })
 it('prevents an older request from overwriting the newer batch',async()=>{
  const pending=deferred<typeof result>();mocks.read.mockResolvedValue([{}]);mocks.normalize.mockReturnValueOnce(pending.promise).mockResolvedValueOnce(result);const apply=await mount()
  let first!:Promise<void>;await act(async()=>{first=controller.run(file())});await act(async()=>controller.run(new File(['[]'],'new.json')))
  await act(async()=>{pending.resolve(result);await first});expect(apply).toHaveBeenCalledTimes(1);expect(apply.mock.calls[0][0].name).toBe('new.json')
 })
 it('exposes API waiting state then applies model output',async()=>{
  const pending=deferred<ScoreRow[]>();mocks.read.mockResolvedValue([{}]);mocks.predict.mockReturnValue(pending.promise);const apply=await mount()
  let running!:Promise<void>;await act(async()=>{running=controller.run(file(),'api')})
  expect(controller.phase).toMatchObject({kind:'scoring',engine:'api',done:0})
  await act(async()=>{pending.resolve([row]);await running});expect(apply.mock.calls[0][0].source).toBe('upload-api')
 })
 it('retains current data on failure and offers explicit API fallback',async()=>{
  mocks.read.mockResolvedValue([{}]);mocks.predict.mockRejectedValue(new Error('Offline'));const apply=await mount()
  await act(async()=>controller.run(file(),'api'));expect(controller.phase).toMatchObject({kind:'error',canFallback:true});expect(apply).not.toHaveBeenCalled()
 })
 it('marks sample fetch busy and cancels it without starting ingestion',async()=>{
  const pending=deferred<Response>();vi.stubGlobal('fetch',vi.fn().mockReturnValue(pending.promise));const apply=await mount()
  let running!:Promise<void>;await act(async()=>{running=controller.trySample()});expect(controller.phase.kind).toBe('parsing')
  await act(async()=>controller.reset());await act(async()=>{pending.resolve(new Response('[]'));await running})
  expect(controller.phase.kind).toBe('idle');expect(mocks.read).not.toHaveBeenCalled();expect(apply).not.toHaveBeenCalled()
 })
 it('starts sample fetching as a new batch and marks only built-in samples',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('[]')))
  mocks.read.mockResolvedValue([{}]);mocks.normalize.mockResolvedValue(result)
  const apply=await mount();const before=controller.batchId
  await act(async()=>{await controller.trySample()});await act(async()=>{})
  expect(controller.batchId).toBeGreaterThan(before)
  expect(apply.mock.calls[0][0].isSample).toBe(true)
  await act(async()=>controller.run(new File(['[]'],'sample_judge_input.csv')))
  expect(apply.mock.calls[1][0].isSample).toBe(false)
 })
 it('rejects empty input and oversized files without applying results',async()=>{
  mocks.read.mockResolvedValue([]);const apply=await mount();await act(async()=>controller.run(file()));expect(controller.phase.kind).toBe('error')
  const big=file();Object.defineProperty(big,'size',{value:51*1024*1024});await act(async()=>controller.run(big));expect(controller.phase).toMatchObject({kind:'error',canFallback:false});expect(apply).not.toHaveBeenCalled()
 })
})
