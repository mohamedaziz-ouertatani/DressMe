// Admin dashboard (team-only, so English only). Same ticket world as the app,
// denser and quieter: receipts and tables instead of big tickets.
import { useState, type FormEvent } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { api } from '../api/client'
import type { Formula, ReviewListing } from '../api/types'
import { useAuth } from '../auth'
import { Wordmark } from '../shell'
import { ItemPhoto } from '../ui/ItemPhoto'
import { Button, Chip } from '../ui/controls'
import { ErrorNote, Skeleton } from '../ui/states'
import { useLoad } from '../useLoad'
import { DayBars, RowBars, TableView } from './charts'

const TYPES = [['scan', 'scans'], ['verdict', 'verdicts'], ['upload', 'uploads'], ['correction', 'corrections'], ['chat', 'chat messages']] as const

const pct = (v: number | null) => (v === null ? '-' : `${(v * 100).toFixed(1)}%`)

export function AdminLayout() {
  const tabs = [['/admin', 'Overview'], ['/admin/quality', 'Model quality'], ['/admin/users', 'Users'], ['/admin/formula', 'Formula'], ['/admin/listings', 'Listings'], ['/admin/moderation', 'Moderation']]
  return (
    <div className="min-h-dvh" dir="ltr" lang="en">
      <header className="border-b border-perf/60 bg-stock-deep/60">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 lg:px-8">
          <Wordmark />
          <span className="text-[14px] font-medium text-carbon-soft">Admin</span>
          <nav aria-label="Admin" className="order-last -mx-1 flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto">
            {tabs.map(([to, label]) => (
              <NavLink key={to} to={to} end
                className={({ isActive }) => `min-h-10 shrink-0 px-3 py-2 text-[14px] font-medium ${isActive ? 'ticket text-ink' : 'text-carbon-soft hover:text-ink'}`}>
                {label}
              </NavLink>
            ))}
          </nav>
          <Link to="/" className="ms-auto inline-flex min-h-10 items-center gap-1.5 text-[14px] text-ink">
            <ArrowLeft className="size-4" aria-hidden /> Back to the app
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-[1200px] px-4 py-6 lg:px-8 lg:py-8">
        <Outlet />
      </main>
    </div>
  )
}

export function Title({ children, note }: { children: string; note?: string }) {
  return (
    <div className="mb-5">
      <h1 className="text-[24px] font-semibold tracking-[-0.01em] text-carbon">{children}</h1>
      {note && <p className="mt-1 max-w-[70ch] text-[14px] text-carbon-soft">{note}</p>}
    </div>
  )
}

