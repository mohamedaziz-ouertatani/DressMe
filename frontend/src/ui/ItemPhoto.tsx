import { useEffect, useState } from 'react'
import { Shirt, ZoomIn } from 'lucide-react'
import { loadImage } from '../api/client'
import { useI18n } from '../i18n'
import { PhotoViewer } from './PhotoViewer'

/** Every item photo at one fixed scale on a white plate, sitting on a shared
 *  baseline, so pieces in a strip compare like registered plates.
 *  `src` is an API path (loaded with the auth header) or a local blob: URL.
 *  `zoomable`: a tap opens the photo full screen, where it can be zoomed. */
export function ItemPhoto({ src, alt, size = 96, zoomable = false }: {
  src?: string; alt: string; size?: number; zoomable?: boolean
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [loaded, setLoaded] = useState<{ src: string; url: string } | null>(null)
  const [failed, setFailed] = useState<string | null>(null)
  const local = src?.startsWith('blob:') ? src : null

  useEffect(() => {
    if (!src || local) return
    let alive = true
    loadImage(src)
      .then((url) => alive && setLoaded({ src, url }))
      .catch(() => alive && setFailed(src))
    return () => { alive = false }
  }, [src, local])

  const url = local ?? (loaded && loaded.src === src ? loaded.url : null)
  const plate = (
    <div
      className="flex shrink-0 items-end justify-center overflow-hidden bg-white"
      style={{ width: size, height: size }}
    >
      {url ? (
        <img src={url} alt={alt} className="h-full w-full object-contain object-bottom" />
      ) : src && failed !== src ? (
        <div aria-label={alt} className="skeleton h-full w-full" />
      ) : (
        <Shirt className="mb-[22%] size-1/3 text-perf" aria-label={alt} />
      )}
    </div>
  )
  if (!zoomable || !url) return plate
  return (
    <>
      <button
        type="button"
        className="relative shrink-0 cursor-zoom-in"
        aria-label={`${t('zoomPhoto')}: ${alt}`}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(true) }}
      >
        {plate}
        <ZoomIn className="absolute end-1 top-1 size-6 bg-paper/80 p-1 text-ink" aria-hidden />
      </button>
      {open && <PhotoViewer url={url} alt={alt} onClose={() => setOpen(false)} />}
    </>
  )
}
