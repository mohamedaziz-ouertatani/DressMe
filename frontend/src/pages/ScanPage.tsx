import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight, ChevronDown, Lightbulb, ShoppingBag, Tag, X } from 'lucide-react'
import { api } from '../api/client'
import type { BuyAdvice, Item, ItemPatch } from '../api/types'
import { useI18n } from '../i18n'
import { plural } from '../i18n/plurals'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { Button, TextField } from '../ui/controls'
import { ExplainPanel } from '../ui/ExplainPanel'
import { FieldRow } from '../ui/Field'
import { VERDICT_PILL, VerdictCard } from '../ui/VerdictCard'
import { PhotoPicker } from '../ui/PhotoPicker'
import { ErrorNote, Skeleton } from '../ui/states'

const CHECK_FIELDS = ['category', 'sub_category', 'colour', 'pattern'] as const

/** How many pieces one scan can hold: each photo takes ~3-5 s to clean and read on the server. */
const MAX_PIECES = 5

/** One photo of the scan, from the pick to its verdict. The photos are read one after the other (`waiting` →
 *  `reading` → `ready` or `failed`); `error` holds the last failure, of the reading or of the verdict. */
type Piece = {
  key: number
  file: File
  preview: string
  status: 'waiting' | 'reading' | 'ready' | 'failed'
  candidate: Item | null
  patch: ItemPatch                // the user's corrections, sent with the verdict request
  priceText: string
  advice: BuyAdvice | null
  askedPrice: number | null       // the price the verdict was asked with (null = none given)
  error: unknown
}

/** Apply a correction locally (the candidate is only saved with the verdict request). */
function applyPatch(item: Item, patch: ItemPatch): Item {
  const next = { ...item, ...patch } as Item
  if (patch.category && patch.category !== item.category && !patch.sub_category) next.sub_category = ''
  next.corrected = Array.from(new Set([...item.corrected, ...Object.keys(patch), ...(next.sub_category !== item.sub_category ? ['sub_category'] : [])]))
  return next
}

