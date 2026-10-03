// Charts for the admin dashboard: plain SVG, one ink hue per chart (magnitude
// only, so no categorical palette is needed). Bar ink #3A4796 passes the
// dataviz validator on the ticket surface (lightness band + contrast).
// Every chart has a hover/focus tooltip and a table view.
import { useState } from 'react'
import { ChevronRight } from 'lucide-react'

const BAR = 'var(--color-ink-soft)'
const BAR_HOVER = 'var(--color-ink)'

/** A column from the baseline up to y, with its top corners rounded (4px). */
function roundedTop(x: number, y: number, w: number, base: number): string {
  const r = Math.min(4, w / 2, base - y)
  return `M${x},${base} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${base} Z`
}

/** Daily counts for one event type: thin columns, 4px rounded tops anchored
 *  to the baseline, 2px gaps, one recessive max line. */
export function DayBars({ title, days, values, details, empty }: {
  title: string
  days: string[]
  values: number[]
  details?: string[]          // extra tooltip line per day (e.g. the breakdown)
  empty: string               // shown instead of an empty chart
}) {
  const [hover, setHover] = useState<number | null>(null)
  const W = 640, H = 120, top = 14, bottom = 16
  const max = Math.max(1, ...values)
  const step = W / Math.max(values.length, 1)
  const barW = Math.max(2, step - 2)
  const total = values.reduce((a, b) => a + b, 0)
  return (
    <figure className="ticket m-0 px-3 pb-2 pt-3">
      <figcaption className="flex items-baseline justify-between">
        <span className="text-[14px] font-semibold text-carbon">{title}</span>
        <span className="font-mono text-[12px] text-carbon-soft tabular">{total}</span>
      </figcaption>
      {total === 0 ? <p className="py-6 text-[13px] text-carbon-soft">{empty}</p> : (
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="mt-1 block h-[120px] w-full" role="img"
          aria-label={`${title}: ${total} in ${values.length} days, at most ${max} per day`}>
          <line x1="0" x2={W} y1={top} y2={top} stroke="var(--color-perf)" strokeOpacity="0.5" strokeWidth="1" />
          <text x={W} y={top - 4} textAnchor="end" fontSize="9" fill="var(--color-carbon-soft)" fontFamily="var(--font-mono)">{max}</text>
          {values.map((v, i) => {
            const h = (v / max) * (H - top - bottom)
            const x = i * step + 1
            const y = H - bottom - h
            return (
              <g key={days[i]} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(i)} onBlur={() => setHover(null)} tabIndex={0}
                aria-label={`${days[i]}: ${v}`}>
                {/* hit target: the whole column, bigger than the mark */}
                <rect x={i * step} y={0} width={step} height={H - bottom} fill="transparent" />
                {v > 0 && <path d={roundedTop(x, y, barW, H - bottom)} fill={hover === i ? BAR_HOVER : BAR} />}
                {v === 0 && <rect x={x} y={H - bottom - 1} width={barW} height={1} fill="var(--color-perf)" />}
              </g>
            )
          })}
          <line x1="0" x2={W} y1={H - bottom} y2={H - bottom} stroke="var(--color-carbon)" strokeWidth="1" />
          <text x="0" y={H - 3} fontSize="9" fill="var(--color-carbon-soft)" fontFamily="var(--font-mono)">{days[0]?.slice(5)}</text>
          <text x={W} y={H - 3} textAnchor="end" fontSize="9" fill="var(--color-carbon-soft)" fontFamily="var(--font-mono)">{days[days.length - 1]?.slice(5)}</text>
        </svg>
        {hover !== null && (
          <div role="tooltip" className="pointer-events-none absolute top-0 bg-carbon px-2 py-1 font-mono text-[11px] text-paper tabular"
            style={{ left: `${Math.min(80, (hover / Math.max(values.length - 1, 1)) * 100)}%` }}>
            {days[hover]} · {values[hover]}
            {details?.[hover] && <span className="block text-paper/80">{details[hover]}</span>}
          </div>
        )}
      </div>
      )}
    </figure>
  )
}

/** Labelled horizontal bars (a value per row), value printed at the bar end. */
export function RowBars({ rows, format = (v) => String(v), max }: {
  rows: { label: string; value: number; note?: string }[]
  format?: (v: number) => string
  max?: number
}) {
  const [hover, setHover] = useState<number | null>(null)
  const top = max ?? Math.max(1e-9, ...rows.map((r) => r.value))
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((r, i) => (
        <li key={r.label} className="grid grid-cols-[112px_minmax(0,1fr)_64px] items-center gap-3"
          onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
          <span className="truncate text-[13px] text-carbon">{r.label}</span>
          <span className="relative h-5 bg-stock-deep/60" title={r.note}>
            <span
              className="absolute inset-y-0 start-0 rounded-e-[4px] transition-colors duration-150"
              style={{ width: `${Math.max(0, Math.min(1, r.value / top)) * 100}%`, background: hover === i ? BAR_HOVER : BAR }}
            />
          </span>
          <span className="text-end font-mono text-[12px] text-carbon tabular">{format(r.value)}</span>
        </li>
      ))}
    </ul>
  )
}

/** "Show as a table" view under a chart (accessibility and exact values). */
export function TableView({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <details className="mt-3 text-[13px]">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-ink [&::-webkit-details-marker]:hidden"><ChevronRight className="size-4 transition-transform duration-150 [details[open]_&]:rotate-90" aria-hidden /><span className="underline decoration-1 underline-offset-4">Show as a table</span></summary>
      <div className="mt-2 max-h-64 overflow-auto">
        <table className="w-full border-collapse text-start">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>{head.map((h) => <th key={h} className="border-b border-perf px-2 py-1 text-start font-medium text-carbon-soft">{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>{r.map((c, j) => <td key={j} className="border-b border-perf/40 px-2 py-1 font-mono tabular">{c}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
