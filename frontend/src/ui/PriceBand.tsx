import { useEffect, useState } from 'react'
import { Banknote } from 'lucide-react'
import { ApiError, api } from '../api/client'
import type { PriceEstimate } from '../api/types'
import { useI18n } from '../i18n'

/** The usual second-hand price of a scan (GET /price-estimate, the trained price model). The model is typically off
 *  by about x1.5, so this is ALWAYS a range with the server's note and the typical error, never a single price.
 *  No model on the server (503) or a failed call: nothing is shown, the verdict stands on its own. */
export function PriceBand({ candidateId }: { candidateId: string }) {
  const { t, lang } = useI18n()
  const [band, setBand] = useState<PriceEstimate | null>(null)

  useEffect(() => {
    let live = true
    api.priceEstimate({ candidateId })
      .then((b) => { if (live) setBand(b) })
      .catch((e) => { if (!(e instanceof ApiError && e.status === 503)) console.error('price estimate', e) })
    return () => { live = false }
  }, [candidateId])

  if (!band) return null
  const number = new Intl.NumberFormat(lang === 'ar' ? 'ar-TN' : lang)
  const known = band.low !== null && band.high !== null

  return (
    <section aria-labelledby="price-band-title" className="pop flex items-start gap-3 rounded-card bg-surface p-card">
      <Banknote className="mt-0.5 size-[22px] shrink-0 text-carbon" strokeWidth={1.75} aria-hidden />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <h2 id="price-band-title" className="text-[16px] font-semibold text-carbon">{t('priceBandTitle')}</h2>
        {known ? (
          <>
            <p className="text-[22px] font-semibold leading-tight text-carbon tabular">
              {t('priceBandRange', { low: number.format(band.low!), high: number.format(band.high!) })}
            </p>
            {band.median !== null && (
              <p className="text-[14px] text-carbon-soft tabular">{t('priceBandMedian', { median: number.format(band.median) })}</p>
            )}
            {band.typical_error_factor !== null && (
              <p className="text-[14px] text-carbon-soft">{t('priceBandError', { factor: number.format(band.typical_error_factor) })}</p>
            )}
            {band.count !== null && (
              <p className="text-[14px] text-carbon-soft">
                {t(band.based_on === 'category' ? 'priceBandBasis' : 'priceBandBasisAll', { count: number.format(band.count) })}
              </p>
            )}
          </>
        ) : (
          <p className="text-[14px] text-carbon-soft">{t('priceBandNone')}</p>
        )}
        <p className="text-[13px] text-carbon-soft" lang="en">{band.note}</p>
      </div>
    </section>
  )
}
