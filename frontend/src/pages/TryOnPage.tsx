import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Download, ShieldAlert, Sparkles } from 'lucide-react'
import { api, ApiError, loadImage } from '../api/client'
import type { Category, Item, TryOnResult } from '../api/types'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { Button } from '../ui/controls'
import { ItemPhoto } from '../ui/ItemPhoto'
import { PhotoPicker } from '../ui/PhotoPicker'
import { Empty, ErrorNote, Skeleton } from '../ui/states'
import { useLoad } from '../useLoad'

// Same as the backend (app/tryon.py): which body part a category dresses, and
// the dressing order (a jacket goes on last, over the top). Other categories
// (shoes, bags, accessories) can't be tried on.
type Kind = 'upper' | 'lower' | 'overall'
const KIND: Partial<Record<Category, Kind>> = {
  top: 'upper', outerwear: 'upper', bottom: 'lower', dress: 'overall', traditional: 'overall', swimwear: 'overall',
}
const ORDER: Category[] = ['dress', 'traditional', 'swimwear', 'bottom', 'top', 'outerwear']

interface Piece { id: string; category: Category; sub_category: string; image_url: string }

/** /tryon?items=a,b (wardrobe ids) and/or ?candidate=c&ccat=dress (a scan). */
export function TryOnPage() {
  const { t, lang } = useI18n()
  const [params] = useSearchParams()
  const itemIds = (params.get('items') ?? '').split(',').filter(Boolean)
  const candidate = params.get('candidate')
  const candidateCat = params.get('ccat') as Category | null
  const items = useLoad(() => (itemIds.length ? api.items() : Promise.resolve([] as Item[])), [params.get('items')])

  const [person, setPerson] = useState<{ file: File; url: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<TryOnResult | null>(null)
  const [fallback, setFallback] = useState(false)
  const [why, setWhy] = useState('')            // the backend's reason, shown under the preview note
  const [error, setError] = useState<unknown>(null)

  useEffect(() => () => { if (person) URL.revokeObjectURL(person.url) }, [person])

  const pieces: Piece[] = [
    ...(items.data ?? []).filter((it) => itemIds.includes(it.id))
      .map((it) => ({ id: it.id, category: it.category, sub_category: it.sub_category, image_url: it.image_url ?? `/items/${it.id}/image` })),
    ...(candidate && candidateCat
      ? [{ id: candidate, category: candidateCat, sub_category: '', image_url: `/candidates/${candidate}/image` }]
      : []),
  ]
  const wearable = pieces.filter((p) => KIND[p.category]).sort((a, b) => ORDER.indexOf(a.category) - ORDER.indexOf(b.category))
  const label = (p: Piece) => vocab(SUB_LABELS, p.sub_category, lang) || vocab(CATEGORY_LABELS, p.category, lang)

  const pick = (file: File) => {
    setPerson({ file, url: URL.createObjectURL(file) })
    setResult(null)
    setFallback(false)
    setError(null)
  }

  const run = async () => {
    if (!person) return
    setBusy(true)
    setError(null)
    try {
      setResult(await api.tryOn(person.file, itemIds, candidate ?? undefined))
      setFallback(false)
    } catch (e) {
      // the AI is off (503), failed or over quota (502), or we're offline: show the 2D preview
      if (e instanceof ApiError && [0, 502, 503].includes(e.status)) {
        setFallback(true)
        setWhy(e.status === 0 ? '' : e.message)
      }
      else setError(e)
    } finally {
      setBusy(false)
    }
  }

  if (!itemIds.length && !candidate) {
    return (
      <Page title={t('tryOnTitle')}>
        <Empty title={t('tryOnNone')} body={t('tryOnNoneBody')}
          action={<Link to="/build" className="inline-flex min-h-11 items-center border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink">{t('navBuild')}</Link>} />
      </Page>
    )
  }

  return (
    <Page title={t('tryOnTitle')}>
      <section aria-labelledby="tryon-pieces" className="mb-5">
        <h2 id="tryon-pieces" className="mb-2 text-[13px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('tryOnPieces')}</h2>
        {items.error ? <ErrorNote error={items.error} onRetry={items.reload} /> : !items.data ? <Skeleton className="h-20" /> : (
          <ul className="flex flex-wrap gap-2">
            {pieces.map((p) => (
              <li key={p.id} className={`ticket p-1.5 ${KIND[p.category] ? '' : 'opacity-50'}`}>
                <ItemPhoto src={p.image_url} alt={label(p)} size={64} />
                <span className="mt-1 block max-w-16 truncate text-[12px] text-carbon">{label(p)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="mb-5 flex max-w-[60ch] items-start gap-2 text-[13px] text-carbon-soft">
        <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden /> {t('tryOnPrivacy')}
      </p>

      {!person ? (
        <div className="max-w-[440px]">
          <p className="mb-4 text-[15px] text-carbon-soft">{t('tryOnHint')}</p>
          <PhotoPicker onPick={pick} />
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
          <div>
            {result ? (
              <img src={result.image} alt={t('tryOnResultAlt')} className="w-full bg-white" />
            ) : fallback ? (
              <Overlay personUrl={person.url} pieces={wearable} />
            ) : (
              <img src={person.url} alt={t('tryOnYourPhoto')} className={`w-full bg-white ${busy ? 'animate-pulse' : ''}`} />
            )}
          </div>
          <div className="flex flex-col items-start gap-3" aria-live="polite">
            {busy && <p className="text-[15px] text-carbon">{t('tryOnWorking')}</p>}
            {fallback && !busy && <p className="max-w-[48ch] text-[15px] text-carbon">{t('tryOnFallback')}</p>}
            {fallback && !busy && why && (
              <details className="max-w-[48ch] text-[12px] text-carbon-soft">
                <summary className="cursor-pointer">{t('tryOnWhy')}</summary>
                <p className="mt-1 break-words font-mono" dir="ltr">{why}</p>
              </details>
            )}
            {result && (
              <>
                <p className="text-[13px] text-carbon-soft">{t('tryOnNote')}</p>
                {result.skipped.length > 0 && <p className="text-[14px] text-carbon-soft">{t('tryOnSkipped', { n: result.skipped.length })}</p>}
                {result.failed.length > 0 && <p className="text-[14px] text-carbon">{t('tryOnFailed', { n: result.failed.length })}</p>}
              </>
            )}
            {error ? <ErrorNote error={error} /> : null}
            {!result && (
              <Button busy={busy} onClick={run} disabled={!wearable.length}>
                <Sparkles className="size-4" aria-hidden /> {fallback ? t('tryOnRetryAi') : t('tryOnBtn')}
              </Button>
            )}
            {result && (
              <a href={result.image} download="dressme-tryon.jpg" className="inline-flex min-h-11 items-center gap-2 border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink">
                <Download className="size-4" aria-hidden /> {t('tryOnSave')}
              </a>
            )}
            <Button variant="quiet" disabled={busy} onClick={() => { setPerson(null); setResult(null); setFallback(false) }}>
              {t('tryOnChange')}
            </Button>
          </div>
        </div>
      )}
    </Page>
  )
}

// ------------------------------------------------------------------ 2D overlay
// The fallback when the AI is unavailable: the cleaned item photos (on white)
// laid over the person photo. "multiply" blending makes their white
// background disappear. Positions are % of the photo; each piece can be dragged
// and resized. Not realistic, but instant, offline and private.
interface Placed { id: string; url: string; x: number; y: number; w: number }
const START: Record<Kind, { x: number; y: number; w: number }> = {
  upper: { x: 50, y: 36, w: 52 }, lower: { x: 50, y: 68, w: 42 }, overall: { x: 50, y: 52, w: 56 },
}

function Overlay({ personUrl, pieces }: { personUrl: string; pieces: Piece[] }) {
  const { t } = useI18n()
  const box = useRef<HTMLDivElement>(null)
  const drag = useRef<{ id: string; px: number; py: number; x: number; y: number } | null>(null)
  const [placed, setPlaced] = useState<Placed[]>([])
  const [active, setActive] = useState<string | null>(null)
  const key = pieces.map((p) => p.id).join(',')

  useEffect(() => {
    let alive = true
    Promise.all(pieces.map(async (p) => ({ id: p.id, url: await loadImage(p.image_url), ...START[KIND[p.category]!] })))
      .then((list) => {
        if (!alive) return
        setPlaced(list)
        setActive(list.at(-1)?.id ?? null)
      })
      .catch(() => alive && setPlaced([]))
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const move = (e: React.PointerEvent) => {
    const d = drag.current
    const rect = box.current?.getBoundingClientRect()
    if (!d || !rect) return
    const x = d.x + ((e.clientX - d.px) / rect.width) * 100
    const y = d.y + ((e.clientY - d.py) / rect.height) * 100
    setPlaced((all) => all.map((p) => (p.id === d.id ? { ...p, x, y } : p)))
  }
  const current = placed.find((p) => p.id === active)

  return (
    <div>
      <div ref={box} className="relative touch-none select-none overflow-hidden bg-white" onPointerMove={move}
        onPointerUp={() => { drag.current = null }} onPointerCancel={() => { drag.current = null }}>
        <img src={personUrl} alt={t('tryOnYourPhoto')} className="block w-full" draggable={false} />
        {placed.map((p) => (
          <img key={p.id} src={p.url} alt="" draggable={false}
            className={`absolute cursor-grab mix-blend-multiply ${p.id === active ? 'outline-1 outline-dashed outline-ink' : ''}`}
            style={{ left: `${p.x}%`, top: `${p.y}%`, width: `${p.w}%`, transform: 'translate(-50%, -50%)' }}
            onPointerDown={(e) => {
              e.currentTarget.parentElement?.setPointerCapture(e.pointerId)
              setActive(p.id)
              drag.current = { id: p.id, px: e.clientX, py: e.clientY, x: p.x, y: p.y }
            }} />
        ))}
      </div>
      {current && (
        <label className="mt-3 flex items-center gap-3 text-[13px] text-carbon-soft">
          {t('tryOnSize')}
          <input type="range" min={15} max={100} value={current.w} className="flex-1 accent-ink"
            onChange={(e) => {
              const w = Number(e.target.value)
              setPlaced((all) => all.map((p) => (p.id === current.id ? { ...p, w } : p)))
            }} />
        </label>
      )}
    </div>
  )
}
