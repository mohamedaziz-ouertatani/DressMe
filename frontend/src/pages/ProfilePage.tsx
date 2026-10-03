import { useState } from 'react'
import { LogOut } from 'lucide-react'
import type { Language } from '../api/types'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { COVERAGE_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { Button, Chip, TextField } from '../ui/controls'
import { ErrorNote } from '../ui/states'

export function ProfilePage() {
  const { t, lang } = useI18n()
  const { user, updateProfile, logout } = useAuth()
  const [name, setName] = useState(user?.name ?? '')
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<unknown>(null)
  if (!user) return null

  const save = async (patch: Parameters<typeof updateProfile>[0]) => {
    setBusy(true)
    setSaved(false)
    setError(null)
    try {
      await updateProfile(patch)
      setSaved(true)
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const langs: [Language, string][] = [['en', 'English'], ['fr', 'Français'], ['ar', 'العربية']]

  return (
    <Page title={t('profileTitle')}>
      <div className="mx-auto flex max-w-[560px] flex-col gap-4">
        <form
          className="ticket flex items-end gap-3 px-4 py-4"
          onSubmit={(e) => { e.preventDefault(); void save({ name: name.trim() }) }}
        >
          <div className="flex-1">
            <TextField label={t('name')} value={name} onChange={(e) => setName(e.target.value)} maxLength={60} required />
          </div>
          <Button type="submit" variant="secondary" busy={busy} disabled={!name.trim() || name.trim() === user.name}>{t('save')}</Button>
        </form>

        <fieldset className="ticket min-w-0 px-4 py-4">
          <legend className="sr-only">{t('modesty')}</legend>
          <h2 className="text-[16px] font-semibold text-carbon">{t('modesty')}</h2>
          <p className="mb-3 mt-1 max-w-[52ch] text-[14px] text-carbon-soft">{t('modestyHelp')}</p>
          <div className="flex flex-wrap gap-2">
            <Chip selected={user.min_coverage === null} onClick={() => void save({ min_coverage: null })}>{t('noPreference')}</Chip>
            {[1, 2, 3, 4, 5].map((n) => (
              <Chip key={n} selected={user.min_coverage === n} onClick={() => void save({ min_coverage: n })}>
                <span className="font-mono tabular" dir="ltr">{n}</span> · {vocab(COVERAGE_LABELS, String(n), lang)}
              </Chip>
            ))}
          </div>
        </fieldset>

        <fieldset className="ticket min-w-0 px-4 py-4">
          <legend className="sr-only">{t('language')}</legend>
          <h2 className="mb-3 text-[16px] font-semibold text-carbon">{t('language')}</h2>
          <div className="flex flex-wrap gap-2">
            {langs.map(([code, label]) => (
              <Chip key={code} selected={user.language === code} onClick={() => void save({ language: code })}>
                <span lang={code}>{label}</span>
              </Chip>
            ))}
          </div>
        </fieldset>

        <p aria-live="polite" className="min-h-5 text-[13px] text-ink-soft">{saved && !busy ? t('saved') : ''}</p>
        {error ? <ErrorNote error={error} /> : null}

        <p className="font-mono text-[12px] text-ink-soft" dir="ltr">{user.email}</p>
        {user.demo && <p className="text-[12px] leading-snug text-carbon-soft">{t('demoNotice')}</p>}
        <Button variant="quiet" className="self-start" onClick={logout}>
          <LogOut className="size-4 mirror-rtl" aria-hidden /> {t('logout')}
        </Button>
      </div>
    </Page>
  )
}
