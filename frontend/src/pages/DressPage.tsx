import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronDown, LocateFixed, RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import type { BuildResult, Item, OccasionChip, WeatherCondition } from '../api/types'
import { useI18n } from '../i18n'
import type { StringKey } from '../i18n/strings'
import { CATEGORY_LABELS, SEASON_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { ItemPhoto } from '../ui/ItemPhoto'
import { OutfitCard } from '../ui/OutfitCard'
import { PillButton, PillChip, Segmented } from '../ui/dress'
import { Empty, ErrorNote, Skeleton } from '../ui/states'
import { useLoad } from '../useLoad'

// ---- the Dress page: "For today" (three outfits) and "Build" (outfits around the pieces you pick)

const CHIP_KEY = 'dressme.dressChip'              // the last chip used
const PLACE_KEY = 'dressme.weatherPlace'          // the position the user shared, rounded to ~10 km
const KNOWN_CHIPS = ['everyday', 'work', 'university', 'outing', 'eid', 'wedding', 'beach']
// used until /outfits/occasions answers (and if it fails): the same list as mappings/dress_occasions.csv
const FALLBACK_CHIPS: OccasionChip[] = [
  { chip: 'everyday', main: true }, { chip: 'work', main: true }, { chip: 'university', main: true }, { chip: 'outing', main: true },
  { chip: 'eid', main: false }, { chip: 'wedding', main: false }, { chip: 'beach', main: false },
]
const CONDITION_KEY: Record<WeatherCondition, StringKey> = {
  clear: 'weatherClear', cloudy: 'weatherCloudy', fog: 'weatherFog', rain: 'weatherRainy', snow: 'weatherSnow', storm: 'weatherStorm',
}
type Place = { lat: number; lon: number }

function remembered(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }       // private mode: nothing is remembered
}
function remember(key: string, value: string) {
  try { localStorage.setItem(key, value) } catch { /* the next visit starts from the default */ }
}
function savedPlace(): Place | null {
  try {
    const place = JSON.parse(remembered(PLACE_KEY) ?? 'null')
    return typeof place?.lat === 'number' && typeof place?.lon === 'number' ? place : null
  } catch {
    return null
  }
}

export function DressPage({ mode }: { mode: 'today' | 'build' }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  return (
    <Page title={t('navDress')}>
      <Segmented
        label={t('navDress')}
        value={mode}
        onChange={(m) => navigate(m === 'today' ? '/dress' : '/dress/build')}
        options={[{ value: 'today', label: t('dressModeToday') }, { value: 'build', label: t('navBuild') }]}
      />
      <div className="mt-stack">{mode === 'today' ? <TodayMode /> : <BuildMode />}</div>
    </Page>
  )
}

function AddLink() {
  const { t } = useI18n()
  return (
    <Link to="/wardrobe" className="inline-flex min-h-11 items-center rounded-pill border-[1.5px] border-pill bg-pill px-5 text-[15px] font-semibold text-pill-text">
      {t('addPieces')}
    </Link>
  )
}

function CardsSkeleton() {
  return (
    <div className="grid gap-stack xl:grid-cols-3" aria-label="…">
      {[0, 1, 2].map((i) => <Skeleton key={i} className="h-72 rounded-card" />)}
    </div>
  )
}

function useChipLabel() {
  const { t } = useI18n()
  return (chip: string) => (KNOWN_CHIPS.includes(chip) ? t(`dressChip_${chip}` as StringKey) : chip)
}

