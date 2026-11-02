import { useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Check, Sparkles, TriangleAlert, X } from 'lucide-react'
import { useI18n } from '../i18n'
import { useTryOn } from '../tryon'
import { ItemPhoto } from './ItemPhoto'
import { estimate, TryOnProgress, useElapsed } from './TryOnProgress'

/** The wait, in front of the page: a dialog over a dimmed screen. "Keep browsing"
 *  shrinks it to the pill; Escape does the same (the try-on keeps running). */
export function TryOnPanel() {
  const { t } = useI18n()
  const { job, panelOpen, cancel, minimise } = useTryOn()
  const box = useRef<HTMLDivElement>(null)
  const open = panelOpen && job?.state === 'running'

  useEffect(() => {
    if (!open) return
    const before = document.activeElement as HTMLElement | null
    box.current?.querySelector<HTMLElement>('button')?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') minimise() }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'                 // the page behind doesn't scroll
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      before?.focus?.()
    }
  }, [open, minimise])

  if (!open || !job) return null
  return (
    <div className="tryon-backdrop fixed inset-0 z-40 grid place-items-center overflow-y-auto bg-carbon/45 p-4 backdrop-blur-[3px]"
      onClick={(e) => { if (e.target === e.currentTarget) minimise() }}>
      <div ref={box} role="dialog" aria-modal="true" aria-labelledby="tryon-panel-title"
        className="tryon-panel w-full max-w-[440px] bg-stock p-3 shadow-[var(--shadow-lift)]">
        <h2 id="tryon-panel-title" className="mb-3 flex items-center gap-2 px-1 text-[20px] font-semibold text-carbon">
          <Sparkles className="size-5 text-ink" aria-hidden /> {t('tryOnPanelTitle')}
        </h2>
        <TryOnProgress personUrl={job.personUrl} pieces={job.pieces} secondsPer={job.secondsPer}
          startedAt={job.startedAt} onCancel={cancel} onMinimise={minimise} />
      </div>
    </div>
  )
}

/** The try-on shrunk to a ticket in the corner, on every page: progress while it
 *  runs (tap = the panel again), then "ready" with a link to the result. */
export function TryOnPill() {
  const { job, panelOpen } = useTryOn()
  const location = useLocation()
  if (!job || panelOpen) return null
  const onItsPage = location.pathname + location.search === job.backTo
  // once finished, the try-on page itself shows the outcome: no pill there
  if (job.state === 'stopped' || (job.state !== 'running' && onItsPage)) return null
  return (
    <div className="tryon-pill fixed bottom-[calc(var(--tabbar-h,88px)+0.75rem)] end-3 z-30 lg:bottom-6 lg:end-6">
      {job.state === 'running' ? <RunningPill /> : <FinishedPill />}
    </div>
  )
}

function RunningPill() {
  const { t } = useI18n()
  const { job, openPanel } = useTryOn()
  const { elapsed } = useElapsed(job!.startedAt)
  const { progress, index } = estimate(elapsed, job!.pieces.length, job!.secondsPer)
  const pct = Math.round(progress * 100)
  const piece = job!.pieces[index]
  return (
    <button type="button" onClick={openPanel}
      className="ticket flex min-h-14 w-[240px] items-center gap-3 p-2 pe-3 text-start shadow-[var(--shadow-lift)]">
      <span className="relative shrink-0 overflow-hidden bg-white" aria-hidden>
        {piece ? <ItemPhoto src={piece.image_url} alt="" size={40} /> : <span className="block size-10" />}
        <span className="tryon-scan pointer-events-none absolute inset-x-0 top-0 h-1/3" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[14px] font-medium text-carbon">{t('tryOnPillRunning', { pct })}</span>
        <span className="mt-1 block h-1 bg-stock-deep" aria-hidden>
          <span className="block h-full bg-ink transition-[width] duration-500" style={{ width: `${pct}%` }} />
        </span>
      </span>
    </button>
  )
}

function FinishedPill() {
  const { t } = useI18n()
  const { job, dismiss } = useTryOn()
  const ok = job!.state === 'done'
  return (
    <div className="ticket stamp-land flex w-[260px] items-center gap-3 p-2 pe-1 shadow-[var(--shadow-lift)]" role="status">
      <span className={`grid size-10 shrink-0 place-items-center ${ok ? 'bg-ink text-paper' : 'bg-stock-deep text-carbon'}`} aria-hidden>
        {ok ? <Check className="size-5" strokeWidth={3} /> : <TriangleAlert className="size-5" />}
      </span>
      <Link to={job!.backTo} className="min-w-0 flex-1 text-[14px] font-medium text-carbon">
        <span className="block truncate">{ok ? t('tryOnPillDone') : t('tryOnPillFailed')}</span>
        <span className="text-[13px] text-ink underline underline-offset-4">{t('tryOnPillView')}</span>
      </Link>
      <button type="button" onClick={dismiss} aria-label={t('tryOnDismiss')}
        className="grid size-11 shrink-0 place-items-center text-carbon-soft hover:text-ink">
        <X className="size-4" aria-hidden />
      </button>
    </div>
  )
}
