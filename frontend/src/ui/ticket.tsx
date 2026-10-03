import type { ReactNode } from 'react'
import { serialOf } from './serial'

/** A printed ticket. `stub` is the tear-off end (inline-end side, so it
 *  mirrors in Arabic), separated by a perforation with punched notches. */
export function Ticket({ children, stub, className = '', as: Tag = 'div' }: {
  children: ReactNode
  stub?: ReactNode
  className?: string
  as?: 'div' | 'section' | 'article' | 'li'
}) {
  return (
    <Tag className={`ticket flex ${className}`}>
      <div className="min-w-0 flex-1">{children}</div>
      {stub && <div className="perf-v flex shrink-0 flex-col items-center justify-center px-3">{stub}</div>}
    </Tag>
  )
}

export function Serial({ id, prefix = '№', className = '' }: { id: string; prefix?: string; className?: string }) {
  return (
    <span className={`font-mono text-[11px] tracking-[0.08em] text-ink-soft tabular ${className}`} dir="ltr">
      {prefix} {serialOf(id)}
    </span>
  )
}

/** The second print line in the other script (Arabic under Latin, Latin under Arabic). */
export function SecondLine({ children }: { children: ReactNode }) {
  if (!children) return null
  return (
    <span className="block text-[12px] leading-tight text-ink-soft" lang="mul">
      {children}
    </span>
  )
}
