import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'quiet'
  busy?: boolean
}

/** Square ticket-office buttons: primary is solid ink, secondary an ink outline. */
export function Button({ variant = 'primary', busy, disabled, children, className = '', ...rest }: ButtonProps) {
  const look = {
    primary: 'bg-ink text-paper hover:bg-ink-soft active:translate-y-px disabled:bg-perf',
    secondary: 'border-[1.5px] border-ink text-ink bg-paper hover:bg-stock active:translate-y-px disabled:border-perf disabled:text-perf',
    quiet: 'text-ink underline decoration-1 underline-offset-4 hover:decoration-2 disabled:text-perf',
  }[variant]
  return (
    <button
      {...rest}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={`inline-flex min-h-11 items-center justify-center gap-2 px-4 text-[15px] font-medium transition-colors duration-150 disabled:cursor-not-allowed ${look} ${className}`}
    >
      {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

/** A fare-zone chip. Selected = the zone is validated: solid ink card with a
 *  hole punched through it (the light ground shows through). Unselected zones
 *  are plain card. */
export function Chip({ selected, children, onClick, className = '' }: {
  selected: boolean
  children: ReactNode
  onClick: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={`inline-flex min-h-9 shrink-0 items-center gap-2 border-[1.5px] px-3 text-[13px] transition-colors duration-150 ${
        selected ? 'border-ink bg-ink font-semibold text-paper' : 'border-perf bg-paper font-medium text-carbon hover:border-ink'
      } ${className}`}
    >
      {selected && (
        <span aria-hidden className="size-2.5 shrink-0 rounded-full bg-stock shadow-[inset_0_1px_1.5px_rgb(20_22_26/0.6)]" />
      )}
      {children}
    </button>
  )
}

export function Swatch({ hex, size = 14 }: { hex: string; size?: number }) {
  return (
    <span
      aria-hidden
      className="inline-block shrink-0 rounded-full border border-carbon/25"
      style={{ width: size, height: size, background: hex }}
    />
  )
}

export function TextField({ label, hint, error, ...rest }: InputHTMLAttributes<HTMLInputElement> & {
  label: string
  hint?: string
  error?: string
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[13px] font-medium text-carbon-soft">{label}</span>
      <input
        {...rest}
        aria-invalid={error ? true : undefined}
        className="block min-h-11 w-full border-b-[1.5px] border-perf bg-transparent px-0 text-[16px] text-carbon outline-none transition-colors duration-150 placeholder:text-carbon-soft/70 focus:border-ink focus-visible:outline-none aria-invalid:border-stamp-deep"
      />
      {(error || hint) && (
        <span className={`mt-1 block text-[12px] ${error ? 'text-stamp-deep' : 'text-carbon-soft'}`}>{error || hint}</span>
      )}
    </label>
  )
}
