import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Minus, Plus, X } from 'lucide-react'
import { useI18n } from '../i18n'

const MIN = 1
const MAX = 5
const STEP = 1.5

type View = { scale: number; x: number; y: number }
const START: View = { scale: 1, x: 0, y: 0 }

/** Full-screen view of one photo. Zoom: pinch (phone), mouse wheel, double tap /
 *  double click, or the + / − buttons; drag to move around once zoomed.
 *  Escape, the × button or a tap on the dark border closes it. */
export function PhotoViewer({ url, alt, onClose }: { url: string; alt: string; onClose: () => void }) {
  const { t } = useI18n()
  const [view, setView] = useState<View>(START)
  const closeRef = useRef<HTMLButtonElement>(null)
  // the fingers / mouse currently pressed on the photo, by pointer id
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  const pinch = useRef<{ distance: number; scale: number } | null>(null)

  // keep the scale between MIN and MAX; back at 1x the photo is centred again
  const zoomTo = (scale: number, v: View = view): View => {
    const s = Math.min(MAX, Math.max(MIN, scale))
    return s === MIN ? START : { scale: s, x: (v.x * s) / v.scale, y: (v.y * s) / v.scale }
  }

  useEffect(() => {
    const before = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'          // the page behind does not scroll
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === '+' || e.key === '=') setView((v) => zoomTo(v.scale * STEP, v))
      else if (e.key === '-') setView((v) => zoomTo(v.scale / STEP, v))
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      before?.focus()                                 // back to the photo that opened it
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onClose])

  const distance = () => {
    const [a, b] = [...pointers.current.values()]
    return Math.hypot(a.x - b.x, a.y - b.y)
  }

  const onPointerDown = (e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId)
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.current.size === 2) pinch.current = { distance: distance(), scale: view.scale }
  }

  const onPointerMove = (e: React.PointerEvent) => {
    const last = pointers.current.get(e.pointerId)
    if (!last) return
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pinch.current && pointers.current.size === 2) {
      const scale = (pinch.current.scale * distance()) / pinch.current.distance
      setView((v) => zoomTo(scale, v))
    } else if (pointers.current.size === 1) {
      setView((v) => (v.scale === 1 ? v : { ...v, x: v.x + e.clientX - last.x, y: v.y + e.clientY - last.y }))
    }
  }

  const onPointerUp = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId)
    if (pointers.current.size < 2) pinch.current = null
  }

  const button = 'inline-flex size-11 items-center justify-center bg-paper text-ink disabled:opacity-40'
  // drawn on <body>, above the app's header and tab bar
  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={alt}
      className="fixed inset-0 z-[100] flex flex-col bg-carbon/90"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="flex justify-end gap-2 p-3">
        <button type="button" className={button} aria-label={t('zoomOut')} disabled={view.scale <= MIN}
          onClick={() => setView(zoomTo(view.scale / STEP))}>
          <Minus className="size-5" aria-hidden />
        </button>
        <button type="button" className={button} aria-label={t('zoomIn')} disabled={view.scale >= MAX}
          onClick={() => setView(zoomTo(view.scale * STEP))}>
          <Plus className="size-5" aria-hidden />
        </button>
        <button ref={closeRef} type="button" className={button} aria-label={t('close')} onClick={onClose}>
          <X className="size-5" aria-hidden />
        </button>
      </div>
      <div
        className="relative mx-3 mb-3 flex flex-1 touch-none select-none items-center justify-center overflow-hidden bg-white"
        style={{ cursor: view.scale > 1 ? 'grab' : 'zoom-in' }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onWheel={(e) => setView(zoomTo(view.scale * (e.deltaY < 0 ? 1.15 : 1 / 1.15)))}
        onDoubleClick={() => setView(view.scale > 1 ? START : zoomTo(2.5))}
      >
        <img
          src={url}
          alt={alt}
          draggable={false}
          className="max-h-full max-w-full object-contain"
          style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`, transition: pointers.current.size ? 'none' : 'transform 120ms ease-out' }}
        />
        <p className="pointer-events-none absolute bottom-2 start-3 font-mono text-[12px] text-carbon-soft tabular" dir="ltr">
          {Math.round(view.scale * 100)}%
        </p>
      </div>
    </div>,
    document.body,
  )
}