/** The price on the tag is optional: empty = unknown (never sent as 0). */
function readPrice(text: string) {
  const price = Number(text.replace(',', '.'))
  const given = text.trim() !== ''
  return { price, given, bad: given && !(price > 0) }
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

/** The label checks of one piece: its four fields and "Why these labels?". */
function CheckFields({ piece, onPatch }: { piece: Piece; onPatch: (p: ItemPatch) => void }) {
  const { t } = useI18n()
  const [why, setWhy] = useState(false)
  const candidate = piece.candidate!
  return (
    <>
      <div className="divide-y divide-line">
        {CHECK_FIELDS.map((f) => (
          <FieldRow key={f} item={candidate} field={f} onSave={async (p) => onPatch(p)} />
        ))}
      </div>
      <Button variant="quiet" className="mt-3" onClick={() => setWhy(!why)} aria-expanded={why}>
        <Lightbulb className="size-4" aria-hidden /> {why ? t('hideWhy') : t('whyLabels')}
      </Button>
      {why && <div className="mt-2 border-t border-line pt-4"><ExplainPanel target={{ candidateId: candidate.id }} /></div>}
    </>
  )
}

/** One piece in the list of a scan with several pieces: its photo, its name (or that it is being read, or failed),
 *  remove, and behind "Check labels and price" the same checks as a single scan plus its own price. */
function PieceCard({ piece, name, onRemove, onRetry, onPatch, onPrice }: {
  piece: Piece
  name: string
  onRemove: () => void
  onRetry: () => void
  onPatch: (p: ItemPatch) => void
  onPrice: (text: string) => void
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const priceBad = readPrice(piece.priceText).bad
  return (
    <li className="rounded-card bg-surface p-4">
      <div className="flex items-center gap-3">
        <span className="grid size-16 shrink-0 place-items-center overflow-hidden rounded-tile bg-white">
          <img src={piece.preview} alt="" className="size-full object-contain" />
        </span>
        <div className="min-w-0 flex-1">
          {piece.status === 'ready' ? (
            <p className="text-[17px] font-semibold text-carbon">{name}</p>
          ) : piece.status === 'failed' ? (
            <p className="text-[15px] text-carbon">{t('buyAnalyseFailed')}</p>
          ) : (
            <div role="status" className="flex flex-col gap-2">
              <p className="text-[15px] text-carbon-soft">{piece.status === 'reading' ? t('scanPieceReading') : t('analysing')}</p>
              <Skeleton className="h-4 w-2/3" />
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={onRemove}
          aria-label={t('scanRemovePiece')}
          className="press grid size-tap shrink-0 place-items-center rounded-pill text-carbon-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          <X className="size-5" aria-hidden />
        </button>
      </div>

      {piece.status === 'failed' && <Button variant="quiet" className="mt-2" onClick={onRetry}>{t('retry')}</Button>}

      {piece.status === 'ready' && (
        <>
          {piece.error ? <div className="mt-3"><ErrorNote error={piece.error} message={t('buyVerdictFailed')} /></div> : null}
          <Button variant="quiet" className="mt-2" onClick={() => setOpen(!open)} aria-expanded={open}>
            <ChevronDown className={`size-4 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden /> {t('scanCheckPiece')}
          </Button>
          {(open || priceBad) && (
            <div className="mt-2 flex flex-col gap-4 border-t border-line pt-3">
              {open && <CheckFields piece={piece} onPatch={onPatch} />}
              <TextField label={t('priceLabel')} hint={t('priceHint')} inputMode="decimal" value={piece.priceText}
                error={priceBad ? t('priceInvalid') : undefined} onChange={(e) => onPrice(e.target.value)} />
            </div>
          )}
        </>
      )}
    </li>
  )
}

export function ScanPage() {
  const { t, lang } = useI18n()
  const [pieces, setPieces] = useState<Piece[]>([])
  const [draftPrice, setDraftPrice] = useState('')     // a price typed before any photo: the first piece takes it
  const [asking, setAsking] = useState(false)
  const [compare, setCompare] = useState(false)        // several pieces: the list of verdicts
  const [openKey, setOpenKey] = useState<number | null>(null)   // several pieces: the one whose verdict is open
  const [tooMany, setTooMany] = useState(false)
  const nextKey = useRef(1)

  // the photos' previews are freed with the page
  const live = useRef(pieces)
  live.current = pieces
  useEffect(() => () => live.current.forEach((p) => URL.revokeObjectURL(p.preview)), [])

  const update = (key: number, change: Partial<Piece> | ((p: Piece) => Partial<Piece>)) =>
    setPieces((old) => old.map((p) => (p.key === key ? { ...p, ...(typeof change === 'function' ? change(p) : change) } : p)))

  // read the photos one after the other: the server cleans each one (~3-5 s), so they are not sent all at once
  useEffect(() => {
    if (pieces.some((p) => p.status === 'reading')) return
    const next = pieces.find((p) => p.status === 'waiting')
    if (!next) return
    update(next.key, { status: 'reading', error: null })
    api.analyze(next.file).then(
      (candidate) => update(next.key, { status: 'ready', candidate }),
      (error) => update(next.key, { status: 'failed', error }),
    )
  }, [pieces])

  const multi = pieces.length > 1
  const single = pieces.length === 1 ? pieces[0] : null
  const open = openKey !== null ? pieces.find((p) => p.key === openKey) : single
  const view = open?.advice ? `verdict-${open.key}` : compare && multi ? 'compare' : 'start'
  // the verdict, the list and the start are separate screens: each opens at the top
  useEffect(() => { window.scrollTo(0, 0) }, [view])

  const newPiece = (file: File, priceText: string): Piece => ({
    key: nextKey.current++, file, preview: URL.createObjectURL(file), status: 'waiting',
    candidate: null, patch: {}, priceText, advice: null, askedPrice: null, error: null,
  })

  // add photos to the scan, at most MAX_PIECES in all (the first piece takes a price typed before it)
  const addFiles = (files: File[], base = pieces, firstPrice = draftPrice) => {
    const room = MAX_PIECES - base.length
    setTooMany(files.length > room)
    const added = files.slice(0, Math.max(0, room)).map((f, i) => newPiece(f, base.length === 0 && i === 0 ? firstPrice : ''))
    setPieces([...base, ...added])
  }

  // a single scan whose photo failed: the new photos replace it and keep the price already typed
  const replaceWith = (files: File[]) => {
    pieces.forEach((p) => URL.revokeObjectURL(p.preview))
    addFiles(files, [], single?.priceText ?? draftPrice)
  }

  const remove = (key: number) => {
    const gone = pieces.find((p) => p.key === key)
    if (gone) URL.revokeObjectURL(gone.preview)
    setPieces((old) => old.filter((p) => p.key !== key))
    setTooMany(false)
  }

  // back to the start
  const reset = () => {
    pieces.forEach((p) => URL.revokeObjectURL(p.preview))
    setPieces([]); setCompare(false); setOpenKey(null); setTooMany(false); setDraftPrice('')
  }

  const patchPiece = (key: number, p: ItemPatch) => update(key, (piece) => ({
    candidate: applyPatch(piece.candidate!, p),
    patch: { ...piece.patch, ...p, ...(p.category && p.category !== piece.candidate!.category ? { sub_category: '' } : {}) },
  }))

  // ask the verdict of every piece that is read and has none yet, one after the other
  const askVerdicts = async () => {
    setAsking(true)
    for (const p of pieces.filter((x) => x.status === 'ready' && !x.advice)) {
      const { price, given } = readPrice(p.priceText)
      update(p.key, { error: null })
      try {
        const advice = await api.buyAdvice(p.candidate!.id, Object.keys(p.patch).length ? p.patch : undefined, given ? price : undefined)
        update(p.key, { advice, askedPrice: given ? price : null })
      } catch (e) {
        update(p.key, { error: e })
      }
    }
    setAsking(false)
    if (multi) setCompare(true)
  }

  const name = (it: Item) => vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)
  const number = new Intl.NumberFormat(lang === 'ar' ? 'ar-TN' : lang)
  const anyBadPrice = pieces.some((p) => p.status === 'ready' && readPrice(p.priceText).bad)
  const stillReading = pieces.some((p) => p.status === 'waiting' || p.status === 'reading')
  const readyCount = pieces.filter((p) => p.status === 'ready').length
  const link = 'inline-flex min-h-11 items-center gap-2 text-[15px] font-semibold text-carbon underline decoration-1 underline-offset-4'

  // a verdict: its own heading (a round back button and the piece's name), the tab bar gives way to the
  // Bought it / Left it bar. "Bought it" saves the scan into the wardrobe on the server (no second analysis).
  // With several pieces, back returns to the list of verdicts.
  if (open?.advice && open.candidate) {
    const back = multi ? () => setOpenKey(null) : reset
    return (
      <Page title={name(open.candidate)} look="soft" header={false}>
        <div className="mx-auto flex max-w-[640px] flex-col gap-5">
          <div className="flex min-h-tap items-center gap-3">
            <button
              type="button"
              onClick={back}
              aria-label={multi ? t('scanBackToPieces') : t('back')}
              className="press grid size-tap shrink-0 place-items-center rounded-pill bg-surface text-carbon focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              <ArrowLeft className="size-6 mirror-rtl" strokeWidth={1.75} aria-hidden />
            </button>
            <h1 className="min-w-0 text-[18px] font-semibold leading-6 text-carbon">{name(open.candidate)}</h1>
          </div>
          <VerdictCard key={open.key} advice={open.advice} candidatePhoto={open.candidate.image_url} price={open.askedPrice} showTryOn
            restart={{ label: t('scanAgain'), onClick: reset }}
            again={multi ? { label: t('scanBackToPieces'), onClick: back } : { label: t('newScan'), onClick: reset }} />
        </div>
      </Page>
    )
  }

  // several pieces, verdicts asked: one row per piece, the best first; tap one for its full verdict
  if (view === 'compare') {
    const order = [...pieces].sort((a, b) => (b.advice?.good_outfits ?? -1) - (a.advice?.good_outfits ?? -1))
    return (
      <Page title={t('scanCompareTitle')} look="soft">
        <div className="mx-auto flex max-w-[640px] flex-col gap-5">
          <p className="-mt-3 text-[16px] leading-6 text-carbon-soft">{t('scanCompareHint')}</p>
          <ul className="flex flex-col gap-3">
            {order.map((p) => {
              const pill = p.advice ? VERDICT_PILL[p.advice.verdict] : null
              return (
                <li key={p.key}>
                  <div className="flex items-center gap-3 rounded-card bg-surface p-4">
                    <span className="grid size-16 shrink-0 place-items-center overflow-hidden rounded-tile bg-white">
                      <img src={p.preview} alt="" className="size-full object-contain" />
                    </span>
                    {p.advice && pill ? (
                      <button type="button" onClick={() => setOpenKey(p.key)}
                        className="press flex min-w-0 flex-1 items-center gap-3 text-start focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
                        <span className="min-w-0 flex-1">
                          <span className="block text-[17px] font-semibold text-carbon">{name(p.advice.candidate)}</span>
                          <span className="block text-[14px] text-carbon-soft">
                            {plural('goodOutfits', p.advice.good_outfits, lang)} · {p.askedPrice !== null ? t('verdictPrice', { p: number.format(p.askedPrice) }) : t('verdictNoPrice')}
                          </span>
                        </span>
                        <span className={`inline-flex h-9 shrink-0 items-center gap-1.5 rounded-pill pe-3 ps-2.5 text-[15px] font-semibold ${pill.look}`}>
                          <pill.icon className="size-4" strokeWidth={2.25} aria-hidden /> {t(`verdict_${p.advice.verdict}`)}
                        </span>
                        <ArrowRight className="size-4 shrink-0 text-carbon-soft mirror-rtl" aria-hidden />
                      </button>
                    ) : (
                      <div className="min-w-0 flex-1">
                        <p className="text-[15px] text-carbon">{p.candidate ? name(p.candidate) : t('buyAnalyseFailed')}</p>
                        {p.candidate && <ErrorNote error={p.error} message={t('buyVerdictFailed')} onRetry={asking ? undefined : askVerdicts} />}
                      </div>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
          <Button variant="secondary" className="w-full" onClick={reset}>{t('scanStartOver')}</Button>
        </div>
      </Page>
    )
  }

  const addMore = pieces.length < MAX_PIECES && (
    <section aria-label={t('scanAddPiece')} className="flex flex-col gap-2">
      <p className="text-[14px] font-medium text-carbon">{t('scanAddPiece')}</p>
      <PhotoPicker onPick={(f) => addFiles([f])} onPickMany={addFiles} />
    </section>
  )
  const tooManyNote = tooMany && <p role="status" className="text-[14px] text-carbon-soft">{t('scanTooMany', { n: MAX_PIECES })}</p>

  // several pieces, before the verdicts: the list, add more, then one button for all the verdicts
  if (multi) {
    return (
      <Page title={t('scanTitle')} look="soft">
        <div className="mx-auto flex max-w-[640px] flex-col gap-6">
          <p className="-mt-3 text-[16px] leading-6 text-carbon-soft">{plural('pieces', pieces.length, lang)}</p>
          <ul className="flex flex-col gap-3">
            {pieces.map((p) => (
              <PieceCard key={p.key} piece={p} name={p.candidate ? name(p.candidate) : ''}
                onRemove={() => remove(p.key)} onRetry={() => update(p.key, { status: 'waiting', error: null })}
                onPatch={(patch) => patchPiece(p.key, patch)} onPrice={(text) => update(p.key, { priceText: text })} />
            ))}
          </ul>
          {tooManyNote}
          <Button className="w-full" busy={asking} disabled={stillReading || anyBadPrice || readyCount === 0} onClick={askVerdicts}>
            {asking ? t('asking') : t('askVerdicts')} <ArrowRight className="size-4 mirror-rtl" aria-hidden />
          </Button>
          {addMore}
        </div>
      </Page>
    )
  }

  // no piece or one piece: the single scan as before, with a way to add more pieces
  const reading = single?.status === 'waiting' || single?.status === 'reading'
  const candidate = single?.status === 'ready' ? single.candidate : null
  const priceText = single ? single.priceText : draftPrice
  const setPrice = (text: string) => (single ? update(single.key, { priceText: text }) : setDraftPrice(text))
  const priceBad = readPrice(priceText).bad

  return (
    <Page title={t('scanTitle')} look="soft">
      <div className="mx-auto flex max-w-[640px] flex-col gap-6">
        <p className="-mt-3 text-[16px] leading-6 text-carbon-soft">{t('scanHint')}</p>

        <CameraFrame preview={single?.preview ?? ''} reading={reading} />

        {single?.error ? (
          <ErrorNote error={single.error} message={t(candidate ? 'buyVerdictFailed' : 'buyAnalyseFailed')}
            onRetry={candidate ? askVerdicts : () => update(single.key, { status: 'waiting', error: null })} />
        ) : null}

        {reading && (
          <div role="status" className="flex flex-col gap-3 rounded-card bg-surface p-card">
            <p className="text-[18px] font-semibold text-carbon">{t('analysing')}</p>
            {CHECK_FIELDS.map((f) => <Skeleton key={f} className="h-6 w-full" />)}
          </div>
        )}

        {single && candidate && (
          <section className="rounded-card bg-surface px-card pb-card pt-4" aria-labelledby="check-title">
            <p className="text-[20px] font-semibold leading-tight text-carbon">{name(candidate)}</p>
            <h2 id="check-title" className="mt-3 text-[16px] font-semibold text-carbon">{t('checkFields')}</h2>
            <p className="mb-2 text-[13px] text-carbon-soft">{t('checkFieldsHint')}</p>
            <CheckFields piece={single} onPatch={(p) => patchPiece(single.key, p)} />
          </section>
        )}

        {!reading && (
          <TextField label={t('priceLabel')} hint={t('priceHint')} inputMode="decimal" value={priceText}
            error={priceBad ? t('priceInvalid') : undefined} onChange={(e) => setPrice(e.target.value)} />
        )}

        {candidate ? (
          <>
            <Button className="w-full" busy={asking} disabled={priceBad} onClick={askVerdicts}>
              {asking ? t('asking') : t('askVerdict')} <ArrowRight className="size-4 mirror-rtl" aria-hidden />
            </Button>
            {addMore}
          </>
        ) : !reading && (
          <>
            {/* a failed photo is replaced by the next one */}
            <PhotoPicker onPick={(f) => replaceWith([f])} onPickMany={replaceWith} />
            {tooManyNote}
            {!single && <p className="-mt-3 text-[14px] text-carbon-soft">{t('scanManyHint', { n: MAX_PIECES })}</p>}
          </>
        )}

        {!single && (
          <div className="flex flex-col items-start">
            <Link to="/shop" className={link}>
              <ShoppingBag className="size-4" aria-hidden /> {t('scanShopLink')}
            </Link>
            <Link to="/sell" className={link}>
              <Tag className="size-4" aria-hidden /> {t('sellLink')}
            </Link>
          </div>
        )}
      </div>
    </Page>
  )
}
