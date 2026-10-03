import { useRef } from 'react'
import { Camera, Images } from 'lucide-react'
import { useI18n } from '../i18n'
import { Button } from './controls'

/** "Take a photo" opens the back camera on phones; "Choose" opens the gallery. */
export function PhotoPicker({ onPick, busy, layout = 'row' }: {
  onPick: (file: File) => void
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
  return (
    <div className={`flex gap-2 ${layout === 'stack' ? 'flex-col' : 'flex-col min-[430px]:flex-row'}`}>
      <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={take} />
      <input ref={gallery} type="file" accept="image/*" hidden onChange={take} />
      <Button busy={busy} onClick={() => camera.current?.click()} className="flex-1 whitespace-nowrap">
        <Camera className="size-5" aria-hidden /> {t('takePhoto')}
      </Button>
      <Button variant="secondary" disabled={busy} onClick={() => gallery.current?.click()} className="flex-1 whitespace-nowrap">
        <Images className="size-5" aria-hidden /> {t('choosePhoto')}
      </Button>
    </div>
  )
}
