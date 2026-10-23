import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, CircleAlert, Search, Sparkles, X } from 'lucide-react'
import { ApiError, api } from '../api/client'
import type { BuyAdvice, Decision, DecisionAnswer } from '../api/types'
import { useI18n } from '../i18n'
import { verdictCodeLine } from '../i18n/explain'
import { plural } from '../i18n/plurals'
import { Button } from './controls'
import { OutfitStrip } from './OutfitStrip'
import { Stamp } from './Stamp'
import { ErrorNote } from './states'
import { ConfidenceBadge, CodeList } from './VerdictExtras'
import { VerdictWhy } from './VerdictWhy'

// TODO(<name>, step 1): keep this list in step with `LOWERING` in src/phase4/verdict.py. Better: let the
// API say which codes lowered the confidence, so the app does not repeat the rule.
/** The codes that lower the confidence (the others only inform). */
const LOWERING_CODES = ['small_wardrobe', 'no_pairing_piece', 'guessed_field']

/** What the buttons at the bottom of the card are doing. */
type DecisionState =
  | { kind: 'idle' }
  | { kind: 'sending'; answer: DecisionAnswer }
  | { kind: 'recorded'; decision: Decision }       // 201, or 200 for the same answer given before
  | { kind: 'conflict' }                           // 409: another answer is already recorded
  | { kind: 'expired' }                            // 404: the scan is gone (kept 24 hours)
  | { kind: 'failed'; answer: DecisionAnswer; error: unknown }

/** "Bought it" / "Left it" through POST /decisions: bought saves the scan into the wardrobe (no second
 *  analysis), left only logs the answer. */
function DecisionBlock({ candidateId, onDecided, restart }: {
  candidateId: string
  onDecided?: (d: Decision) => void
  restart: { label: string; onClick: () => void }
}) {
  const { t } = useI18n()
  const [state, setState] = useState<DecisionState>({ kind: 'idle' })

  const answer = async (a: DecisionAnswer) => {
    setState({ kind: 'sending', answer: a })
    try {
      const decision = await api.decide(candidateId, a)
      setState({ kind: 'recorded', decision })
      onDecided?.(decision)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setState({ kind: 'expired' })
      else if (e instanceof ApiError && e.status === 409) setState({ kind: 'conflict' })
      else setState({ kind: 'failed', answer: a, error: e })
    }
  }

  const sending = state.kind === 'sending' ? state.answer : ''
  // once something is recorded, expired or in conflict, a second tap would only repeat the problem
  const locked = state.kind === 'sending' || state.kind === 'recorded' || state.kind === 'conflict' || state.kind === 'expired'

  return (
    <div className="mt-5 border-t border-perf/40 pt-4">
      <div className="flex flex-wrap gap-2">
        <Button busy={sending === 'bought'} disabled={locked} onClick={() => answer('bought')}>
          <Check className="size-4" aria-hidden /> {t('boughtIt')}
        </Button>
        <Button variant="secondary" busy={sending === 'left'} disabled={locked} onClick={() => answer('left')}>
          <X className="size-4" aria-hidden /> {t('leftIt')}
        </Button>
      </div>

      {state.kind === 'recorded' && (
        <p role="status" className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[15px] text-carbon">
          <span className="inline-flex items-center gap-2">
            <Check className="size-4 shrink-0 text-ink" aria-hidden />
            {state.decision.answer === 'bought' ? t('decisionAdded') : t('decisionLeft')}
          </span>
          {state.decision.answer === 'bought' && state.decision.item_id && (
            <Link to={`/wardrobe/${state.decision.item_id}`} className="inline-flex min-h-11 items-center text-ink underline decoration-1 underline-offset-4">
              {t('openItem')}
            </Link>
          )}
        </p>
      )}

      {(state.kind === 'conflict' || state.kind === 'expired') && (
        <div role="alert" className="mt-3 flex items-start gap-3 border-[1.5px] border-carbon bg-paper px-4 py-3">
          <CircleAlert className="mt-0.5 size-5 shrink-0 text-carbon" aria-hidden />
          <div className="min-w-0 flex-1 text-[14px] text-carbon">
            <p>{state.kind === 'conflict' ? t('decisionConflict') : t('decisionExpired')}</p>
            {state.kind === 'expired' && (
              <Button variant="secondary" className="mt-2" onClick={restart.onClick}>{restart.label}</Button>
            )}
          </div>
        </div>
      )}

      {state.kind === 'failed' && (
        <div className="mt-3"><ErrorNote error={state.error} onRetry={() => answer(state.answer)} /></div>
      )}
    </div>
  )
}

