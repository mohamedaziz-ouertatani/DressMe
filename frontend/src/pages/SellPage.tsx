import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Check, Tag, Trash2 } from 'lucide-react'
import { api } from '../api/client'
import type { Item, Listing, ListingPatch, SellForm } from '../api/types'
import { useI18n } from '../i18n'
import { Page } from '../shell'
import { Button, TextField } from '../ui/controls'
import { FieldRow } from '../ui/Field'
import { ItemPhoto } from '../ui/ItemPhoto'
import { PhotoPicker } from '../ui/PhotoPicker'
import { Empty, ErrorNote, Skeleton } from '../ui/states'
import { useListingFormat } from '../ui/listingText'
import { useLoad } from '../useLoad'

const CHECK_FIELDS = ['category', 'sub_category', 'colour', 'pattern'] as const
const EMPTY: SellForm = { price_tnd: 0, size: '', city: '', contact: '', title: '' }

/** A seller listing shaped like an item, so the Scan page's field rows can correct it. */
const asItem = (l: Listing): Item => ({
  id: l.id, category: (l.category || 'top') as Item['category'], sub_category: l.sub_category,
  pattern: l.pattern, colour: l.colour, coverage: null, season: [], usage: [],
  predicted: l.predicted, corrected: l.corrected,
})

export function SellPage() {
  const { t } = useI18n()
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [form, setForm] = useState<SellForm>(EMPTY)
  const [priceText, setPriceText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [sent, setSent] = useState<Listing | null>(null)
  const mine = useLoad(() => api.myListings(), [])

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  const pick = (f: File) => {
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setError(null)
  }
  const reset = () => {
    setFile(null); setPreview(''); setForm(EMPTY); setPriceText(''); setSent(null); setError(null)
  }
  const price = Number(priceText.replace(',', '.'))
  const ready = file && price > 0 && form.city.trim() && form.contact.trim()

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!file || !ready) return
    setBusy(true)
    setError(null)
    try {
      setSent(await api.sell(file, { ...form, price_tnd: price }))
      mine.reload()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const correct = async (patch: ListingPatch) => {
    if (!sent) return
    setSent(await api.updateListing(sent.id, patch))
    mine.reload()
  }

  return (
    <Page title={t('sellTitle')}>
      <div className="mx-auto flex max-w-[640px] flex-col gap-8">
        {!sent ? (
          <form className="ticket flex flex-col gap-5 px-5 py-6" onSubmit={submit}>
            <div className="flex items-start gap-4">
              {preview ? <ItemPhoto src={preview} alt="" size={112} /> : <Tag className="mt-1 size-8 shrink-0 text-ink" aria-hidden />}
              <p className="text-[15px] leading-relaxed text-carbon">{t('sellHint')}</p>
            </div>
            <PhotoPicker onPick={pick} />
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField label={t('sellPrice')} inputMode="decimal" required value={priceText}
                onChange={(e) => setPriceText(e.target.value)} />
              <TextField label={t('sellSize')} maxLength={20} value={form.size}
                onChange={(e) => setForm({ ...form, size: e.target.value })} />
              <TextField label={t('sellCity')} maxLength={40} required value={form.city}
                onChange={(e) => setForm({ ...form, city: e.target.value })} />
              <TextField label={t('sellName')} maxLength={80} value={form.title} dir="auto"
                onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <TextField label={t('sellContact')} hint={t('sellContactHint')} maxLength={60} required dir="auto"
              value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} />
            {error ? <ErrorNote error={error} /> : null}
            <Button type="submit" busy={busy} disabled={!ready}>
              {t('sellSend')} <ArrowRight className="size-4 mirror-rtl" aria-hidden />
            </Button>
          </form>
        ) : (
          <section className="ticket px-4 pb-4 pt-3" aria-live="polite">
            <div className="flex items-end gap-4 py-2">
              <ItemPhoto src={preview} alt="" size={112} />
              <p className="pb-1 text-[15px] text-carbon">{t('sellSent')}</p>
            </div>
            <h2 className="mt-2 text-[16px] font-semibold text-carbon">{t('checkFields')}</h2>
            <p className="mb-2 text-[13px] text-carbon-soft">{t('checkFieldsHint')}</p>
            <div className="divide-y divide-perf/40">
              {CHECK_FIELDS.map((f) => <FieldRow key={f} item={asItem(sent)} field={f} onSave={correct} />)}
            </div>
            <Button variant="secondary" className="mt-4 w-full" onClick={reset}>{t('sellAnother')}</Button>
          </section>
        )}

        <section>
          <h2 className="mb-3 text-[18px] font-semibold text-carbon">{t('myListings')}</h2>
          {mine.error ? <ErrorNote error={mine.error} onRetry={mine.reload} />
            : !mine.data ? <Skeleton className="h-32" />
            : mine.data.length === 0 ? <Empty title={t('myListings')} body={t('myListingsEmpty')} />
            : (
              <ul className="flex flex-col gap-3">
                {mine.data.map((l) => <MyListing key={l.id} listing={l} onChange={mine.reload} />)}
              </ul>
            )}
        </section>
      </div>
    </Page>
  )
}

function MyListing({ listing: l, onChange }: { listing: Listing; onChange: () => void }) {
  const { t } = useI18n()
  const { price, name } = useListingFormat()
  const [busy, setBusy] = useState<'' | 'sold' | 'delete'>('')
  const [error, setError] = useState<unknown>(null)
  const act = async (what: 'sold' | 'delete') => {
    setBusy(what)
    setError(null)
    try {
      if (what === 'sold') await api.updateListing(l.id, { sold: true })
      else await api.deleteListing(l.id)
      onChange()
    } catch (e) {
      setError(e)
    } finally {
      setBusy('')
    }
  }
  return (
    <li className="ticket flex flex-col gap-2 p-2 sm:flex-row sm:items-end">
      <div className="flex min-w-0 flex-1 items-end gap-3">
        <ItemPhoto src={l.image_url} alt={name(l)} size={80} />
        <div className="min-w-0 pb-1">
          {l.status === 'active'
            ? <Link to={`/shop/${l.id}`} className="block truncate text-[15px] font-medium text-ink underline decoration-1 underline-offset-4" dir="auto">{name(l)}</Link>
            : <p className="truncate text-[15px] font-medium text-carbon" dir="auto">{name(l)}</p>}
          <p className="font-mono text-[12px] text-ink-soft tabular">{price(l.price_tnd)} · {t(`status_${l.status}`)}</p>
          {l.seller?.review_note && <p className="text-[12px] text-stamp-deep">{t('reviewNote', { n: l.seller.review_note })}</p>}
        </div>
      </div>
      <div className="flex gap-2 sm:pb-1">
        {(l.status === 'active' || l.status === 'pending') && (
          <Button variant="secondary" busy={busy === 'sold'} onClick={() => act('sold')}>
            <Check className="size-4" aria-hidden /> {t('markSold')}
          </Button>
        )}
        <Button variant="quiet" busy={busy === 'delete'} onClick={() => act('delete')} aria-label={t('delete')}>
          <Trash2 className="size-4" aria-hidden /> {t('delete')}
        </Button>
      </div>
      {error ? <ErrorNote error={error} /> : null}
    </li>
  )
}
