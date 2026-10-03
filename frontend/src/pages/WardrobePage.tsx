import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, CheckCheck, Search, Trash2 } from 'lucide-react'
import { api } from '../api/client'
import type { Category, Item, ItemPatch } from '../api/types'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { plural } from '../i18n/plurals'
import { CATEGORY_LABELS, SUB_LABELS, secondLine, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { Button, Chip } from '../ui/controls'
import { FieldRow } from '../ui/Field'
import { ItemPhoto } from '../ui/ItemPhoto'
import { PhotoPicker } from '../ui/PhotoPicker'
import { Empty, ErrorNote, Skeleton } from '../ui/states'
import { SecondLine, Serial, Ticket } from '../ui/ticket'
import { useLoad } from '../useLoad'

const ORDER: Category[] = ['top', 'bottom', 'dress', 'outerwear', 'shoes', 'bag', 'accessory', 'traditional', 'swimwear']
const GUESSABLE = ['category', 'sub_category', 'pattern', 'colour'] as const

function guessedCount(it: Item) {
  return GUESSABLE.filter((f) => it.predicted[f] && !it.corrected.includes(f)).length
}

export function WardrobePage() {
  const { t, lang } = useI18n()
  const { user } = useAuth()
  const navigate = useNavigate()
  const items = useLoad(() => api.items(), [])
  const [filter, setFilter] = useState<Category | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<unknown>(null)

  const add = async (file: File) => {
    setUploading(true)
    setUploadError(null)
    try {
      const item = await api.addItem(file)
      navigate(`/wardrobe/${item.id}`)
    } catch (e) {
      setUploadError(e)
      setUploading(false)
    }
  }

  const all = items.data ?? []
  const present = ORDER.filter((c) => all.some((i) => i.category === c))
  const shown = filter ? all.filter((i) => i.category === filter) : all

  return (
    <Page title={t('wardrobeTitle')}>
      <section className="ticket mb-6 flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-[15px] text-carbon">
          {uploading ? t('uploading') : items.data ? plural('pieces', all.length, lang) : t('loading')}
        </p>
        <div className="sm:w-[420px]"><PhotoPicker onPick={add} busy={uploading} /></div>
      </section>
      {uploadError ? <div className="mb-4"><ErrorNote error={uploadError} /></div> : null}
      {user?.demo && <p className="-mt-3 mb-5 text-[12px] leading-snug text-carbon-soft">{t('demoNotice')}</p>}

      {items.error ? (
        <ErrorNote error={items.error} onRetry={items.reload} />
      ) : !items.data ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-[190px]" />)}
        </div>
      ) : all.length === 0 ? (
        <Empty title={t('wardrobeEmptyTitle')} body={t('wardrobeEmptyBody')} />
      ) : (
        <>
          <div className="-mx-4 mb-4 flex gap-2 no-scrollbar overflow-x-auto px-4 pb-1 lg:mx-0 lg:flex-wrap lg:px-0">
            <Chip selected={!filter} onClick={() => setFilter(null)}>{t('all')} · {all.length}</Chip>
            {present.map((c) => (
              <Chip key={c} selected={filter === c} onClick={() => setFilter(c)}>
                {vocab(CATEGORY_LABELS, c, lang)} · {all.filter((i) => i.category === c).length}
              </Chip>
            ))}
          </div>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {shown.map((it) => {
              const guessed = guessedCount(it)
              return (
                <li key={it.id}>
                  <Link to={`/wardrobe/${it.id}`} className="ticket block p-2 transition-shadow duration-150 hover:[box-shadow:var(--shadow-lift)]">
                    <div className="flex justify-center"><ItemPhoto src={it.image_url} alt={vocab(SUB_LABELS, it.sub_category, lang)} size={128} /></div>
                    <div className="perf-h mt-2 pt-2">
                      <p className={`truncate pb-0.5 text-[15px] font-semibold text-carbon ${guessed ? 'field-guess' : 'field-sure'} inline-block max-w-full`}>
                        {vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)}
                      </p>
                      <SecondLine>{secondLine(SUB_LABELS, it.sub_category, lang) || secondLine(CATEGORY_LABELS, it.category, lang)}</SecondLine>
                      <Serial id={it.id} className="mt-1 block" />
                    </div>
                  </Link>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </Page>
  )
}

export function ItemPage() {
  const { id = '' } = useParams()
  const { t, lang } = useI18n()
  const navigate = useNavigate()
  const item = useLoad(() => api.item(id), [id])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const save = async (patch: ItemPatch) => {
    setSaving(true)
    setError(null)
    try {
      item.setData(await api.updateItem(id, patch))
    } catch (e) {
      setError(e)
    } finally {
      setSaving(false)
    }
  }

  const it = item.data
  const confirmAll = () => {
    if (!it) return
    const patch: ItemPatch = {}
    for (const f of GUESSABLE) {
      if (it.predicted[f] && !it.corrected.includes(f) && it[f]) (patch as Record<string, string>)[f] = it[f]
    }
    if (Object.keys(patch).length) void save(patch)
  }
  const remove = async () => {
    try {
      await api.deleteItem(id)
      navigate('/wardrobe')
    } catch (e) {
      setError(e)
    }
  }

  return (
    <Page title={it ? vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang) : t('loading')}>
      <div className="mx-auto max-w-[640px]">
        <Link to="/wardrobe" className="mb-4 inline-flex min-h-10 items-center gap-2 text-[14px] text-ink">
          <ArrowLeft className="size-4 mirror-rtl" aria-hidden /> {t('wardrobeTitle')}
        </Link>
        {item.error ? (
          <ErrorNote error={item.error} onRetry={item.reload} />
        ) : !it ? (
          <Skeleton className="h-[420px]" />
        ) : (
          <>
            <Ticket stub={<Serial id={it.id} className="[writing-mode:vertical-rl]" />}>
              <div className="flex items-end gap-4 p-3">
                <ItemPhoto src={it.image_url} alt={vocab(SUB_LABELS, it.sub_category, lang)} size={160} />
                <div className="pb-1">
                  <SecondLine>{secondLine(SUB_LABELS, it.sub_category, lang) || secondLine(CATEGORY_LABELS, it.category, lang)}</SecondLine>
                </div>
              </div>
            </Ticket>
            <section className="ticket mt-3 px-4 pb-4 pt-3" aria-busy={saving || undefined}>
              <p className="mb-1 text-[13px] text-carbon-soft">{t('checkFieldsHint')}</p>
              <div className="divide-y divide-perf/40">
                {(['category', 'sub_category', 'colour', 'pattern', 'coverage', 'season', 'usage'] as const).map((f) => (
                  <FieldRow key={f} item={it} field={f} onSave={save} saving={saving} />
                ))}
              </div>
              {guessedCount(it) > 0 && (
                <Button variant="secondary" className="mt-4 w-full" busy={saving} onClick={confirmAll}>
                  <CheckCheck className="size-4" aria-hidden /> {t('confirmAll')}
                </Button>
              )}
            </section>
            {error ? <div className="mt-3"><ErrorNote error={error} /></div> : null}
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <Link to={`/similar?item=${it.id}`} className="inline-flex min-h-11 items-center gap-2 border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink">
                <Search className="size-4" aria-hidden /> {t('seeSimilar')}
              </Link>
              {confirmDelete ? (
                <span className="flex items-center gap-2" role="group">
                  <span className="text-[14px] text-carbon">{t('deleteConfirm')}</span>
                  <Button variant="primary" onClick={remove}>{t('delete')}</Button>
                  <Button variant="quiet" onClick={() => setConfirmDelete(false)}>{t('cancel')}</Button>
                </span>
              ) : (
                <Button variant="quiet" onClick={() => setConfirmDelete(true)}>
                  <Trash2 className="size-4" aria-hidden /> {t('delete')}
                </Button>
              )}
            </div>
          </>
        )}
      </div>
    </Page>
  )
}
