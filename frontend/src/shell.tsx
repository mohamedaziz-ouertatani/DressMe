import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { House, LayoutGrid, LogOut, MessageCircle, ScanLine, Shirt, ShieldCheck, ShoppingBag, UserRound } from 'lucide-react'
import { useAuth } from './auth'
import { useI18n } from './i18n'
import type { StringKey } from './i18n/strings'
import { LookContext } from './ui/look'

// The desktop rail lists every item, Home first. The phone tab bar (the prototype's floating pill) has five:
// Home, Dress, Buy?, Wardrobe, Assistant; Shops is reached from Home and the rail.
// short = a shorter label for the phone tab bar, where a long one does not fit.
type NavItem = { to: string; key: StringKey; icon: typeof Shirt; short?: StringKey }
const NAV: NavItem[] = [
  { to: '/', key: 'navHome', icon: House },
  { to: '/dress', key: 'navDress', icon: Shirt },
  { to: '/wardrobe', key: 'navWardrobe', icon: LayoutGrid },
  { to: '/scan', key: 'navScan', short: 'navScanShort', icon: ScanLine },
  { to: '/shop', key: 'navShop', icon: ShoppingBag },
  { to: '/chat', key: 'navChat', icon: MessageCircle },
]
const PHONE_NAV = ['/', '/dress', '/scan', '/wardrobe', '/chat'].map((to) => NAV.find((n) => n.to === to)!)

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
export function Page({ title, children, aside, serial, look = 'ticket', kicker }: {
  title: string
  children: ReactNode
  aside?: ReactNode
  serial?: string
  look?: 'ticket' | 'soft'         // soft = the team prototype's look (step H): kicker + display headline, flat cards
  kicker?: ReactNode               // soft look only: the short line above the headline
}) {
  if (look === 'soft') {
    return (
      <LookContext.Provider value="soft">
        <div className="look-soft page-enter mx-auto w-full max-w-[1080px] px-5 pb-6 pt-4 lg:px-10 lg:pb-16 lg:pt-10">
          <PageHeader title={title} kicker={kicker} />
          {aside ? (
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
              <div className="min-w-0">{children}</div>
              <aside className="min-w-0">{aside}</aside>
            </div>
          ) : (
            children
          )}
        </div>
      </LookContext.Provider>
    )
  }
  return (
    <div className="page-enter mx-auto w-full max-w-[1080px] px-4 pb-6 pt-3 lg:px-10 lg:pb-16 lg:pt-10">
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

/** The soft look's page header: a short kicker line, then the one display headline of the screen. */
export function PageHeader({ title, kicker, aside }: { title: ReactNode; kicker?: ReactNode; aside?: ReactNode }) {
  return (
    <header className="mb-6 flex items-start justify-between gap-4">
      <div className="flex min-w-0 flex-col gap-1.5">
        {kicker && <p className="text-[14px] font-medium leading-5 text-carbon-soft">{kicker}</p>}
        <h1 className="font-display text-[32px] font-bold leading-9 text-carbon lg:text-[40px] lg:leading-[42px]">{title}</h1>
      </div>
      {aside}
    </header>
  )
}

/** Keeps the CSS variable --tabbar-h equal to the room the phone tab bar takes at the bottom of the screen: the
 *  floating bar's height PLUS its distance from the bottom edge (which includes env(safe-area-inset-bottom)), so
 *  `pb-[var(--tabbar-h)]` clears it. 0 when the bar is hidden (desktop). The content reads the variable instead of
 *  a fixed number, so it follows the bar if its size or offset ever changes. */
function useTabBarHeight() {
  const root = useRef<HTMLDivElement>(null)
  const bar = useRef<HTMLElement>(null)
  useEffect(() => {
    const el = bar.current
    if (!root.current || !el) return
    const update = () => {
      const box = el.getBoundingClientRect()
      const room = box.height ? Math.ceil(window.innerHeight - box.top) : 0
      root.current?.style.setProperty('--tabbar-h', `${room}px`)
    }
    update()
    const watcher = new ResizeObserver(update)
    watcher.observe(el, { box: 'border-box' })
    window.addEventListener('resize', update)        // the offset from the bottom changes with the viewport
    return () => { watcher.disconnect(); window.removeEventListener('resize', update) }
  }, [])
  return { root, bar }
}

export function AppShell() {
  const { t } = useI18n()
  const { user, logout } = useAuth()
  const { root, bar } = useTabBarHeight()
  const { pathname } = useLocation()
  const home = pathname === '/'                         // Home has its own header (greeting and avatar)
  const current = (to: string) => (to === '/' ? pathname === '/' : pathname === to || pathname.startsWith(`${to}/`))

  return (
    <div ref={root} className="min-h-dvh lg:flex">
      <a href="#main-content" className="sr-only fixed start-3 top-3 z-50 bg-ink px-4 py-2 text-sm text-paper focus:not-sr-only">
        Skip to content
      </a>
      {/* desktop rail: the nav as a column of ticket stubs */}
      <nav aria-label="Main" className="sticky top-0 hidden h-dvh w-[264px] shrink-0 flex-col border-e border-perf/60 bg-stock-deep/60 px-4 py-6 lg:flex">
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
        <div className={`items-center justify-between px-4 pt-[max(12px,env(safe-area-inset-top))] lg:hidden ${home ? 'hidden' : 'flex'}`}>
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
        {/* below lg the floating tab bar covers the bottom: pad by the room it takes (its height, its offset and the
            safe-area inset) plus a little air, so the last element scrolls fully clear */}
        <main id="main-content" tabIndex={-1} className="pb-[calc(var(--tabbar-h,88px)+1rem)] lg:pb-0">
          <Outlet />
        </main>
      </div>

      {/* phone tab bar: the prototype's floating pill. The current tab is a near-black pill with its icon and label;
          the others show the icon only (their name is the aria-label). */}
      <nav
        ref={bar}
        aria-label="Main"
        className="look-soft fixed inset-x-5 bottom-[calc(1.5rem+env(safe-area-inset-bottom))] z-20 mx-auto flex h-tabbar max-w-[440px] items-center justify-between rounded-pill bg-surface p-2 shadow-[var(--shadow-float)] lg:hidden"
      >
        {PHONE_NAV.map(({ to, key, short, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            aria-label={current(to) ? undefined : t(key)}
            className={({ isActive }) =>
              `press flex h-tap min-w-tap shrink-0 items-center justify-center gap-2 rounded-pill text-[14px] font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
                isActive ? 'bg-pill px-4 text-pill-text' : 'text-carbon-soft'
              }`}
          >
            {({ isActive }) => (
              <>
                <Icon className="size-6" strokeWidth={1.75} aria-hidden />
                {isActive && <span className="whitespace-nowrap">{t(short ?? key)}</span>}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
