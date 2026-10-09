import { useState } from 'react'
import { Lightbulb } from 'lucide-react'
import type { BuyExplanation, ShortItem } from '../api/types'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Button } from './controls'
import { ItemPhoto } from './ItemPhoto'

/** "Why this verdict?": the team's thresholds, what the piece beats, which owned
 *  pieces beat it, near misses, and the near twins with their pictures. */
export function VerdictWhy({ explanation: e }: { explanation: BuyExplanation }) {
  const { t, lang } = useI18n()
  const [open, setOpen] = useState(false)
  const name = (it: ShortItem) => vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)
  return (
    <div className="mt-3">
      <Button variant="quiet" onClick={() => setOpen(!open)} aria-expanded={open}>
        <Lightbulb className="size-4" aria-hidden /> {open ? t('hideWhyScore') : t('verdictWhy')}
      </Button>
      {open && (
        <div className="ticket mt-2 space-y-3 px-4 py-4 text-[14px] text-carbon">
          <p>{t('verdictPath', { good: e.path.good, buy: e.path.buy_min, think: e.path.think_min })}</p>
          {e.to_next_verdict !== null && e.to_next_verdict > 0 && <p>{t('toNextVerdict', { n: e.to_next_verdict })}</p>}
          {e.beats.length > 0 && (
            <ul className="space-y-1">
              {e.beats.slice(0, 3).map((b, i) => (
                <li key={i} className="flex items-center gap-2">
                  {b.owned && <ItemPhoto src={b.owned.image_url} alt="" size={40} />}
                  {b.owned ? t('beatsOwned', { piece: name(b.owned), margin: b.margin.toFixed(1) }) : t('fillsGap')}
                </li>
              ))}
            </ul>
          )}
          {e.lost_to.map((l) => (
            <p key={l.owned_id} className="flex items-center gap-2 text-carbon-soft">
              <ItemPhoto src={l.owned.image_url} alt="" size={40} /> {t('lostTo', { piece: name(l.owned), n: l.outfits })}
            </p>
          ))}
          {e.near_misses > 0 && <p className="text-carbon-soft">{t('nearMisses', { n: e.near_misses })}</p>}
          {e.twins.length > 0 && (
            <div>
              <h3 className="mb-1 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('twinsTitle')}</h3>
              <ul className="flex flex-wrap gap-3">
                {e.twins.map((tw) => (
                  <li key={tw.item.id} className="flex flex-col items-center gap-1">
                    <ItemPhoto src={tw.item.image_url} alt={name(tw.item)} size={64} />
                    <span className="font-mono text-[11px] tabular" dir="ltr">{Math.round(tw.similarity * 100)}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
