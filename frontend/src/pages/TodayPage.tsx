import { useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import type { Occasion, Season } from '../api/types'
import { useI18n } from '../i18n'
import { OCCASION_LABELS, SEASON_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { Button, Chip } from '../ui/controls'
import { OutfitStrip } from '../ui/OutfitStrip'
import { Empty, ErrorNote, Skeleton } from '../ui/states'
import { groupSerial } from '../ui/serial'
import { useLoad } from '../useLoad'

const SEASONS: Season[] = ['summer', 'mid-season', 'winter']
const OCCASIONS: Occasion[] = ['casual', 'work', 'formal', 'sport', 'wedding', 'eid']

export function TodayPage() {
  const { t, lang } = useI18n()
  const [season, setSeason] = useState<Season | undefined>()
  const [occasion, setOccasion] = useState<Occasion | undefined>()
  const [index, setIndex] = useState(0)

  const wardrobe = useLoad(() => api.items(), [])
  const outfits = useLoad(async () => {
    setIndex(0)
    return api.suggest({ season, occasion, n: 6 })
  }, [season, occasion])

  const filters = (
    <div className="flex flex-col gap-4">
      {([['season', SEASONS, SEASON_LABELS, season, setSeason], ['occasion', OCCASIONS, OCCASION_LABELS, occasion, setOccasion]] as const).map(
        ([key, values, table, current, set]) => (
          <fieldset key={key} className="min-w-0">
            <legend className="mb-2 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t(key)}</legend>
            <div className="-mx-4 flex gap-2 no-scrollbar overflow-x-auto px-4 pb-1 lg:mx-0 lg:flex-wrap lg:px-0">
              <Chip selected={!current} onClick={() => (set as (v: undefined) => void)(undefined)}>{t('any')}</Chip>
              {values.map((v) => (
                <Chip key={v} selected={current === v} onClick={() => (set as (v: string) => void)(v)}>
                  {vocab(table, v, lang)}
                </Chip>
              ))}
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
  else if (!outfit) body = <Empty title={t('todayTitle')} body={t('todayNoMatch')} />
  else
    body = (
      <div aria-busy={outfits.loading || undefined} className={outfits.loading ? 'opacity-60' : ''}>
        {list.length > 1 && (
          <p className="mb-2 text-end font-mono text-[12px] text-ink-soft tabular" dir="ltr">
            {index + 1} / {list.length}
          </p>
        )}
        <OutfitStrip key={index} outfit={outfit} land />
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
      {body}
      {/* on phones the strip comes first; filters follow it */}
      <div className="mt-8 lg:hidden">{filters}</div>
    </Page>
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
