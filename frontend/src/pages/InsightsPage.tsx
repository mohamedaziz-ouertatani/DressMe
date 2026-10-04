import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { RowBars } from '../admin/charts'
import { api } from '../api/client'
import type { Insights, OutfitItem } from '../api/types'
import { useI18n } from '../i18n'
import { plural } from '../i18n/plurals'
import { CATEGORY_LABELS, COLOUR_HEX, COLOUR_LABELS, PATTERN_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { Swatch } from '../ui/controls'
import { ItemPhoto } from '../ui/ItemPhoto'
import { Empty, ErrorNote, Skeleton } from '../ui/states'
import { useLoad } from '../useLoad'

/** What the wardrobe is made of, what it can do and what it lacks
 *  (GET /insights; every number is computed from the user's own pieces). */
export function InsightsPage() {
  const { t } = useI18n()
  const res = useLoad(() => api.insights(), [])

  let body
  if (res.error) body = <ErrorNote error={res.error} onRetry={res.reload} />
  else if (!res.data) body = <Skeleton className="h-72" />
  else if (res.data.total === 0)
    body = (
      <Empty
        title={t('wardrobeEmptyTitle')}
        body={t('wardrobeEmptyBody')}
        action={<Link to="/wardrobe" className="inline-flex min-h-11 items-center bg-ink px-4 text-[15px] font-medium text-paper">{t('addPieces')}</Link>}
      />
    )
  else body = <InsightsBody data={res.data} />

  return <Page title={t('insightsTitle')}>{body}</Page>
}

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="text-[18px] font-semibold text-carbon">{title}</h2>
      {note && <p className="mt-1 max-w-[60ch] text-[13px] text-carbon-soft">{note}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

function InsightsBody({ data }: { data: Insights }) {
  const { t, lang } = useI18n()
  const label = (it: { sub_category: string; category: string }) =>
    vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)
  const coloured = data.colours.reduce((a, c) => a + c.count, 0)
  const neutral = data.colours.filter((c) => c.neutral).reduce((a, c) => a + c.count, 0)
  const confirm = (['colour', 'coverage', 'season', 'usage'] as const).filter((f) => data.to_confirm[f] > 0)
  const fieldName = { colour: t('colour'), coverage: t('coverage'), season: t('seasons'), usage: t('occasions') }
  // pairs only make sense once there is something to pair with
  const showPairs = data.new_pairs.top + data.new_pairs.bottom > 0

  return (
    <div className="flex flex-col gap-10">
      {/* headline: how many good outfits the wardrobe makes */}
      <section className="ticket flex flex-col gap-1 px-4 py-4 lg:px-6">
        <p className="text-[28px] font-semibold leading-tight text-carbon lg:text-[34px]">
          {plural('goodOutfits', data.outfits.good, lang)}
        </p>
        <p className="text-[14px] text-carbon-soft">
          {plural('pieces', data.total, lang)} · {t('insightsOutfitsNote', { s: data.outfits.good_score })}
        </p>
        {!data.outfits.complete && <p className="text-[13px] text-carbon-soft">{t('insightsLowerBound')}</p>}
        {data.filtered > 0 && <p className="text-[13px] text-carbon-soft">{t('insightsFiltered', { n: data.filtered })}</p>}
      </section>

      {(data.missing.length > 0 || showPairs) && (
        <Section title={t('insightsNext')} note={showPairs ? t('insightsPairsNote') : undefined}>
          <ul className="flex flex-col gap-2">
            {data.missing.map((m) => (
              <li key={m} className="border-s-[3px] border-stamp bg-paper px-3 py-2 text-[15px] text-carbon">
                {t(`insightsMissing_${m}`)}
              </li>
            ))}
            {showPairs && (
              <li className="ticket grid grid-cols-2">
                {([['insightsAddBottom', data.new_pairs.bottom], ['insightsAddTop', data.new_pairs.top]] as const).map(([key, n]) => (
                  <div key={key} className="px-3 py-3 [&+&]:border-s [&+&]:border-dashed [&+&]:border-perf">
                    <p className="text-[13px] text-carbon-soft">{t(key)}</p>
                    <p className="text-[17px] font-semibold text-carbon">{plural('newPairs', n, lang)}</p>
                  </div>
                ))}
              </li>
            )}
          </ul>
        </Section>
      )}

      {data.versatile.length > 0 && (
        <Section title={t('insightsVersatile')}>
          <PieceGrid items={data.versatile} label={label} line={(it) => plural('inOutfits', it.outfits, lang)} />
        </Section>
      )}

      {data.unmatched.length > 0 && (
        <Section title={t('insightsUnmatched')} note={t('insightsUnmatchedNote')}>
          <PieceGrid items={data.unmatched} label={label} />
        </Section>
      )}

      {data.twins.length > 0 && (
        <Section title={t('insightsTwins')} note={t('insightsTwinsNote')}>
          <ul className="grid gap-3 sm:grid-cols-2">
            {data.twins.map((tw) => (
              <li key={tw.items.map((i) => i.id).join('|')} className="ticket flex items-center gap-3 p-2">
                {tw.items.map((it) => (
                  <Link key={it.id} to={`/wardrobe/${it.id}`} className="shrink-0">
                    <ItemPhoto src={it.image_url} alt={label(it)} size={88} />
                  </Link>
                ))}
                <div className="min-w-0">
                  <p className="truncate text-[15px] font-medium text-carbon">{label(tw.items[0])}</p>
                  <p className="font-mono text-[12px] text-ink-soft tabular">{t('match', { p: Math.round(tw.similarity * 100) })}</p>
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title={t('insightsMix')}>
        <div className="grid gap-8 lg:grid-cols-3">
          <figure className="m-0">
            <figcaption className="mb-2 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('category')}</figcaption>
            <RowBars rows={data.categories.map((c) => ({ label: vocab(CATEGORY_LABELS, c.category, lang), value: c.count }))} />
          </figure>
          <figure className="m-0">
            <figcaption className="mb-2 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('insightsColours')}</figcaption>
            <ColourBars colours={data.colours} />
            {coloured > 0 && (
              <p className="mt-2 text-[13px] text-carbon-soft">{t('insightsNeutral', { p: Math.round((neutral / coloured) * 100) })}</p>
            )}
          </figure>
          <figure className="m-0">
            <figcaption className="mb-2 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('insightsPatterns')}</figcaption>
            <RowBars rows={data.patterns.map((p) => ({ label: vocab(PATTERN_LABELS, p.pattern, lang), value: p.count }))} />
          </figure>
        </div>
      </Section>

      <Section title={t('insightsConfirm')} note={confirm.length ? t('insightsConfirmNote') : undefined}>
        {confirm.length === 0 ? (
          <p className="text-[14px] text-carbon-soft">{t('insightsAllSet')}</p>
        ) : (
          <ul className="ticket divide-y divide-dashed divide-perf">
            {confirm.map((f) => (
              <li key={f} className="flex items-center justify-between gap-3 px-3 py-2.5 text-[15px]">
                <span className="text-carbon">{fieldName[f]}</span>
                <Link to="/wardrobe" className="text-ink underline decoration-1 underline-offset-4">
                  {plural('pieces', data.to_confirm[f], lang)}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  )
}

function PieceGrid<T extends OutfitItem>({ items, label, line }: {
  items: T[]
  label: (it: T) => string
  line?: (it: T) => string
}) {
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {items.map((it) => (
        <li key={it.id}>
          <Link to={`/wardrobe/${it.id}`} className="ticket block p-2">
            <div className="flex justify-center"><ItemPhoto src={it.image_url} alt={label(it)} size={112} /></div>
            <p className="perf-h mt-2 truncate pt-2 text-[14px] font-medium text-carbon">{label(it)}</p>
            {line && <p className="font-mono text-[11px] text-ink-soft tabular">{line(it)}</p>}
          </Link>
        </li>
      ))}
    </ul>
  )
}

/** One row per colour: its swatch, name and a bar for the number of pieces. */
function ColourBars({ colours }: { colours: Insights['colours'] }) {
  const { lang } = useI18n()
  const max = Math.max(1, ...colours.map((c) => c.count))
  return (
    <ul className="flex flex-col gap-2">
      {colours.map((c) => (
        <li key={c.colour} className="grid grid-cols-[112px_minmax(0,1fr)_32px] items-center gap-3">
          <span className="flex min-w-0 items-center gap-2 text-[13px] text-carbon">
            <Swatch hex={COLOUR_HEX[c.colour] ?? '#ccc'} size={12} />
            <span className="truncate">{vocab(COLOUR_LABELS, c.colour, lang)}</span>
          </span>
          <span className="relative h-5 bg-stock-deep/60">
            <span className="absolute inset-y-0 start-0 rounded-e-[4px] bg-ink-soft" style={{ width: `${(c.count / max) * 100}%` }} />
          </span>
          <span className="text-end font-mono text-[12px] text-carbon tabular">{c.count}</span>
        </li>
      ))}
    </ul>
  )
}
