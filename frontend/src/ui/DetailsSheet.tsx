import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { useI18n } from '../i18n'

/** A sheet that slides up from the bottom on a phone and sits in the middle on a wide screen. It is drawn in
 *  <body> (a portal): inside the page, its animation would trap it under the phone tab bar. Escape, the
 *  close button or a tap on the dark area close it; the page behind does not scroll while it is open.
 *  `onClose` should be stable (useCallback), or the focus jumps back to the close button at each render. */
export function DetailsSheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const { t } = useI18n()
  const closeButton = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    const before = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButton.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = before
    }
  }, [onClose])

  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-scrim sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[88dvh] w-full overflow-y-auto rounded-t-sheet bg-paper p-card pb-[calc(env(safe-area-inset-bottom)+1.25rem)] sm:max-w-[560px] sm:rounded-sheet"
      >
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-[20px] font-bold text-carbon">{title}</h2>
          <button
            ref={closeButton}
            type="button"
            aria-label={t('close')}
            onClick={onClose}
            className="grid size-11 shrink-0 place-items-center rounded-pill border-[1.5px] border-pill-line text-pill focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pill"
          >
            <X className="size-5" aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  )
}