/** Totals printed like a receipt: label, dotted leader, value. */
export function Receipt({ lines }: { lines: [string, number | string][] }) {
  return (
    <dl className="ticket px-4 py-3 text-[14px]">
      {lines.map(([k, v]) => (
        <div key={k} className="flex items-baseline gap-2 py-1">
          <dt className="text-carbon-soft">{k}</dt>
          <span aria-hidden className="mb-1 flex-1 border-b border-dotted border-perf" />
          <dd className="m-0 font-mono text-carbon tabular">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

// ------------------------------------------------------------------ overview
export function AdminOverview() {
  const [days, setDays] = useState(30)
  const [now] = useState(() => Date.now())          // the window ends today
  const stats = useLoad(() => api.admin.stats(days), [days])
  const s = stats.data

  // every day of the window, also the quiet ones
  const dayList = Array.from({ length: days }, (_, i) => {
    const d = new Date(now - (days - 1 - i) * 86400000)
    return d.toISOString().slice(0, 10)
  })
  const series = (type: 'upload' | 'scan' | 'verdict' | 'correction' | 'chat') =>
    dayList.map((d) => s?.per_day.find((r) => r.day === d)?.[type] ?? 0)
  const verdictTotal = s ? s.verdicts.buy + s.verdicts.think + s.verdicts.skip : 0

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Title note="What people do in the app, counted from the event log.">Overview</Title>
        <div className="mb-5 flex gap-2">
          {[7, 30, 90].map((d) => <Chip key={d} selected={days === d} onClick={() => setDays(d)}>{d} days</Chip>)}
        </div>
      </div>
      {stats.error ? <ErrorNote error={stats.error} onRetry={stats.reload} /> : !s ? <Skeleton className="h-72" /> : (
        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <div className="flex flex-col gap-6">
            <Receipt lines={[
              ['Accounts', s.totals.users],
              [`Active (${days} d)`, s.totals.active_users],
              ['Wardrobe items', s.totals.items],
              ['Uploads', s.totals.upload],
              ['Scans', s.totals.scan],
              ['Verdicts', s.totals.verdict],
              ['Corrections', s.totals.correction],
              ['Chat messages', s.totals.chat],
              ['Try-ons', s.totals.tryon ?? 0],
            ]} />
            <section>
              <h2 className="mb-3 text-[15px] font-semibold text-carbon">Verdict mix</h2>
              {verdictTotal === 0 ? <p className="text-[13px] text-carbon-soft">No verdicts in this window.</p> : (
                <RowBars
                  max={1}
                  format={(v) => `${Math.round(v * 100)}%`}
                  rows={(['buy', 'think', 'skip'] as const).map((v) => ({ label: `${v} (${s.verdicts[v]})`, value: s.verdicts[v] / verdictTotal }))}
                />
              )}
            </section>
          </div>
          <section>
            <h2 className="sr-only">Per day</h2>
            <DayBars
              title="Activity per day"
              days={dayList}
              values={dayList.map((_, i) => TYPES.reduce((a, [type]) => a + series(type)[i], 0))}
              details={dayList.map((_, i) => TYPES.filter(([type]) => series(type)[i] > 0)
                .map(([type, label]) => `${label} ${series(type)[i]}`).join(' · '))}
              empty={`No activity in the last ${days} days.`}
            />
            <TableView caption="Events per day" head={['Day', 'Uploads', 'Scans', 'Verdicts', 'Corrections', 'Chat']}
              rows={s.per_day.map((r) => [r.day, r.upload, r.scan, r.verdict, r.correction, r.chat])} />
          </section>
        </div>
      )}
    </>
  )
}

// ------------------------------------------------------------------ model quality
export function AdminQuality() {
  const q = useLoad(() => api.admin.quality(), [])
  const d = q.data
  return (
    <>
      <Title note="How often users change what the models predicted, on every wardrobe item. A high rate on a field is where the model fails in real use.">
        Model quality
      </Title>
      {q.error ? <ErrorNote error={q.error} onRetry={q.reload} /> : !d ? <Skeleton className="h-72" /> : (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="ticket px-4 py-4">
            <h2 className="mb-1 text-[15px] font-semibold text-carbon">Corrected by users</h2>
            <p className="mb-4 text-[13px] text-carbon-soft">{d.items} wardrobe items · share whose value the user changed</p>
            <RowBars max={1} format={pct}
              rows={d.fields.map((f) => ({ label: f.field.replace('_', ' '), value: f.rate ?? 0,
                note: `${f.corrected} of ${f.items} · mean confidence ${f.mean_confidence ?? '-'}` }))} />
            <TableView caption="Corrections per field" head={['Field', 'Items', 'Corrected', 'Rate', 'Mean confidence']}
              rows={d.fields.map((f) => [f.field, f.items, f.corrected, pct(f.rate), f.mean_confidence ?? '-'])} />
            <Receipt lines={[
              [`Colours below the ${d.colour_below_cut.cut} cut (left for the user)`, `${d.colour_below_cut.items} · ${pct(d.colour_below_cut.rate)}`],
            ]} />
          </section>
          <section className="ticket px-4 py-4">
            <h2 className="mb-3 text-[15px] font-semibold text-carbon">Most frequent corrections</h2>
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="text-start text-carbon-soft">
                  {['Field', 'Model said', 'User set', 'Times'].map((h) => <th key={h} className="border-b border-perf px-2 py-1.5 text-start font-medium">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {d.fields.flatMap((f) => f.top_changes.map((c) => (
                  <tr key={`${f.field}-${c.predicted}-${c.corrected}`}>
                    <td className="border-b border-perf/40 px-2 py-1.5">{f.field.replace('_', ' ')}</td>
                    <td className="border-b border-perf/40 px-2 py-1.5">{c.predicted}</td>
                    <td className="border-b border-perf/40 px-2 py-1.5 font-medium">{c.corrected}</td>
                    <td className="border-b border-perf/40 px-2 py-1.5 font-mono tabular">{c.n}</td>
                  </tr>
                )))}
                {d.fields.every((f) => f.top_changes.length === 0) && (
                  <tr><td colSpan={4} className="px-2 py-3 text-carbon-soft">No corrections yet.</td></tr>
                )}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </>
  )
}

// ------------------------------------------------------------------ users
export function AdminUsers() {
  const { user: me } = useAuth()
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const res = useLoad(() => api.admin.users(search, page), [search, page])
  const [confirm, setConfirm] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)

  const act = async (id: string, fn: () => Promise<unknown>) => {
    setBusy(id)
    setError(null)
    try {
      await fn()
      setConfirm(null)
      await res.reload()
    } catch (e) {
      setError(e)
    } finally {
      setBusy(null)
    }
  }
  const pages = res.data ? Math.max(1, Math.ceil(res.data.total / res.data.size)) : 1

  return (
    <>
      <Title note="Disable an account to block its log-in at once; deleting removes the account with its wardrobe, photos, scans and chats.">Users</Title>
      <form className="mb-4 flex max-w-md gap-2" onSubmit={(e: FormEvent) => { e.preventDefault(); setPage(1); setSearch(query.trim()) }}>
        <label className="sr-only" htmlFor="user-search">Search by email</label>
        <input id="user-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by email"
          className="ticket min-h-11 flex-1 px-3 text-[15px] outline-none focus-visible:outline-2 focus-visible:outline-ink" />
        <Button type="submit" variant="secondary" aria-label="Search"><Search className="size-4" aria-hidden /></Button>
      </form>
      {error ? <div className="mb-3"><ErrorNote error={error} /></div> : null}
      {res.error ? <ErrorNote error={res.error} onRetry={res.reload} /> : !res.data ? <Skeleton className="h-64" /> : (
        <div className="ticket overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-[14px]">
            <thead>
              <tr className="text-carbon-soft">
                {['Email', 'Name', 'Role', 'Items', 'Status', ''].map((h) => <th key={h} className="border-b border-perf px-3 py-2 text-start font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {res.data.users.map((u) => {
                const self = u.id === me?.id
                return (
                  <tr key={u.id} className={u.disabled ? 'text-carbon-soft' : 'text-carbon'}>
                    <td className="border-b border-perf/40 px-3 py-2 font-mono text-[13px]">{u.email}</td>
                    <td className="border-b border-perf/40 px-3 py-2">{u.name}</td>
                    <td className="border-b border-perf/40 px-3 py-2">{u.role}</td>
                    <td className="border-b border-perf/40 px-3 py-2 font-mono tabular">{u.items}</td>
                    <td className="border-b border-perf/40 px-3 py-2">{u.disabled ? 'Disabled' : 'Active'}</td>
                    <td className="border-b border-perf/40 px-3 py-1.5 text-end">
                      {self ? <span className="text-[13px] text-carbon-soft">you</span> : confirm === u.id ? (
                        <span className="inline-flex items-center gap-2">
                          <span className="text-[13px]">Delete {u.email} and all their data?</span>
                          <Button className="min-h-9" busy={busy === u.id} onClick={() => act(u.id, () => api.admin.deleteUser(u.id))}>Delete</Button>
                          <Button variant="quiet" className="min-h-9" onClick={() => setConfirm(null)}>Cancel</Button>
                        </span>
                      ) : (
                        <span className="inline-flex gap-1">
                          <Button variant="quiet" className="min-h-9" disabled={busy === u.id}
                            onClick={() => act(u.id, () => api.admin.updateUser(u.id, { disabled: !u.disabled }))}>
                            {u.disabled ? 'Enable' : 'Disable'}
                          </Button>
                          <Button variant="quiet" className="min-h-9" disabled={busy === u.id}
                            onClick={() => act(u.id, () => api.admin.updateUser(u.id, { role: u.role === 'admin' ? 'user' : 'admin' }))}>
                            {u.role === 'admin' ? 'Remove admin' : 'Make admin'}
                          </Button>
                          <Button variant="quiet" className="min-h-9" onClick={() => setConfirm(u.id)}>Delete</Button>
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
              {res.data.users.length === 0 && <tr><td colSpan={6} className="px-3 py-4 text-carbon-soft">No account matches “{search}”.</td></tr>}
            </tbody>
          </table>
          <div className="flex items-center justify-between px-3 py-2 text-[13px] text-carbon-soft">
            <span className="font-mono tabular">{res.data.total} accounts · page {page} / {pages}</span>
            <span className="flex gap-1">
              <Button variant="quiet" className="min-h-9" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft className="size-4" aria-hidden /></Button>
              <Button variant="quiet" className="min-h-9" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight className="size-4" aria-hidden /></Button>
            </span>
          </div>
        </div>
      )}
    </>
  )
}

// ------------------------------------------------------------------ formula
export function AdminFormula() {
  const res = useLoad(() => api.admin.formula(), [])
  const [edits, setEdits] = useState<Record<string, string>>({})   // typed but not saved
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState<Formula | null>(null)
  const [error, setError] = useState<unknown>(null)

  const settings = res.data?.settings ?? []
  const values: Record<string, string> = Object.fromEntries(settings.map((s) => [s.name, edits[s.name] ?? String(s.value)]))
  const setValues = (v: Record<string, string>) => setEdits(v)
  const num = (k: string) => Number(values[k])
  const weights = settings.filter((s) => s.name.startsWith('weight_'))
  const weightSum = weights.reduce((a, s) => a + (num(s.name) || 0), 0)
  const problems = [
    ...settings.filter((s) => values[s.name] === '' || Number.isNaN(num(s.name)) || num(s.name) < 0).map((s) => `${s.name} must be a number ≥ 0`),
    ...(weights.length && weightSum <= 0 ? ['At least one weight must be above 0'] : []),
    ...(num('style_low') >= num('style_high') ? ['style_low must be below style_high'] : []),
  ]
  const changed = settings.filter((s) => num(s.name) !== s.value)

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const r = await api.admin.saveFormula(Object.fromEntries(changed.map((s) => [s.name, num(s.name)])))
      setResult(r)
      res.setData(r)
      setEdits({})
    } catch (e) {
      setError(e)
    } finally {
      setSaving(false)
    }
  }

  const field = (s: Formula['settings'][number]) => (
    <label key={s.name} className="grid grid-cols-[minmax(0,1fr)_96px] items-start gap-3 border-b border-perf/40 py-2.5">
      <span>
        <span className="block font-mono text-[13px] text-carbon">{s.name}</span>
        <span className="block text-[12px] leading-snug text-carbon-soft">{s.note.replace(/^REVIEW:?\s*/, '')}</span>
      </span>
      <input type="number" step="any" min={0} value={values[s.name] ?? ''} onChange={(e) => setValues({ ...values, [s.name]: e.target.value })}
        className="min-h-10 w-full border-b-[1.5px] border-perf bg-transparent px-1 text-end font-mono text-[15px] tabular outline-none focus:border-ink" />
      {num(s.name) !== s.value && <span className="col-span-2 -mt-1 text-end font-mono text-[11px] text-ink">edited · was {s.value}</span>}
    </label>
  )

  return (
    <>
      <Title note={`Team-set weights and settings of the compatibility formula. Saving rewrites ${res.data?.file ?? 'mappings/compatibility_weights.csv'} and applies at once; commit the file so the team keeps the change.`}>
        Formula
      </Title>
      {res.error ? <ErrorNote error={res.error} onRetry={res.reload} /> : !res.data ? <Skeleton className="h-72" /> : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="flex flex-col gap-6">
            <section className="ticket px-4 py-3">
              <h2 className="text-[15px] font-semibold text-carbon">Weights</h2>
              <p className="text-[12px] text-carbon-soft">Rescaled to sum 1 over the parts that can be computed. Current sum <span className="font-mono tabular">{weightSum.toFixed(2)}</span>.</p>
              {weights.map(field)}
            </section>
            <section className="ticket px-4 py-3">
              <h2 className="text-[15px] font-semibold text-carbon">Settings</h2>
              {settings.filter((s) => !s.name.startsWith('weight_')).map(field)}
            </section>
          </div>
          <aside className="flex flex-col gap-4 lg:sticky lg:top-8 lg:self-start">
            <div className="ticket px-4 py-4">
              <p className="text-[14px] text-carbon">{changed.length ? `${changed.length} unsaved ${new Intl.PluralRules('en').select(changed.length) === 'one' ? 'change' : 'changes'}` : 'No changes'}</p>
              {problems.length > 0 && (
                <ul role="alert" className="mt-2 space-y-1 text-[13px] text-stamp-deep">{problems.map((p) => <li key={p}>{p}</li>)}</ul>
              )}
              <Button className="mt-3 w-full" busy={saving} disabled={!changed.length || problems.length > 0} onClick={save}>Save to CSV</Button>
              {error ? <div className="mt-3"><ErrorNote error={error} /></div> : null}
              {result?.note && !error && <p role="status" className="mt-3 text-[13px] text-carbon">{result.note}</p>}
              <p className="mt-3 text-[12px] text-carbon-soft">Measure the effect: <code className="font-mono">python src/evaluate_compatibility.py</code></p>
            </div>
            <details className="ticket px-4 py-3 text-[13px]">
              <summary className="cursor-pointer font-medium text-ink">Colour and pattern rules (read-only)</summary>
              <p className="mt-2 text-carbon-soft">Edit mappings/colour_harmony.csv and pattern_mixing.csv in the repository.</p>
              <ul className="mt-2 max-h-64 space-y-0.5 overflow-auto font-mono text-[12px]">
                {[...res.data.colour_harmony, ...res.data.pattern_mixing].map((r) => (
                  <li key={`${r.a}-${r.b}`}>{r.a} + {r.b} = {r.score}</li>
                ))}
              </ul>
            </details>
          </aside>
        </div>
      )}
    </>
  )
}


// ------------------------------------------------------------------ seller listings (moderation)
function ReviewCard({ l, onDone }: { l: ReviewListing; onDone: () => void }) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState<'' | 'active' | 'rejected'>('')
  const [error, setError] = useState<unknown>(null)
  const decide = async (status: 'active' | 'rejected') => {
    setBusy(status)
    setError(null)
    try {
      await api.admin.review(l.id, status, note)
      onDone()
    } catch (e) {
      setError(e)
      setBusy('')
    }
  }
  const fields = [l.category, l.sub_category, l.colour, l.pattern].filter(Boolean).join(' · ')
  return (
    <section className="ticket flex flex-col gap-3 p-3 sm:flex-row">
      <ItemPhoto src={l.image_url} alt={l.title || fields} size={140} />
      <div className="min-w-0 flex-1 text-[13px]">
        <p className="text-[15px] font-semibold text-carbon" dir="auto">{l.title || '(no name)'}</p>
        <p className="text-carbon-soft">{fields || 'no fields'} · size {l.sizes.join(', ') || '-'}</p>
        <p className="mt-1 font-mono text-carbon tabular">{l.price_tnd} TND</p>
        <p className="mt-1 text-carbon" dir="auto">{l.seller?.city} · {l.seller?.contact}</p>
        <p className="text-carbon-soft">{l.seller_email} · {l.seen_at ? new Date(l.seen_at).toLocaleString('en-GB') : ''}</p>
        <label className="mt-2 block">
          <span className="sr-only">Note to the seller</span>
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} placeholder="Note to the seller (optional, e.g. why it is rejected)"
            className="min-h-10 w-full border-b-[1.5px] border-perf bg-transparent px-1 text-[14px] outline-none focus:border-ink" />
        </label>
        <div className="mt-3 flex gap-2">
          <Button busy={busy === 'active'} disabled={!!busy} onClick={() => decide('active')}>Approve</Button>
          <Button variant="secondary" busy={busy === 'rejected'} disabled={!!busy} onClick={() => decide('rejected')}>Reject</Button>
        </div>
        {error ? <div className="mt-2"><ErrorNote error={error} /></div> : null}
      </div>
    </section>
  )
}

export function AdminModeration() {
  const res = useLoad(() => api.admin.reviewQueue('pending'), [])
  return (
    <>
      <Title note="Friperie sellers' listings, oldest first. Only approved listings show in the app. Check that the photo shows one piece, with no face or person, and that the contact is a handle or a number (nothing offensive). The note is shown to the seller.">
        Moderation
      </Title>
      {res.error ? <ErrorNote error={res.error} onRetry={res.reload} /> : !res.data ? <Skeleton className="h-72" />
        : res.data.listings.length === 0 ? <p className="text-[14px] text-carbon-soft">Nothing waiting for review.</p> : (
          <>
            <p className="mb-3 text-[14px] text-carbon-soft">{res.data.total} waiting</p>
            <div className="grid gap-4 lg:grid-cols-2">
              {res.data.listings.map((l) => <ReviewCard key={l.id} l={l} onDone={res.reload} />)}
            </div>
          </>
        )}
    </>
  )
}
