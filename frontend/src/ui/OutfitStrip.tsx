import { ThumbsDown, ThumbsUp } from 'lucide-react'
import type { Outfit, OutfitRating } from '../api/types'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, COLOUR_HEX, COLOUR_LABELS, SUB_LABELS, secondLine, vocab } from '../i18n/vocab'
import { Swatch } from './controls'
import { ItemPhoto } from './ItemPhoto'
import { Stamp } from './Stamp'
import { SecondLine, Serial, Ticket } from './ticket'

/** An outfit as a strip of perforated tickets, one per piece, with the score
 *  stamped across the top corner. */
export function OutfitStrip({ outfit, land = false, compact = false, photoOf, onFeedback, feedback }: {
  outfit: Outfit
  land?: boolean
  compact?: boolean
  photoOf?: (id: string) => string | undefined   // e.g. the scanned photo, not stored on the server
  onFeedback?: (rating: OutfitRating) => void
  feedback?: OutfitRating
}) {
  const { t, lang, reason } = useI18n()
  const size = compact ? 72 : 96
  return (
    <div className="relative">
      <ol className="flex flex-col gap-2">
        {outfit.items.map((it, i) => (
          <Ticket
            key={it.id}
            as="li"
            stub={
              <span className="font-mono text-[11px] text-ink-soft tabular" dir="ltr">
                {String(i + 1).padStart(2, '0')}/{String(outfit.items.length).padStart(2, '0')}
              </span>
            }
          >
            <div className="flex items-end gap-3 p-2">
              <ItemPhoto src={photoOf?.(it.id) ?? it.image_url} alt={vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)} size={size} zoomable />
              <div className="min-w-0 pb-1">
                <p className="text-[16px] font-semibold leading-tight text-carbon">
                  {vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)}
                </p>
                <SecondLine>{secondLine(SUB_LABELS, it.sub_category, lang) || secondLine(CATEGORY_LABELS, it.category, lang)}</SecondLine>
                <p className="mt-1.5 flex items-center gap-1.5 text-[13px] text-carbon-soft">
                  {it.colour && <Swatch hex={COLOUR_HEX[it.colour]} size={11} />}
                  {it.colour ? vocab(COLOUR_LABELS, it.colour, lang) : ''}
                  {!compact && <Serial id={it.id} className="ms-2" />}
                </p>
              </div>
            </div>
          </Ticket>
        ))}
      </ol>
      <div className="pointer-events-none absolute -top-6 end-14 sm:end-20">
        <Stamp
          big={String(Math.round(outfit.score))}
          ring={`${t('score').toUpperCase()} · DRESSME · ${t('score').toUpperCase()} · DRESSME ·`}
          size={compact ? 76 : 96}
          land={land}
          tone={compact ? 'ink' : 'stamp'}
          label={`${t('score')} ${Math.round(outfit.score)} / 100`}
        />
      </div>
      <ul className="mt-3 space-y-1 text-[14px] text-carbon-soft">
        {(outfit.reasons.length ? outfit.reasons : ['']).map((r, i) => (
          <li key={i} className="flex gap-2">
            <span aria-hidden className="mt-[9px] h-px w-3 shrink-0 bg-perf" />
            {r ? reason(r) : t('noReasons')}
          </li>
        ))}
      </ul>
      {onFeedback && (
        <div className="mt-4 flex items-center gap-2" aria-label={t('outfitFeedback')}>
          <span className="text-[13px] text-carbon-soft">{t('outfitFeedback')}</span>
          {([1, -1] as const).map((rating) => (
            <button
              key={rating}
              type="button"
              aria-label={t(rating === 1 ? 'outfitLike' : 'outfitDislike')}
              aria-pressed={feedback === rating}
              onClick={() => onFeedback(rating)}
              className={`grid size-9 place-items-center border transition-colors ${
                feedback === rating ? 'border-ink bg-ink text-paper' : 'border-carbon/20 text-carbon-soft hover:border-ink hover:text-ink'
              }`}
            >
              {rating === 1 ? <ThumbsUp className="size-4" aria-hidden /> : <ThumbsDown className="size-4" aria-hidden />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
