import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, MessageCircle, Plus, ScanLine, ShoppingBag } from 'lucide-react'
import { api } from '../api/client'
import type { Outfit, TodayOutfits } from '../api/types'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { explainLine } from '../i18n/explain'
import { plural } from '../i18n/plurals'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { CONDITION_KEY, savedPlace, startChip } from '../dressPrefs'
import { PageHeader } from '../shell'
import { IncompleteNote } from '../ui/IncompleteNote'
import { ItemPhoto } from '../ui/ItemPhoto'
import { LookContext } from '../ui/look'
import { Collage } from '../ui/OutfitCard'
import { ErrorNote, Skeleton } from '../ui/states'
import { useLoad } from '../useLoad'

// ---- Home (step H): the landing page after login, in the team prototype's layout. Every section loads on its
// own and has its own loading, empty and error state, so one failing call never blanks the page. No new endpoint:
// today's outfits are the SAME GET /outfits/today call the Dress page makes (same chip, same position, shuffle 0),
// the strip is GET /items (oldest first, so reversed), the gap is GET /insights.

const STRIP = 10                    // newest pieces shown in the strip
type Loaded<T> = { data: T | null; error: unknown; reload: () => void }

function locale(lang: string) {
  return lang === 'ar' ? 'ar-TN-u-nu-latn' : lang
}

export function HomePage() {
  // today's outfits are loaded once here: the header shows their weather, the hero their safe outfit
  const today = useLoad(() => api.outfitsToday({ occasion: startChip(), shuffle: 0, at: savedPlace() ?? undefined }), [])
  return (
    <LookContext.Provider value="soft">
      <div className="look-soft page-enter mx-auto flex w-full max-w-[640px] flex-col gap-7 px-5 pb-6 pt-[max(2rem,env(safe-area-inset-top))] lg:pt-10">
        <Header weather={today.data?.weather ?? null} />
        <TodayPick today={today} />
        <Tiles />
        <Rows />
        <WardrobeStrip />
        <GapCard />
      </div>
    </LookContext.Provider>
  )
}

