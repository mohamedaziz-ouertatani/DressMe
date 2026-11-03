import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUp, MessageCircle, PlugZap, RotateCcw, Search } from 'lucide-react'
import { ApiError, api } from '../api/client'
import type { ChatResponse, ChatToolLine, ChatTraceLine, Item } from '../api/types'
import { useI18n } from '../i18n'
import type { StringKey } from '../i18n/strings'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { Button } from '../ui/controls'
import { ItemCard } from '../ui/ItemCard'
import { SearchBox } from '../ui/SearchBox'
import { Empty, ErrorNote, Skeleton } from '../ui/states'

/** The assistant's conversation (step 3f). Spec: the POST /chat answer (docs/superpowers/handoff/chat-assistant-state.md).
 *
 *  - Every turn stands alone on the server (no history goes to the model), so the page says so once; the turns are kept
 *    in this page's memory only, and `chat_id` groups them in the saved `chats`.
 *  - The answer names the user's pieces as {n}; `pieces` holds the items behind the numbers used. Each {n} becomes a
 *    small link to the piece, and the pieces are listed as cards under the answer. Shop listings are named in words by
 *    the model and are not in `pieces`.
 *  - "How I answered" opens the trace: which agent answered (and a handoff), and the tools it called (XAI).
 *  - The model off (status false, or a 503): a card with shortcuts to the screens that work, never the server's text. */

type Turn =
  | { id: number; question: string; phase: 'waiting' }
  | { id: number; question: string; phase: 'answered'; reply: ChatResponse }
  | { id: number; question: string; phase: 'failed'; error: unknown }

const SUGGESTIONS: StringKey[] = ['chatSuggest1', 'chatSuggest2', 'chatSuggest3', 'chatSuggest4']
const AGENT_KEYS: Record<string, StringKey> = {
  stylist: 'agent_stylist', general: 'agent_general', wardrobe_analyst: 'agent_wardrobe_analyst',
  explainer: 'agent_explainer', seller: 'agent_seller', shopping: 'agent_shopping',
}
const focusRing = 'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink'

