import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Cloud, CloudFog, CloudLightning, CloudRain, CloudSnow, LocateFixed, RefreshCw, Sun } from 'lucide-react'
import { api } from '../api/client'
import type { Occasion, Season, Weather, WeatherCondition } from '../api/types'
import { useI18n } from '../i18n'
import type { StringKey } from '../i18n/strings'
import { OCCASION_LABELS, SEASON_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { Button, Chip } from '../ui/controls'
import { OutfitStrip } from '../ui/OutfitStrip'
import { Empty, ErrorNote, Skeleton } from '../ui/states'
import { groupSerial } from '../ui/serial'
import { useLoad } from '../useLoad'

const SEASONS: Season[] = ['summer', 'mid-season', 'winter']
const OCCASIONS: Occasion[] = ['casual', 'work', 'formal', 'sport', 'wedding', 'eid']

// The season by the calendar in Tunisia: used until today's real weather arrives
// (and when the weather service is off or unreachable).
function currentSeason(): Season {
  const month = new Date().getMonth() + 1
  if (month >= 6 && month <= 9) return 'summer'
  if (month === 12 || month <= 2) return 'winter'
  return 'mid-season'
}

// The user's position, rounded to ~10 km, remembered once they share it.
// Only this rounded position is sent to the backend (which asks Open-Meteo).
const PLACE_KEY = 'dressme.weatherPlace'
type Place = { lat: number; lon: number }

function savedPlace(): Place | null {
  try {
    const place = JSON.parse(localStorage.getItem(PLACE_KEY) ?? 'null')
    return typeof place?.lat === 'number' && typeof place?.lon === 'number' ? place : null
  } catch {
    return null
  }
}

function savePlace(place: Place) {
  try {
    localStorage.setItem(PLACE_KEY, JSON.stringify(place))
  } catch {
    /* private mode: the position is asked again next time */
  }
}

export function TodayPage() {
  const { t, lang } = useI18n()
  // The first suggestion fits today's weather (shorts on a hot day, a jacket on a
  // cold one): the calendar season first, then the weather's once it arrives,
  // unless the user has already picked a season themselves.
  const [place, setPlace] = useState<Place | null>(savedPlace)
  const [locationDenied, setLocationDenied] = useState(false)
  const weather = useLoad(() => api.weather(place ?? undefined), [place])
  const [picked, setPicked] = useState<{ season: Season | undefined } | null>(null)
  const season = picked ? picked.season : (weather.data?.season ?? currentSeason())
  const pickSeason = (value: Season | undefined) => setPicked({ season: value })

  const locateMe = () => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const rounded = { lat: Math.round(pos.coords.latitude * 10) / 10, lon: Math.round(pos.coords.longitude * 10) / 10 }
        savePlace(rounded)
        setLocationDenied(false)
        setPlace(rounded)
      },
      () => setLocationDenied(true),
      { maximumAge: 60 * 60 * 1000, timeout: 10_000 },
    )
  }
  const [occasion, setOccasion] = useState<Occasion | undefined>()
  // Beach: outfits around a swimsuit (swimwear stays out of the other suggestions).
  // It sits in the occasion row, so picking it clears the occasion and vice versa.
  const [beach, setBeach] = useState(false)
  const pickOccasion = (value: Occasion | undefined) => { setBeach(false); setOccasion(value) }
  const [index, setIndex] = useState(0)
  const [feedback, setFeedback] = useState<Record<string, 1 | -1>>({})
  const [feedbackError, setFeedbackError] = useState<unknown>(null)

  const wardrobe = useLoad(() => api.items(), [])
  const outfits = useLoad(async () => {
    setIndex(0)
    // a beach outfit is a summer outfit (sandals, no jacket), whatever the season row says
    return beach ? api.suggest({ season: 'summer', beach, n: 6 }) : api.suggest({ season, occasion, n: 6 })
  }, [season, occasion, beach])

  const filters = (
    <div className="flex flex-col gap-4">
      {/* beach outfits are always summer outfits, so the season row is hidden for them */}
      {([['season', SEASONS, SEASON_LABELS, season, pickSeason], ['occasion', OCCASIONS, OCCASION_LABELS, beach ? null : occasion, pickOccasion]] as const).map(
        ([key, values, table, current, set]) => (beach && key === 'season') ? null : (
          <fieldset key={key} className="min-w-0">
            <legend className="mb-2 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t(key)}</legend>
            <div className="-mx-4 flex gap-2 no-scrollbar overflow-x-auto px-4 pb-1 lg:mx-0 lg:flex-wrap lg:px-0">
              <Chip selected={current === undefined} onClick={() => (set as (v: undefined) => void)(undefined)}>{t('any')}</Chip>
              {values.map((v) => (
                <Chip key={v} selected={current === v} onClick={() => (set as (v: string) => void)(v)}>
                  {vocab(table, v, lang)}
                </Chip>
              ))}
              {key === 'occasion' && (
                <Chip selected={beach} onClick={() => { setOccasion(undefined); setBeach(true) }}>{t('beach')}</Chip>
              )}
            </div>
          </fieldset>
        ),
      )}
    </div>
  )

  const list = outfits.data ?? []
  const outfit = list[index]
  const tooFew = wardrobe.data !== null && wardrobe.data.length < 3

  let body
  if (outfits.error) body = <ErrorNote error={outfits.error} onRetry={outfits.reload} />
  else if (outfits.loading && !outfits.data) body = <TodaySkeleton />
  else if (tooFew && !outfit)
    body = (
      <Empty
        title={t('todayEmptyTitle')}
        body={t('todayEmptyBody')}
        action={<Link to="/wardrobe" className="inline-flex min-h-11 items-center bg-ink px-4 text-[15px] font-medium text-paper">{t('addPieces')}</Link>}
      />
    )
  else if (!outfit) body = <Empty title={t('todayTitle')} body={t(beach ? 'todayNoBeach' : 'todayNoMatch')} />
  else
    body = (
      <div aria-busy={outfits.loading || undefined} className={outfits.loading ? 'opacity-60' : ''}>
        {list.length > 1 && (
          <p className="mb-2 text-end font-mono text-[12px] text-ink-soft tabular" dir="ltr">
            {index + 1} / {list.length}
          </p>
        )}
        <OutfitStrip
          key={index}
          outfit={outfit}
          land
          feedback={feedback[outfit.items.map((item) => item.id).sort().join('|')]}
          onFeedback={(rating) => {
            const key = outfit.items.map((item) => item.id).sort().join('|')
            const previous = feedback[key]
            setFeedback((current) => ({ ...current, [key]: rating }))
            setFeedbackError(null)
            api.feedback(outfit.items.map((item) => item.id), rating).catch((error) => {
              setFeedback((current) => {
                const next = { ...current }
                if (previous === undefined) delete next[key]
                else next[key] = previous
                return next
              })
              setFeedbackError(error)
            })
          }}
        />
        {feedbackError ? <ErrorNote error={feedbackError} /> : null}
        {list.length > 1 && (
          <Button variant="secondary" className="mt-5 w-full sm:w-auto" onClick={() => setIndex((index + 1) % list.length)}>
            <RefreshCw className="size-4" aria-hidden /> {t('anotherOne')}
          </Button>
        )}
      </div>
    )

  return (
    <Page
      title={t('todayTitle')}
      serial={outfit ? groupSerial(outfit.items.map((i) => i.id)) : undefined}
      aside={<div className="hidden lg:sticky lg:top-10 lg:block">{filters}</div>}
    >
      {/* the weather is a help, not a must: nothing is shown if it can't be loaded */}
      {weather.data && (
        <WeatherLine
          weather={weather.data}
          canLocate={!place && 'geolocation' in navigator}
          locationDenied={locationDenied}
          onLocate={locateMe}
        />
      )}
      {body}
      {/* on phones the strip comes first; filters follow it */}
      <div className="mt-8 lg:hidden">{filters}</div>
    </Page>
  )
}

