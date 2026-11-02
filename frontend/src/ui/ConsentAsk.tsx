import { useState } from 'react'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { Wordmark } from '../shell'
import { PillButton } from './dress'
import { ErrorNote } from './states'

// TODO(step 5): the consent wording is a first version, written for the app and not checked by anyone who
// knows the rules (what is kept, for how long, which outside services receive what). The team should review it.

/** Accounts created before the sign-up checkbox: asked once, the app opens after "I agree". It cannot be
 *  dismissed: the only other way out is to log out. */
export function ConsentAsk() {
  const { t } = useI18n()
  const { acceptConsent, logout } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const agree = async () => {
    setBusy(true)
    setError(null)
    try {
      await acceptConsent()
    } catch (e) {
      setError(e)
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-[440px] flex-col justify-center gap-5 px-4 py-8">
      <Wordmark />
      <div role="dialog" aria-modal="true" aria-labelledby="consent-title" className="flex flex-col gap-3 rounded-card bg-label-neutral p-card">
        <h1 id="consent-title" className="text-[20px] font-bold text-carbon">{t('consentTitle')}</h1>
        <p className="text-[15px] leading-relaxed text-carbon-soft">{t('consentBody')}</p>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row-reverse">
          <PillButton busy={busy} onClick={() => void agree()} className="sm:flex-1">{t('consentAgree')}</PillButton>
          <PillButton variant="outline" onClick={logout} disabled={busy} className="sm:flex-1">{t('logout')}</PillButton>
        </div>
      </div>
      {error ? <ErrorNote error={error} message={t('dressActionFailed')} onRetry={() => void agree()} /> : null}
    </div>
  )
}
