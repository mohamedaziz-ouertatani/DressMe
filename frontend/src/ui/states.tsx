import { useEffect, type ReactNode } from 'react'
import { CircleAlert, Inbox, WifiOff, type LucideIcon } from 'lucide-react'
import { ApiError } from '../api/client'
import { useI18n } from '../i18n'
import { Button } from './controls'
import { useLook } from './look'

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`skeleton ${className}`} />
}

/** An empty state that teaches what to do next. In the soft look: the prototype's state card (an icon on a sky
 *  disc, a title, one sentence, one action). */
export function Empty({ title, body, action, icon: Icon = Inbox }: { title: string; body: ReactNode; action?: ReactNode; icon?: LucideIcon }) {
  const soft = useLook() === 'soft'
  if (soft) {
    return (
      <div className="flex flex-col items-start gap-2 rounded-card bg-surface px-5 pb-5 pt-6">
        <span aria-hidden className="mb-2 grid size-14 place-items-center rounded-full bg-tint-sky text-carbon">
          <Icon className="size-[26px]" strokeWidth={1.75} />
        </span>
        <h2 className="font-display text-[24px] font-semibold leading-7 text-carbon">{title}</h2>
        <div className="max-w-[52ch] text-[16px] leading-6 text-carbon-soft">{body}</div>
        {action && <div className="mt-3 w-full">{action}</div>}
      </div>
    )
  }
  return (
    <div className="ticket border border-dashed border-perf px-5 py-7 sm:px-6">
      <h2 className="text-[18px] font-semibold text-carbon">{title}</h2>
      <div className="mt-2 max-w-[52ch] text-[15px] leading-relaxed text-carbon-soft">{body}</div>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

/** Error with its recovery. Offline gets its own message. With `message` (a translated sentence) the server's
 *  own text is never shown: the technical detail goes to the console only. */
export function ErrorNote({ error, onRetry, message }: { error: unknown; onRetry?: () => void; message?: string }) {
  const { t } = useI18n()
  useEffect(() => { if (message) console.error(error) }, [error, message])
  const offline = error instanceof ApiError && error.status === 0
  const text = offline ? t('offline') : message ?? (error instanceof ApiError && error.message ? error.message : t('genericError'))
  const Icon = offline ? WifiOff : CircleAlert
  const soft = useLook() === 'soft'
  return (
    <div role="alert" className={`flex items-start gap-3 px-4 py-3 ${soft ? 'rounded-photo bg-surface ring-1 ring-inset ring-line-strong' : 'border-[1.5px] border-carbon bg-paper'}`}>
      <Icon className="mt-0.5 size-5 shrink-0 text-carbon" aria-hidden />
      <div className="min-w-0 flex-1 text-[14px] text-carbon">
        <p>{text}</p>
        {onRetry && (
          <Button variant="quiet" className="mt-1 min-h-11 px-0" onClick={onRetry}>
            {t('retry')}
          </Button>
        )}
      </div>
    </div>
  )
}
