import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import type { Gender, Language } from '../api/types'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { Wordmark } from '../shell'
import { Button, TextField } from '../ui/controls'
import { GenderChoice } from '../ui/GenderChoice'
import { Stamp } from '../ui/Stamp'

export function LanguageSwitch() {
  const { lang, setLang } = useI18n()
  const langs: [Language, string][] = [['en', 'English'], ['fr', 'Français'], ['ar', 'العربية']]
  return (
    <div role="group" aria-label="Language" className="flex gap-1">
      {langs.map(([code, label]) => (
        <button
          key={code}
          type="button"
          lang={code}
          aria-pressed={lang === code}
          onClick={() => setLang(code)}
          className={`min-h-9 px-2.5 text-[13px] font-medium ${lang === code ? 'bg-ink text-paper' : 'text-ink hover:bg-paper'}`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

export function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const { t } = useI18n()
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [gender, setGender] = useState<Gender | null>(null)
  const signup = mode === 'signup'

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    if (signup && !gender) {
      setError(t('genderRequired'))
      return
    }
    setBusy(true)
    setError('')
    try {
      const email = String(form.get('email')), password = String(form.get('password'))
      if (signup) await register(email, password, String(form.get('name')), gender!)
      else await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError && err.status !== 0 ? err.message : t('offline'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col px-4 pb-10 pt-[max(16px,env(safe-area-inset-top))]">
      <div className="flex items-center justify-between">
        <Wordmark />
        <LanguageSwitch />
      </div>

      <div className="mx-auto mt-10 w-full max-w-[440px] sm:mt-16">
        <p className="mb-6 max-w-[34ch] text-[20px] font-medium leading-snug text-carbon sm:text-[22px]">{t('authPitch')}</p>

        <form onSubmit={submit} className="ticket relative flex flex-col gap-5 px-5 pb-6 pt-5" noValidate={false}>
          <div className="pointer-events-none absolute -top-8 end-3">
            <Stamp big="DM" ring="DRESSME · FRIPERIE · DRESSME · FRIPERIE ·" size={74} angle={12} label="" tone="ink" />
          </div>
          <h1 className="text-[22px] font-semibold text-carbon">{signup ? t('signupTitle') : t('loginTitle')}</h1>
          {signup && <TextField label={t('name')} name="name" required autoComplete="given-name" maxLength={60} />}
          {signup && (
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-medium text-carbon">{t('gender')}</span>
              <GenderChoice value={gender} onChange={(g) => { setGender(g); setError('') }} />
              <p className="text-[12px] text-carbon-soft">{t('genderHelp')}</p>
            </div>
          )}
          <TextField label={t('email')} name="email" type="email" required autoComplete="email" inputMode="email" dir="ltr" />
          <TextField
            label={t('password')}
            name="password"
            type="password"
            required
            minLength={signup ? 8 : undefined}
            autoComplete={signup ? 'new-password' : 'current-password'}
            hint={signup ? t('passwordHint') : undefined}
            dir="ltr"
          />
          {error && (
            <p role="alert" className="border-[1.5px] border-carbon px-3 py-2 text-[14px] text-carbon">
              {error}
            </p>
          )}
          <Button type="submit" busy={busy} className="mt-1 w-full">
            {signup ? t('signupBtn') : t('loginBtn')}
          </Button>
        </form>

        <p className="mt-5 text-center text-[14px]">
          <Link to={signup ? '/login' : '/signup'} className="text-ink underline decoration-1 underline-offset-4 hover:decoration-2">
            {signup ? t('toLogin') : t('toSignup')}
          </Link>
        </p>
      </div>
    </div>
  )
}
