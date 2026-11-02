import { TriangleAlert } from 'lucide-react'
import type { Outfit } from '../api/types'
import { useI18n } from '../i18n'

/** "Incomplete: add a bottom": shown next to the score of an outfit that has no top + bottom (and no dress).
 *  Only a note: the score stays visible and the outfit is not blocked. Nothing for a complete outfit, or for an
 *  answer from before the flag existed. The unsure colours (step H), with a thin warning icon and the word
 *  "Incomplete", so the meaning never rests on colour alone. */
export function IncompleteNote({ outfit, className = '' }: { outfit: Pick<Outfit, 'complete' | 'missing'>; className?: string }) {
  const { t } = useI18n()
  if (outfit.complete !== false || !outfit.missing) return null
  return (
    <p role="note" className={`inline-flex max-w-full items-center gap-1.5 rounded-pill bg-unsure-soft px-3 py-1 text-[13px] font-medium text-unsure ${className}`}>
      <TriangleAlert className="size-4 shrink-0" strokeWidth={1.75} aria-hidden />
      <span className="min-w-0">{t(`incomplete_${outfit.missing}`)}</span>
    </p>
  )
}
