import { useEffect, useState } from 'react'
import { Shirt } from 'lucide-react'
import { loadImage } from '../api/client'

/** Every item photo at one fixed scale on a white plate, sitting on a shared
 *  baseline, so pieces in a strip compare like registered plates.
 *  `src` is an API path (loaded with the auth header) or a local blob: URL. */
export function ItemPhoto({ src, alt, size = 96 }: { src?: string; alt: string; size?: number }) {
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
  return (
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
}
