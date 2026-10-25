import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { Camera, Check, Search, SearchX } from 'lucide-react'
import { ApiError, api } from '../api/client'
import type { SearchResponse } from '../api/types'
import { useI18n } from '../i18n'
import type { StringKey } from '../i18n/strings'
import { Button } from './controls'
import { ItemCard } from './ItemCard'
import { Empty, ErrorNote, Skeleton } from './states'

type Via = 'text' | 'photo'
type State =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'done'; data: SearchResponse }
  | { phase: 'error'; error: unknown; via: Via; retry: () => void }

const GRID = 'grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4'

/** The translated sentence for a failed search: the server's own text is never shown. */
function failureKey(error: unknown, via: Via): StringKey {
  if (error instanceof ApiError && error.status === 413) return 'searchPhotoTooBig'
  if (error instanceof ApiError && error.status === 400 && via === 'photo') return 'searchPhotoFailed'
  return 'searchFailed'
}

/** Search the user's own pieces by words or by a photo (POST /search, step 3b). A photo search saves nothing.
 *  The box shows its own results under itself; `onActive(true)` tells the page a search is on screen (so it can hide
 *  what the results replace), `onActive(false)` that it was cleared (the Clear button, or the box emptied by hand).
 *  No numbers are shown. Only the close pieces are listed, each marked "Close match"; when none is close it says
 *  "No sure match" and lists the nearest few, faded, under "Closest pieces in your wardrobe:". */
export function SearchBox({ onActive }: { onActive?: (active: boolean) => void }) {
  const { t } = useI18n()
  const inputId = useId()
  const camera = useRef<HTMLInputElement>(null)
  const latest = useRef(0)                                    // only the newest search may answer
  const [text, setText] = useState('')
  const [state, setState] = useState<State>({ phase: 'idle' })
  const [preview, setPreview] = useState<string | null>(null)  // the photo the search was made with

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  const run = async (input: { text: string } | { photo: File }) => {
    const mine = ++latest.current
    const via: Via = 'photo' in input ? 'photo' : 'text'
    setPreview('photo' in input ? URL.createObjectURL(input.photo) : null)
    if ('photo' in input) setText('')                           // the results belong to the photo, not to words left in the box
    setState({ phase: 'loading' })
    onActive?.(true)
    try {
      const data = await api.search(input)
      if (mine === latest.current) setState({ phase: 'done', data })
    } catch (error) {
      if (mine === latest.current) setState({ phase: 'error', error, via, retry: () => void run(input) })
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const words = text.trim()
    if (words) void run({ text: words })
  }

  const pick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''                                       // the same photo can be picked again
    if (file) void run({ photo: file })
  }

  const clear = () => {
    latest.current += 1                                       // an answer still on its way is dropped
    setState({ phase: 'idle' })
    setPreview(null)
    setText('')
    onActive?.(false)
  }

  const fade = 'rounded-pill bg-surface text-carbon ring-1 ring-inset ring-line-strong'
  const focus = 'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink'

  return (
    <section className="mb-6">
      <form onSubmit={submit} className="flex items-center gap-2" role="search">
        <label htmlFor={inputId} className="sr-only">{t('searchLabel')}</label>
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute start-4 top-1/2 size-5 -translate-y-1/2 text-carbon-soft" aria-hidden />
          <input
            id={inputId}
            type="text"
            name="q"
            value={text}
            onChange={(e) => {
              setText(e.target.value)
              if (e.target.value === '' && state.phase !== 'idle') clear()   // emptying the box ends the search
            }}
            maxLength={120}
            autoComplete="off"
            enterKeyHint="search"
            placeholder={t('searchPlaceholder')}
            className={`h-tap w-full text-[16px] placeholder:text-carbon-soft ps-12 pe-4 ${fade} ${focus}`}
          />
        </div>
        <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={pick} />
        <button type="button" aria-label={t('searchPhoto')} onClick={() => camera.current?.click()}
          className={`press grid size-12 shrink-0 place-items-center ${fade} ${focus}`}>
          <Camera className="size-5" strokeWidth={1.75} aria-hidden />
        </button>
        <button type="submit" aria-label={t('searchSubmit')}
          className={`press grid size-12 shrink-0 place-items-center rounded-pill bg-pill text-pill-text ${focus}`}>
          <Search className="size-5" strokeWidth={1.75} aria-hidden />
        </button>
      </form>

      <div aria-live="polite" className="mt-4">
        {state.phase !== 'idle' && (
          <div className="mb-3 flex items-center justify-between gap-3">
            {preview ? <img src={preview} alt={t('searchPhotoAlt')} className="size-14 rounded-photo object-cover" /> : <span />}
            <Button variant="quiet" onClick={clear}>{t('searchClear')}</Button>
          </div>
        )}
        {state.phase === 'loading' && (
          <>
            <p role="status" className="mb-3 text-[15px] text-carbon-soft">{t('searchLoading')}</p>
            <div className={GRID}>{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-[190px]" />)}</div>
          </>
        )}
        {state.phase === 'error' && (
          <ErrorNote error={state.error} message={t(failureKey(state.error, state.via))} onRetry={state.retry} />
        )}
        {state.phase === 'done' && (
          <>
            {/* the server also sends the next nearest pieces; they are listed only when none is close */}
            {state.data.nothing_close ? (
              <>
                <Empty icon={SearchX} title={t('searchNoSure')} body={t('searchNothingBody')} />
                {state.data.results.length > 0 && (
                  <>
                    <h2 className="mb-3 mt-6 text-[15px] font-semibold text-carbon-soft">{t('searchClosest')}</h2>
                    <ul className={GRID}>
                      {state.data.results.map((r) => <li key={r.item.id}><ItemCard item={r.item} muted /></li>)}
                    </ul>
                  </>
                )}
              </>
            ) : (
              <ul className={GRID}>
                {state.data.results.filter((r) => r.close).map((r) => (
                  <li key={r.item.id}>
                    <ItemCard
                      item={r.item}
                      badge={
                        <span className="inline-flex items-center gap-1 rounded-pill bg-buy-soft px-2 py-0.5 text-[12px] font-semibold text-buy">
                          <Check className="size-3.5" strokeWidth={2.25} aria-hidden /> {t('searchClose')}
                        </span>
                      }
                    />
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </section>
  )
}
