import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { ItemPhoto } from '../ui/ItemPhoto'
import { ErrorNote, Skeleton } from '../ui/states'
import { useLoad } from '../useLoad'
import { ListingCard } from '../ui/ListingCard'

export function SimilarPage() {
  const { t, lang } = useI18n()
  const [params] = useSearchParams()
  const itemId = params.get('item') ?? undefined
  const candidateId = params.get('candidate') ?? undefined
  const res = useLoad(() => api.similar({ itemId, candidateId }, 6), [itemId, candidateId])
  const label = (sub: string, cat: string) => vocab(SUB_LABELS, sub, lang) || vocab(CATEGORY_LABELS, cat, lang)
  const pct = (s: number) => t('match', { p: Math.round(Math.max(0, s) * 100) })

  return (
    <Page title={t('similarTitle')}>
      {res.error ? (
        <ErrorNote error={res.error} onRetry={res.reload} />
      ) : !res.data ? (
        <Skeleton className="h-64" />
      ) : (
        <div className="flex flex-col gap-10">
          <section>
            <h2 className="mb-3 text-[18px] font-semibold text-carbon">{t('inWardrobe')}</h2>
            {res.data.wardrobe.length === 0 ? (
              <p className="text-[14px] text-carbon-soft">{t('wardrobeEmptyTitle')}</p>
            ) : (
              <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {res.data.wardrobe.map((it) => (
                  <li key={it.id}>
                    <Link to={`/wardrobe/${it.id}`} className="ticket block p-2">
                      <div className="flex justify-center"><ItemPhoto src={it.image_url} alt={label(it.sub_category, it.category)} size={112} /></div>
                      <p className="perf-h mt-2 truncate pt-2 text-[14px] font-medium text-carbon">{label(it.sub_category, it.category)}</p>
                      <p className="font-mono text-[11px] text-ink-soft tabular">{pct(it.similarity)}</p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
          {res.data.listings && res.data.listings.length > 0 && (
            <section>
              <h2 className="text-[18px] font-semibold text-carbon">{t('listingsTitle')}</h2>
              <p className="mb-3 mt-1 text-[13px] text-carbon-soft">{t('listingsNote')}</p>
              <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {res.data.listings.map((l) => (
                  <li key={l.id}><ListingCard listing={l} note={pct(l.score)} /></li>
                ))}
              </ul>
            </section>
          )}
          {res.data.shop && res.data.shop.length > 0 && (
            <section>
              <h2 className="text-[18px] font-semibold text-carbon">{t('shopTitle')}</h2>
              <p className="mb-3 mt-1 text-[13px] text-carbon-soft">{t('shopNote')}</p>
              <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {res.data.shop.map((s) => (
                  <li key={s.id} className="ticket p-2">
                    <div className="flex justify-center"><ItemPhoto src={s.image_url} alt={s.name} size={112} /></div>
                    {/* the shop's own product name, as H&M wrote it (not translated) */}
                    <p className="perf-h mt-2 truncate pt-2 text-[14px] font-medium text-carbon" dir="auto" title={s.name}>{s.name}</p>
                    <p className="font-mono text-[11px] text-ink-soft tabular">{s.shop} · {pct(s.score)}</p>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <section>
            <h2 className="text-[18px] font-semibold text-carbon">{t('inspiration')}</h2>
            <p className="mb-3 mt-1 text-[13px] text-carbon-soft">{t('inspirationNote')}</p>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {res.data.catalog.map((c) => (
                <li key={c.id} className="ticket p-2">
                  <div className="flex justify-center"><ItemPhoto src={c.image_url} alt={label(c.sub_category, c.category)} size={112} /></div>
                  <p className="perf-h mt-2 truncate pt-2 text-[14px] font-medium text-carbon">{label(c.sub_category, c.category)}</p>
                  <p className="font-mono text-[11px] text-ink-soft tabular">{pct(c.score)}</p>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </Page>
  )
}