const CONDITION: Record<WeatherCondition, { icon: typeof Sun; label: StringKey }> = {
  clear: { icon: Sun, label: 'weatherClear' },
  cloudy: { icon: Cloud, label: 'weatherCloudy' },
  fog: { icon: CloudFog, label: 'weatherFog' },
  rain: { icon: CloudRain, label: 'weatherRainy' },
  snow: { icon: CloudSnow, label: 'weatherSnow' },
  storm: { icon: CloudLightning, label: 'weatherStorm' },
}

function WeatherLine({ weather, canLocate, locationDenied, onLocate }: {
  weather: Weather
  canLocate: boolean
  locationDenied: boolean
  onLocate: () => void
}) {
  const { t, lang } = useI18n()
  const condition = weather.condition ? CONDITION[weather.condition] : null
  const Icon = condition?.icon ?? Cloud
  const place = weather.place === 'here' ? t('weatherHere') : weather.place
  return (
    <section className="mb-5 border-b border-perf pb-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[14px] text-carbon">
        <Icon className="size-5 shrink-0 text-ink" aria-hidden />
        <span className="font-medium text-ink">{place}</span>
        {condition && <span>{t(condition.label)}</span>}
        <span className="tabular">{t('weatherNow', { temp: weather.temperature, min: weather.min, max: weather.max })}</span>
        <span className="text-ink-soft tabular">{t('weatherFeels', { temp: weather.feels_like })}</span>
      </div>
      <p className="mt-1 text-[13px] text-ink-soft">
        {t('weatherSeason', { season: vocab(SEASON_LABELS, weather.season, lang) })}
      </p>
      {weather.rain_likely && (
        <p className="mt-1 text-[13px] text-carbon">{t('weatherRain', { p: weather.rain_probability ?? '' })}</p>
      )}
      {locationDenied && <p className="mt-1 text-[13px] text-ink-soft">{t('weatherLocationDenied', { place: weather.place })}</p>}
      {canLocate && !locationDenied && (
        <button type="button" onClick={onLocate} className="mt-2 inline-flex min-h-9 items-center gap-1.5 text-[13px] font-medium text-ink underline underline-offset-4">
          <LocateFixed className="size-4" aria-hidden /> {t('weatherUseLocation')}
        </button>
      )}
    </section>
  )
}

function TodaySkeleton() {
  return (
    <div className="flex flex-col gap-2" aria-label="…">
      {[0, 1, 2].map((i) => (
        <div key={i} className="ticket flex items-end gap-3 p-2">
          <Skeleton className="size-24" />
          <div className="flex-1 space-y-2 pb-1">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
      ))}
    </div>
  )
}
