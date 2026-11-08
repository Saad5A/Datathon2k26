import { MessageCircle, Send, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { askProjectChat } from '@/lib/backend'

type Turn = { role: 'user' | 'assistant'; content: string }

const BOOT: Turn = {
  role: 'assistant',
  content:
    'Gemini 2.5 Flash, answering live. It cannot see this project\'s results files, so its answers are AI-generated and unaudited; check numbers on the Evidence page.',
}

type Props = {
  open: boolean
  onClose: () => void
  cveId?: string | null
}

export function JudgeQaDrawer({ open, onClose, cveId }: Props) {
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [chatMessages, setChatMessages] = useState<Turn[]>([BOOT])
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const el = bodyRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [chatMessages, open])

  if (!open) return null

  const sendCustomGeminiQuery = async (e?: FormEvent) => {
    e?.preventDefault()
    const query = input.trim()
    if (!query || busy) return

    // 1. Append user question immediately
    setChatMessages((prev) => [...prev, { role: 'user', content: query }])
    setInput('')
    setBusy(true)

    // 2. Typing placeholder
    setChatMessages((prev) => [...prev, { role: 'assistant', content: 'Analyzing project data...' }])

    try {
      // history omits the temporary placeholder (and we rebuild from state snapshot)
      const historySnapshot = [...chatMessages, { role: 'user' as const, content: query }].filter(
        (m) => m !== BOOT && !m.content.toLowerCase().startsWith('analyzing project data'),
      )
      const res = await askProjectChat({
        question: query,
        active_cve: cveId || 'CVE-2026-10523',
        history: historySnapshot.slice(0, -1).map((m) => ({ role: m.role, content: m.content })),
      })
      const answer = (res.answer || res.reply || '').trim() || 'No answer returned from chat service.'
      setChatMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = { role: 'assistant', content: answer }
        return next
      })
    } catch (err) {
      const raw = err instanceof Error ? err.message : String(err)
      const hint = /GEMINI_API_KEY/i.test(raw)
        ? 'Add GEMINI_API_KEY to Datathon2k26/.env and restart FastAPI.'
        : 'Ensure FastAPI is running on port 8000 with google-genai installed.'
      setChatMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = {
          role: 'assistant',
          content: `Error: ${raw}\n\n${hint}`,
        }
        return next
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-[#1E1611]/35 backdrop-blur-[2px]">
      <button type="button" className="flex-1 cursor-default" aria-label="Close Q&A" onClick={onClose} />
      <aside className="flex h-full w-full max-w-md flex-col border-l border-[#E8DFC8] bg-[#FAF7F2] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#E8DFC8] px-4 py-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-extrabold text-[#1E1611]">
              <MessageCircle className="h-4 w-4 text-[#8B3A0F]" />
              Judge Q&A
            </div>
            <p className="text-[11px] text-[#7A6B5D]">Gemini 2.5 Flash · AI-generated answers, unaudited</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#E8DFC8] bg-white p-1.5 text-[#451A03] hover:bg-[#F7EFE2]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div
          id="gemini-interactive-output"
          ref={bodyRef}
          className="custom-scroll flex-1 space-y-1 overflow-y-auto px-4 py-4"
        >
          <div id="output-action-body">
            {chatMessages.map((msg, i) => (
              <div key={`${msg.role}-${i}-${msg.content.slice(0, 12)}`} className={`mb-3 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                <div
                  className={`inline-block max-w-[85%] rounded-xl px-3.5 py-2 text-left text-xs ${
                    msg.role === 'user'
                      ? 'bg-[#8B3A0F] font-medium text-white'
                      : 'border border-[#451A03] bg-[#2A160C] text-[#F5ECE5]'
                  }`}
                >
                  <div className="mb-0.5 text-[9px] font-bold uppercase tracking-wider opacity-60">
                    {msg.role === 'user' ? 'User' : 'Gemini 2.5 Flash · AI-generated'}
                  </div>
                  <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <form onSubmit={(e) => void sendCustomGeminiQuery(e)} className="border-t border-[#E8DFC8] bg-white/80 p-3">
          <div className="flex items-center gap-2">
            <input
              id="gemini-custom-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a technical question…"
              className="flex-1 rounded-xl border border-[#E8DFC8] bg-white px-3 py-2.5 text-xs focus:border-[#8B3A0F] focus:outline-none"
              disabled={busy}
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="flex items-center gap-1 rounded-xl bg-[#451A03] px-3 py-2.5 text-xs font-bold text-white hover:bg-[#2D1204] disabled:opacity-50"
            >
              <Send className="h-3.5 w-3.5" />
              Ask
            </button>
          </div>
        </form>
      </aside>
    </div>
  )
}
