import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, ExternalLink, MessageCircle, Search, Tag } from 'lucide-react'
import { api } from '../api/client'
import type { BuyAdvice, Category, Item, Listing, ListingFilters } from '../api/types'
import { useI18n } from '../i18n'
import { plural } from '../i18n/plurals'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { ListingCard, StockLine } from '../ui/ListingCard'
import { brandName, useListingFormat } from '../ui/listingText'
import { Page } from '../shell'
import { Button, Chip } from '../ui/controls'
import { ItemPhoto } from '../ui/ItemPhoto'
import { OutfitStrip } from '../ui/OutfitStrip'
import { Stamp } from '../ui/Stamp'
import { Empty, ErrorNote, Skeleton } from '../ui/states'
import { Ticket } from '../ui/ticket'
import { useLoad } from '../useLoad'

const CATEGORIES: Category[] = ['top', 'bottom', 'dress', 'outerwear', 'shoes', 'bag', 'accessory']
export function ShopPage() {
  const { t, lang } = useI18n()
  const [filters, setFilters] = useState<ListingFilters>({ sort: 'new' })
  const [priceText, setPriceText] = useState('')
  const [extra, setExtra] = useState<Listing[]>([])
  const [page, setPage] = useState(1)
  const [moreBusy, setMoreBusy] = useState(false)
  const [moreError, setMoreError] = useState<unknown>(null)
  const sources = useLoad(() => api.listingSources(), [])
  const res = useLoad(() => api.listings({ ...filters, page: 1 }), [filters])

  // a new filter starts again from the first page
  const set = (patch: Partial<ListingFilters>) => {
    setFilters((f) => ({ ...f, ...patch }))
    setExtra([])
    setPage(1)
  }
  const applyPrice = () => {
    const v = Number(priceText.replace(',', '.'))
    set({ max_price: priceText.trim() && v > 0 ? v : undefined })
  }

  const loadMore = async () => {
    setMoreBusy(true)
    setMoreError(null)
    try {
      const next = await api.listings({ ...filters, page: page + 1 })
      setExtra((old) => [...old, ...next.items])
      setPage(page + 1)
    } catch (e) {
      setMoreError(e)
    } finally {
      setMoreBusy(false)
    }
  }

  const shown = [...(res.data?.items ?? []), ...extra]
  return (
    <Page title={t('shopPageTitle')}>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <p className="max-w-[70ch] text-[13px] text-carbon-soft">{t('shopPageNote')}</p>
        <Link to="/sell" className="inline-flex min-h-11 shrink-0 items-center gap-2 self-start border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink">
          <Tag className="size-4" aria-hidden /> {t('sellLink')}
        </Link>
      </div>

      <div className="mb-5 flex flex-col gap-3">
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
          <Chip selected={!filters.category} onClick={() => set({ category: undefined })}>{t('allCategories')}</Chip>
          {CATEGORIES.map((c) => (
            <Chip key={c} selected={filters.category === c} onClick={() => set({ category: c })}>
              {vocab(CATEGORY_LABELS, c, lang)}
            </Chip>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(sources.data?.length ?? 0) > 1 && (
            <>
              <Chip selected={!filters.source} onClick={() => set({ source: undefined })}>{t('allShops')}</Chip>
              {sources.data!.map((s) => (
                <Chip key={s.source_id} selected={filters.source === s.source_id} onClick={() => set({ source: s.source_id })}>
                  {s.source_id === 'sellers' ? t('friperieSellers') : s.brands.map(brandName).join(' · ')}
                </Chip>
              ))}
              <span aria-hidden className="mx-1 h-6 border-s border-perf" />
            </>
          )}
          <Chip selected={filters.sort === 'new'} onClick={() => set({ sort: 'new' })}>{t('sortNew')}</Chip>
          <Chip selected={filters.sort === 'price'} onClick={() => set({ sort: 'price' })}>{t('sortPrice')}</Chip>
          <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); applyPrice() }}>
            <label className="sr-only" htmlFor="max-price">{t('maxPrice')}</label>
            <input
              id="max-price"
              inputMode="decimal"
              placeholder={t('maxPrice')}
              value={priceText}
              onChange={(e) => setPriceText(e.target.value)}
              onBlur={applyPrice}
              className="min-h-9 w-[150px] border-[1.5px] border-perf bg-paper px-3 text-[13px] text-carbon focus-visible:border-ink focus-visible:outline-none"
            />
          </form>
        </div>
      </div>

      {res.error ? (
        <ErrorNote error={res.error} onRetry={res.reload} />
      ) : !res.data ? (
        <Skeleton className="h-64" />
      ) : shown.length === 0 ? (
        <Empty title={t('shopEmptyTitle')} body={t('shopEmptyBody')} />
      ) : (
        <>
          <p className="mb-3 text-[14px] text-carbon-soft">{plural('pieces', res.data.total, lang)}</p>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {shown.map((l) => <li key={l.id}><ListingCard listing={l} /></li>)}
          </ul>
          {moreError ? <div className="mt-4"><ErrorNote error={moreError} onRetry={loadMore} /></div> : null}
          {shown.length < res.data.total && (
            <div className="mt-6 flex justify-center">
              <Button variant="secondary" busy={moreBusy} onClick={loadMore}>{t('loadMore')}</Button>
            </div>
          )}
        </>
      )}
    </Page>
  )
}

