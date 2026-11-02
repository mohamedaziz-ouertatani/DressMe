import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'

// The pieces of the Dress look: pill buttons, pill chips, a two-way switch. Their colours, radii and
// spacing come from the design tokens in index.css (bg-pill, rounded-pill ...), nothing is hard-coded here.

/** A pill button: solid black (primary) or outlined. */
export function PillButton({ variant = 'solid', busy, disabled, children, className = '', ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'solid' | 'outline'; busy?: boolean }) {
  const look = variant === 'solid'
    ? 'bg-pill text-pill-text border-[1.5px] border-pill disabled:opacity-50'
    : 'bg-surface text-pill border-[1.5px] border-line-strong disabled:opacity-50'
  return (
    <button
      {...rest}
      type={rest.type ?? 'button'}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={`press inline-flex min-h-button items-center justify-center gap-2 rounded-pill px-6 text-[16px] font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pill disabled:cursor-not-allowed ${look} ${className}`}
    >
      {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

/** An outlined pill chip; the selected one is filled black. */
export function PillChip({ selected, children, onClick, expanded }: {
  selected: boolean
  children: ReactNode
  onClick: () => void
  expanded?: boolean           // for a chip that opens more chips ("More")
}) {
  return (
    <button
      type="button"
      aria-pressed={expanded === undefined ? selected : undefined}
      aria-expanded={expanded}
      onClick={onClick}
      className={`press inline-flex min-h-chip items-center gap-1.5 rounded-pill border-[1.5px] px-4 text-[14px] font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pill ${
        selected ? 'border-pill bg-pill text-pill-text' : 'border-line-strong bg-surface text-pill'
      }`}
    >
      {children}
    </button>
  )
}

/** A two-way switch ("For today" | "Build"). */
export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
  label: string
}) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex w-full rounded-pill bg-surface p-1 sm:w-auto">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          onClick={() => onChange(o.value)}
          className={`min-h-11 flex-1 rounded-pill px-5 text-[14px] font-semibold transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pill sm:flex-none ${
            o.value === value ? 'bg-pill text-pill-text' : 'text-pill'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
