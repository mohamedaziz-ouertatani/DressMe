import { useCallback, useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { Decision, Item, Language, WearEntry, WearSummary } from '../api/types'
import { useAuth } from '../auth'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, COLOUR_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { TextField } from '../ui/controls'
import { DetailsSheet } from '../ui/DetailsSheet'
import { PillButton } from '../ui/dress'
import { ItemPhoto } from '../ui/ItemPhoto'
import { Empty, ErrorNote, Skeleton } from '../ui/states'
import { useLoad } from '../useLoad'
import { StatsSection } from './InsightsPage'

/** The Wardrobe view (step 5; it was the Insights page, same route /insights): what was worn, what was bought
 *  or left, the wardrobe stats and the profile. The look is the Dress one (tokens in index.css). */
export function WardrobeViewPage() {
  const { t } = useI18n()
  return (
    <Page title={t('insightsTitle')}>
      <div className="flex flex-col gap-10">
        {/* TODO(step 4): the "To check" section goes here, first: pieces added from a photo that still wait for the
            user to confirm their labels (drafts). Hidden until drafts exist. */}
        <WornSection />
        <BoughtSection />
        <ViewSection title={t('wvStats')}><StatsSection /></ViewSection>
        <ProfileSection />
      </div>
    </Page>
  )
}

function ViewSection({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="text-[22px] font-bold text-carbon">{title}</h2>
      {note && <p className="mt-1 max-w-[60ch] text-[14px] text-carbon-soft">{note}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

function useDate() {
  const { lang } = useI18n()
  return (iso: string) => new Date(iso.length === 10 ? `${iso}T12:00:00` : iso)      // a plain date: noon, no day shift
    .toLocaleDateString(lang === 'ar' ? 'ar-TN-u-nu-latn' : lang, { day: 'numeric', month: 'short', year: 'numeric' })
}

// ------------------------------------------------------------------ Worn
const HISTORY_SHOWN = 20          // TODO(step 5): paging; GET /wear itself stops at 500 entries

function WornSection() {
  const { t, lang } = useI18n()
  const date = useDate()
  const summary = useLoad(() => api.wearSummary(), [])
  const history = useLoad(() => api.wearList(), [])
  const items = useLoad(() => api.items(), [])
  const reload = () => { void summary.reload(); void history.reload(); void items.reload() }
  const name = (it: Item) => vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)

  let body
  const error = summary.error ?? history.error ?? items.error
  if (error) body = <ErrorNote error={error} onRetry={reload} message={t('wvWornFailed')} />
  else if (!summary.data || !history.data || !items.data) body = <Skeleton className="h-40 rounded-card" />
  else {
    const byId = new Map(items.data.map((it) => [it.id, it]))
    body = (
      <div className="flex flex-col gap-stack">
        <Block title={t('wvWornLately', { n: summary.data.window_days })} empty={t('wvWornLatelyEmpty')}
          pieces={lately(summary.data, byId)} name={name} line={(p) => t('wvLastWorn', { date: date(p.extra) })} />
        <Block title={t('wvNeverWorn')} note={t('wvNeverWornNote', { n: summary.data.grace_days })} empty={t('wvNeverWornEmpty')}
          pieces={summary.data.never_worn.flatMap((id) => (byId.has(id) ? [{ item: byId.get(id)!, extra: '' }] : []))} name={name} />
        <div>
          <h3 className="text-[16px] font-bold text-carbon">{t('wvHistory')}</h3>
          {history.data.length === 0 ? (
            <p className="mt-2 text-[14px] text-carbon-soft">{t('wvHistoryEmpty')}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {history.data.slice(0, HISTORY_SHOWN).map((e) => <HistoryRow key={e.id} entry={e} byId={byId} name={name} date={date} />)}
            </ul>
          )}
        </div>
      </div>
    )
  }
  return <ViewSection title={t('wvWorn')}>{body}</ViewSection>
}

function lately(summary: WearSummary, byId: Map<string, Item>) {
  return summary.worn_lately.flatMap((w) => (byId.has(w.item_id) ? [{ item: byId.get(w.item_id)!, extra: w.last_worn_on }] : []))
}

/** A titled grid of pieces (photo, name, an optional line), each linking to its page. */
function Block({ title, note, empty, pieces, name, line }: {
  title: string; note?: string; empty: string
  pieces: { item: Item; extra: string }[]
  name: (it: Item) => string
  line?: (p: { item: Item; extra: string }) => string
}) {
  return (
    <div>
      <h3 className="text-[16px] font-bold text-carbon">{title}</h3>
      {note && <p className="mt-0.5 text-[13px] text-carbon-soft">{note}</p>}
      {pieces.length === 0 ? (
        <p className="mt-2 text-[14px] text-carbon-soft">{empty}</p>
      ) : (
        <ul className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          {pieces.map((p) => (
            <li key={p.item.id}>
              <Link to={`/wardrobe/${p.item.id}`} className="block rounded-tile bg-tile p-2 text-center">
                <div className="flex justify-center"><ItemPhoto src={p.item.image_url} alt={name(p.item)} size={96} /></div>
                <p className="mt-2 truncate text-[14px] font-medium text-carbon">{name(p.item)}</p>
                {line && <p className="truncate text-[12px] text-carbon-soft">{line(p)}</p>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function HistoryRow({ entry, byId, name, date }: {
  entry: WearEntry; byId: Map<string, Item>; name: (it: Item) => string; date: (iso: string) => string
}) {
  const pieces = entry.item_ids.flatMap((id) => (byId.has(id) ? [byId.get(id)!] : []))      // a deleted piece has no photo
  return (
    <li className="flex items-center gap-3 rounded-card bg-label-neutral px-4 py-3">
      <span className="w-28 shrink-0 text-[14px] font-medium text-carbon">{date(entry.worn_on)}</span>
      <span className="flex min-w-0 flex-wrap gap-1.5">
        {pieces.slice(0, 5).map((it) => (
          <Link key={it.id} to={`/wardrobe/${it.id}`} className="shrink-0 rounded-tile bg-tile p-1">
            <ItemPhoto src={it.image_url} alt={name(it)} size={44} />
          </Link>
        ))}
      </span>
    </li>
  )
}

// ------------------------------------------------------------------ Bought and left
// TODO(step 5): the decisions are listed as they were stored. The full version could show the photo of a piece that
// was bought (it is in the wardrobe, `item_id`), the cost per wear (price paid / times worn) and a summary
// ("you left 5 of the 8 pieces the app said skip").
function BoughtSection() {
  const { t, lang } = useI18n()
  const date = useDate()
  const res = useLoad(() => api.decisions(), [])

  let body
  if (res.error) body = <ErrorNote error={res.error} onRetry={res.reload} message={t('wvBoughtFailed')} />
  else if (!res.data) body = <Skeleton className="h-32 rounded-card" />
  else if (res.data.length === 0) body = <Empty title={t('wvBought')} body={t('wvBoughtEmpty')} />
  else {
    body = (
      <ul className="flex flex-col gap-2">
        {res.data.map((d) => <DecisionRow key={d.id} d={d} date={date} lang={lang} />)}
      </ul>
    )
  }
  return <ViewSection title={t('wvBought')} note={t('wvBoughtNote')}>{body}</ViewSection>
}

function DecisionRow({ d, date, lang }: { d: Decision; date: (iso: string) => string; lang: Language }) {
  const { t } = useI18n()
  const piece = [vocab(COLOUR_LABELS, d.colour, lang), vocab(SUB_LABELS, d.sub_category, lang) || vocab(CATEGORY_LABELS, d.category, lang)]
    .filter(Boolean).join(' ')
  const price = d.price_paid ?? d.price_tnd
  const advice = d.last_advice
  const title = <span className="font-medium text-carbon">{piece}</span>
  return (
    <li className="rounded-card bg-label-neutral px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <p className="min-w-0 text-[15px]">
          {d.item_id ? <Link to={`/wardrobe/${d.item_id}`} className="underline decoration-1 underline-offset-4">{title}</Link> : title}
        </p>
        <span className={`rounded-pill px-3 py-0.5 text-[13px] font-semibold ${d.answer === 'bought' ? 'bg-pill text-pill-text' : 'border-[1.5px] border-pill-line text-pill'}`}>
          {t(d.answer === 'bought' ? 'wvDecisionBought' : 'wvDecisionLeft')}
        </span>
      </div>
      <p className="mt-1 text-[13px] text-carbon-soft">
        {t('wvVerdictThen', { verdict: t(`verdict_${advice.verdict}`), confidence: t(`confidence_${advice.confidence}`) })}
        {price != null ? ` · ${d.price_paid != null ? t('wvPaid', { price: t('priceTnd', { p: price }) }) : t('priceTnd', { p: price })}` : ''}
        {` · ${date(d.created_at)}`}
      </p>
    </li>
  )
}

// ------------------------------------------------------------------ Profile
function ProfileSection() {
  const { t } = useI18n()
  const date = useDate()
  const { user } = useAuth()
  if (!user) return null
  return (
    <ViewSection title={t('wvProfile')}>
      <div className="flex flex-col gap-stack">
        <BudgetCard />
        <p className="text-[14px] text-carbon-soft">{user.consent_at ? t('wvConsentOn', { date: date(user.consent_at) }) : t('wvConsentNone')}</p>
        <DeleteAccount />
      </div>
    </ViewSection>
  )
}

function BudgetCard() {
  const { t } = useI18n()
  const { user, updateProfile } = useAuth()
  const [value, setValue] = useState(user?.budget_tnd != null ? String(user.budget_tnd) : '')
  const [busy, setBusy] = useState(false)
  const [invalid, setInvalid] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const save = async (budget: number | null) => {
    setBusy(true)
    setSaved(false)
    setError(null)
    try {
      await updateProfile({ budget_tnd: budget })
      if (budget === null) setValue('')
      setSaved(true)
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const n = Number(value.replace(',', '.'))
    if (!Number.isFinite(n) || n <= 0) { setInvalid(true); return }
    setInvalid(false)
    void save(n)
  }

  return (
    <form onSubmit={submit} className="rounded-card bg-label-neutral p-card" noValidate>
      <TextField
        label={t('wvBudget')}
        hint={t('wvBudgetHelp')}
        error={invalid ? t('wvBudgetInvalid') : undefined}
        value={value}
        onChange={(e) => { setValue(e.target.value); setInvalid(false); setSaved(false) }}
        inputMode="decimal"
        dir="ltr"
      />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <PillButton type="submit" busy={busy}>{t('save')}</PillButton>
        {user?.budget_tnd != null && <PillButton variant="outline" disabled={busy} onClick={() => void save(null)}>{t('wvBudgetRemove')}</PillButton>}
        <p aria-live="polite" className="text-[13px] text-carbon-soft">{saved && !busy ? t('saved') : ''}</p>
      </div>
      {error ? <div className="mt-3"><ErrorNote error={error} message={t('dressActionFailed')} /></div> : null}
    </form>
  )
}

function DeleteAccount() {
  const { t } = useI18n()
  const { user, deleteAccount, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const close = useCallback(() => { setOpen(false); setPassword(''); setError(null) }, [])     // stable: the sheet keeps focus

  if (user?.demo) return <p className="text-[13px] text-carbon-soft">{t('wvDeleteDemo')}</p>

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await deleteAccount(password)
      logout()                                     // the account is gone: forget the token, then open the login page
      window.location.assign('/login')             // a full load: the router would send a logged-out user to /welcome first
    } catch (err) {
      setError(err)
      setBusy(false)
    }
  }
  const wrong = error instanceof ApiError && error.status === 403

  return (
    <div>
      <PillButton variant="outline" onClick={() => setOpen(true)}>{t('wvDelete')}</PillButton>
      {open && (
        <DetailsSheet title={t('wvDeleteTitle')} onClose={close}>
          <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
            <p role="alert" className="rounded-tile border-[1.5px] border-pill-line px-4 py-3 text-[14px] text-carbon">{t('wvDeleteWarning')}</p>
            <TextField
              label={t('wvDeletePassword')}
              type="password"
              autoComplete="current-password"
              required
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={wrong ? t('wvDeleteWrong') : undefined}
              dir="ltr"
            />
            {error && !wrong ? <ErrorNote error={error} message={t('wvDeleteFailed')} /> : null}
            <div className="flex flex-col gap-2 sm:flex-row-reverse">
              <PillButton type="submit" busy={busy} disabled={!password} className="sm:flex-1">{t('wvDeleteGo')}</PillButton>
              <PillButton variant="outline" onClick={close} disabled={busy} className="sm:flex-1">{t('close')}</PillButton>
            </div>
          </form>
        </DetailsSheet>
      )}
    </div>
  )
}
