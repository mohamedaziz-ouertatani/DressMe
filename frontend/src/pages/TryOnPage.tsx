import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { Camera, Download, Lightbulb, ShieldAlert, ShieldCheck, Sparkles, Sun, User } from 'lucide-react'
import { api, loadImage } from '../api/client'
import type { Category, Item } from '../api/types'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { CompareSlider } from '../ui/CompareSlider'
import { Button } from '../ui/controls'
import { ItemPhoto } from '../ui/ItemPhoto'
import { PhotoPicker } from '../ui/PhotoPicker'
import { Empty, ErrorNote, Skeleton } from '../ui/states'
import { clock } from '../ui/TryOnProgress'
import { useTryOn } from '../tryon'
import { useLoad } from '../useLoad'

// Same as the backend (app/tryon.py): which body part a piece dresses, and the
// dressing order (a jacket over the top, shoes over the hems, glasses last). Shoes and
// glasses only when the engine can (GET /tryon/info `kinds`); bags, belts, jewellery never.
type Kind = 'upper' | 'lower' | 'overall' | 'shoes' | 'glasses' | 'scarf'
const KIND: Partial<Record<Category, Kind>> = {
  top: 'upper', outerwear: 'upper', bottom: 'lower', dress: 'overall', traditional: 'overall', swimwear: 'overall',
  shoes: 'shoes',
}
const ORDER: Category[] = ['dress', 'traditional', 'swimwear', 'bottom', 'top', 'outerwear', 'shoes', 'accessory']
const BASIC_KINDS: Kind[] = ['upper', 'lower', 'overall']

function kindOf(p: { category: Category; sub_category: string }): Kind | undefined {
  if (p.category === 'accessory') {
    if (['glasses', 'sunglasses'].includes(p.sub_category)) return 'glasses'
    return p.sub_category === 'scarf' ? 'scarf' : undefined
  }
  return KIND[p.category]
}

interface Piece { id: string; category: Category; sub_category: string; image_url: string }

