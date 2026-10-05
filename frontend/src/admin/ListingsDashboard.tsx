// Admin > Listings: the shop listings at a glance, and the collector runs
// (src/collect_listings.py) started, followed and stopped from here.
// English only, like the rest of the admin pages.
import { Fragment, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Play, Square } from 'lucide-react'
import { api } from '../api/client'
import type { Job, JobStatus, ListingRun, ListingsOverview, OverviewSource, SourceCheck } from '../api/types'
import { Button } from '../ui/controls'
import { ErrorNote, Skeleton } from '../ui/states'
import { useLoad } from '../useLoad'
import { Receipt, Title } from './AdminPages'
import { DayBars, RowBars, TableView } from './charts'

const FINAL: JobStatus[] = ['finished', 'failed', 'stopped', 'lost']
const POLL_MS = 2000
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString('en-GB') : '-')

const TONE: Record<string, string> = {
  running: 'border-ink text-ink', stopping: 'border-stamp-deep text-stamp-deep', finished: 'border-carbon text-carbon',
  ok: 'border-carbon text-carbon', failed: 'border-stamp-deep text-stamp-deep', error: 'border-stamp-deep text-stamp-deep',
  blocked: 'border-stamp-deep text-stamp-deep', stopped: 'border-carbon-soft text-carbon-soft',
  lost: 'border-carbon-soft text-carbon-soft', skipped: 'border-carbon-soft text-carbon-soft',
}

function Pill({ value }: { value: string }) {
  return (
    <span className={`inline-flex items-center border px-1.5 font-mono text-[11px] uppercase tracking-wide ${TONE[value] ?? 'border-perf text-carbon-soft'}`}>
      {value}
    </span>
  )
}

function lastRunText(run: ListingRun | null) {
  return run ? `${run.result} · ${when(run.finished_at)}` : 'never'
}

export function AdminListings() {
  const overview = useLoad(() => api.admin.listingsOverview(), [])
  const history = useLoad(() => api.admin.jobs(), [])
  const [picked, setPicked] = useState<string | null>(null)
  const [startError, setStartError] = useState<unknown>(null)
  const [starting, setStarting] = useState(false)
  const ov = overview.data
  const running = ov?.running ?? null
  const shownId = picked ?? running?.id ?? ov?.last_job?.id ?? null

  const reloadAll = () => { overview.reload(); history.reload() }
  const start = async (body: Parameters<typeof api.admin.startJob>[0]) => {
    setStarting(true)
    setStartError(null)
    try {
      const job = await api.admin.startJob(body)
      setPicked(job.id)
      reloadAll()
    } catch (e) {
      setStartError(e)
    } finally {
      setStarting(false)
    }
  }

  return (
    <>
      <Title note="Shop and friperie listings, and the collector runs. A run here is the same as python src/collect_listings.py: only sources enabled and approved in mappings/listing_sources.csv can run, one run at a time. A blocked source stops by itself; never work around it.">
        Listings
      </Title>
      {overview.error ? <ErrorNote error={overview.error} onRetry={overview.reload} /> : !ov ? <Skeleton className="h-72" /> : (
        <div className="flex flex-col gap-6">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
            <Totals ov={ov} />
            <RunForm sources={ov.sources} busy={!!running || starting} running={running} error={startError} onStart={start} />
          </div>

          {shownId && <JobPanel key={shownId} jobId={shownId} onFinished={reloadAll} />}

          <SourcesTable sources={ov.sources} disabled={!!running || starting} onChecked={overview.reload}
            onRun={(id) => start({ sources: [id], catalogue: false, force: true, limit: 0 })} />

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="ticket px-4 py-3">
              <h2 className="mb-3 text-[15px] font-semibold text-carbon">Listed now, by category</h2>
              {ov.categories.length === 0 ? <p className="text-[13px] text-carbon-soft">Nothing listed yet.</p> : (
                <>
                  <RowBars rows={ov.categories.map((c) => ({ label: c.category || '(none)', value: c.count }))} />
                  <TableView caption="Listed now, by category" head={['category', 'listings']}
                    rows={ov.categories.map((c) => [c.category || '(none)', c.count])} />
                </>
              )}
            </section>
            <RunsChart runs={ov.runs_by_day} />
          </div>

          <History jobs={history.data} error={history.error} onRetry={history.reload} shownId={shownId} onPick={setPicked} />
        </div>
      )}
    </>
  )
}

