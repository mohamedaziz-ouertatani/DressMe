import { useEffect, useState } from 'react'
import { Lightbulb } from 'lucide-react'
import { api } from '../api/client'
import type { Contribution, ExplainLine, Outfit, OutfitExplanation, PartName } from '../api/types'
import { useI18n } from '../i18n'
import { explainLine } from '../i18n/explain'
import type { StringKey } from '../i18n/strings'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Button } from './controls'
import { ItemPhoto } from './ItemPhoto'
import { ErrorNote, Skeleton } from './states'

const PART_KEY: Record<PartName, StringKey> = {
  style: 'partStyle', colour: 'partColour', pattern: 'partPattern', structure: 'partStructure',
}
const PART_COLOUR: Record<PartName, string> = {
  style: 'bg-ink', colour: 'bg-stamp', pattern: 'bg-ink-soft', structure: 'bg-carbon-soft',
}

/** The score split into its four parts: one slot per counted part, as wide as the
 *  points it can earn, filled as far as the points it did earn. */
export function PointsBar({ contributions }: { contributions: Contribution[] }) {
  const { t } = useI18n()
  return (
    <div className="space-y-1.5">
      <div className="flex h-2.5 w-full gap-px overflow-hidden" aria-hidden>
        {contributions.filter((c) => c.counted).map((c) => (
          <span key={c.part} className="flex h-full bg-stock-deep" style={{ width: `${c.max_points}%` }}>
            <span className={`h-full ${PART_COLOUR[c.part]}`} style={{ width: `${c.max_points ? (100 * c.points) / c.max_points : 0}%` }} />
          </span>
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-carbon-soft">
        {contributions.map((c) => (
          <li key={c.part} className="inline-flex items-center gap-1.5">
            <span aria-hidden className={`size-2 ${c.counted ? PART_COLOUR[c.part] : 'bg-perf'}`} />
            {t(PART_KEY[c.part])}{' '}
            {/* no dir="ltr" here: the sentence holds a word ("of", "من") that must follow the page's direction */}
            <span className="font-mono tabular">
              {c.counted ? t('pointsOf', { p: c.points.toFixed(1), max: c.max_points.toFixed(1) }) : t('partNotCounted')}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Strengths (+) then problems (−), as sentences in the user's language. */
export function ExplainLines({ lines }: { lines: ExplainLine[] }) {
  const { lang } = useI18n()
  const sorted = [...lines.filter((l) => l.sign === '+'), ...lines.filter((l) => l.sign === '-')]
  return (
    <ul className="space-y-1 text-[14px]">
      {sorted.map((l, i) => (
        <li key={i} className={`flex gap-2 ${l.sign === '+' ? 'text-carbon' : 'text-carbon-soft'}`}>
          <span aria-hidden className={`w-3 shrink-0 font-mono ${l.sign === '+' ? 'text-ink' : 'text-stamp'}`}>{l.sign === '+' ? '+' : '−'}</span>
          {explainLine(l, lang)}
        </li>
      ))}
    </ul>
  )
}

/** "Why this score?": loads the swaps and the pair map on demand. */
export function ScoreDetails({ outfit, onSwap }: { outfit: Outfit; onSwap?: (from: string, to: string) => void }) {
  const { t, lang } = useI18n()
  const [open, setOpen] = useState(false)
  // the answer is kept with the outfit it is for: after a swap on Build, the old one is not shown
  const [answer, setAnswer] = useState<{ key: string; data?: OutfitExplanation; error?: unknown }>({ key: '' })
  const ids = outfit.items.map((i) => i.id)
  const key = ids.join(',')

  useEffect(() => {
    if (!open) return
    let live = true
    api.explainOutfit(key.split(','))
      .then((data) => { if (live) setAnswer({ key, data }) })
      .catch((error) => { if (live) setAnswer({ key, error }) })
    return () => { live = false }
  }, [open, key])

  const data = answer.key === key ? answer.data ?? null : null
  const error = answer.key === key ? answer.error : null
  const name = (id: string) => {
    const it = outfit.items.find((i) => i.id === id)
    return it ? vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang) : ''
  }
  const pct = (v: number | null) => (v === null ? '–' : `${Math.round(v * 100)}`)
  const weakest = data?.swaps.find((s) => s.item_id === data.weakest)

  return (
    <div className="mt-2">
      <Button variant="quiet" onClick={() => setOpen(!open)} aria-expanded={open}>
        <Lightbulb className="size-4" aria-hidden /> {open ? t('hideWhyScore') : t('whyScore')}
      </Button>
      {open && (
        <div className="mt-2 space-y-4 border-t border-perf/40 pt-3">
          {error ? <ErrorNote error={error} /> : !data ? <Skeleton className="h-32" /> : (
            <>
              {weakest?.swap ? (
                <div className="flex flex-wrap items-center gap-3">
                  <ItemPhoto src={weakest.swap.image_url} alt="" size={56} />
                  <p className="min-w-0 flex-1 text-[14px] text-carbon">
                    {t('weakestPiece', {
                      piece: name(weakest.item_id),
                      swap: vocab(SUB_LABELS, weakest.swap.sub_category, lang) || vocab(CATEGORY_LABELS, weakest.swap.category, lang),
                      gain: weakest.gain.toFixed(1),
                    })}
                  </p>
                  {onSwap && <Button variant="secondary" onClick={() => onSwap(weakest.item_id, weakest.swap!.id)}>{t('applySwap')}</Button>}
                </div>
              ) : <p className="text-[14px] text-carbon-soft">{t('noBetterSwap')}</p>}
              <div>
                <h3 className="mb-1 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('pairMap')}</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="text-carbon-soft">
                        <th className="py-1 text-start font-normal" />
                        <th className="py-1 text-end font-normal">{t('partStyle')}</th>
                        <th className="py-1 text-end font-normal">{t('partColour')}</th>
                        <th className="py-1 text-end font-normal">{t('partPattern')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.pair_map.map((p) => (
                        <tr key={`${p.a}-${p.b}`} className="border-t border-perf/30">
                          <td className="py-1 pe-2 text-carbon">{name(p.a)} + {name(p.b)}</td>
                          {[p.style, p.colour, p.pattern].map((v, i) => (
                            <td key={i} className="py-1 text-end font-mono tabular" dir="ltr">{pct(v)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