export function AssistantPage() {
  const { t } = useI18n()
  const inputId = useId()
  const [available, setAvailable] = useState<boolean | null>(null)     // null = still asking
  const [turns, setTurns] = useState<Turn[]>([])
  const [text, setText] = useState('')
  const [searching, setSearching] = useState(false)
  const chatId = useRef<string | undefined>(undefined)
  const nextId = useRef(1)
  const end = useRef<HTMLDivElement>(null)
  const busy = turns.some((turn) => turn.phase === 'waiting')

  const askStatus = () => api.assistantStatus().then((s) => setAvailable(s.available)).catch(() => setAvailable(false))
  const checkStatus = () => {
    setAvailable(null)
    void askStatus()
  }
  useEffect(() => { void askStatus() }, [])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [turns])

  const ask = async (question: string) => {
    const words = question.trim()
    if (!words || busy) return
    const id = nextId.current++
    setText('')
    setTurns((all) => [...all, { id, question: words, phase: 'waiting' }])
    try {
      const reply = await api.chat(words, chatId.current)
      chatId.current = reply.chat_id
      setTurns((all) => all.map((turn) => (turn.id === id ? { id, question: words, phase: 'answered', reply } : turn)))
    } catch (error) {
      if (error instanceof ApiError && error.status === 503) setAvailable(false)    // the model went away meanwhile
      setTurns((all) => all.map((turn) => (turn.id === id ? { id, question: words, phase: 'failed', error } : turn)))
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    void ask(text)
  }

  const restart = () => {
    chatId.current = undefined
    setTurns([])
  }

  return (
    <Page title={t('navAssistant')} look="soft" kicker={t('assistantKicker')}>
      {available === false ? (
        <ModelOff onCheck={checkStatus} />
      ) : (
        <>
          {turns.length === 0 ? (
            <Empty
              icon={MessageCircle}
              title={t('chatEmptyTitle')}
              body={<><p>{t('chatEmptyBody')}</p><p className="mt-2 text-[14px]">{t('chatOneByOne')}</p></>}
              action={
                <div className="flex flex-wrap gap-2">
                  {SUGGESTIONS.map((key) => (
                    <button key={key} type="button" disabled={available === null} onClick={() => void ask(t(key))}
                      className={`press min-h-11 rounded-pill bg-paper px-4 text-start text-[15px] text-carbon ring-1 ring-inset ring-line-strong disabled:opacity-50 ${focusRing}`}>
                      {t(key)}
                    </button>
                  ))}
                </div>
              }
            />
          ) : (
            <div className="mb-4 flex justify-end">
              <Button variant="quiet" onClick={restart} disabled={busy}>
                <RotateCcw className="size-4" aria-hidden /> {t('chatNew')}
              </Button>
            </div>
          )}

          <ol aria-live="polite" className="mt-4 flex flex-col gap-6">
            {turns.map((turn) => (
              <li key={turn.id} className="flex flex-col gap-3">
                <Bubble mine label={t('chatYou')}>{turn.question}</Bubble>
                {turn.phase === 'waiting' && (
                  <div className="flex flex-col gap-2">
                    <p role="status" className="text-[15px] text-carbon-soft">{t('chatThinking')}</p>
                    <Skeleton className="h-20 max-w-[80%] rounded-card" />
                  </div>
                )}
                {turn.phase === 'failed' && (
                  <ErrorNote error={turn.error} message={t('chatFailed')}
                    onRetry={() => {
                      setTurns((all) => all.filter((other) => other.id !== turn.id))
                      void ask(turn.question)
                    }} />
                )}
                {turn.phase === 'answered' && <Answer reply={turn.reply} />}
              </li>
            ))}
          </ol>
          <div ref={end} />

          {/* the question box stays above the phone tab bar */}
          <form onSubmit={submit} className="sticky z-10 -mx-5 mt-6 bg-stock/95 px-5 py-3 backdrop-blur lg:mx-0 lg:px-0"
            style={{ bottom: 'var(--tabbar-h, 0px)' }}>
            <label htmlFor={inputId} className="sr-only">{t('chatLabel')}</label>
            <div className="flex items-end gap-2">
              <textarea
                id={inputId}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {                                   // Enter sends, Shift+Enter starts a new line
                  if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault()
                    void ask(text)
                  }
                }}
                rows={1}
                maxLength={1000}
                placeholder={t('chatPlaceholder')}
                disabled={available === null}
                className={`max-h-40 min-h-12 flex-1 resize-none rounded-[24px] bg-surface px-4 py-3 text-[16px] leading-6 text-carbon ring-1 ring-inset ring-line-strong placeholder:text-carbon-soft field-sizing-content ${focusRing}`}
              />
              <button type="submit" aria-label={t('chatSend')} disabled={busy || !text.trim() || available === null}
                className={`press grid size-12 shrink-0 place-items-center rounded-pill bg-pill text-pill-text disabled:opacity-40 ${focusRing}`}>
                <ArrowUp className="size-5" strokeWidth={2} aria-hidden />
              </button>
            </div>
          </form>
        </>
      )}

      <div className="mt-8">
        {searching ? (
          <SearchBox />
        ) : (
          <Button variant="quiet" onClick={() => setSearching(true)}>
            <Search className="size-4" aria-hidden /> {t('chatSearchInstead')}
          </Button>
        )}
      </div>
    </Page>
  )
}