function Totals({ ov }: { ov: ListingsOverview }) {
  const t = ov.totals
  return (
    <div className="flex flex-col gap-3">
      <Receipt lines={[
        ['Listed (active)', t.active],
        ['In stock', t.in_stock],
        ['Gone (sold out or removed)', t.gone],
        ['Friperie sellers listed', t.sellers_active],
        ['Waiting for review', t.pending],
        ['Sources allowed to run', `${t.sources_on} / ${t.sources_total}`],
      ]} />
      {t.pending > 0 && (
        <Link to="/admin/moderation" className="self-start text-[14px] text-ink underline decoration-1 underline-offset-4">
          Review {t.pending} seller listing{t.pending === 1 ? '' : 's'}
        </Link>
      )}
    </div>
  )
}

function RunForm({ sources, busy, running, error, onStart }: {
  sources: OverviewSource[]
  busy: boolean
  running: Job | null
  error: unknown
  onStart: (body: { sources: string[]; catalogue: boolean; force: boolean; limit: number }) => void
}) {
  const allowed = sources.filter((s) => !s.refused)
  const [chosen, setChosen] = useState<string[]>([])
  const [catalogue, setCatalogue] = useState(false)
  const [force, setForce] = useState(false)
  const [limit, setLimit] = useState('')
  const limitNumber = Number(limit || 0)
  const badLimit = !Number.isInteger(limitNumber) || limitNumber < 0 || limitNumber > 10000

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!badLimit) onStart({ sources: chosen, catalogue, force, limit: limitNumber })
  }
  const toggle = (id: string) => setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]))
  return (
    <form className="ticket flex flex-col gap-3 px-4 py-3 text-[14px]" onSubmit={submit}>
      <h2 className="text-[15px] font-semibold text-carbon">Start a run</h2>
      <fieldset>
        <legend className="mb-1 text-[13px] text-carbon-soft">Sources (none ticked = every source that is due)</legend>
        {allowed.length === 0 && <p className="text-[13px] text-carbon-soft">No source is enabled and approved.</p>}
        {allowed.map((s) => (
          <label key={s.source_id} className="flex min-h-9 items-center gap-2">
            <input type="checkbox" checked={chosen.includes(s.source_id)} onChange={() => toggle(s.source_id)} className="size-4 accent-[var(--color-ink)]" />
            <span className="font-mono text-[13px]">{s.source_id}</span>
            <span className="text-[12px] text-carbon-soft">{s.kind}</span>
          </label>
        ))}
      </fieldset>
      <label className="flex min-h-9 items-center gap-2">
        <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="size-4 accent-[var(--color-ink)]" />
        Run even if it ran recently (ignore refresh_days)
      </label>
      <label className="flex min-h-9 items-center gap-2">
        <input type="checkbox" checked={catalogue} onChange={(e) => setCatalogue(e.target.checked)} className="size-4 accent-[var(--color-ink)]" />
        Whole catalogue (Inditex sources only)
      </label>
      <label className="flex items-center gap-3">
        <span>Limit (smoke test, 0 = all)</span>
        <input inputMode="numeric" value={limit} onChange={(e) => setLimit(e.target.value)} placeholder="0" aria-invalid={badLimit || undefined}
          className="min-h-9 w-24 border-b-[1.5px] border-perf bg-transparent px-1 text-end font-mono outline-none focus:border-ink aria-invalid:border-stamp-deep" />
      </label>
      <p className="text-[12px] text-carbon-soft">A run with a limit never marks listings as gone. The first run loads the models (~1 min).</p>
      <Button type="submit" busy={busy && !running} disabled={busy || badLimit}>
        <Play className="size-4" aria-hidden /> {running ? 'A run is going on' : 'Start'}
      </Button>
      {error ? <ErrorNote error={error} /> : null}
    </form>
  )
}

