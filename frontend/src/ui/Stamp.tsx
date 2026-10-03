import { useId } from 'react'

/** Round rubber validation stamp in magenta: the only place that colour lives.
 *  `big` is the centre word or number; `ring` runs around the edge.
 *  With `land`, it presses onto the ticket once (180 ms press, then settles). */
export function Stamp({ big, ring, size = 112, angle = -9, land = false, label, tone = 'stamp' }: {
  big: string
  ring: string
  size?: number
  angle?: number
  land?: boolean
  label: string                // empty = decorative, hidden from screen readers
  tone?: 'stamp' | 'ink'       // magenta only for the active verdict / today's score
}) {
  const uid = useId().replace(/:/g, '')
  const long = big.length > 4
  return (
    <svg
      role={label ? 'img' : undefined}
      aria-label={label || undefined}
      aria-hidden={label ? undefined : true}
      width={size}
      height={size}
      viewBox="0 0 120 120"
      className={`shrink-0 ${tone === 'ink' ? 'text-ink' : 'text-stamp'} ${land ? 'stamp-land' : ''}`}
      style={{ transform: `rotate(${angle}deg)`, ['--stamp-angle' as string]: `${angle}deg` }}
    >
      <defs>
        {/* rubber ink: uneven edges and pressure */}
        <filter id={`ink-${uid}`} x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="2.2" result="rough" />
          <feComponentTransfer in="noise" result="mask">
            <feFuncA type="table" tableValues="0.45 1 1 1" />
          </feComponentTransfer>
          <feComposite in="rough" in2="mask" operator="in" />
        </filter>
        <path id={`ring-${uid}`} d="M60,60 m-41,0 a41,41 0 1,1 82,0 a41,41 0 1,1 -82,0" />
      </defs>
      <g filter={`url(#ink-${uid})`} fill="currentColor" stroke="currentColor">
        <circle cx="60" cy="60" r="56" fill="none" strokeWidth="3.5" />
        <circle cx="60" cy="60" r="48" fill="none" strokeWidth="1.2" />
        <circle cx="60" cy="60" r="30" fill="none" strokeWidth="1.2" />
        <text fontSize="9.5" fontWeight="600" letterSpacing="2.2" stroke="none" fontFamily="var(--font-sans)" direction="ltr" unicodeBidi="isolate">
          <textPath href={`#ring-${uid}`} startOffset="0">{ring}</textPath>
        </text>
        <text
          x="60" y="60" textAnchor="middle" dominantBaseline="central" stroke="none"
          fontFamily="var(--font-sans)" fontWeight="700"
          fontSize={long ? 14 : big.length > 3 ? 18 : 24}
          style={{ textTransform: 'uppercase' }}
        >
          {big}
        </text>
      </g>
    </svg>
  )
}
