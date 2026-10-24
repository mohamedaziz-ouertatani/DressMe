import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Lightbulb, ShoppingBag, Tag } from 'lucide-react'
import { api } from '../api/client'
import type { BuyAdvice, Item, ItemPatch } from '../api/types'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { Button, TextField } from '../ui/controls'
import { ExplainPanel } from '../ui/ExplainPanel'
import { FieldRow } from '../ui/Field'
import { VerdictCard } from '../ui/VerdictCard'
import { PhotoPicker } from '../ui/PhotoPicker'
import { ErrorNote, Skeleton } from '../ui/states'

const CHECK_FIELDS = ['category', 'sub_category', 'colour', 'pattern'] as const

/** Apply a correction locally (the candidate is only saved with the verdict request). */
function applyPatch(item: Item, patch: ItemPatch): Item {
  const next = { ...item, ...patch } as Item
  if (patch.category && patch.category !== item.category && !patch.sub_category) next.sub_category = ''
  next.corrected = Array.from(new Set([...item.corrected, ...Object.keys(patch), ...(next.sub_category !== item.sub_category ? ['sub_category'] : [])]))
  return next
}

/** The camera frame of the start screen (the prototype's Buy screen, step H2): white corner marks on near-black, the
 *  hint, and while the photo is read, the photo and a line sweeping down (still under reduced motion). */
function CameraFrame({ preview, reading }: { preview: string; reading: boolean }) {
  const { t } = useI18n()
  return (
    <div className="relative grid h-[280px] place-items-center overflow-hidden rounded-hero bg-pill">
      <svg width="230" height="230" viewBox="0 0 230 230" fill="none" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" aria-hidden className="absolute">
        <path d="M3 44V19A16 16 0 0 1 19 3h25M186 3h25a16 16 0 0 1 16 16v25M227 186v25a16 16 0 0 1-16 16h-25M44 227H19A16 16 0 0 1 3 211v-25" />
      </svg>
      {preview ? (
        <div className="pop relative size-[190px] overflow-hidden rounded-photo bg-white">
          <img src={preview} alt="" className="size-full object-contain" />
        </div>
      ) : (
        <p className="relative px-6 text-center text-[14px] font-medium text-white/80">{t('scanFrameHint')}</p>
      )}
      {reading && <span aria-hidden className="sweep absolute inset-x-10 top-[22px] h-0.5 rounded-pill bg-white" />}
    </div>
  )
}