/** One run, followed live: status, progress, results per source, the log, and Stop. */
function JobPanel({ jobId, onFinished }: { jobId: string; onFinished: () => void }) {
  const [job, setJob] = useState<Job | null>(null)
  const [log, setLog] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [stopping, setStopping] = useState(false)
  const offset = useRef(0)
  const sawRunning = useRef(false)
  const finished = useRef(onFinished)
  const pre = useRef<HTMLPreElement>(null)
  useEffect(() => { finished.current = onFinished })

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const tick = async () => {
      try {
        const j = await api.admin.job(jobId)
        const l = await api.admin.jobLog(jobId, offset.current)
        if (!alive) return
        offset.current = l.offset
        if (l.text) setLog((old) => (old + l.text).slice(-200_000))   // keep the page light
        setJob(j)
        setError(null)
        if (FINAL.includes(j.status)) {
          if (sawRunning.current) finished.current()            // it just ended: refresh the counts
          return
        }
        sawRunning.current = true
      } catch (e) {
        if (alive) setError(e)
      }
      if (alive) timer = setTimeout(tick, POLL_MS)
    }
    void tick()
    return () => { alive = false; clearTimeout(timer) }
  }, [jobId])

  // follow the end of the log, unless the admin scrolled up to read
  useEffect(() => {
    const el = pre.current
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 80) el.scrollTop = el.scrollHeight
  }, [log])

  const stop = async () => {
    setStopping(true)
    try {
      setJob(await api.admin.stopJob(jobId))
    } catch (e) {
      setError(e)
    } finally {
      setStopping(false)
    }
  }

  if (!job) return error ? <ErrorNote error={error} /> : <Skeleton className="h-40" />
  const live = !FINAL.includes(job.status)
  const p = job.progress
  const share = p.total ? Math.min(1, (p.done ?? 0) / p.total) : 0
  return (
    <section className="ticket px-4 py-3" aria-live="polite">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 className="text-[15px] font-semibold text-carbon">Run {job.id.slice(-6)}</h2>
        <Pill value={job.status} />
        <span className="text-[13px] text-carbon-soft">
          {job.sources.length ? job.sources.join(', ') : 'every source that is due'}
          {job.catalogue && ' · whole catalogue'}{job.force && ' · forced'}{job.limit ? ` · limit ${job.limit}` : ''}
        </span>
        {live && (
          <Button variant="secondary" className="ms-auto" busy={stopping} disabled={job.status === 'stopping'} onClick={stop}>
            <Square className="size-4" aria-hidden /> {job.status === 'stopping' ? 'Stopping…' : 'Stop'}
          </Button>
        )}
      </div>
      <p className="mt-1 text-[12px] text-carbon-soft">
        Started {when(job.started_at)} by {job.started_by}{job.finished_at && ` · ended ${when(job.finished_at)}`}
        {job.exit_code !== null && job.exit_code !== 0 && ` · exit code ${job.exit_code}`}
      </p>
      {job.status === 'stopping' && (
        <p className="mt-1 text-[12px] text-stamp-deep">Finishing the current item; if it takes more than 30 s, the whole run is ended.</p>
      )}
      {job.status === 'lost' && (
        <p className="mt-1 text-[12px] text-stamp-deep">This run stopped answering (the backend or the computer restarted). What it saved stays.</p>
      )}
      {live && (
        <div className="mt-3">
          <p className="text-[13px] text-carbon">
            {p.source ? <span className="font-mono">{p.source}</span> : null}{p.source && ' · '}{p.phase ?? 'starting'}
            {p.total ? <span className="font-mono tabular"> · {p.done ?? 0} / {p.total}</span> : null}
          </p>
          <div className="mt-1 h-2 bg-stock-deep/60" role="progressbar" aria-valuemin={0} aria-valuemax={p.total ?? 0} aria-valuenow={p.done ?? 0}>
            <div className="h-full bg-ink-soft transition-[width] duration-500" style={{ width: `${share * 100}%` }} />
          </div>
        </div>
      )}
      {Object.keys(job.results).length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
          {Object.entries(job.results).map(([sid, outcome]) => (
            <li key={sid} className="flex items-center gap-1.5"><span className="font-mono">{sid}</span> <Pill value={outcome} /></li>
          ))}
        </ul>
      )}
      {Object.entries(job.plan).some(([, why]) => why !== 'run') && (
        <details className="mt-2 text-[12px] text-carbon-soft">
          <summary className="cursor-pointer text-ink">Skipped sources</summary>
          <ul className="mt-1 space-y-0.5">
            {Object.entries(job.plan).filter(([, why]) => why !== 'run').map(([sid, why]) => (
              <li key={sid}><span className="font-mono">{sid}</span>: {why}</li>
            ))}
          </ul>
        </details>
      )}
      <pre ref={pre} tabIndex={0} aria-label="Run log"
        className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap bg-stock-deep/60 p-2 font-mono text-[11px] leading-relaxed text-carbon" dir="ltr">
        {log || (live ? 'Waiting for the first lines…' : '(empty log)')}
      </pre>
      {error ? <div className="mt-2"><ErrorNote error={error} /></div> : null}
    </section>
  )
}