// ------------------------------------------------------------------ For today
function TodayMode() {
  const { t, lang } = useI18n()
  const chipLabel = useChipLabel()
  const chips = useLoad(() => api.occasions().catch(() => FALLBACK_CHIPS), [])
  const list = chips.data ?? FALLBACK_CHIPS
  const [chosen, setChosen] = useState(() => remembered(CHIP_KEY) ?? 'everyday')
  const chip = list.some((c) => c.chip === chosen) ? chosen : 'everyday'
  const [more, setMore] = useState(() => { const c = remembered(CHIP_KEY); return FALLBACK_CHIPS.some((x) => x.chip === c && !x.main) })
  const [shuffle, setShuffle] = useState(0)
  const [place, setPlace] = useState<Place | null>(savedPlace)
  const [locationDenied, setLocationDenied] = useState(false)
  const data = useLoad(() => api.outfitsToday({ occasion: chip, shuffle, at: place ?? undefined }), [chip, shuffle, place])

  const pick = (value: string) => { remember(CHIP_KEY, value); setChosen(value); setShuffle(0) }
  const locateMe = () => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const rounded = { lat: Math.round(pos.coords.latitude * 10) / 10, lon: Math.round(pos.coords.longitude * 10) / 10 }
        remember(PLACE_KEY, JSON.stringify(rounded))
        setLocationDenied(false)
        setPlace(rounded)
      },
      () => setLocationDenied(true),
      { maximumAge: 60 * 60 * 1000, timeout: 10_000 },
    )
  }

  const today = data.data
  const weather = today?.weather
  const occasion = chipLabel(chip)
  let context = ''
  if (today) {
    const condition = weather?.condition ? t(CONDITION_KEY[weather.condition]).toLowerCase() : ''
    context = weather && condition
      ? t('dressContext', { occasion, temp: weather.temp_c, condition })
      : t('dressContextSeason', { occasion, season: weather ? `${weather.temp_c}°` : vocab(SEASON_LABELS, today.season, lang) })
  }

  let body
  if (data.error) body = <ErrorNote error={data.error} onRetry={data.reload} />
  else if (!today) body = <CardsSkeleton />
  else if (today.outfits.length === 0) {
    body = chip === 'beach'
      ? <Empty title={t('dressThreeTitle')} body={t('todayNoBeach')} />
      : today.missing.length > 0
        ? <Empty
            title={t('todayEmptyTitle')}
            body={<ul className="space-y-1">{today.missing.map((m) => <li key={m}>{t(`insightsMissing_${m}`)}</li>)}</ul>}
            action={<AddLink />}
          />
        : <Empty title={t('dressThreeTitle')} body={t('todayNoMatch')} />
  } else {
    const noTaste = today.outfits.every((o) => !o.label)
    body = (
      <div aria-busy={data.loading || undefined} className={data.loading ? 'opacity-60' : ''}>
        {noTaste && <p className="mb-4 rounded-card bg-label-neutral px-card py-3 text-[14px] text-carbon">{t('dressNoTaste')}</p>}
        <div className="mx-auto grid max-w-[640px] gap-stack xl:max-w-none xl:grid-cols-3">
          {today.outfits.map((o, i) => (
            <OutfitCard key={o.items.map((x) => x.id).join('|')} outfit={o} index={i} source="card" occasion={chip === 'beach' ? undefined : usageOf(chip)} />
          ))}
        </div>
        <div className="mt-stack flex justify-center">
          <PillButton variant="outline" busy={data.loading} onClick={() => setShuffle(shuffle + 1)}>
            <RefreshCw className="size-4" aria-hidden /> {t('dressNew')}
          </PillButton>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-stack">
      <div>
        <p className="min-h-6 text-[14px] text-carbon-soft" aria-live="polite">{context || <Skeleton className="h-5 w-64" />}</p>
        {!place && 'geolocation' in navigator && !locationDenied && (
          <button type="button" onClick={locateMe} className="mt-1 inline-flex min-h-9 items-center gap-1.5 text-[13px] font-medium text-pill underline underline-offset-4">
            <LocateFixed className="size-4" aria-hidden /> {t('weatherUseLocation')}
          </button>
        )}
        {locationDenied && <p className="mt-1 text-[13px] text-carbon-soft">{t('weatherLocationDenied', { place: 'Tunis' })}</p>}
        <h2 className="mt-2 text-[34px] font-extrabold leading-tight tracking-[-0.02em] text-carbon">{t('dressThreeTitle')}</h2>
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label={t('occasion')}>
        {list.filter((c) => c.main).map((c) => (
          <PillChip key={c.chip} selected={chip === c.chip} onClick={() => pick(c.chip)}>{chipLabel(c.chip)}</PillChip>
        ))}
        {list.some((c) => !c.main) && (
          <PillChip selected={more && list.some((c) => !c.main && c.chip === chip)} expanded={more} onClick={() => setMore(!more)}>
            {t('dressMore')} <ChevronDown className={`size-4 transition-transform ${more ? 'rotate-180' : ''}`} aria-hidden />
          </PillChip>
        )}
        {more && list.filter((c) => !c.main).map((c) => (
          <PillChip key={c.chip} selected={chip === c.chip} onClick={() => pick(c.chip)}>{chipLabel(c.chip)}</PillChip>
        ))}
      </div>

      {body}
    </div>
  )
}

/** The usage the occasion log keeps for a chip ("everyday" = casual ...): only to say what the outfit was for. */
function usageOf(chip: string): string | undefined {
  return { everyday: 'casual', university: 'casual', work: 'work', outing: 'casual', eid: 'eid', wedding: 'wedding' }[chip]
}

// ------------------------------------------------------------------ Build
type BuildState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'done'; data: BuildResult }
  | { kind: 'error'; error: unknown }