/** /tryon?items=a,b (wardrobe ids) and/or ?candidate=c&ccat=dress (a scan). */
export function TryOnPage() {
  const { t, lang } = useI18n()
  const [params] = useSearchParams()
  const itemIds = (params.get('items') ?? '').split(',').filter(Boolean)
  const candidate = params.get('candidate')
  const candidateCat = params.get('ccat') as Category | null
  const lookMode = params.get('look') === '1'          // /tryon?look=1: a whole outfit from a photo
  const items = useLoad(() => (itemIds.length ? api.items() : Promise.resolve([] as Item[])), [params.get('items')])

  const info = useLoad(() => api.tryOnInfo(), [])   // engine on? photo private? time per piece

  // the try-on itself lives above the pages (tryon.tsx), so it keeps running while the
  // user browses; this page shows it when it was started from here (same ?items=)
  const location = useLocation()
  const here = location.pathname + location.search
  const tryon = useTryOn()
  const job = tryon.job?.backTo === here ? tryon.job : null
  const [picked, setPicked] = useState<{ file: File; url: string } | null>(null)
  const [offline2d, setOffline2d] = useState(false)   // the AI is switched off: 2D preview at once

  useEffect(() => () => { if (picked) URL.revokeObjectURL(picked.url) }, [picked])
  const [look, setLook] = useState<{ file: File; url: string } | null>(null)
  useEffect(() => () => { if (look) URL.revokeObjectURL(look.url) }, [look])

  const pieces: Piece[] = [
    ...(items.data ?? []).filter((it) => itemIds.includes(it.id))
      .map((it) => ({ id: it.id, category: it.category, sub_category: it.sub_category, image_url: it.image_url ?? `/items/${it.id}/image` })),
    ...(candidate && candidateCat
      ? [{ id: candidate, category: candidateCat, sub_category: '', image_url: `/candidates/${candidate}/image` }]
      : []),
  ]
  // what the AI can put on (shoes / glasses only with the local engine); the 2D preview
  // can lay out anything that has a body part
  const kinds: string[] = info.data?.kinds?.length ? info.data.kinds : BASIC_KINDS
  const canWear = (p: Piece) => { const k = kindOf(p); return !!k && kinds.includes(k) }
  const byOrder = (a: Piece, b: Piece) => ORDER.indexOf(a.category) - ORDER.indexOf(b.category)
  const wearable = pieces.filter(canWear).sort(byOrder)
  const previewable = pieces.filter((p) => kindOf(p)).sort(byOrder)
  const label = (p: Piece) => vocab(SUB_LABELS, p.sub_category, lang) || vocab(CATEGORY_LABELS, p.category, lang)

  const secondsPer = info.data?.seconds_per_garment ?? 60
  const ready = lookMode ? !!look : wearable.length > 0           // something to put on
  // a look is two passes in the service: its shoes, then its clothes
  const estimateMin = Math.max(1, Math.round(((lookMode ? 2 : wearable.length) * secondsPer) / 60))

  // what is on screen: the try-on's own photo once started, else the photo just picked
  const personUrl = job?.personUrl ?? picked?.url
  const running = job?.state === 'running'
  const result = job?.state === 'done' ? job.result : undefined
  const fallback = job?.state === 'fallback' || offline2d

  const pick = (file: File) => {
    if (job) tryon.dismiss()
    setPicked({ file, url: URL.createObjectURL(file) })
    // the AI is switched off: no point waiting, go straight to the 2D preview
    setOffline2d(Boolean(info.data && !info.data.enabled))
  }

  const run = () => {
    const person = job?.person ?? picked?.file
    if (!person) return
    tryon.start({
      backTo: here, person, secondsPer, itemIds, candidate: candidate ?? undefined, look: look?.file,
      pieces: lookMode
        ? (look ? [{ id: 'look-shoes', label: t('tryOnTheLook'), image_url: look.url },
                   { id: 'look', label: t('tryOnTheLook'), image_url: look.url }] : [])
        : wearable.map((p) => ({ id: p.id, label: label(p), image_url: p.image_url })),
    })
  }

  const reset = () => {
    if (job) tryon.dismiss()
    setPicked(null)
    setOffline2d(false)
  }

  if (!itemIds.length && !candidate && !lookMode) {
    return (
      <Page title={t('tryOnTitle')}>
        <Empty title={t('tryOnNone')} body={t('tryOnNoneBody')}
          action={<div className="flex flex-wrap gap-3">
            <Link to="/dress/build" className="inline-flex min-h-11 items-center border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink">{t('navBuild')}</Link>
            {info.data?.looks && <Link to="/tryon?look=1" className="inline-flex min-h-11 items-center text-[15px] font-medium text-ink underline underline-offset-4">{t('tryOnLookLink')}</Link>}
          </div>} />
      </Page>
    )
  }

  return (
    <Page title={t('tryOnTitle')}>
      {lookMode ? (
        <section aria-labelledby="tryon-look" className="mb-5 max-w-[440px]">
          <h2 id="tryon-look" className="mb-2 text-[13px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('tryOnTheLook')}</h2>
          {look ? (
            <div className="flex items-end gap-3">
              <img src={look.url} alt={t('tryOnTheLook')} className="h-40 w-auto bg-white object-contain" />
              <Button variant="quiet" disabled={running} onClick={() => setLook(null)}>{t('tryOnLookChange')}</Button>
            </div>
          ) : (
            <>
              <p className="mb-3 text-[14px] text-carbon-soft">{t('tryOnLookHint')}</p>
              <PhotoPicker onPick={(file) => setLook({ file, url: URL.createObjectURL(file) })} />
            </>
          )}
        </section>
      ) : (
      <section aria-labelledby="tryon-pieces" className="mb-5">
        <h2 id="tryon-pieces" className="mb-2 text-[13px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('tryOnPieces')}</h2>
        {items.error ? <ErrorNote error={items.error} onRetry={items.reload} /> : !items.data ? <Skeleton className="h-20" /> : (
          <ul className="flex flex-wrap gap-2">
            {pieces.map((p) => (
              <li key={p.id} className={`ticket p-1.5 ${canWear(p) ? '' : 'opacity-50'}`}>
                <ItemPhoto src={p.image_url} alt={label(p)} size={64} />
                <span className="mt-1 block max-w-16 truncate text-[12px] text-carbon">{label(p)}</span>
              </li>
            ))}
          </ul>
        )}
        {info.data?.looks && (
          <Link to="/tryon?look=1" className="mt-3 inline-flex min-h-11 items-center text-[14px] text-ink underline underline-offset-4">{t('tryOnLookLink')}</Link>
        )}
      </section>
      )}

      {/* privacy: where the photo goes depends on the engine (local = never leaves this computer) */}
      <p className="mb-5 flex max-w-[60ch] items-start gap-2 text-[13px] text-carbon-soft">
        {info.data?.private
          ? <><ShieldCheck className="mt-0.5 size-4 shrink-0 text-ink" aria-hidden /> {t('tryOnPrivacyLocal')}</>
          : <><ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden /> {t('tryOnPrivacy')}</>}
      </p>

      {!personUrl ? (
        <div className="grid max-w-[880px] gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,300px)]">
          <PhotoPicker onPick={pick} />
          <aside className="ticket self-start p-4">
            <h2 className="mb-3 text-[16px] font-semibold text-carbon">{t('tryOnTipsTitle')}</h2>
            <ul className="flex flex-col gap-3 text-[14px] text-carbon">
              {([[User, 'tryOnTip1'], [Camera, 'tryOnTip2'], [Sun, 'tryOnTip3']] as const).map(([Icon, key]) => (
                <li key={key} className="flex items-start gap-3">
                  <Icon className="mt-0.5 size-4 shrink-0 text-ink" aria-hidden /> {t(key)}
                </li>
              ))}
            </ul>
            {ready && (
              <p className="perf-h mt-4 pt-3 font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-soft">
                {t('tryOnEstimate', { n: estimateMin })}
              </p>
            )}
          </aside>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
          <div>
            {result ? (
              <CompareSlider before={personUrl} after={result.image} afterAlt={t('tryOnResultAlt')} />
            ) : fallback ? (
              <Overlay personUrl={personUrl} pieces={previewable} />
            ) : (
              <img src={personUrl} alt={t('tryOnYourPhoto')}
                className={`w-full bg-white transition-[opacity,filter] ${running ? 'opacity-60 saturate-50' : ''}`} />
            )}
          </div>
          {running ? (
            <div className="flex flex-col items-start gap-3">
              <p className="text-[15px] text-carbon">{t('tryOnInProgress')}</p>
              <Button onClick={tryon.openPanel}>
                <Sparkles className="size-4" aria-hidden /> {t('tryOnShowProgress')}
              </Button>
              <Button variant="quiet" onClick={tryon.cancel}>{t('tryOnCancel')}</Button>
            </div>
          ) : (
          <div className="flex flex-col items-start gap-3" aria-live="polite">
            {result && job?.tookSeconds !== undefined && (
              <p className="font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-soft">
                {t('tryOnMadeIn', { time: clock(job.tookSeconds) })}
              </p>
            )}
            {job?.state === 'stopped' && <p className="max-w-[48ch] text-[14px] text-carbon-soft">{t('tryOnStopped')}</p>}
            {!result && !fallback && ready && (
              <p className="flex items-center gap-2 text-[14px] text-carbon-soft">
                <Lightbulb className="size-4 text-ink" aria-hidden /> {t('tryOnEstimate', { n: estimateMin })}
              </p>
            )}
            {fallback && <p className="max-w-[48ch] text-[15px] text-carbon">{t('tryOnFallback')}</p>}
            {fallback && job?.why && (
              <details className="max-w-[48ch] text-[12px] text-carbon-soft">
                <summary className="cursor-pointer">{t('tryOnWhy')}</summary>
                <p className="mt-1 break-words font-mono" dir="ltr">{job.why}</p>
              </details>
            )}
            {result && (
              <>
                <p className="text-[13px] text-carbon-soft">{t('tryOnNote')}</p>
                {result.skipped.length > 0 && <p className="text-[14px] text-carbon-soft">{t('tryOnSkipped', { n: result.skipped.length })}</p>}
                {result.failed.length > 0 && <p className="text-[14px] text-carbon">{t('tryOnFailed', { n: result.failed.length })}</p>}
              </>
            )}
            {job?.state === 'failed' ? <ErrorNote error={job.error} /> : null}
            {!result && info.data?.enabled !== false && (
              <Button onClick={run} disabled={!ready}>
                <Sparkles className="size-4" aria-hidden /> {fallback ? t('tryOnRetryAi') : t('tryOnBtn')}
              </Button>
            )}
            {result && (
              <a href={result.image} download="dressme-tryon.jpg" className="inline-flex min-h-11 items-center gap-2 border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink">
                <Download className="size-4" aria-hidden /> {t('tryOnSave')}
              </a>
            )}
            <Button variant="quiet" onClick={reset}>
              {t('tryOnChange')}
            </Button>
          </div>
          )}
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
  shoes: { x: 50, y: 93, w: 30 }, glasses: { x: 50, y: 11, w: 16 }, scarf: { x: 50, y: 24, w: 30 },
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
    Promise.all(pieces.map(async (p) => ({ id: p.id, url: await loadImage(p.image_url), ...START[kindOf(p)!] })))
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
