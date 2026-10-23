import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { Sparkles, ThumbsDown, ThumbsUp } from 'lucide-react'
import { api } from '../api/client'
import type { ExplainLine, Outfit, OutfitItem, OutfitRating } from '../api/types'
import { useI18n } from '../i18n'
import { confidenceReasonLine, explainLine } from '../i18n/explain'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { DetailsSheet } from './DetailsSheet'
import { ItemPhoto } from './ItemPhoto'
import { ErrorNote } from './states'
import { ExplainLines, PointsBar, ScoreDetails } from './ScoreWhy'
import { WearButton } from './WearButton'

// An outfit of the Dress page: a soft card tinted by its label, the confidence as dots, a collage of the
// pieces, two reasons, "Wear this" and a details sheet. Colours, radii and spacing are design tokens (index.css).
const TONE = { safe: 'bg-label-safe', bolder: 'bg-label-bolder', experimental: 'bg-label-experimental' } as const
const DOTS = { high: 5, medium: 3, low: 1 } as const
// accessories sit small under the main pieces
const SMALL = new Set(['shoes', 'bag', 'accessory'])

/** Main pieces large (by how many there are, so the row always fits a 320 px phone), accessories small. */
function Collage({ items }: { items: OutfitItem[] }) {
  const { lang } = useI18n()
  const main = items.filter((i) => !SMALL.has(i.category))
  const small = items.filter((i) => SMALL.has(i.category))
  const size = main.length <= 1 ? 160 : main.length === 2 ? 120 : 88
  const name = (it: OutfitItem) => vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)
  const tile = (it: OutfitItem, px: number) => (
    <div key={it.id} className="overflow-hidden rounded-tile bg-tile">
      <ItemPhoto src={it.image_url} alt={name(it)} size={px} />
    </div>
  )
  return (
    <div className="mt-4 flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">{main.map((it) => tile(it, size))}</div>
      {small.length > 0 && <div className="flex flex-wrap gap-2">{small.map((it) => tile(it, 56))}</div>}
    </div>
  )
}

/** Five dots and a word: high ●●●●●, medium ●●●○○, low ●○○○○. */
function ConfidenceDots({ level }: { level: 'high' | 'medium' | 'low' }) {
  const { t } = useI18n()
  const word = t(`confidence_${level}`)
  return (
    <span className="inline-flex shrink-0 items-center gap-2 text-[13px] font-medium text-carbon" aria-label={`${t('confidenceLabel')}: ${word}`}>
      <span aria-hidden className="inline-flex gap-1">
        {[0, 1, 2, 3, 4].map((i) => (
          <span key={i} className={`size-2 rounded-pill border-[1.5px] border-pill ${i < DOTS[level] ? 'bg-pill' : 'bg-transparent'}`} />
        ))}
      </span>
      {word}
    </span>
  )
}

export function OutfitCard({ outfit, index, source, occasion, yourPick = false }: {
  outfit: Outfit
  index: number                          // 0, 1, 2: the card is titled "Outfit n" when it has no label
  source: 'card' | 'build'
  occasion?: string
  yourPick?: boolean                     // Build: the pieces you chose already make this outfit
}) {
  const { t, lang } = useI18n()
  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])
  const tone = outfit.label ? TONE[outfit.label] : 'bg-label-neutral'
  const title = outfit.label ? t(`labelChip_${outfit.label}`) : t('dressOutfitN', { n: index + 1 })

  // two reasons at most: the best positive one, and that it fits today
  const lines = outfit.explanations ?? []
  const shown = [lines.find((l) => l.sign === '+' && l.code !== 'fits_context'), lines.find((l) => l.code === 'fits_context')]
    .filter((l): l is ExplainLine => Boolean(l))

  return (
    <article className={`rounded-card p-card ${tone}`}>
      {yourPick && <p className="mb-1 text-[12px] font-semibold uppercase tracking-[0.06em] text-carbon">{t('dressYourPick')}</p>}
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h3 className="text-[22px] font-bold leading-tight text-carbon">{title}</h3>
        {outfit.confidence && <ConfidenceDots level={outfit.confidence} />}
      </header>
      <Collage items={outfit.items} />
      {shown.length > 0 && (
        <ul className="mt-4 space-y-1 text-[14px] text-carbon">
          {shown.map((l) => <li key={l.code}>{explainLine(l, lang)}</li>)}
        </ul>
      )}
      <div className="mt-4 flex items-center justify-between gap-3">
        <WearButton key={outfit.items.map((i) => i.id).join('|')} outfit={outfit} source={source} occasion={occasion} pill />
        <button
          type="button"
          aria-label={t('dressDetails')}
          aria-haspopup="dialog"
          onClick={() => setOpen(true)}
          className="grid size-11 shrink-0 place-items-center rounded-pill border-[1.5px] border-pill-line text-[18px] text-pill focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pill"
        >
          <span aria-hidden>✦</span>
        </button>
      </div>
      {open && <DetailsSheet title={t('dressDetails')} onClose={close}><OutfitDetails outfit={outfit} /></DetailsSheet>}
    </article>
  )
}

