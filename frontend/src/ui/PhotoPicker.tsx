import { useRef } from 'react'
import { Camera, Images } from 'lucide-react'
import { useI18n } from '../i18n'
import { Button } from './controls'

/** "Take a photo" opens the back camera on phones; "Choose" opens the gallery. With `onPickMany`, the gallery lets
 *  the user choose several photos at once and hands them all over (the camera still takes one). */
export function PhotoPicker({ onPick, onPickMany, busy, layout = 'row' }: {
  onPick: (file: File) => void
  onPickMany?: (files: File[]) => void
  busy?: boolean
  layout?: 'row' | 'stack'
}) {
  const { t } = useI18n()
  const camera = useRef<HTMLInputElement>(null)
  const gallery = useRef<HTMLInputElement>(null)
  const take = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    e.target.value = ''               // the same photo can be picked again
    if (f) onPick(f)
  }
  const takeMany = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    e.target.value = ''
    if (files.length) onPickMany?.(files)
  }
  return (
    <div className={`flex gap-2 ${layout === 'stack' ? 'flex-col' : 'flex-col min-[430px]:flex-row'}`}>
      <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={take} />
      <input ref={gallery} type="file" accept="image/*" hidden multiple={!!onPickMany} onChange={onPickMany ? takeMany : take} />
      <Button busy={busy} onClick={() => camera.current?.click()} className="flex-1 whitespace-nowrap">
        <Camera className="size-5" aria-hidden /> {t('takePhoto')}
      </Button>
      <Button variant="secondary" disabled={busy} onClick={() => gallery.current?.click()} className="flex-1 whitespace-nowrap">
        <Images className="size-5" aria-hidden /> {t('choosePhoto')}
      </Button>
    </div>
  )
}