/** One listing: picture, price, stock, a link to the shop, and the buy verdict. */
export function ListingPage() {
  const { id = '' } = useParams()
  const { t, lang, reason } = useI18n()
  const { price, day, name } = useListingFormat()
  const res = useLoad(() => api.listing(id), [id])
  // the verdict belongs to one listing: opening another one starts clean
  const [state, setState] = useState<{ id: string; candidate?: Item; advice?: BuyAdvice; error?: unknown }>({ id })
  const [busy, setBusy] = useState(false)
  const { candidate, advice, error } = state.id === id ? state : { candidate: undefined, advice: undefined, error: undefined }

  const ask = async () => {
    setBusy(true)
    let cand = candidate
    try {
      cand = cand ?? await api.listingCandidate(id)
      setState({ id, candidate: cand, advice: await api.buyAdvice(cand.id) })
    } catch (e) {
      setState({ id, candidate: cand, error: e })
    } finally {
      setBusy(false)
    }
  }

  const l = res.data
  const kind = l ? vocab(SUB_LABELS, l.sub_category, lang) || vocab(CATEGORY_LABELS, l.category, lang) : ''
  return (
    <Page title={t('shopPageTitle')}>
      <div className="mx-auto max-w-[640px]">
        <Link to="/shop" className="mb-4 inline-flex min-h-11 items-center gap-1.5 text-[15px] text-ink">
          <ArrowLeft className="size-4 mirror-rtl" aria-hidden /> {t('back')}
        </Link>
        {res.error ? (
          <ErrorNote error={res.error} onRetry={res.reload} />
        ) : !l ? (
          <Skeleton className="h-64" />
        ) : (
          <>
            <Ticket className="relative">
              <div className="flex items-end gap-4 p-3">
                <ItemPhoto src={l.image_url} alt={name(l)} size={160} />
                <div className="min-w-0 pb-1">
                  <p className="text-[20px] font-semibold leading-tight text-carbon" dir="auto">{name(l)}</p>
                  <p className="mt-1 text-[14px] text-carbon-soft">
                    {l.seller ? t('friperieSellers') : brandName(l.brand)}{l.shop_colour ? <> · <span dir="auto">{l.shop_colour}</span></> : null}{kind && l.title ? ` · ${kind}` : ''}
                  </p>
                  {l.price_tnd !== null && <p className="mt-2 font-mono text-[18px] text-carbon tabular">{price(l.price_tnd)}</p>}
                  <p className="mt-1 text-[13px] text-carbon-soft">
                    {l.status === 'gone' ? t('listingGone') : <StockLine listing={l} />}
                  </p>
                  {l.snapshot ? (
                    <p className="mt-1 text-[12px] text-stamp-deep">{t('snapshotFrom', { d: day(l.checked_at) })}</p>
                  ) : l.checked_at && !l.seller ? (
                    <p className="font-mono text-[11px] text-ink-soft tabular">{t('lastChecked', { d: day(l.checked_at) })}</p>
                  ) : null}
                </div>
              </div>
              {/* the stamp lands over the photo, so it never hides the price */}
              {advice && (
                <div className="pointer-events-none absolute -top-5 start-24">
                  <Stamp big={t(`verdict_${advice.verdict}`)} ring="DRESSME · VALIDÉ · مصادق · DRESSME · VALIDÉ ·"
                    size={110} angle={-11} land label={t(`verdict_${advice.verdict}`)} />
                </div>
              )}
            </Ticket>

            {l.seller && (
              <p className="ticket mt-3 flex items-center gap-2 px-4 py-3 text-[15px] text-carbon">
                <MessageCircle className="size-4 shrink-0 text-ink" aria-hidden />
                <span>{t('sellerCity', { c: l.seller.city })} · <span dir="auto">{t('sellerContact', { c: l.seller.contact })}</span></span>
              </p>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              {l.url && (
                <a href={l.url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex min-h-11 items-center gap-2 border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink">
                  <ExternalLink className="size-4" aria-hidden /> {t('openInShop', { brand: brandName(l.brand) })}
                </a>
              )}
              {l.status === 'active' && !advice && (
                <Button busy={busy} onClick={ask}>
                  {busy ? t('asking') : t('shouldIBuy')} <ArrowRight className="size-4 mirror-rtl" aria-hidden />
                </Button>
              )}
            </div>

            {error ? <div className="mt-4"><ErrorNote error={error} onRetry={ask} /></div> : null}

            {advice && candidate && (
              <section className="mt-6" aria-live="polite">
                <p className="text-[18px] font-medium leading-snug text-carbon">
                  {t(`verdictLine_${advice.verdict}`, { outfits: plural('goodOutfits', advice.good_outfits, lang) })}
                </p>
                {advice.reasons.length > 0 && (
                  <ul className="mt-2 space-y-1 text-[15px] text-carbon-soft">
                    {advice.reasons.map((r) => <li key={r}>{reason(r)}</li>)}
                  </ul>
                )}
                <Link to={`/similar?candidate=${candidate.id}`} className="mt-5 inline-flex min-h-11 items-center gap-2 border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink">
                  <Search className="size-4" aria-hidden /> {t('seeSimilar')}
                </Link>
                {advice.best.length > 0 && (
                  <div className="mt-8">
                    <h2 className="mb-4 text-[18px] font-semibold text-carbon">{t('bestOutfits')}</h2>
                    <div className="grid gap-10 pt-4 sm:grid-cols-2">
                      {advice.best.slice(0, 2).map((o, i) => (
                        <OutfitStrip key={i} outfit={o} compact photoOf={(pid) => (pid === candidate.id ? l.image_url : undefined)} />
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </Page>
  )
}