function Bubble({ mine = false, label, children }: { mine?: boolean; label: string; children: ReactNode }) {
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] whitespace-pre-line rounded-[22px] px-4 py-3 text-[16px] leading-6 ${
        mine ? 'rounded-ee-md bg-pill text-pill-text' : 'rounded-es-md bg-surface text-carbon'}`}>
        <span className="sr-only">{label}: </span>
        {children}
      </div>
    </div>
  )
}

/** One answer: the text with each {n} as a link to the piece, the pieces as cards, and how it was made. */
function Answer({ reply }: { reply: ChatResponse }) {
  const { t } = useI18n()
  const agent = t(AGENT_KEYS[reply.agent] ?? 'agent_general')
  const used = [...new Set([...reply.answer.matchAll(/\{(\d+)\}/g)].map((m) => m[1]))].filter((n) => reply.pieces[n])
  return (
    <div className="flex flex-col gap-3">
      <Bubble label={agent}><AnswerText answer={reply.answer} pieces={reply.pieces} /></Bubble>
      {(reply.stop_reason === 'max_rounds' || reply.stop_reason === 'repeat') && (
        <p className="text-[14px] text-carbon-soft">{t('chatCutShort')}</p>
      )}
      {used.length > 0 && (
        <section>
          <h3 className="mb-2 text-[14px] font-semibold text-carbon-soft">{t('chatPieces')}</h3>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {used.map((n) => (
              <li key={n} className="relative">
                <span aria-hidden className="absolute start-2 top-2 z-[1] grid min-w-6 place-items-center rounded-pill bg-pill px-1.5 text-[12px] font-semibold text-pill-text">{n}</span>
                <ItemCard item={reply.pieces[n]} />
              </li>
            ))}
          </ul>
        </section>
      )}
      <HowAnswered trace={reply.trace} />
    </div>
  )
}

/** The answer's text: a known {n} becomes a link to that piece (its name + its number); anything else stays text. */
function AnswerText({ answer, pieces }: { answer: string; pieces: Record<string, Item> }) {
  const { lang } = useI18n()
  const parts = answer.split(/(\{\d+\})/g)
  return (
    <>
      {parts.map((part, i) => {
        const n = /^\{(\d+)\}$/.exec(part)?.[1]
        const item = n ? pieces[n] : undefined
        if (!item) return <span key={i}>{part}</span>
        const name = vocab(SUB_LABELS, item.sub_category, lang) || vocab(CATEGORY_LABELS, item.category, lang)
        return (
          <Link key={i} to={`/wardrobe/${item.id}`}
            className={`mx-0.5 inline-flex items-baseline gap-1 rounded-pill bg-paper px-2 text-[15px] font-semibold text-ink underline-offset-2 hover:underline ${focusRing}`}>
            {name}<span className="text-[12px] text-carbon-soft">{n}</span>
          </Link>
        )
      })}
    </>
  )
}

/** The trace, folded: who answered, a handoff if any, and the tools called (with a mark for a refused call). */
function HowAnswered({ trace }: { trace: ChatTraceLine[] }) {
  const { t } = useI18n()
  const agentName = (name: string) => t(AGENT_KEYS[name] ?? 'agent_general')
  const router = trace.find((line) => 'router' in line)
  const handoff = trace.find((line) => 'handoff' in line)
  const tools = trace.filter((line): line is ChatToolLine => 'tool' in line)
  return (
    <details className="group text-[14px] text-carbon-soft">
      <summary className={`min-h-11 cursor-pointer list-none py-2 font-semibold text-ink underline decoration-1 underline-offset-4 ${focusRing}`}>
        {t('chatHow')}
      </summary>
      <div className="mt-1 flex flex-col gap-2 rounded-card bg-surface p-4">
        {router && 'router' in router && <p>{t('chatRouted', { agent: agentName(router.router) })}</p>}
        {handoff && 'handoff' in handoff && <p>{t('chatHandedTo', { agent: agentName(handoff.handoff.to) })}</p>}
        <p className="font-semibold text-carbon">{t('chatSteps')}</p>
        {tools.length === 0 ? (
          <p>{t('chatNoSteps')}</p>
        ) : (
          <ol className="flex flex-wrap gap-1.5">
            {tools.map((line, i) => (
              <li key={i} dir="ltr" className={`rounded-pill px-2.5 py-1 font-mono text-[12px] ${line.ok ? 'bg-paper text-carbon' : 'bg-leave-soft text-leave line-through'}`}>
                {line.tool}
              </li>
            ))}
          </ol>
        )}
      </div>
    </details>
  )
}

/** The model is off: say so, and offer the screens that work without it (the fallback of step 4). */
function ModelOff({ onCheck }: { onCheck: () => void }) {
  const { t } = useI18n()
  const link = `press inline-flex min-h-11 items-center rounded-pill bg-paper px-4 text-[15px] font-semibold text-carbon ring-1 ring-inset ring-line-strong ${focusRing}`
  return (
    <Empty
      icon={PlugZap}
      title={t('chatOffTitle')}
      body={t('chatOffBody')}
      action={
        <div className="flex flex-col items-start gap-4">
          <div className="flex flex-wrap gap-2">
            <Link to="/dress" className={link}>{t('navDress')}</Link>
            <Link to="/scan" className={link}>{t('navScan')}</Link>
            <Link to="/wardrobe" className={link}>{t('navWardrobe')}</Link>
            <Link to="/shop" className={link}>{t('navShop')}</Link>
          </div>
          <Button variant="secondary" onClick={onCheck}>{t('chatCheckAgain')}</Button>
        </div>
      }
    />
  )
}
