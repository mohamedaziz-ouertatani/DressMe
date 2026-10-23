import type { Outfit } from '../api/types'
import { useI18n } from '../i18n'

/** "Incomplete: add a bottom": shown next to the score of an outfit that has no top + bottom (and no dress).
 *  Only a note: the score stays visible and the outfit is not blocked. Nothing for a complete outfit, or for an
 *  answer from before the flag existed. */
export function IncompleteNote({ outfit, className = '' }: { outfit: Pick<Outfit, 'complete' | 'missing'>; className?: string }) {
  const { t } = useI18n()
  if (outfit.complete !== false || !outfit.missing) return null
  return (
    <p role="note" className={`text-[13px] font-medium text-carbon ${className}`}>
      <span aria-hidden>△ </span>{t(`incomplete_${outfit.missing}`)}
    </p>
  )
}
