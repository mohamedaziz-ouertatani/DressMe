import type { ReactNode } from 'react'
import { CircleAlert, WifiOff } from 'lucide-react'
import { ApiError } from '../api/client'
import { useI18n } from '../i18n'
import { Button } from './controls'

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`skeleton ${className}`} />
}

/** An empty state that teaches what to do next. */
export function Empty({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="ticket border border-dashed border-perf px-5 py-7 sm:px-6">
      <h2 className="text-[18px] font-semibold text-carbon">{title}</h2>
      <p className="mt-2 max-w-[52ch] text-[15px] leading-relaxed text-carbon-soft">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

/** Error with its recovery. Offline gets its own message. */
export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n()
  const offline = error instanceof ApiError && error.status === 0
  const text = offline ? t('offline') : error instanceof ApiError && error.message ? error.message : t('genericError')
  const Icon = offline ? WifiOff : CircleAlert
  return (
    <div role="alert" className="flex items-start gap-3 border-[1.5px] border-carbon bg-paper px-4 py-3">
      <Icon className="mt-0.5 size-5 shrink-0 text-carbon" aria-hidden />
      <div className="min-w-0 flex-1 text-[14px] text-carbon">
        <p>{text}</p>
        {onRetry && (
          <Button variant="quiet" className="mt-1 min-h-8 px-0" onClick={onRetry}>
            {t('retry')}
          </Button>
        )}
      </div>
    </div>
  )
}