// ------------------------------------------------------------------ header
function Header({ weather }: { weather: TodayOutfits['weather'] }) {
  const { t, lang } = useI18n()
  const { user } = useAuth()
  const [now] = useState(() => new Date())              // read once: the header does not tick
  const date = new Intl.DateTimeFormat(locale(lang), { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Africa/Tunis' })
    .format(now)
  const sky = weather?.condition ? t('homeWeather', { temp: Math.round(weather.temp_c), condition: t(CONDITION_KEY[weather.condition]).toLowerCase() }) : ''
  const name = user?.name?.trim()
  const initial = (name || user?.email || '?').charAt(0).toUpperCase()
  return (
    <PageHeader
      kicker={sky ? `${date} · ${sky}` : date}
      title={name ? t('homeHello', { name }) : t('homeHelloNoName')}
      aside={
        <Link
          to="/insights#profile"
          aria-label={t('homeProfile')}
          className="press mt-1 grid size-tap shrink-0 place-items-center rounded-pill bg-pill text-[18px] font-semibold text-pill-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          <span aria-hidden>{initial}</span>
        </Link>
      }
    />
  )
}

// ------------------------------------------------------------------ Today's pick
function TodayPick({ today }: { today: Loaded<TodayOutfits> }) {
  const { t, lang } = useI18n()
  if (today.error) return <ErrorNote error={today.error} onRetry={today.reload} message={t('homePickFailed')} />
  if (!today.data) return <Skeleton className="h-[372px] rounded-[2rem]" />
  const outfits = today.data.outfits
  if (outfits.length === 0) return <StartHere />

  const pick: Outfit = outfits.find((o) => o.label === 'safe') ?? outfits[0]
  const lines = pick.explanations ?? []
  const line = lines.find((l) => l.sign === '+' && l.code !== 'fits_context') ?? lines.find((l) => l.code === 'fits_context')
  const meta = [pick.label ? t(`labelChip_${pick.label}`) : '', pick.confidence ? `${t('confidenceLabel')}: ${t(`confidence_${pick.confidence}`)}` : '']
    .filter(Boolean).join(' · ')
  return (
    <Link
      to="/dress"
      aria-label={t('homePickAria')}
      className="press flex flex-col gap-4 rounded-[2rem] bg-tint-sage p-5 text-carbon focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
    >
      <span className="flex items-center justify-between gap-3">
        <span className="inline-flex h-8 items-center rounded-pill bg-surface px-3 text-[14px] font-semibold">{t('homePick')}</span>
        {meta && <span className="text-[12px] font-medium leading-4 text-carbon-soft">{meta}</span>}
      </span>
      <Collage items={pick.items} />
      <IncompleteNote outfit={pick} className="self-start" />
      <span className="flex items-end justify-between gap-3">
        <span className="flex min-w-0 flex-col gap-1">
          <span className="font-display text-[24px] font-semibold leading-7">{t('homePickTitle')}</span>
          {line && <span className="text-[14px] leading-5 text-carbon-soft">{explainLine(line, lang)}</span>}
        </span>
        <span aria-hidden className="grid size-tap shrink-0 place-items-center rounded-pill bg-pill text-pill-text">
          <ArrowRight className="mirror-rtl size-6" strokeWidth={1.75} />
        </span>
      </span>
    </Link>
  )
}

function StartHere() {
  const { t } = useI18n()
  return (
    <section className="flex flex-col items-start gap-2 rounded-[2rem] bg-tint-sage p-5">
      <p className="text-[12px] font-medium leading-4 text-carbon-soft">{t('homeStartKicker')}</p>
      <h2 className="font-display text-[24px] font-semibold leading-7 text-carbon">{t('homeStartTitle')}</h2>
      <p className="text-[16px] leading-6 text-carbon-soft">{t('homeStartBody')}</p>
      <PillLink to="/wardrobe" className="mt-2">{t('homeAddTitle')}</PillLink>
    </section>
  )
}

function PillLink({ to, children, tone = 'ink', className = '' }: { to: string; children: ReactNode; tone?: 'ink' | 'surface'; className?: string }) {
  return (
    <Link
      to={to}
      className={`press inline-flex min-h-tap items-center justify-center rounded-pill px-5 text-[14px] font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
        tone === 'ink' ? 'bg-pill text-pill-text' : 'bg-surface text-carbon'
      } ${className}`}
    >
      {children}
    </Link>
  )
}

// ------------------------------------------------------------------ two tiles and two rows
function Tiles() {
  const { t } = useI18n()
  const tile = 'press flex h-[156px] flex-col items-start justify-between rounded-card p-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink'
  return (
    <div className="grid grid-cols-2 gap-3">
      <Link to="/scan" className={`${tile} bg-pill text-pill-text`}>
        <span aria-hidden className="grid size-11 place-items-center rounded-pill bg-white/15"><ScanLine className="size-6" strokeWidth={1.75} /></span>
        <span className="flex flex-col gap-0.5">
          <span className="text-[18px] font-semibold leading-[22px]">{t('scanTitle')}</span>
          <span className="text-[14px] leading-5 text-white/80">{t('homeBuySub')}</span>
        </span>
      </Link>
      <Link to="/wardrobe" className={`${tile} bg-surface text-carbon`}>
        <span aria-hidden className="grid size-11 place-items-center rounded-pill bg-sunken"><Plus className="size-6" strokeWidth={1.75} /></span>
        <span className="flex flex-col gap-0.5">
          <span className="text-[18px] font-semibold leading-[22px]">{t('homeAddTitle')}</span>
          <span className="text-[14px] leading-5 text-carbon-soft">{t('homeAddSub')}</span>
        </span>
      </Link>
    </div>
  )
}

function Rows() {
  const { t } = useI18n()
  const row = (to: string, tone: string, disc: string, Icon: typeof ShoppingBag, title: string, sub: string) => (
    <Link
      to={to}
      className={`press flex items-center gap-3.5 rounded-card py-3.5 pe-3.5 ps-5 text-carbon focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${tone}`}
    >
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-[18px] font-semibold leading-6">{title}</span>
        <span className="text-[14px] leading-5 text-carbon-soft">{sub}</span>
      </span>
      <span aria-hidden className={`grid size-11 shrink-0 place-items-center rounded-pill ${disc}`}><Icon className="size-[22px]" strokeWidth={1.75} /></span>
    </Link>
  )
  return (
    <div className="-mt-4 flex flex-col gap-3">
      {row('/chat', 'bg-tint-lilac', 'bg-surface', MessageCircle, t('homeStylistTitle'), t('homeStylistSub'))}
      {row('/shop', 'bg-surface', 'bg-sunken', ShoppingBag, t('navShop'), t('homeShopsSub'))}
    </div>
  )
}

// ------------------------------------------------------------------ the wardrobe strip
function WardrobeStrip() {
  const { t, lang } = useI18n()
  const items = useLoad(() => api.items(), [])
  if (items.error) return <ErrorNote error={items.error} onRetry={items.reload} message={t('dressWardrobeFailed')} />
  if (!items.data) return <Skeleton className="h-[156px] rounded-card" />
  if (items.data.length === 0) return null                 // the "Start here" card already says what to do
  const newest = [...items.data].reverse().slice(0, STRIP)  // GET /items is oldest first
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-[18px] font-semibold leading-6 text-carbon">
          {t('homeWardrobe')} <span className="font-medium text-carbon-soft">· {plural('pieces', items.data.length, lang)}</span>
        </h2>
        <Link to="/wardrobe" className="inline-flex min-h-11 items-center ps-3 text-[14px] font-semibold text-carbon underline decoration-1 underline-offset-4">
          {t('homeSeeAll')}
        </Link>
      </div>
      <ul className="no-scrollbar -mx-5 flex gap-2 overflow-x-auto px-5">
        {newest.map((it) => {
          const name = vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)
          return (
            <li key={it.id} className="shrink-0">
              <Link
                to={`/wardrobe/${it.id}`}
                aria-label={name}
                className="press grid h-[116px] w-[92px] place-items-center overflow-hidden rounded-photo bg-surface p-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
              >
                <ItemPhoto src={it.image_url} alt="" size={68} />
              </Link>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// ------------------------------------------------------------------ the gap card
function GapCard() {
  const { t, lang } = useI18n()
  const insights = useLoad(() => api.insights(), [])
  if (insights.error) return <ErrorNote error={insights.error} onRetry={insights.reload} message={t('homeGapFailed')} />
  if (!insights.data) return <Skeleton className="h-40 rounded-card" />
  const missing = insights.data.missing[0]
  if (!missing || insights.data.total === 0) return null   // nothing missing; an empty wardrobe has "Start here"
  const title = missing === 'main'
    ? t('homeGapMain')
    : t('homeGapTitle', { category: vocab(CATEGORY_LABELS, missing, lang).toLowerCase() })
  return (
    <section className="flex flex-col items-start gap-1.5 rounded-card bg-tint-peach p-5">
      <p className="text-[12px] font-medium leading-4 text-carbon-soft">{t('homeGapKicker')}</p>
      <h2 className="font-display text-[24px] font-semibold leading-7 text-carbon">{title}</h2>
      <p className="text-[16px] leading-6 text-carbon-soft">{t(`insightsMissing_${missing}`)}</p>
      <PillLink to="/scan" tone="surface" className="mt-2">{t('homeGapCheck')}</PillLink>
    </section>
  )
}