export function ScanPage() {
  const { t, lang } = useI18n()
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string>('')
  const [candidate, setCandidate] = useState<Item | null>(null)
  const [patch, setPatch] = useState<ItemPatch>({})
  const [advice, setAdvice] = useState<BuyAdvice | null>(null)
  const [askedPrice, setAskedPrice] = useState<number | null>(null)
  const [busy, setBusy] = useState<'' | 'analyse' | 'verdict'>('')
  const [error, setError] = useState<unknown>(null)
  const [why, setWhy] = useState(false)
  const [priceText, setPriceText] = useState('')

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])
  // the verdict and the start are two screens: each opens at the top
  useEffect(() => { window.scrollTo(0, 0) }, [advice])

  // back to the start; a new photo keeps the price already typed
  const clearScan = () => {
    setFile(null); setPreview(''); setCandidate(null); setPatch({}); setAdvice(null); setError(null); setWhy(false)
  }
  const reset = () => {
    clearScan()
    setPriceText('')
  }

  // the price on the tag is optional: empty = unknown (never sent as 0)
  const price = Number(priceText.replace(',', '.'))
  const priceGiven = priceText.trim() !== ''
  const priceBad = priceGiven && !(price > 0)

  const analyse = async (f: File) => {
    clearScan()
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setBusy('analyse')
    try {
      setCandidate(await api.analyze(f))
    } catch (e) {
      setError(e)
    } finally {
      setBusy('')
    }
  }

  const askVerdict = async () => {
    if (!candidate) return
    setBusy('verdict')
    setError(null)
    try {
      setAdvice(await api.buyAdvice(candidate.id, Object.keys(patch).length ? patch : undefined,
        priceGiven ? price : undefined))
      setAskedPrice(priceGiven ? price : null)
    } catch (e) {
      setError(e)
    } finally {
      setBusy('')
    }
  }

  const name = (it: Item) => vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)

  // the verdict: its own heading (a round back button to the start and the piece's name), the tab bar gives way to
  // the Bought it / Left it bar. "Bought it" saves the scan into the wardrobe on the server (no second analysis).
  if (advice && candidate) {
    return (
      <Page title={name(candidate)} look="soft" header={false}>
        <div className="mx-auto flex max-w-[640px] flex-col gap-5">
          <div className="flex min-h-tap items-center gap-3">
            <button
              type="button"
              onClick={reset}
              aria-label={t('back')}
              className="press grid size-tap shrink-0 place-items-center rounded-pill bg-surface text-carbon focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              <ArrowLeft className="size-6 mirror-rtl" strokeWidth={1.75} aria-hidden />
            </button>
            <h1 className="min-w-0 text-[18px] font-semibold leading-6 text-carbon">{name(candidate)}</h1>
          </div>
          <VerdictCard advice={advice} candidatePhoto={candidate.image_url} price={askedPrice} showTryOn
            restart={{ label: t('scanAgain'), onClick: reset }} again={{ label: t('newScan'), onClick: reset }} />
        </div>
      </Page>
    )
  }

  return (
    <Page title={t('scanTitle')} look="soft">
      <div className="mx-auto flex max-w-[640px] flex-col gap-6">
        <p className="-mt-3 text-[16px] leading-6 text-carbon-soft">{t('scanHint')}</p>

        <CameraFrame preview={preview} reading={busy === 'analyse'} />

        {error ? (
          <ErrorNote error={error} message={t(candidate ? 'buyVerdictFailed' : 'buyAnalyseFailed')}
            onRetry={candidate ? askVerdict : file ? () => analyse(file) : undefined} />
        ) : null}

        {busy === 'analyse' && (
          <div role="status" className="flex flex-col gap-3 rounded-card bg-surface p-card">
            <p className="text-[18px] font-semibold text-carbon">{t('analysing')}</p>
            {CHECK_FIELDS.map((f) => <Skeleton key={f} className="h-6 w-full" />)}
          </div>
        )}

        {candidate && (
          <section className="rounded-card bg-surface px-card pb-card pt-4" aria-labelledby="check-title">
            <p className="text-[20px] font-semibold leading-tight text-carbon">{name(candidate)}</p>
            <h2 id="check-title" className="mt-3 text-[16px] font-semibold text-carbon">{t('checkFields')}</h2>
            <p className="mb-2 text-[13px] text-carbon-soft">{t('checkFieldsHint')}</p>
            <div className="divide-y divide-line">
              {CHECK_FIELDS.map((f) => (
                <FieldRow
                  key={f}
                  item={candidate}
                  field={f}
                  onSave={async (p) => {
                    setCandidate(applyPatch(candidate, p))
                    setPatch((old) => ({ ...old, ...p, ...(p.category && p.category !== candidate.category ? { sub_category: '' } : {}) }))
                  }}
                />
              ))}
            </div>
            <Button variant="quiet" className="mt-3" onClick={() => setWhy(!why)} aria-expanded={why}>
              <Lightbulb className="size-4" aria-hidden /> {why ? t('hideWhy') : t('whyLabels')}
            </Button>
            {why && <div className="mt-2 border-t border-line pt-4"><ExplainPanel target={{ candidateId: candidate.id }} /></div>}
          </section>
        )}

        {busy !== 'analyse' && (
          <TextField label={t('priceLabel')} hint={t('priceHint')} inputMode="decimal" value={priceText}
            error={priceBad ? t('priceInvalid') : undefined} onChange={(e) => setPriceText(e.target.value)} />
        )}

        {candidate ? (
          <Button className="w-full" busy={busy === 'verdict'} disabled={priceBad} onClick={askVerdict}>
            {busy === 'verdict' ? t('asking') : t('askVerdict')} <ArrowRight className="size-4 mirror-rtl" aria-hidden />
          </Button>
        ) : busy !== 'analyse' && (
          <PhotoPicker onPick={analyse} />
        )}

        {!file && (
          <div className="flex flex-col items-start">
            <Link to="/shop" className="inline-flex min-h-11 items-center gap-2 text-[15px] font-semibold text-carbon underline decoration-1 underline-offset-4">
              <ShoppingBag className="size-4" aria-hidden /> {t('scanShopLink')}
            </Link>
            <Link to="/sell" className="inline-flex min-h-11 items-center gap-2 text-[15px] font-semibold text-carbon underline decoration-1 underline-offset-4">
              <Tag className="size-4" aria-hidden /> {t('sellLink')}
            </Link>
          </div>
        )}
      </div>
    </Page>
  )
}