/** The sheet: score and points, why the confidence is what it is, the weakest piece and its swap, every
 *  reason, a like / dislike (it teaches the taste vector), and Try it on. */
function OutfitDetails({ outfit }: { outfit: Outfit }) {
  const { t, lang } = useI18n()
  const [rating, setRating] = useState<OutfitRating>()
  const [error, setError] = useState<unknown>(null)
  const ids = outfit.items.map((i) => i.id)
  const pieceName = (id: string) => {
    const it = outfit.items.find((i) => i.id === id)
    return it ? vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang) : ''
  }
  const heading = 'mb-1 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft'
  const rate = (value: OutfitRating) => {
    const before = rating
    setRating(value)
    setError(null)
    api.feedback(ids, value).catch((e) => { setRating(before); setError(e) })
  }

  return (
    <div className="space-y-5">
      <section>
        <h3 className={heading}>{t('score')}</h3>
        <p className="text-[28px] font-bold leading-none text-carbon tabular">{Math.round(outfit.score)} <span className="text-[15px] font-medium text-carbon-soft">/ 100</span></p>
        {outfit.contributions && <div className="mt-3"><PointsBar contributions={outfit.contributions} /></div>}
      </section>

      <section>
        <h3 className={heading}>{t('dressWhyConfidence')}</h3>
        {outfit.confidence_reasons && outfit.confidence_reasons.length > 0 ? (
          <ul className="space-y-1 text-[14px] text-carbon">
            {outfit.confidence_reasons.map((r, i) => (
              <li key={`${r.code}-${i}`}>{confidenceReasonLine(r, pieceName(String(r.params.item_id ?? '')), lang)}</li>
            ))}
          </ul>
        ) : <p className="text-[14px] text-carbon-soft">{t('dressConfidenceNone')}</p>}
      </section>

      <ScoreDetails outfit={outfit} startOpen />

      {outfit.explanations && outfit.explanations.length > 0 && (
        <section>
          <h3 className={heading}>{t('dressAllReasons')}</h3>
          <ExplainLines lines={outfit.explanations} />
        </section>
      )}

      <section className="flex flex-wrap items-center gap-3">
        <Link
          to={`/tryon?items=${ids.join(',')}`}
          className="inline-flex min-h-11 items-center gap-2 rounded-pill border-[1.5px] border-pill-line px-5 text-[15px] font-semibold text-pill focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pill"
        >
          <Sparkles className="size-4" aria-hidden /> {t('tryOnBtn')}
        </Link>
        <div className="ms-auto flex items-center gap-2" aria-label={t('outfitFeedback')}>
          {([1, -1] as const).map((value) => (
            <button
              key={value}
              type="button"
              aria-label={t(value === 1 ? 'outfitLike' : 'outfitDislike')}
              aria-pressed={rating === value}
              onClick={() => rate(value)}
              className={`grid size-11 place-items-center rounded-pill border-[1.5px] ${rating === value ? 'border-pill bg-pill text-pill-text' : 'border-pill-line text-pill'}`}
            >
              {value === 1 ? <ThumbsUp className="size-4" aria-hidden /> : <ThumbsDown className="size-4" aria-hidden />}
            </button>
          ))}
        </div>
      </section>
      {error ? <ErrorNote error={error} /> : null}
    </div>
  )
}