/** The verdict on a piece, shared by the "Should I buy this?" screen and a Shop listing: stamp and
 *  number of good outfits, how far to trust it, the reasons, the best outfits, the optional extras
 *  and the Bought it / Left it answer. `onDecided` lets a page react to the answer (the Scan page
 *  opens the new item); without it the card just shows what was recorded. `restart` is offered when
 *  the scan has expired (404). */
export function VerdictCard({ advice, candidatePhoto, showTryOn = false, onDecided, restart }: {
  advice: BuyAdvice
  candidatePhoto?: string
  showTryOn?: boolean
  onDecided?: (d: Decision) => void
  restart: { label: string; onClick: () => void }
}) {
  const { t, lang, reason } = useI18n()
  const candidate = advice.candidate
  // the codes that lowered the confidence say why it is not higher; the others are "good to know"
  const lowered = advice.codes.filter((c) => LOWERING_CODES.includes(c.code))
  const info = advice.codes.filter((c) => !LOWERING_CODES.includes(c.code))
  const linkClass = 'inline-flex min-h-11 items-center gap-2 border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink'

  return (
    <section aria-live="polite">
      <div className="flex items-center gap-4">
        <Stamp big={t(`verdict_${advice.verdict}`)} ring="DRESSME · VALIDÉ · مصادق · DRESSME · VALIDÉ ·"
          size={96} angle={-11} land label={t(`verdict_${advice.verdict}`)} />
        <p className="min-w-0 text-[18px] font-medium leading-snug text-carbon">
          {t(`verdictLine_${advice.verdict}`, { outfits: plural('goodOutfits', advice.good_outfits, lang) })}
        </p>
      </div>

      {advice.reasons.length > 0 && (
        <ul className="mt-3 space-y-1 text-[15px] text-carbon-soft">
          {advice.reasons.map((r) => <li key={r}>{reason(r)}</li>)}
        </ul>
      )}

      <div className="mt-3">
        <ConfidenceBadge confidence={advice.confidence} />
        {lowered.length > 0 && (
          <ul className="mt-2 space-y-1 text-[14px] text-carbon-soft">
            {lowered.map((c, i) => <li key={`${c.code}-${i}`}>{verdictCodeLine(c, lang)}</li>)}
          </ul>
        )}
      </div>
      <CodeList codes={info} />
      {advice.explanation && <VerdictWhy explanation={advice.explanation} />}

      {advice.best.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-4 text-[18px] font-semibold text-carbon">{t('bestOutfits')}</h2>
          <div className="grid gap-10 pt-4 sm:grid-cols-2">
            {advice.best.slice(0, 2).map((o, i) => (
              <OutfitStrip key={i} outfit={o} compact photoOf={(id) => (id === candidate.id ? candidatePhoto : undefined)} />
            ))}
          </div>
        </div>
      )}

      <div className="mt-6 flex flex-wrap gap-2">
        <Link to={`/similar?candidate=${candidate.id}`} className={linkClass}>
          <Search className="size-4" aria-hidden /> {t('seeSimilar')}
        </Link>
        {showTryOn && (
          <Link to={`/tryon?candidate=${candidate.id}&ccat=${candidate.category}`} className={linkClass}>
            <Sparkles className="size-4" aria-hidden /> {t('tryOnBtn')}
          </Link>
        )}
      </div>

      <DecisionBlock candidateId={candidate.id} onDecided={onDecided} restart={restart} />
    </section>
  )
}
