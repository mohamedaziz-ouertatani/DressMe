import { useState } from 'react'
import { Check, X } from 'lucide-react'
import { api } from '../api/client'
import type { Confidence, Decision, DecisionAnswer, VerdictCode } from '../api/types'
import { useI18n } from '../i18n'
import { verdictCodeLine } from '../i18n/explain'
import { Button } from './controls'
import { ErrorNote } from './states'

/** How far to trust the verdict. Solid = high, outlined = medium, dashed = low (dashed means
 *  "guessed" everywhere else in the app). */
export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  const { t } = useI18n()
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

/** The reason codes of the verdict as sentences (the ones that lower the confidence come first). */
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

/** "Bought it" / "Left it" after a verdict. Both go through POST /decisions: bought saves the scan into
 *  the wardrobe (no second analysis), left only logs the answer. `onDone` gets the decision. */
export function DecisionButtons({ candidateId, onDone }: { candidateId: string; onDone: (d: Decision) => void }) {
  const { t } = useI18n()
  const [busy, setBusy] = useState<'' | DecisionAnswer>('')
  const [error, setError] = useState<unknown>(null)

  const answer = async (a: DecisionAnswer) => {
    setBusy(a)
    setError(null)
    try {
      onDone(await api.decide(candidateId, a))
    } catch (e) {
      setError(e)
      setBusy('')
    }
  }

  return (
    <div className="mt-5">
      <div className="flex flex-wrap gap-2">
        <Button busy={busy === 'bought'} disabled={busy !== ''} onClick={() => answer('bought')}>
          <Check className="size-4" aria-hidden /> {t('boughtIt')}
        </Button>
        <Button variant="secondary" busy={busy === 'left'} disabled={busy !== ''} onClick={() => answer('left')}>
          <X className="size-4" aria-hidden /> {t('leftIt')}
        </Button>
      </div>
      {error ? <div className="mt-3"><ErrorNote error={error} /></div> : null}
    </div>
  )
}
