import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import { useI18n } from '../i18n'
import { QUIPS, shuffled } from '../i18n/quips'
import type { StringKey } from '../i18n/strings'
import { ItemPhoto } from './ItemPhoto'

// The wait while the AI dresses the user (about a minute per piece). The backend
// answers only at the end, so progress is ESTIMATED from the time one piece
// usually takes (GET /tryon/info): the bar never claims to be done before the
// answer, and past the estimate it crawls and says it's taking longer.

export interface ProgressPiece { id: string; label: string; image_url: string }

const QUIP_EVERY = 5000          // ms each playful line stays: 60 lines = 5 min without a repeat
const OVERHEAD = 4               // s for the upload and the answer, on top of the pieces

/** Where we probably are: which piece, which stage of it, and how far overall (0-1). */
export function estimate(elapsed: number, pieces: number, secondsPer: number) {
  const total = pieces * secondsPer + OVERHEAD
  const late = elapsed > total
  // up to 95% on schedule; past the estimate, creep towards 99% without reaching it
  const progress = late ? 0.95 + 0.04 * (1 - Math.exp(-(elapsed - total) / 60)) : 0.95 * (elapsed / total)
  const index = Math.min(pieces - 1, Math.floor(elapsed / secondsPer))
  const within = late ? 1 : (elapsed - index * secondsPer) / secondsPer
  const stage: StringKey = late ? 'tryOnStageLonger'
    : within < 0.12 ? 'tryOnStagePose'
    : within < 0.3 ? 'tryOnStageMask'
    : within < 0.85 ? 'tryOnStageStitch'
    : 'tryOnStageFinish'
  return { progress, index, stage, left: Math.max(0, total - elapsed), late }
}

export function clock(seconds: number) {
  const s = Math.floor(seconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** Ticks every 250 ms: the time since `startedAt` drives the estimate. */
export function useElapsed(startedAt: number) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(id)
  }, [])
  return { now, elapsed: (now - startedAt) / 1000 }
}

export function TryOnProgress({ personUrl, pieces, secondsPer, startedAt, onCancel, onMinimise }: {
  personUrl: string; pieces: ProgressPiece[]; secondsPer: number; startedAt: number
  onCancel: () => void; onMinimise?: () => void
}) {
  const { t, lang } = useI18n()
  const { now, elapsed } = useElapsed(startedAt)
  const { progress, index, stage, left, late } = estimate(elapsed, pieces.length, secondsPer)
  const piece = pieces[index]
  // a new playful line every few seconds, in a fresh random order for each try-on
  const lines = QUIPS[lang]
  const [order] = useState(() => shuffled(lines.length))
  const quipNo = Math.floor((now - startedAt) / QUIP_EVERY)
  const quip = lines[order[quipNo % order.length] % lines.length]
  const pct = Math.round(progress * 100)

  return (
    <div className="flex flex-col gap-4">
      {/* the user's own photo, dimmed, with a scanning line going over it */}
      <div className="relative mx-auto w-fit max-w-full overflow-hidden bg-white">
        <img src={personUrl} alt={t('tryOnYourPhoto')} className="block max-h-[42dvh] w-auto max-w-full opacity-70 saturate-50" />
        <div aria-hidden className="tryon-scan pointer-events-none absolute inset-x-0 top-0 h-1/4" />
        <span aria-hidden className="absolute end-2 top-2 bg-paper px-2 py-1 font-mono text-[11px] font-medium tracking-[0.08em] text-ink-soft">
          {String(index + 1).padStart(2, '0')}/{String(pieces.length).padStart(2, '0')}
        </span>
        {piece && (
          <div aria-hidden className="tryon-float absolute bottom-3 start-3 bg-white p-1 shadow-[var(--shadow-lift)]">
            <ItemPhoto src={piece.image_url} alt="" size={56} />
          </div>
        )}
      </div>

      {/* the ticket: stage, playful line, bar, time */}
      <div className="ticket p-4">
        <p className="mb-1 font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-soft">
          {t('tryOnPieceOf', { i: index + 1, n: pieces.length })}
        </p>
        <p className="text-[16px] font-semibold text-carbon" aria-live="polite">
          {t(stage, { piece: piece?.label ?? '' })}
        </p>
        <p key={quipNo} className="tryon-quip mt-1 min-h-[1.6em] text-[14px] text-carbon-soft" aria-hidden>
          {quip}
        </p>

        <div className="mt-4 h-2 bg-stock-deep" role="progressbar" aria-label={t('tryOnProgress')}
          aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
          <div className={`h-full bg-ink transition-[width] duration-500 ease-out ${late ? 'tryon-late' : ''}`}
            style={{ width: `${pct}%` }} />
        </div>
        <div className="mt-2 flex items-baseline justify-between gap-3 text-[13px] text-carbon-soft">
          <span>{late ? '' : left < 60 ? t('tryOnLeftSoon') : t('tryOnLeft', { n: Math.ceil(left / 60) })}</span>
          <span className="font-mono text-[11px] tracking-[0.08em] text-ink-soft" dir="ltr">{clock(elapsed)}</span>
        </div>

        {/* every piece, ticked when it's probably done */}
        {pieces.length > 1 && (
          <ol className="perf-h mt-4 flex flex-wrap gap-2 pt-3">
            {pieces.map((p, i) => (
              <li key={p.id} className={`relative p-0.5 transition-opacity ${i === index && !late ? 'outline-2 outline-ink' : ''} ${i > index ? 'opacity-45' : ''}`}>
                <ItemPhoto src={p.image_url} alt={p.label} size={40} />
                {(i < index || late) && (
                  <span className="absolute -end-1.5 -top-1.5 grid size-4 place-items-center rounded-full bg-ink text-paper" aria-hidden>
                    <Check className="size-3" strokeWidth={3} />
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">
          {onMinimise && (
            <button type="button" onClick={onMinimise}
              className="inline-flex min-h-11 items-center gap-2 bg-ink px-4 text-[15px] font-medium text-paper shadow-[var(--shadow-ticket)] hover:bg-ink-soft">
              {t('tryOnKeepBrowsing')}
            </button>
          )}
          <button type="button" onClick={onCancel}
            className="min-h-11 text-[15px] font-medium text-ink underline decoration-1 underline-offset-4 hover:decoration-2">
            {t('tryOnCancel')}
          </button>
        </div>
      </div>
    </div>
  )
}
