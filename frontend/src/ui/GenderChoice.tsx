import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Gender } from '../api/types'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { Wordmark } from '../shell'
import { Chip } from './controls'
import { ErrorNote } from './states'

/** Female / male, as two chips (sign-up, profile, the one-time question). */
export function GenderChoice({ value, onChange }: { value: Gender | null; onChange: (g: Gender) => void }) {
  const { t } = useI18n()
  return (
    <div role="radiogroup" aria-label={t('gender')} className="flex flex-wrap gap-2">
      <Chip selected={value === 'women'} onClick={() => onChange('women')}>{t('genderWomen')}</Chip>
      <Chip selected={value === 'men'} onClick={() => onChange('men')}>{t('genderMen')}</Chip>
    </div>
  )
}

/** Accounts created before the question: asked once, the app opens after the answer. */
export function GenderAsk() {
  const { t } = useI18n()
  const { updateProfile } = useAuth()
  const [error, setError] = useState<unknown>(null)
  const choose = async (gender: Gender) => {
    setError(null)
    try {
      await updateProfile({ gender })
    } catch (e) {
      setError(e)
    }
  }
  return (
    <div className="mx-auto flex min-h-dvh max-w-[440px] flex-col justify-center gap-5 px-4">
      <Wordmark />
      <div className="ticket flex flex-col gap-3 px-5 py-5">
        <h1 className="text-[20px] font-semibold text-carbon">{t('genderAskTitle')}</h1>
        <p className="text-[14px] text-carbon-soft">{t('genderHelp')}</p>
        <GenderChoice value={null} onChange={(g) => void choose(g)} />
      </div>
      {error ? <ErrorNote error={error} /> : null}
    </div>
  )
}

type SubGender = Record<string, 'men' | 'women' | 'unisex'>
let subGender: Promise<SubGender> | null = null

/** The team's table of men's / women's / unisex pieces (loaded once per session). */
// eslint-disable-next-line react-refresh/only-export-components
export function useSubGender(): SubGender | null {
  const [table, setTable] = useState<SubGender | null>(null)
  useEffect(() => {
    subGender ??= api.subCategoryGender()
    subGender.then(setTable).catch(() => { subGender = null })   // retried next time
  }, [])
  return table
}

/** "Showing men's + unisex · Show all" above shop and look-alike results. */
export function ScopeLine({ all, onToggle }: { all: boolean; onToggle: () => void }) {
  const { t } = useI18n()
  const { user } = useAuth()
  const mine = user?.gender === 'men' ? t('showingMen') : t('showingWomen')
  return (
    <p className="flex flex-wrap items-center gap-2 text-[13px] text-carbon-soft">
      <span>{all ? t('showingAll') : mine}</span>
      <button type="button" onClick={onToggle} className="text-ink underline decoration-1 underline-offset-4 hover:decoration-2">
        {all ? t('showMine') : t('showAll')}
      </button>
    </p>
  )
}
