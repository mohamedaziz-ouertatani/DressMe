import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { useLook } from './look'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'quiet'
  busy?: boolean
}

/** Square ticket-office buttons: primary is solid ink, secondary an ink outline. In the soft look (step H): the
 *  primary is a 56 px near-black pill, the secondary a surface pill with a line-strong ring, quiet an underlined link. */
export function Button({ variant = 'primary', busy, disabled, children, className = '', ...rest }: ButtonProps) {
  const soft = useLook() === 'soft'
  if (soft) {
    const softLook = {
      primary: 'press min-h-button rounded-pill bg-pill px-6 font-semibold text-pill-text disabled:opacity-50',
      secondary: 'press min-h-button rounded-pill bg-surface px-6 font-semibold text-carbon ring-[1.5px] ring-inset ring-line-strong disabled:opacity-50',
      quiet: 'min-h-11 font-semibold text-ink underline decoration-1 underline-offset-4 hover:decoration-2 disabled:opacity-50',
    }[variant]
    return (
      <button
        {...rest}
        type={rest.type ?? 'button'}
        disabled={disabled || busy}
        aria-busy={busy || undefined}
        className={`inline-flex items-center justify-center gap-2 text-[16px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:cursor-not-allowed ${softLook} ${className}`}
      >
        {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
        {children}
      </button>
    )
  }
  const look = {
    primary: 'bg-ink text-paper hover:bg-ink-soft active:translate-y-px disabled:bg-perf',
    secondary: 'border-[1.5px] border-ink text-ink bg-paper hover:bg-stock active:translate-y-px disabled:border-perf disabled:text-perf',
    quiet: 'text-ink underline decoration-1 underline-offset-4 hover:decoration-2 disabled:text-perf',
  }[variant]
  return (
    <button
      {...rest}
      type={rest.type ?? 'button'}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={`inline-flex min-h-11 items-center justify-center gap-2 px-4 text-[15px] font-medium shadow-[var(--shadow-ticket)] transition-[background-color,border-color,box-shadow,transform,color] duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:cursor-not-allowed disabled:shadow-none ${look} ${className}`}
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
  const soft = useLook() === 'soft'
  if (soft) {             // the soft look: a 44 px pill, selected = near-black fill
    return (
      <button
        type="button"
        aria-pressed={selected}
        onClick={onClick}
        className={`press inline-flex min-h-chip shrink-0 items-center gap-2 rounded-pill px-4 text-[14px] font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
          selected ? 'bg-pill text-pill-text' : 'bg-surface text-carbon ring-1 ring-inset ring-line-strong'
        } ${className}`}
      >
        {children}
      </button>
    )
  }
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={`inline-flex min-h-9 shrink-0 items-center gap-2 border-[1.5px] px-3 text-[13px] shadow-[var(--shadow-ticket)] transition-[background-color,border-color,box-shadow,transform,color] duration-150 hover:shadow-[var(--shadow-lift)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink active:translate-y-px ${
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
  const soft = useLook() === 'soft'
  if (soft) {             // the soft look: a 56 px surface field with a line-strong ring
    return (
      <label className="block">
        <span className="mb-2 block text-[14px] font-medium text-carbon">{label}</span>
        <input
          {...rest}
          aria-invalid={error ? true : undefined}
          className="block min-h-button w-full rounded-photo bg-surface px-4 text-[16px] text-carbon outline-none ring-1 ring-inset ring-line-strong transition-shadow duration-150 placeholder:text-carbon-soft/70 focus:ring-2 focus:ring-ink aria-invalid:ring-2 aria-invalid:ring-leave"
        />
        {(error || hint) && (
          <span className={`mt-1.5 block text-[13px] ${error ? 'font-medium text-leave' : 'text-carbon-soft'}`}>{error || hint}</span>
        )}
      </label>
    )
  }
  return (
    <label className="block">
      <span className="mb-1 block text-[13px] font-medium text-carbon-soft">{label}</span>
      <input
        {...rest}
        aria-invalid={error ? true : undefined}
        className="block min-h-11 w-full border-b-[1.5px] border-perf bg-transparent px-0 text-[16px] text-carbon outline-none transition-[border-color] duration-150 placeholder:text-carbon-soft/70 focus:border-ink focus-visible:outline-none aria-invalid:border-stamp-deep"
      />
      {(error || hint) && (
        <span className={`mt-1 block text-[12px] ${error ? 'text-stamp-deep' : 'text-carbon-soft'}`}>{error || hint}</span>
      )}
    </label>
  )
}
