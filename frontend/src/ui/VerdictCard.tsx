import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, CircleAlert, CircleHelp, Minus, Plus, Search, Sparkles, X } from 'lucide-react'
import { ApiError, api } from '../api/client'
import type { BuyAdvice, Decision, DecisionAnswer, OutfitItem } from '../api/types'
import { useI18n } from '../i18n'
import { verdictCodeLine } from '../i18n/explain'
import { plural } from '../i18n/plurals'
import type { StringKey } from '../i18n/strings'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Button } from './controls'
import { ItemPhoto } from './ItemPhoto'
import { ConfidenceDots, OutfitCard } from './OutfitCard'
import { ErrorNote } from './states'
import { useHideTabBar } from './tabBar'
import { VerdictWhy } from './VerdictWhy'

// TODO(step 1): keep this list in step with `LOWERING` in src/phase4/verdict.py. Better: let the
// API say which codes lowered the confidence, so the app does not repeat the rule.
/** The codes that lower the confidence (the others only inform). */
const LOWERING_CODES = ['small_wardrobe', 'no_pairing_piece', 'guessed_field']

/** The banner's sentence for the first code that lowered the confidence. */
const LOW_SENTENCE: Record<string, StringKey> = {
  small_wardrobe: 'lowConf_small_wardrobe',
  no_pairing_piece: 'lowConf_no_pairing_piece',
  guessed_field: 'lowConf_guessed_field',
}

/** What the buttons at the bottom are doing. */
type DecisionState =
  | { kind: 'idle' }
  | { kind: 'sending'; answer: DecisionAnswer }
  | { kind: 'recorded'; decision: Decision }       // 201, or 200 for the same answer given before
  | { kind: 'conflict' }                           // 409: another answer is already recorded
  | { kind: 'expired' }                            // 404: the scan is gone (kept 24 hours)
  | { kind: 'failed'; answer: DecisionAnswer; error: unknown }

/** "Bought it" / "Left it" through POST /decisions, in a bar fixed to the bottom of the phone screen (the tab bar
 *  is hidden meanwhile; on a desktop it sticks under the content). Bought saves the scan into the wardrobe (no
 *  second analysis), left only logs the answer. Afterwards the bar says it is saved and offers the next step:
 *  open the new item, or `again` (Scan: scan another). There is no undo: the API keeps the first answer. */
