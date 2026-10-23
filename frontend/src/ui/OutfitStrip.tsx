import { FlaskConical, Flame, Shield, ThumbsDown, ThumbsUp } from 'lucide-react'
import type { Outfit, OutfitLabel, OutfitRating } from '../api/types'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, COLOUR_HEX, COLOUR_LABELS, SUB_LABELS, secondLine, vocab } from '../i18n/vocab'
import { Swatch } from './controls'
import { ConfidenceBadge } from './VerdictExtras'
import { WearButton } from './WearButton'
import { ItemPhoto } from './ItemPhoto'
import { Stamp } from './Stamp'
import { SecondLine, Serial, Ticket } from './ticket'
import { ExplainLines, PointsBar, ScoreDetails } from './ScoreWhy'

const LABEL_ICON: Record<OutfitLabel, typeof Shield> = { safe: Shield, bolder: Flame, experimental: FlaskConical }

/** An outfit as a strip of perforated tickets, one per piece, with the score
 *  stamped across the top corner. */
export function OutfitStrip({ outfit, land = false, compact = false, photoOf, onFeedback, feedback, explainable = false, onSwap, wear }: {
  outfit: Outfit
  land?: boolean
  compact?: boolean
  photoOf?: (id: string) => string | undefined   // e.g. the scanned photo, not stored on the server
  onFeedback?: (rating: OutfitRating) => void
  feedback?: OutfitRating
  explainable?: boolean                            // show "Why this score?" (swaps + pair map)
  onSwap?: (from: string, to: string) => void      // Build: apply the suggested swap
  wear?: { source: 'card' | 'build'; occasion?: string }   // show "I wore this" (Today and Build)
}) {
  const { t, lang, reason } = useI18n()
  const size = compact ? 72 : 96
  const Icon = outfit.label ? LABEL_ICON[outfit.label] : null
  return (
    <div className="relative">
      {/* how far from the usual style, and a quiet note when the outfit is a weaker bet; hidden when unknown.
          Kept clear of the score stamp on the other side. */}
      {(outfit.label || outfit.confidence === 'low') && (
        <div className="mb-3 flex max-w-[calc(100%-10rem)] flex-wrap items-center gap-2">
          {outfit.label && Icon && (
            <span className="inline-flex items-center gap-1.5 border-[1.5px] border-ink bg-paper px-2 py-0.5 text-[12px] font-medium text-ink">
              <Icon className="size-3.5" aria-hidden /> {t(`labelChip_${outfit.label}`)}
            </span>
          )}
          {outfit.confidence === 'low' && <ConfidenceBadge confidence="low" />}
        </div>
      )}
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
      {outfit.contributions && <div className="mt-3"><PointsBar contributions={outfit.contributions} /></div>}
      <div className="mt-3">
        {outfit.explanations
          ? (outfit.explanations.length ? <ExplainLines lines={outfit.explanations} /> : <p className="text-[14px] text-carbon-soft">{t('noReasons')}</p>)
          : (
            <ul className="space-y-1 text-[14px] text-carbon-soft">
              {(outfit.reasons.length ? outfit.reasons : ['']).map((r, i) => (
                <li key={i} className="flex gap-2">
                  <span aria-hidden className="mt-[9px] h-px w-3 shrink-0 bg-perf" />
                  {r ? reason(r) : t('noReasons')}
                </li>
              ))}
            </ul>
          )}
      </div>
      {wear && <WearButton key={outfit.items.map((i) => i.id).join('|')} outfit={outfit} source={wear.source} occasion={wear.occasion} />}
      {explainable && <ScoreDetails outfit={outfit} onSwap={onSwap} />}
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
