import type { Confidence, VerdictCode } from '../api/types'
import { useI18n } from '../i18n'
import { verdictCodeLine } from '../i18n/explain'
import { useLook } from './look'

/** How far to trust the verdict. Solid = high, outlined = medium, dashed = low (dashed means
 *  "guessed" everywhere else in the app). */
export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  const { t } = useI18n()
  const softLook = useLook() === 'soft'
  if (softLook) {           // step H: a pill; low = the unsure colour with a dashed edge, with its word
    const soft = {
      high: 'bg-surface text-carbon ring-1 ring-inset ring-line-strong',
      medium: 'bg-surface text-carbon ring-1 ring-inset ring-line-strong',
      low: 'border-[1.5px] border-dashed border-unsure bg-unsure-soft text-unsure',
    }[confidence]
    return (
      <span className={`inline-flex min-h-8 items-center rounded-pill px-3 text-[13px] font-medium ${soft}`}>
        {t('confidenceLabel')}: {t(`confidence_${confidence}`)}
      </span>
    )
  }
  const look = {
    high: 'border-ink bg-ink text-paper',
    medium: 'border-ink bg-paper text-ink',
    low: 'border-dashed border-ink bg-paper text-ink',
  }[confidence]
  return (
    <span className={`inline-flex items-center border-[1.5px] px-2 py-0.5 text-[12px] font-medium ${look}`}>
      {t('confidenceLabel')}: {t(`confidence_${confidence}`)}
    </span>
  )
}

/** The codes that only inform ("Good to know") as sentences. */
export function CodeList({ codes }: { codes: VerdictCode[] }) {
  const { t, lang } = useI18n()
  if (codes.length === 0) return null
  return (
    <div className="mt-3">
      <h3 className="mb-1 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('codesTitle')}</h3>
      <ul className="space-y-1 text-[15px] text-carbon-soft">
        {codes.map((c, i) => <li key={`${c.code}-${i}`}>{verdictCodeLine(c, lang)}</li>)}
      </ul>
    </div>
  )
}
