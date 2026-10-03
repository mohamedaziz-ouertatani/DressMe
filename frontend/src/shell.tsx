import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { CalendarDays, LayoutGrid, LogOut, MessageCircle, ScanLine, Shapes, ShieldCheck, UserRound } from 'lucide-react'
import { useAuth } from './auth'
import { useI18n } from './i18n'
import type { StringKey } from './i18n/strings'

const NAV: { to: string; key: StringKey; icon: typeof CalendarDays }[] = [
  { to: '/', key: 'navToday', icon: CalendarDays },
  { to: '/wardrobe', key: 'navWardrobe', icon: LayoutGrid },
  { to: '/scan', key: 'navScan', icon: ScanLine },
  { to: '/build', key: 'navBuild', icon: Shapes },
  { to: '/chat', key: 'navChat', icon: MessageCircle },
]

/** The wordmark: a small perforated tag before the name. */
export function Wordmark({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 text-ink ${className}`} dir="ltr">
      <svg width="26" height="18" viewBox="0 0 26 18" aria-hidden>
        <rect x="1" y="1" width="24" height="16" fill="none" stroke="currentColor" strokeWidth="2" />
        <line x1="17" y1="2" x2="17" y2="16" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2 2" />
        <circle cx="9" cy="9" r="3.4" fill="none" stroke="var(--color-stamp)" strokeWidth="2" />
      </svg>
      <span className="text-[19px] font-semibold tracking-[-0.01em]">DressMe</span>
    </span>
  )
}

function todaySerial(): string {
  const d = new Date()
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`
}

/** Page frame: a header ticket (title on the face; date and serial on the
 *  perforated stub, like a validated fare), then the content. */
export function Page({ title, children, aside, serial }: {
  title: string
  children: ReactNode
  aside?: ReactNode
  serial?: string
}) {
  return (
    <div className="mx-auto w-full max-w-[1080px] px-4 pb-32 pt-3 lg:px-10 lg:pb-16 lg:pt-10">
      <header className="ticket mb-5 flex">
        <h1 className="min-w-0 flex-1 self-center px-3 py-3 text-[22px] font-semibold leading-tight tracking-[-0.015em] text-carbon min-[420px]:px-4 min-[420px]:text-[24px] lg:px-6 lg:py-4 lg:text-[32px]">
          {title}
        </h1>
        <div className="perf-v flex shrink-0 flex-col items-end justify-center gap-0.5 px-3 font-mono min-[420px]:px-4 text-[12px] leading-tight text-ink-soft tabular" dir="ltr">
          <span>{todaySerial()}</span>
          {serial && <span>№ {serial}</span>}
        </div>
      </header>
      {aside ? (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0">{children}</div>
          <aside className="min-w-0">{aside}</aside>
        </div>
      ) : (
        children
      )}
    </div>
  )
}

export function AppShell() {
  const { t } = useI18n()
  const { user, logout } = useAuth()

  return (
    <div className="min-h-dvh lg:flex">
      {/* desktop rail: the nav as a column of ticket stubs */}
      <nav aria-label="Main" className="sticky top-0 hidden h-dvh w-[236px] shrink-0 flex-col border-e border-perf/60 bg-stock-deep/60 px-4 py-6 lg:flex">
        <Wordmark className="mb-8 px-2" />
        <ul className="flex flex-col gap-2">
          {NAV.map(({ to, key, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `ticket flex min-h-12 transition-shadow duration-150 hover:[box-shadow:var(--shadow-lift)] ${
                    isActive ? 'text-ink' : 'bg-paper/70 text-carbon-soft hover:text-ink'
                  }`}
              >
                {({ isActive }) => (
                  <>
                    <span className={`flex flex-1 items-center gap-3 px-3 text-[15px] ${isActive ? 'font-semibold' : 'font-medium'}`}>
                      <Icon className="size-5" aria-hidden />
                      {t(key)}
                    </span>
                    {/* the tear-off stub, punched when this is the current page */}
                    <span className="perf-v flex w-11 shrink-0 flex-col items-center justify-center gap-1">
                      {isActive && <span aria-hidden className="size-2.5 rounded-full bg-stamp" />}
                    </span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="mt-auto flex flex-col gap-1.5 border-t border-perf/60 pt-4">
          {user?.role === 'admin' && (
            <NavLink to="/admin" className="flex min-h-10 items-center gap-3 px-3 text-[14px] text-carbon-soft hover:text-ink">
              <ShieldCheck className="size-5" aria-hidden /> {t('navAdmin')}
            </NavLink>
          )}
          <NavLink to="/me" className="flex min-h-10 items-center gap-3 px-3 text-[14px] text-carbon-soft hover:text-ink">
            <UserRound className="size-5" aria-hidden /> {user?.name ?? t('navProfile')}
          </NavLink>
          <button onClick={logout} className="flex min-h-10 items-center gap-3 px-3 text-start text-[14px] text-carbon-soft hover:text-ink">
            <LogOut className="size-5 mirror-rtl" aria-hidden /> {t('logout')}
          </button>
        </div>
      </nav>

      <div className="min-w-0 flex-1">
        {/* phone header */}
        <div className="flex items-center justify-between px-4 pt-[max(12px,env(safe-area-inset-top))] lg:hidden">
          <Wordmark />
          <div className="flex items-center gap-1">
            {user?.role === 'admin' && (
              <NavLink to="/admin" aria-label={t('navAdmin')} className="grid size-11 place-items-center text-ink">
                <ShieldCheck className="size-5" aria-hidden />
              </NavLink>
            )}
            <NavLink to="/me" aria-label={t('navProfile')} className="grid size-11 place-items-center text-ink">
              <UserRound className="size-5" aria-hidden />
            </NavLink>
          </div>
        </div>
        <main>
          <Outlet />
        </main>
      </div>

      {/* phone tab bar: stubs torn along a perforation; Scan is the big centre slot */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-20 border-t-[1.5px] border-dashed border-perf bg-paper pb-[env(safe-area-inset-bottom)] lg:hidden">
        <ul className="mx-auto grid max-w-md grid-cols-5 items-end">
          {NAV.map(({ to, key, icon: Icon }) => {
            const scan = to === '/scan'
            return (
              <li key={to} className="flex justify-center">
                <NavLink
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    scan
                      ? `-mt-6 flex size-[68px] flex-col items-center justify-center gap-0.5 text-[11px] font-semibold shadow-[var(--shadow-lift)] ${isActive ? 'bg-stamp text-paper' : 'bg-ink text-paper'}`
                      : `relative flex min-h-14 w-full flex-col items-center justify-center gap-0.5 text-[11px] font-medium ${isActive ? 'text-ink' : 'text-carbon-soft'}`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && !scan && <span aria-hidden className="absolute top-1.5 size-2 rounded-full bg-stamp" />}
                      <Icon className={scan ? 'size-7' : 'size-5'} aria-hidden />
                      {t(key)}
                    </>
                  )}
                </NavLink>
              </li>
            )
          })}
        </ul>
      </nav>
    </div>
  )
}
