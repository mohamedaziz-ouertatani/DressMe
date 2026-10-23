import { useEffect, useState } from 'react'
import { Check, Shirt } from 'lucide-react'
import { ApiError, api } from '../api/client'
import type { Outfit, WearEntry } from '../api/types'
import { useI18n } from '../i18n'
import { Button } from './controls'
import { ErrorNote } from './states'

/** Today's date in Tunis as YYYY-MM-DD (the wear log is dated there, by the server). */
function tunisToday(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Tunis' }).format(new Date())
}

const sameSet = (a: string[], b: string[]) => a.length === b.length && [...a].sort().join('|') === [...b].sort().join('|')

type State =
  | { kind: 'checking' }                                  // looking for an entry made earlier today (a reload)
  | { kind: 'idle' }
  | { kind: 'sending' }
  | { kind: 'worn'; entry: WearEntry; undoing?: boolean }  // "Worn today · Undo"
  | { kind: 'failed'; action: 'wear' | 'undo'; error: unknown; entry?: WearEntry }

/** "I wore this" under an outfit card. POST /wear once, then "Worn today · Undo" (DELETE /wear/{id}).
 *  The server keeps one entry per set of pieces and day, so an outfit already worn today shows as worn
 *  after a reload too. Remount it (a `key`) when the outfit changes. */
export function WearButton({ outfit, source, occasion }: {
  outfit: Outfit
  source: 'card' | 'build'
  occasion?: string
}) {
  const { t } = useI18n()
  const ids = outfit.items.map((i) => i.id)
  const [state, setState] = useState<State>({ kind: 'checking' })

  useEffect(() => {
    let stale = false
    const day = tunisToday()
    api.wearList({ from: day, to: day })
      .then((entries) => {
        if (stale) return
        const entry = entries.find((e) => sameSet(e.item_ids, ids))
        setState(entry ? { kind: 'worn', entry } : { kind: 'idle' })
      })
      // a failed look-up is harmless: the button still works, and a second POST returns the same entry
      .catch(() => !stale && setState({ kind: 'idle' }))
    return () => { stale = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const wear = async () => {
    setState({ kind: 'sending' })
    try {
      const entry = await api.wear({
        item_ids: ids, source, occasion, score_shown: outfit.score, label_shown: outfit.label ?? undefined,
      })
      setState({ kind: 'worn', entry })
    } catch (error) {
      setState({ kind: 'failed', action: 'wear', error })
    }
  }

  const undo = async (entry: WearEntry) => {
    setState({ kind: 'worn', entry, undoing: true })
    try {
      await api.unwear(entry.id)
      setState({ kind: 'idle' })
    } catch (error) {
      setState({ kind: 'failed', action: 'undo', error, entry })
    }
  }

  if (state.kind === 'worn') {
    return (
      <p role="status" className="mt-4 flex flex-wrap items-center gap-x-3 text-[15px] text-carbon">
        <span className="inline-flex items-center gap-2">
          <Check className="size-4 shrink-0 text-ink" aria-hidden /> {t('wornToday')}
        </span>
        <Button variant="quiet" busy={state.undoing} onClick={() => undo(state.entry)}>{t('wearUndo')}</Button>
      </p>
    )
  }

  const failed = state.kind === 'failed' ? state : null
  const tooLate = failed?.action === 'undo' && failed.error instanceof ApiError && failed.error.status === 409
  return (
    <div className="mt-4">
      {failed?.action === 'undo' && failed.entry ? (
        <div className="flex flex-wrap items-center gap-x-3 text-[15px] text-carbon">
          <span className="inline-flex items-center gap-2"><Check className="size-4 shrink-0 text-ink" aria-hidden /> {t('wornToday')}</span>
        </div>
      ) : (
        <Button variant="secondary" busy={state.kind === 'sending'} disabled={state.kind === 'checking'} onClick={wear}>
          <Shirt className="size-4" aria-hidden /> {t('wearBtn')}
        </Button>
      )}
      {failed && (
        <div className="mt-3">
          {tooLate ? (
            <p role="alert" className="border-[1.5px] border-carbon bg-paper px-4 py-3 text-[14px] text-carbon">{t('wearUndoLate')}</p>
          ) : (
            <ErrorNote error={failed.error} onRetry={() => (failed.action === 'undo' && failed.entry ? undo(failed.entry) : wear())} />
          )}
        </div>
      )}
    </div>
  )
}