function DecisionBar({ candidateId, restart, again }: {
  candidateId: string
  restart: { label: string; onClick: () => void }
  again?: { label: string; onClick: () => void }
}) {
  const { t } = useI18n()
  const [state, setState] = useState<DecisionState>({ kind: 'idle' })
  const bar = useRef<HTMLDivElement>(null)
  const [room, setRoom] = useState(0)

  // the content ends with an empty block as tall as the bar, so the bar never hides the last lines
  useEffect(() => {
    const el = bar.current
    if (!el) return
    const watcher = new ResizeObserver(() => setRoom(el.offsetHeight))
    watcher.observe(el)
    return () => watcher.disconnect()
  }, [])

  const answer = async (a: DecisionAnswer) => {
    setState({ kind: 'sending', answer: a })
    try {
      setState({ kind: 'recorded', decision: await api.decide(candidateId, a) })
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setState({ kind: 'expired' })
      else if (e instanceof ApiError && e.status === 409) setState({ kind: 'conflict' })
      else setState({ kind: 'failed', answer: a, error: e })
    }
  }

  const sending = state.kind === 'sending' ? state.answer : ''
  const link = 'inline-flex min-h-11 shrink-0 items-center text-[14px] font-semibold text-carbon underline decoration-1 underline-offset-4'

  return (
    <>
      <div aria-hidden className="lg:hidden" style={{ height: room }} />
      <div ref={bar} className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-stock px-5 pb-[calc(env(safe-area-inset-bottom)+1rem)] pt-3 lg:sticky lg:mt-6 lg:px-0">
        <div className="mx-auto max-w-[640px]">
          {state.kind === 'recorded' ? (
            <div role="status" className="pop flex min-h-button items-center gap-3">
              <span className="grid size-8 shrink-0 place-items-center rounded-pill bg-pill text-pill-text">
                <Check className="size-[18px]" strokeWidth={2.5} aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[16px] font-semibold text-carbon">{t('decisionSaved')}</p>
                <p className="text-[14px] text-carbon-soft">{state.decision.answer === 'bought' ? t('decisionAdded') : t('decisionLeft')}</p>
              </div>
              {state.decision.answer === 'bought' && state.decision.item_id ? (
                <Link to={`/wardrobe/${state.decision.item_id}`} className={link}>{t('openItem')}</Link>
              ) : state.decision.answer === 'left' && again ? (
                <button type="button" onClick={again.onClick} className={link}>{again.label}</button>
              ) : null}
            </div>
          ) : state.kind === 'conflict' || state.kind === 'expired' ? (
            <div role="alert" className="flex items-start gap-3 rounded-photo bg-surface px-4 py-3 ring-1 ring-inset ring-line-strong">
              <CircleAlert className="mt-0.5 size-5 shrink-0 text-carbon" strokeWidth={1.75} aria-hidden />
              <div className="min-w-0 flex-1 text-[14px] text-carbon">
                <p>{state.kind === 'conflict' ? t('decisionConflict') : t('decisionExpired')}</p>
                {state.kind === 'expired' && (
                  <button type="button" onClick={restart.onClick} className={link}>{restart.label}</button>
                )}
              </div>
            </div>
          ) : (
            <>
              {state.kind === 'failed' && (
                <div className="mb-3"><ErrorNote error={state.error} onRetry={() => answer(state.answer)} /></div>
              )}
              <div className="flex gap-3">
                <Button busy={sending === 'bought'} disabled={sending !== ''} onClick={() => answer('bought')} className="min-w-0 flex-[1.4]">
                  {t('boughtIt')}
                </Button>
                <Button variant="secondary" busy={sending === 'left'} disabled={sending !== ''} onClick={() => answer('left')} className="min-w-0 flex-1">
                  {t('leftIt')}
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}

// The verdict's colour: buy / think / skip on their soft fills, always with a word and an icon (step H)
const VERDICT_PILL = {
  buy: { look: 'bg-buy-soft text-buy', icon: Check },
  think: { look: 'bg-unsure-soft text-unsure', icon: CircleHelp },
  skip: { look: 'bg-leave-soft text-leave', icon: X },
} as const

/** One line of "Why": in favour (buy colours, +) or against (leave colours, −), with the owned pieces it is about. */
type WhyRow = { pro: boolean; text: string; thumbs: Pick<OutfitItem, 'id' | 'image_url'>[] }

/** The verdict on a piece, shared by the "Should I buy this?" screen and a Shop listing (step H2, the prototype's
 *  verdict screen): the photo, the verdict pill, how many good outfits it makes and the price, the path to the
 *  verdict (good outfits against what Buy and Think need), how far to trust it, a banner when that is low, the
 *  reasons for and against, "Why this verdict?", the best outfits as Dress cards, and the Bought it / Left it bar.
 *  `price` = the price the verdict was asked with (null = none given). `restart` is offered when the scan has
 *  expired (404); `again` after "Left it". */
export function VerdictCard({ advice, candidatePhoto, price = null, showTryOn = false, restart, again }: {
  advice: BuyAdvice
  candidatePhoto?: string
  price?: number | null
  showTryOn?: boolean
  restart: { label: string; onClick: () => void }
  again?: { label: string; onClick: () => void }
}) {
  const { t, lang, reason } = useI18n()
  useHideTabBar()
  const candidate = advice.candidate
  const pill = VERDICT_PILL[advice.verdict]
  const number = new Intl.NumberFormat(lang === 'ar' ? 'ar-TN' : lang)
  const name = vocab(SUB_LABELS, candidate.sub_category, lang) || vocab(CATEGORY_LABELS, candidate.category, lang)
  const photoOf = (id: string) => (id === candidate.id ? candidatePhoto : undefined)
  const lowered = advice.codes.filter((c) => LOWERING_CODES.includes(c.code))
  const lowSentence = lowered.map((c) => LOW_SENTENCE[c.code]).find(Boolean)

  // the path to the verdict, on one scale: the good outfits, then what "Buy" and "Think" need
  const path = advice.explanation?.path
  const bars: [StringKey, number][] = path ? [['pathGood', path.good], ['pathBuy', path.buy_min], ['pathThink', path.think_min]] : []
  const scale = Math.max(1, ...bars.map(([, n]) => n))

  // the owned pieces of the best outfits (only when they are good ones), and the near twins
  const owned: WhyRow['thumbs'] = []
  if (advice.good_outfits > 0) {
    for (const it of advice.best.flatMap((o) => o.items)) {
      if (it.id !== candidate.id && !owned.some((o) => o.id === it.id)) owned.push(it)
    }
  }
  const twins = (advice.explanation?.twins ?? []).map((tw) => tw.item)
  const rows: WhyRow[] = [
    { pro: advice.verdict !== 'skip', text: t(`verdictLine_${advice.verdict}`, { outfits: plural('goodOutfits', advice.good_outfits, lang) }), thumbs: owned },
    ...advice.reasons.map((r) => ({ pro: false, text: reason(r), thumbs: twins })),
    ...advice.codes.map((c) => ({ pro: c.code === 'fills_gap', text: verdictCodeLine(c, lang), thumbs: [] })),
  ]
  const secondary = 'press inline-flex min-h-11 items-center gap-2 rounded-pill bg-surface px-4 text-[15px] font-semibold text-carbon ring-[1.5px] ring-inset ring-line-strong'

  return (
    <section aria-live="polite" className="flex flex-col gap-5">
      <section aria-label={name} className="flex flex-col gap-5 rounded-hero bg-surface p-card">
        <div className="flex items-stretch gap-4">
          <div className="grid w-[132px] shrink-0 place-items-center rounded-photo bg-photo p-3.5">
            <ItemPhoto src={candidatePhoto ?? candidate.image_url} alt={name} size={104} blend />
          </div>
          <div className="flex min-w-0 flex-1 flex-col items-start justify-between gap-3 py-0.5">
            <span className={`pop inline-flex h-10 items-center gap-2 rounded-pill pe-4 ps-3 text-[16px] font-semibold ${pill.look}`}>
              <pill.icon className="size-5" strokeWidth={2.25} aria-hidden /> {t(`verdict_${advice.verdict}`)}
            </span>
            <div>
              <p className="font-display text-[80px] font-bold leading-[76px] tracking-[-0.04em] text-carbon tabular">{number.format(advice.good_outfits)}</p>
              <p className="text-[14px] font-medium text-carbon-soft">
                {plural('goodOutfitsUnit', advice.good_outfits, lang)} · {price !== null && price > 0 ? t('verdictPrice', { p: number.format(price) }) : t('verdictNoPrice')}
              </p>
            </div>
          </div>
        </div>

        {bars.length > 0 && (
          <ul aria-label={t('verdictPathLabel')} className="flex flex-col gap-3">
            {bars.map(([key, n]) => (
              <li key={key} className="grid grid-cols-[minmax(0,7.75rem)_1fr_2rem] items-center gap-3 text-[14px] font-medium text-carbon">
                <span>{t(key)}</span>
                <span aria-hidden className="block h-2 overflow-hidden rounded-pill bg-sunken">
                  <span className="block h-full rounded-pill bg-pill" style={{ width: `${(100 * Math.min(n, scale)) / scale}%` }} />
                </span>
                <span className="text-end tabular">{number.format(Math.round(n))}</span>
              </li>
            ))}
          </ul>
        )}

        <div className="border-t border-line pt-4">
          <ConfidenceDots level={advice.confidence} />
        </div>
      </section>

      {advice.confidence === 'low' && (
        <section aria-label={t('lowConfTitle')} className="pop flex items-start gap-3 rounded-card bg-unsure-soft p-4 text-unsure">
          <CircleHelp className="mt-0.5 size-[22px] shrink-0" strokeWidth={1.75} aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="text-[16px] font-semibold">{t('lowConfTitle')}</p>
            {lowSentence && <p className="text-[14px]">{t(lowSentence)}</p>}
          </div>
        </section>
      )}

      <section aria-labelledby="why-title" className="flex flex-col gap-3">
        <h2 id="why-title" className="px-1 text-[18px] font-semibold text-carbon">{t('whyTitle')}</h2>
        <ul className="divide-y divide-line rounded-card bg-surface px-4 py-2">
          {rows.map((r, i) => (
            <li key={i} className="flex items-center gap-3 py-3">
              <span
                role="img"
                aria-label={t(r.pro ? 'reasonFor' : 'reasonAgainst')}
                className={`grid size-7 shrink-0 place-items-center rounded-pill ${r.pro ? 'bg-buy-soft text-buy' : 'bg-leave-soft text-leave'}`}
              >
                {r.pro ? <Plus className="size-4" strokeWidth={2.5} aria-hidden /> : <Minus className="size-4" strokeWidth={2.5} aria-hidden />}
              </span>
              <p className="min-w-0 flex-1 text-[16px] leading-6 text-carbon">{r.text}</p>
              {r.thumbs.length > 0 && (
                <span aria-hidden className="flex shrink-0 ps-2.5">
                  {r.thumbs.slice(0, 3).map((p) => (
                    <span key={p.id} className="-ms-2.5 grid h-12 w-10 place-items-center overflow-hidden rounded-tile bg-photo ring-2 ring-surface">
                      <ItemPhoto src={p.image_url} alt="" size={32} blend />
                    </span>
                  ))}
                </span>
              )}
            </li>
          ))}
        </ul>
        {advice.explanation && <VerdictWhy explanation={advice.explanation} />}
      </section>

      <div className="flex flex-wrap gap-2">
        <Link to={`/similar?candidate=${candidate.id}`} className={secondary}>
          <Search className="size-4" aria-hidden /> {t('seeSimilar')}
        </Link>
        {showTryOn && (
          <Link to={`/tryon?candidate=${candidate.id}&ccat=${candidate.category}`} className={secondary}>
            <Sparkles className="size-4" aria-hidden /> {t('tryOnBtn')}
          </Link>
        )}
      </div>

      {advice.best.length > 0 && (
        <section aria-labelledby="best-title" className="flex flex-col gap-4">
          <h2 id="best-title" className="px-1 text-[18px] font-semibold text-carbon">{t('bestOutfits')}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {advice.best.slice(0, 2).map((o, i) => (
              <OutfitCard key={o.items.map((it) => it.id).join('|')} outfit={o} index={i} source="verdict" photoOf={photoOf} />
            ))}
          </div>
        </section>
      )}

      <DecisionBar candidateId={candidate.id} restart={restart} again={again} />
    </section>
  )
}
