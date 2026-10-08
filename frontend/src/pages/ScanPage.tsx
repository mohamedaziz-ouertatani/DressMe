import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Lightbulb, Plus, ScanLine, Search, ShoppingBag, Sparkles, Tag } from 'lucide-react'
import { api } from '../api/client'
import type { BuyAdvice, Item, ItemPatch } from '../api/types'
import { useI18n } from '../i18n'
import { plural } from '../i18n/plurals'
import { CATEGORY_LABELS, SUB_LABELS, secondLine, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { Button } from '../ui/controls'
import { ExplainPanel } from '../ui/ExplainPanel'
import { FieldRow } from '../ui/Field'
import { ItemPhoto } from '../ui/ItemPhoto'
import { OutfitStrip } from '../ui/OutfitStrip'
import { VerdictWhy } from '../ui/VerdictWhy'
import { PhotoPicker } from '../ui/PhotoPicker'
import { Stamp } from '../ui/Stamp'
import { ErrorNote, Skeleton } from '../ui/states'
import { SecondLine, Serial, Ticket } from '../ui/ticket'

const CHECK_FIELDS = ['category', 'sub_category', 'colour', 'pattern'] as const

/** Apply a correction locally (the candidate is only saved with the verdict request). */
function applyPatch(item: Item, patch: ItemPatch): Item {
  const next = { ...item, ...patch } as Item
  if (patch.category && patch.category !== item.category && !patch.sub_category) next.sub_category = ''
  next.corrected = Array.from(new Set([...item.corrected, ...Object.keys(patch), ...(next.sub_category !== item.sub_category ? ['sub_category'] : [])]))
  return next
}

export function ScanPage() {
  const { t, lang, reason } = useI18n()
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string>('')
  const [candidate, setCandidate] = useState<Item | null>(null)
  const [patch, setPatch] = useState<ItemPatch>({})
  const [advice, setAdvice] = useState<BuyAdvice | null>(null)
  const [busy, setBusy] = useState<'' | 'analyse' | 'verdict' | 'add'>('')
  const [error, setError] = useState<unknown>(null)
  const [why, setWhy] = useState(false)

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  const reset = () => {
    setFile(null); setPreview(''); setCandidate(null); setPatch({}); setAdvice(null); setError(null); setWhy(false)
  }

  const analyse = async (f: File) => {
    reset()
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
      setAdvice(await api.buyAdvice(candidate.id, Object.keys(patch).length ? patch : undefined))
    } catch (e) {
      setError(e)
    } finally {
      setBusy('')
    }
  }

  const addToWardrobe = async () => {
    if (!file) return
    setBusy('add')
    try {
      const item = await api.addItem(file)
      if (Object.keys(patch).length) await api.updateItem(item.id, patch)
      navigate(`/wardrobe/${item.id}`)
    } catch (e) {
      setError(e)
      setBusy('')
    }
  }

  const name = (it: Item) => vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)

  return (
    <Page title={t('scanTitle')}>
      <div className="mx-auto max-w-[640px]">
        {!file && (
          <div className="ticket flex flex-col gap-5 px-5 py-6">
            <div className="flex items-start gap-4">
              <ScanLine className="mt-1 size-8 shrink-0 text-ink" aria-hidden />
              <p className="text-[16px] leading-relaxed text-carbon">{t('scanHint')}</p>
            </div>
            <PhotoPicker onPick={analyse} />
            <Link to="/shop" className="inline-flex min-h-11 items-center gap-2 self-start text-[15px] text-ink underline decoration-1 underline-offset-4">
              <ShoppingBag className="size-4" aria-hidden /> {t('scanShopLink')}
            </Link>
            <Link to="/sell" className="-mt-3 inline-flex min-h-11 items-center gap-2 self-start text-[15px] text-ink underline decoration-1 underline-offset-4">
              <Tag className="size-4" aria-hidden /> {t('sellLink')}
            </Link>
          </div>
        )}

        {file && (
          <Ticket
            className="relative"
            stub={candidate ? <Serial id={candidate.id} prefix="№" className="[writing-mode:vertical-rl]" /> : undefined}
          >
            <div className="flex items-end gap-4 p-3">
              <ItemPhoto src={preview} alt="" size={132} />
              <div className="min-w-0 pb-1">
                {candidate ? (
                  <>
                    <p className="text-[20px] font-semibold leading-tight text-carbon">{name(candidate)}</p>
                    <SecondLine>{secondLine(SUB_LABELS, candidate.sub_category, lang) || secondLine(CATEGORY_LABELS, candidate.category, lang)}</SecondLine>
                  </>
                ) : busy === 'analyse' ? (
                  <p className="text-[15px] text-carbon-soft" aria-live="polite">{t('analysing')}</p>
                ) : null}
              </div>
            </div>
            {advice && (
              <div className="pointer-events-none absolute -top-4 end-14 sm:end-20">
                <Stamp
                  big={t(`verdict_${advice.verdict}`)}
                  ring="DRESSME · VALIDÉ · مصادق · DRESSME · VALIDÉ ·"
                  size={118}
                  angle={-11}
                  land
                  label={t(`verdict_${advice.verdict}`)}
                />
              </div>
            )}
          </Ticket>
        )}

        {error ? <div className="mt-4"><ErrorNote error={error} onRetry={candidate ? askVerdict : file ? () => analyse(file) : undefined} /></div> : null}

        {busy === 'analyse' && (
          <div className="ticket mt-3 space-y-3 px-4 py-4">
            {CHECK_FIELDS.map((f) => <Skeleton key={f} className="h-6 w-full" />)}
          </div>
        )}

        {candidate && !advice && (
          <section className="ticket mt-3 px-4 pb-4 pt-3" aria-labelledby="check-title">
            <h2 id="check-title" className="text-[16px] font-semibold text-carbon">{t('checkFields')}</h2>
            <p className="mb-2 text-[13px] text-carbon-soft">{t('checkFieldsHint')}</p>
            <div className="divide-y divide-perf/40">
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
            {why && <div className="mt-2 border-t border-perf/40 pt-4"><ExplainPanel target={{ candidateId: candidate.id }} /></div>}
            <Button className="mt-4 w-full" busy={busy === 'verdict'} onClick={askVerdict}>
              {busy === 'verdict' ? t('asking') : t('askVerdict')} <ArrowRight className="size-4 mirror-rtl" aria-hidden />
            </Button>
          </section>
        )}

        {advice && (
          <section className="mt-4" aria-live="polite">
            <p className="text-[18px] font-medium leading-snug text-carbon">
              {t(`verdictLine_${advice.verdict}`, { outfits: plural('goodOutfits', advice.good_outfits, lang) })}
            </p>
            {advice.reasons.length > 0 && (
              <ul className="mt-2 space-y-1 text-[15px] text-carbon-soft">
                {advice.reasons.map((r) => <li key={r}>{reason(r)}</li>)}
              </ul>
            )}
            {advice.explanation && <VerdictWhy explanation={advice.explanation} />}

            <div className="mt-5 flex flex-wrap gap-2">
              <Link to={`/similar?candidate=${advice.candidate.id}`} className="inline-flex min-h-11 items-center gap-2 border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink">
                <Search className="size-4" aria-hidden /> {t('seeSimilar')}
              </Link>
              <Link to={`/tryon?candidate=${advice.candidate.id}&ccat=${advice.candidate.category}`} className="inline-flex min-h-11 items-center gap-2 border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink">
                <Sparkles className="size-4" aria-hidden /> {t('tryOnBtn')}
              </Link>
              <Button variant="secondary" onClick={reset}>
                <ScanLine className="size-4" aria-hidden /> {t('newScan')}
              </Button>
              <Button variant="quiet" busy={busy === 'add'} onClick={addToWardrobe}>
                <Plus className="size-4" aria-hidden /> {t('addToWardrobe')}
              </Button>
            </div>

            {advice.best.length > 0 && (
              <div className="mt-8">
                <h2 className="mb-4 text-[18px] font-semibold text-carbon">{t('bestOutfits')}</h2>
                <div className="grid gap-10 pt-4 sm:grid-cols-2">
                  {advice.best.slice(0, 2).map((o, i) => (
                    <OutfitStrip key={i} outfit={o} compact photoOf={(id) => (id === advice.candidate.id ? preview : undefined)} />
                  ))}
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </Page>
  )
}