function BuildMode() {
  const { t, lang } = useI18n()
  const items = useLoad(() => api.items(), [])
  const [picked, setPicked] = useState<string[]>([])
  const [state, setState] = useState<BuildState>({ kind: 'idle' })
  const [shuffle, setShuffle] = useState(0)
  const results = useRef<HTMLDivElement>(null)

  const name = (it: Item) => vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)
  const byId = new Map((items.data ?? []).map((it) => [it.id, it]))
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-8)))

  const run = async (nextShuffle: number) => {
    setState({ kind: 'loading' })
    setShuffle(nextShuffle)
    try {
      const data = await api.buildOutfits(picked, nextShuffle)
      setPicked(data.used_item_ids)                 // a clash was swapped: the selection shows what was used
      setState({ kind: 'done', data })
    } catch (error) {
      setState({ kind: 'error', error })
    }
  }

  // the outfits appear below the pieces: bring them into view once they are there
  const done = state.kind === 'done' ? state.data : null
  useEffect(() => { if (done) results.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }, [done])

  if (items.error) return <ErrorNote error={items.error} onRetry={items.reload} />
  if (!items.data) return <Skeleton className="h-64 rounded-card" />
  if (items.data.length === 0) {
    return <Empty title={t('wardrobeEmptyTitle')} body={t('wardrobeEmptyBody')} action={<AddLink />} />
  }

  return (
    <div className="flex flex-col gap-stack">
      <div>
        <h2 className="text-[34px] font-extrabold leading-tight tracking-[-0.02em] text-carbon">{t('navBuild')}</h2>
        <p className="mt-1 max-w-[60ch] text-[15px] text-carbon-soft">{t('dressBuildHint')}</p>
        <p className="mt-2 text-[13px] font-medium text-carbon" aria-live="polite">{t('dressSelected', { n: picked.length })}</p>
      </div>

      {Object.keys(CATEGORY_LABELS).map((cat) => {
        const group = items.data!.filter((it) => it.category === cat)
        if (!group.length) return null
        return (
          <section key={cat} aria-labelledby={`dress-${cat}`}>
            <h3 id={`dress-${cat}`} className="mb-2 text-[13px] font-semibold uppercase tracking-[0.06em] text-carbon-soft">
              {vocab(CATEGORY_LABELS, cat, lang)} <span className="font-mono tabular" dir="ltr">· {group.length}</span>
            </h3>
            <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 xl:grid-cols-6">
              {group.map((it) => {
                const on = picked.includes(it.id)
                return (
                  <li key={it.id}>
                    <button
                      type="button"
                      aria-pressed={on}
                      onClick={() => toggle(it.id)}
                      className={`block w-full rounded-tile p-1.5 text-start transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pill ${on ? 'bg-pill text-pill-text' : 'bg-tile text-carbon'}`}
                    >
                      <div className="flex justify-center overflow-hidden rounded-tile"><ItemPhoto src={it.image_url} alt={name(it)} size={88} /></div>
                      <span className="mt-1 block truncate text-[12px]">{name(it)}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </section>
        )
      })}

      {/* above the phone tab bar; the page keeps room under the last piece for it */}
      <div className="sticky bottom-[calc(var(--tabbar-h,57px)+0.75rem)] z-30 mb-16 flex justify-center lg:bottom-4">
        <PillButton className="w-full shadow-lg sm:w-auto" disabled={picked.length === 0} busy={state.kind === 'loading'} onClick={() => run(0)}>
          {t('dressBuildBtn', { n: picked.length })}
        </PillButton>
      </div>

      <div ref={results} className="scroll-mt-4">
        {state.kind === 'loading' && <CardsSkeleton />}
        {state.kind === 'error' && <ErrorNote error={state.error} onRetry={() => run(shuffle)} />}
        {done && (
          <div>
            {done.notes.length > 0 && (
              <ul className="mb-4 space-y-1" role="status">
                {done.notes.map((n) => (
                  <li key={`${n.params.dropped}-${n.params.kept}`} className="rounded-card bg-label-neutral px-card py-3 text-[14px] text-carbon">
                    {t('dressClash', {
                      kept: byId.get(n.params.kept) ? name(byId.get(n.params.kept)!) : '',
                      dropped: byId.get(n.params.dropped) ? name(byId.get(n.params.dropped)!) : '',
                    })}
                  </li>
                ))}
              </ul>
            )}
            {done.outfits.length === 0 ? (
              <Empty title={t('navBuild')} body={t('dressBuildNone')} />
            ) : (
              <>
                <div className="mx-auto grid max-w-[640px] gap-stack xl:max-w-none xl:grid-cols-3">
                  {done.outfits.map((o, i) => (
                    <OutfitCard key={o.items.map((x) => x.id).join('|')} outfit={o} index={i} source="build" yourPick={o.pick === true} />
                  ))}
                </div>
                <div className="mt-stack flex justify-center">
                  <PillButton variant="outline" onClick={() => run(shuffle + 1)}>
                    <RefreshCw className="size-4" aria-hidden /> {t('dressNew')}
                  </PillButton>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
