import { useEffect, useState } from 'react'
import { Banknote, TrendingDown, TrendingUp } from 'lucide-react'
import { ApiError, api } from '../api/client'
import type { PriceCondition, PriceEstimate, PriceTag } from '../api/types'
import { useI18n } from '../i18n'
import { plural } from '../i18n/plurals'
import type { StringKey } from '../i18n/strings'

// which prices the band was estimated against, per channel (the translated form of the server's English `note`)
const NOTE: Record<string, StringKey> = { friperie: 'priceNoteFriperie', classified: 'priceNoteClassified' }

/** The usual second-hand price of a scan (GET /price-estimate, the trained price model). The model is typically off
 *  by about x1.5, so this is ALWAYS a range with the channel it was estimated against and the typical error, never a
 *  single price. No model on the server (503) or a failed call: nothing is shown, the verdict stands on its own. */
export function PriceBand({ candidateId }: { candidateId: string }) {
  // the model reads the photo and does not see damage: the user says the condition, the band is scaled server-side
  const [condition, setCondition] = useState<PriceCondition>('good')
  const band = usePriceEstimate({ candidateId }, condition)
  return band ? <PriceBandView band={band} condition={condition} onCondition={setCondition} /> : null
}

/** GET /price-estimate for a scan or a listing: null while loading, on 503 (no model) or on an error.
 *  While another condition is being fetched, the band of the same piece stays on screen (no flicker). */
// eslint-disable-next-line react-refresh/only-export-components
export function usePriceEstimate(ref: { candidateId?: string; listingId?: string }, condition?: PriceCondition) {
  const [state, setState] = useState<{ key: string; band: PriceEstimate } | null>(null)
  const { candidateId, listingId } = ref
  const key = `${candidateId ?? ''}|${listingId ?? ''}`

  useEffect(() => {
    if (!candidateId && !listingId) return
    let live = true
    api.priceEstimate({ candidateId, listingId }, 'friperie', condition)
      .then((b) => { if (live) setState({ key, band: b }) })
      .catch((e) => { if (!(e instanceof ApiError && e.status === 503)) console.error('price estimate', e) })
    return () => { live = false }
  }, [candidateId, listingId, key, condition])

  // an answer for another piece (the page moved on) is never shown
  return state && state.key === key ? state.band : null
}

// the options of the condition selector, in order, and the line under the band for each
// (where each factor was measured: the notes of mappings/price_model.csv)
const CONDITIONS: { value: PriceCondition; label: StringKey; line: StringKey }[] = [
  { value: 'new_tags', label: 'priceCondNewTags', line: 'priceCondLineNewTags' },
  { value: 'like_new', label: 'priceCondLikeNew', line: 'priceCondLineLikeNew' },
  { value: 'good', label: 'priceCondGood', line: 'priceCondLineGood' },
  { value: 'stained', label: 'priceCondStained', line: 'priceCondLineStained' },
  { value: 'torn', label: 'priceCondTorn', line: 'priceCondLineTorn' },
]

/** The band itself, already loaded. With `onCondition` (the scan page), a condition selector sits under the title
 *  and the factor applied under the band. A listing has no condition: neither shows. */
export function PriceBandView({ band, condition, onCondition }: {
  band: PriceEstimate
  condition?: PriceCondition
  onCondition?: (c: PriceCondition) => void
}) {
  const { t, lang } = useI18n()
  const locale = lang === 'ar' ? 'ar-TN' : lang
  const number = new Intl.NumberFormat(locale)
  const known = band.low !== null && band.high !== null
  const picked = CONDITIONS.find((c) => c.value === band.condition)

  return (
    <section aria-labelledby="price-band-title" className="pop flex items-start gap-3 rounded-card bg-surface p-card">
      <Banknote className="mt-0.5 size-[22px] shrink-0 text-carbon" strokeWidth={1.75} aria-hidden />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <h2 id="price-band-title" className="text-[16px] font-semibold text-carbon">{t('priceBandTitle')}</h2>
        {onCondition && (
          <label className="flex flex-wrap items-center gap-2 py-1 text-[14px] text-carbon-soft">
            {t('priceCondition')}
            <select
              value={condition ?? 'good'}
              onChange={(e) => onCondition(e.target.value as PriceCondition)}
              className="min-h-[36px] rounded-pill bg-surface px-3 text-[14px] font-medium text-carbon ring-1 ring-inset ring-line-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              {CONDITIONS.map((c) => <option key={c.value} value={c.value}>{t(c.label)}</option>)}
            </select>
          </label>
        )}
        {known ? (
          <>
            <p className="text-[22px] font-semibold leading-tight text-carbon tabular">
              {plural('priceRange', band.high!, lang, { low: number.format(band.low!) })}
            </p>
            {/* a group the model ranks badly (e.g. friperie shoes): the range is rough */}
            {band.reliable === false && (
              <p className="text-[13px] text-carbon-soft">{t('priceNoteRough')}</p>
            )}
            {band.median !== null && (
              <p className="text-[14px] text-carbon-soft tabular">{plural('priceAbout', band.median, lang)}</p>
            )}
            {onCondition && picked && band.condition_factor != null && (
              <p className="text-[13px] text-carbon-soft">
                {t(picked.line, {
                  factor: new Intl.NumberFormat(locale, { minimumFractionDigits: 2 }).format(band.condition_factor),
                })}
              </p>
            )}
            {band.typical_error_factor !== null && (
              <p className="text-[14px] text-carbon-soft">{t('priceBandError', { factor: number.format(band.typical_error_factor) })}</p>
            )}
            {band.count !== null && (
              <p className="text-[14px] text-carbon-soft">
                {plural(band.based_on === 'category' ? 'pricedPieces' : 'pricedPiecesAll', band.count, lang)}
              </p>
            )}
          </>
        ) : (
          <p className="text-[14px] text-carbon-soft">{t('priceBandNone')}</p>
        )}
        {/* the server's `note` is English only: the same sentence is built here from the channel */}
        {NOTE[band.channel] && (
          <p className="text-[13px] text-carbon-soft">
            {t(NOTE[band.channel])}{known && band.based_on === 'all' ? ` ${t('priceNoteFallback')}` : ''}
          </p>
        )}
      </div>
    </section>
  )
}

const TAG: Record<PriceTag, { label: StringKey; look: string; icon: typeof TrendingDown }> = {
  good_deal: { label: 'priceTagGoodDeal', look: 'bg-buy-soft text-buy', icon: TrendingDown },
  priced_high: { label: 'priceTagHigh', look: 'bg-unsure-soft text-unsure', icon: TrendingUp },
}

/** "Good price" next to a friperie seller's price (GET /price-estimate?listing_id=, its `tag`). A word and an icon,
 *  never colour alone. No tag (null, 503, a shop listing): nothing. */
export function PriceTagChip({ tag, className = '' }: { tag?: PriceTag | null; className?: string }) {
  const { t } = useI18n()
  if (!tag || !TAG[tag]) return null
  const { label, look, icon: Icon } = TAG[tag]
  return (
    <span role="note" className={`inline-flex items-center gap-1 rounded-pill px-2.5 py-0.5 text-[13px] font-medium ${look} ${className}`}>
      <Icon className="size-3.5 shrink-0 mirror-rtl" strokeWidth={1.75} aria-hidden />
      {t(label)}
    </span>
  )
}
