import { useState } from 'react'
import { useI18n } from '../i18n'

/** The try-on result over the user's photo, with a handle to slide between them.
 *  Both pictures have the same size and framing (the try-on service keeps them),
 *  so they line up. Kept left-to-right in Arabic too: it is a picture, not text. */
export function CompareSlider({ before, after, afterAlt }: { before: string; after: string; afterAlt: string }) {
  const { t } = useI18n()
  const [pos, setPos] = useState(100)            // % of the result shown, from the left

  return (
    <div>
      <div className="tryon-reveal relative select-none overflow-hidden bg-white" dir="ltr">
        <img src={before} alt={t('tryOnYourPhoto')} className="block w-full" draggable={false} />
        <img src={after} alt={afterAlt} draggable={false}
          className="absolute inset-0 block h-full w-full object-contain"
          style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }} />
        {pos > 0 && pos < 100 && (
          <div aria-hidden className="pointer-events-none absolute inset-y-0 w-0.5 bg-paper shadow-[0_0_0_1px_var(--color-ink)]"
            style={{ left: `${pos}%` }} />
        )}
        <span aria-hidden className="absolute start-2 top-2 bg-paper px-2 py-1 font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-soft">
          {pos > 50 ? t('tryOnAfter') : t('tryOnBefore')}
        </span>
        {/* the range input sits over the picture: drag anywhere, or use the arrow keys */}
        <input type="range" min={0} max={100} value={pos} aria-label={t('tryOnCompare')}
          onChange={(e) => setPos(Number(e.target.value))}
          className="absolute inset-0 h-full w-full cursor-ew-resize opacity-0" />
      </div>
      <p className="mt-2 text-[12px] text-carbon-soft">{t('tryOnCompare')}</p>
    </div>
  )
}
