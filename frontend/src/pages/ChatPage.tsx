import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Eraser, SendHorizontal } from 'lucide-react'
import { ApiError, api } from '../api/client'
import type { ChatTurn } from '../api/types'
import { useI18n } from '../i18n'
import type { StringKey } from '../i18n/strings'
import { Page } from '../shell'
import { Button } from '../ui/controls'
import { ErrorNote, Skeleton } from '../ui/states'
import { useLoad } from '../useLoad'

export function ChatPage() {
  const { t } = useI18n()
  const history = useLoad(() => api.chatHistory(), [])
  const [local, setLocal] = useState<ChatTurn[] | null>(null)   // null = show the saved history
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const end = useRef<HTMLDivElement>(null)

  const turns = local ?? history.data ?? []
  const setTurns = (fn: (t: ChatTurn[]) => ChatTurn[]) => setLocal((cur) => fn(cur ?? history.data ?? []))
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }) }, [turns.length, sending])

  const send = async (e: FormEvent) => {
    e.preventDefault()
    const message = text.trim()
    if (!message || sending) return
    setText('')
    setError(null)
    setTurns((tt) => [...tt, { role: 'user', text: message, tools_used: [] }])
    setSending(true)
    try {
      const r = await api.chat(message)
      setTurns((tt) => [...tt, { role: 'model', text: r.reply, tools_used: r.tools_used }])
    } catch (err) {
      setError(err)
      setTurns((tt) => tt.slice(0, -1))
      setText(message)                 // nothing typed is lost
    } finally {
      setSending(false)
    }
  }

  const clear = async () => {
    await api.clearChat().catch(() => {})
    setLocal([])
  }

  const unavailable = error instanceof ApiError && error.status === 503

  return (
    <Page title={t('chatTitle')}>
      <div className="mx-auto flex max-w-[720px] flex-col">
        {history.loading && !history.data ? (
          <Skeleton className="h-40" />
        ) : turns.length === 0 && !unavailable ? (
          <p className="ticket px-4 py-4 text-[15px] leading-relaxed text-carbon-soft">{t('chatEmpty')}</p>
        ) : (
          <ol className="flex flex-col gap-3" aria-live="polite">
            {turns.map((m, i) => (
              <li key={i} className={m.role === 'user' ? 'ms-10 self-end' : 'me-10 self-start'}>
                <div className={`whitespace-pre-wrap px-4 py-3 text-[15px] leading-relaxed ${m.role === 'user' ? 'bg-ink text-paper' : 'ticket text-carbon'}`}>
                  {m.text}
                </div>
                {m.tools_used.length > 0 && (
                  <p className="mt-1 font-mono text-[11px] text-ink-soft">
                    {Array.from(new Set(m.tools_used)).map((tool) => t(`tool_${tool}` as StringKey)).join(' · ')}
                  </p>
                )}
              </li>
            ))}
            {sending && (
              <li className="me-10 self-start" aria-label={t('loading')}>
                <div className="ticket flex gap-1.5 px-4 py-4">
                  {[0, 1, 2].map((d) => <span key={d} className="skeleton size-2 rounded-full" />)}
                </div>
              </li>
            )}
          </ol>
        )}
        <div ref={end} />

        {unavailable ? (
          <p role="status" className="mt-4 border-[1.5px] border-carbon bg-paper px-4 py-3 text-[14px] text-carbon">
            {t('chatUnavailable')}
          </p>
        ) : error ? (
          <div className="mt-4"><ErrorNote error={error} /></div>
        ) : null}

        <form onSubmit={send} className="sticky bottom-[96px] mt-5 flex gap-2 lg:bottom-6">
          <label className="sr-only" htmlFor="chat-input">{t('chatPlaceholder')}</label>
          <input
            id="chat-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t('chatPlaceholder')}
            maxLength={2000}
            dir="auto"
            className="ticket min-h-12 min-w-0 flex-1 px-4 text-[16px] text-carbon outline-none placeholder:text-carbon-soft/80 focus-visible:outline-2 focus-visible:outline-ink"
          />
          <Button type="submit" busy={sending} disabled={!text.trim()} aria-label={t('send')} className="min-h-12 w-12 px-0">
            {!sending && <SendHorizontal className="size-5 mirror-rtl" aria-hidden />}
          </Button>
        </form>
        {turns.length > 0 && (
          <Button variant="quiet" className="mt-2 self-start" onClick={clear}>
            <Eraser className="size-4" aria-hidden /> {t('clearChat')}
          </Button>
        )}
      </div>
    </Page>
  )
}