function SourcesTable({ sources, disabled, onRun, onChecked }: {
  sources: OverviewSource[]
  disabled: boolean
  onRun: (id: string) => void
  onChecked: () => void
}) {
  const [checking, setChecking] = useState<string | null>(null)
  const [result, setResult] = useState<{ id: string; check?: SourceCheck; error?: unknown } | null>(null)

  /** The read-only check from the page: the same as python src/check_shop_source.py <id> --save. */
  const check = async (id: string) => {
    setChecking(id)
    setResult(null)
    try {
      setResult({ id, check: await api.admin.checkSource(id) })
      onChecked()
    } catch (e) {
      setResult({ id, error: e })
    } finally {
      setChecking(null)
    }
  }

  return (
    <section className="ticket overflow-x-auto px-4 py-3">
      <h2 className="mb-2 text-[15px] font-semibold text-carbon">Sources</h2>
      <table className="w-full min-w-[760px] border-collapse text-start text-[13px]">
        <thead>
          <tr className="text-carbon-soft">
            {['Source', 'Kind', 'Can run?', 'Listed', 'In stock', 'Gone', 'Last run', ''].map((h) => (
              <th key={h} className="border-b border-perf px-2 py-1 text-start font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <Fragment key={s.source_id}>
              <tr className="align-top">
                <td className="border-b border-perf/40 px-2 py-2 font-mono" title={s.note}>{s.source_id}</td>
                <td className="border-b border-perf/40 px-2 py-2">{s.kind || '-'}</td>
                <td className="border-b border-perf/40 px-2 py-2">
                  {s.refused ? <span className="text-carbon-soft">{s.refused}</span> : 'yes'}
                  {s.last_check && (
                    <span className="block text-[12px] text-carbon-soft">
                      checked {when(s.last_check.checked_at)}: {s.last_check.kind || 'nothing supported'}
                    </span>
                  )}
                </td>
                <td className="border-b border-perf/40 px-2 py-2 font-mono tabular">{s.active}</td>
                <td className="border-b border-perf/40 px-2 py-2 font-mono tabular">{s.in_stock}</td>
                <td className="border-b border-perf/40 px-2 py-2 font-mono tabular">{s.gone}</td>
                <td className="border-b border-perf/40 px-2 py-2">
                  {s.last_run ? <><Pill value={s.last_run.result} /> <span className="font-mono text-[12px] tabular">{when(s.last_run.finished_at)}</span></> : 'never'}
                  {s.last_run && s.last_run.result !== 'ok' && <span className="block text-[12px] text-carbon-soft">last good: {lastRunText(s.last_ok)}</span>}
                </td>
                <td className="border-b border-perf/40 px-2 py-2 text-end">
                  <div className="flex flex-col items-end gap-1">
                    {!s.refused && (
                      <Button variant="quiet" disabled={disabled || !!checking} onClick={() => onRun(s.source_id)} className="min-h-9 whitespace-nowrap px-2 text-[13px]">
                        Run now
                      </Button>
                    )}
                    {s.checkable && (
                      <Button variant="quiet" busy={checking === s.source_id} disabled={disabled || !!checking}
                        onClick={() => check(s.source_id)} className="min-h-9 whitespace-nowrap px-2 text-[13px]">
                        {checking === s.source_id ? 'Checking… (up to a minute)' : 'Check'}
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
              {result?.id === s.source_id && (
                <tr>
                  <td colSpan={8} className="border-b border-perf/40 px-2 pb-3">
                    {result.error ? <ErrorNote error={result.error} /> : result.check && (
                      <div className="bg-stock-deep/60 p-3" aria-live="polite">
                        <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-carbon" dir="ltr">{result.check.lines.join('\n')}</pre>
                        <p className={`mt-2 text-[13px] ${result.check.saved ? 'text-carbon' : 'text-stamp-deep'}`}>
                          {result.check.saved
                            ? `Kind saved: ${result.check.kind}. ${result.check.note ?? ''}`
                            : result.check.note ?? 'No supported way to read this shop was found.'}
                        </p>
                      </div>
                    )}
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[12px] text-carbon-soft">
        Check reads the shop's robots.txt and one product (read-only, polite) and saves how to read it; the shop stays off.
        Turn a source on in mappings/listing_sources.csv (team decision: enabled + approved_on, after a team member has read the shop's terms).
      </p>
    </section>
  )
}

function RunsChart({ runs }: { runs: ListingsOverview['runs_by_day'] }) {
  const [now] = useState(() => Date.now())
  const byDay = new Map(runs.map((r) => [r.day, r]))
  const days = Array.from({ length: 30 }, (_, i) => new Date(now - (29 - i) * 86400000).toISOString().slice(0, 10))
  const parts = (d: string) => Object.entries(byDay.get(d) ?? {}).filter(([k]) => k !== 'day') as [string, number][]
  const values = days.map((d) => parts(d).reduce((a, [, n]) => a + n, 0))
  return (
    <div>
      <DayBars title="Source runs per day (30 days)" days={days} values={values}
        details={days.map((d) => parts(d).map(([k, n]) => `${n} ${k}`).join(', '))} empty="No run in the last 30 days." />
      <TableView caption="Source runs per day" head={['day', 'runs', 'results']}
        rows={days.filter((_, i) => values[i] > 0).map((d) => [d, parts(d).reduce((a, [, n]) => a + n, 0), parts(d).map(([k, n]) => `${n} ${k}`).join(', ')])} />
    </div>
  )
}

function History({ jobs, error, onRetry, shownId, onPick }: {
  jobs: Job[] | null
  error: unknown
  onRetry: () => void
  shownId: string | null
  onPick: (id: string) => void
}) {
  return (
    <section className="ticket overflow-x-auto px-4 py-3">
      <h2 className="mb-2 text-[15px] font-semibold text-carbon">Runs started here</h2>
      {error ? <ErrorNote error={error} onRetry={onRetry} /> : !jobs ? <Skeleton className="h-24" /> : jobs.length === 0 ? (
        <p className="text-[13px] text-carbon-soft">None yet. The nightly task runs are on the Sources table (last run).</p>
      ) : (
        <table className="w-full min-w-[640px] border-collapse text-start text-[13px]">
          <thead>
            <tr className="text-carbon-soft">
              {['Started', 'By', 'Sources', 'Status', 'Results', ''].map((h) => <th key={h} className="border-b border-perf px-2 py-1 text-start font-medium">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} className={j.id === shownId ? 'bg-stock-deep/50' : ''}>
                <td className="border-b border-perf/40 px-2 py-1.5 font-mono tabular">{when(j.started_at)}</td>
                <td className="border-b border-perf/40 px-2 py-1.5">{j.started_by}</td>
                <td className="border-b border-perf/40 px-2 py-1.5 font-mono">{j.sources.length ? j.sources.join(', ') : 'all due'}</td>
                <td className="border-b border-perf/40 px-2 py-1.5"><Pill value={j.status} /></td>
                <td className="border-b border-perf/40 px-2 py-1.5">{Object.entries(j.results).map(([s, r]) => `${s}: ${r}`).join(', ') || '-'}</td>
                <td className="border-b border-perf/40 px-2 py-1.5 text-end">
                  {j.id !== shownId && <Button variant="quiet" className="min-h-9 px-2 text-[13px]" onClick={() => onPick(j.id)}>Show</Button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
