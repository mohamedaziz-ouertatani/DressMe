// Admin > Explainability (team-only, English): the XAI evaluations' numbers, how the
// "not sure" flag behaves on real uploads, what the chat agents' tool calls did, and
// the team's XAI settings (mappings/xai_settings.csv), editable like the Formula page.
import { useState } from 'react'
import { api } from '../api/client'
import type { AdminXai, XaiSetting } from '../api/types'
import { Button } from '../ui/controls'
import { ErrorNote, Skeleton } from '../ui/states'
import { useLoad } from '../useLoad'
import { Title } from './AdminPages'

const pct = (v: number | null | undefined) => (v === null || v === undefined ? '-' : `${(v * 100).toFixed(1)}%`)
const COUNTS = new Set(['near_miss', 'min_swap_gain'])          // in points; every other setting is 0-1

/** A small always-visible table (the numbers ARE the content here, not a chart's companion). */
function Table({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full border-collapse text-start text-[13px]">
        <caption className="mb-1 text-start text-[12px] text-carbon-soft">{caption}</caption>
        <thead>
          <tr>{head.map((h) => <th key={h} className="border-b border-perf px-2 py-1 text-start font-medium text-carbon-soft">{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.length === 0
            ? <tr><td colSpan={head.length} className="px-2 py-2 text-carbon-soft">Nothing yet.</td></tr>
            : rows.map((r, i) => (
              <tr key={i}>{r.map((c, j) => <td key={j} className="border-b border-perf/40 px-2 py-1 font-mono tabular">{c}</td>)}</tr>
            ))}
        </tbody>
      </table>
    </div>
  )
}

function Evaluation({ title, block, children }: {
  title: string
  block: { missing?: true; date?: string; command: string; report?: string }
  children: React.ReactNode
}) {
  return (
    <section className="ticket px-4 py-3">
      <h2 className="text-[15px] font-semibold text-carbon">{title}</h2>
      {block.missing
        ? <p className="mt-1 text-[13px] text-carbon-soft">No report yet.</p>
        : <div className="mt-2">{children}</div>}
      <p className="mt-2 font-mono text-[11px] text-ink-soft">
        {block.date ? `${block.report} · ${block.date} · ` : ''}re-run: {block.command}
      </p>
    </section>
  )
}

export function AdminXai() {
  const res = useLoad(() => api.admin.xai(), [])
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<AdminXai | null>(null)
  const [error, setError] = useState<unknown>(null)

  const d = res.data
  const settings = d?.settings ?? []
  const value = (s: XaiSetting) => edits[s.name] ?? String(s.value)
  const num = (s: XaiSetting) => Number(value(s))
  const problems = settings.filter((s) => value(s) === '' || Number.isNaN(num(s)) || num(s) < 0 || (!COUNTS.has(s.name) && num(s) > 1))
    .map((s) => `${s.name} must be ${COUNTS.has(s.name) ? 'a number ≥ 0' : 'between 0 and 1'}`)
  const changed = settings.filter((s) => num(s) !== s.value)

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const r = await api.admin.saveXai(Object.fromEntries(changed.map((s) => [s.name, num(s)])))
      setSaved(r)
      res.setData(r)
      setEdits({})
    } catch (e) {
      setError(e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <Title note="Why the app's answers can be trusted, and where they cannot. The numbers come from the XAI evaluation reports (reports/phase4/) and from real use; the full write-up is reports/phase4/xai_report.pdf.">
        Explainability
      </Title>
      {res.error ? <ErrorNote error={res.error} onRetry={res.reload} /> : !d ? <Skeleton className="h-72" /> : (
        <div className="flex flex-col gap-6">
          <div className="grid gap-4 lg:grid-cols-3">
            <Evaluation title="“Not sure, check” flag (test set)" block={d.evaluations.labels}>
              <Table caption="Accuracy of sure vs flagged answers" head={['Field', 'Sure', 'Flagged', 'Share flagged']}
                rows={(d.evaluations.labels.flag ?? []).map((f) => [f.field, pct(f.sure_accuracy), pct(f.unsure_accuracy), pct(f.unsure_share)])} />
              <Table caption="Deletion test at 10% (confidence drop)" head={['Field', 'Heatmap', 'Same size, wrong place', 'Scattered']}
                rows={(d.evaluations.labels.deletion ?? []).map((r) => [r.field, r.heatmap.toFixed(3), r.shifted_region.toFixed(3), r.scattered_pixels.toFixed(3)])} />
            </Evaluation>
            <Evaluation title="Weakest piece (outfits)" block={d.evaluations.outfits}>
              <Table caption="Finds a random intruder" head={['Dataset', 'Outfits', 'Found', 'Chance', 'Points add up']}
                rows={(d.evaluations.outfits.rows ?? []).map((r) => [r.dataset, r.outfits, pct(r.hit), pct(r.chance), r.points_add_up])} />
            </Evaluation>
            <Evaluation title="Concept probes (similarity)" block={d.evaluations.concepts}>
              <p className="mb-1 text-[13px] text-carbon">Mean AUC <span className="font-mono tabular">{d.evaluations.concepts.mean_auc?.toFixed(3) ?? '-'}</span> (0.5 = chance)</p>
              <Table caption="AUC against the matching label (e.g. denim vs jeans)" head={['Concept', 'Labelled', 'AUC']}
                rows={(d.evaluations.concepts.rows ?? []).map((r) => [r.concept, r.with_label, r.auc === null ? 'too few' : r.auc.toFixed(3)])} />
            </Evaluation>
          </div>

          <section className="ticket px-4 py-3">
            <h2 className="text-[15px] font-semibold text-carbon">Real use: the flag on uploads</h2>
            <p className="text-[12px] text-carbon-soft">
              {d.real_use.items} wardrobe items; {d.real_use.before_xai} were analysed before the XAI layer (no stored alternatives) and are left out.
              A useful flag means flagged guesses get corrected much more often than sure ones.
            </p>
            <Table caption="Corrections after a sure vs a flagged guess" head={['Field', 'Items', 'Flagged', 'Corrected when flagged', 'Corrected when sure']}
              rows={d.real_use.fields.map((f) => [f.field, f.items, f.unsure, pct(f.unsure_corrected_rate), pct(f.sure_corrected_rate)])} />
          </section>

          <section className="ticket px-4 py-3">
            <h2 className="text-[15px] font-semibold text-carbon">Chat: what the agents' tools did (last {d.traces.days} days)</h2>
            <p className="text-[12px] text-carbon-soft">
              {d.traces.answers} answers with a trace. The Explainer answered {d.traces.explainer_answers} times,
              {' '}{d.traces.explainer_without_tools} of them without calling any tool (from memory: check those answers).
            </p>
            <Table caption="Tool calls" head={['Tool', 'Calls', 'Errors', 'Error rate', 'Agents']}
              rows={d.traces.tools.map((t) => [t.tool, t.calls, t.errors, pct(t.calls ? t.errors / t.calls : null), t.agents.join(', ')])} />
          </section>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <section className="ticket px-4 py-3">
              <h2 className="text-[15px] font-semibold text-carbon">XAI settings ({d.file})</h2>
              {settings.map((s) => (
                <label key={s.name} className="grid grid-cols-[minmax(0,1fr)_96px] items-start gap-3 border-b border-perf/40 py-2.5">
                  <span>
                    <span className="block font-mono text-[13px] text-carbon">{s.name}</span>
                    <span className="block text-[12px] leading-snug text-carbon-soft">{s.note.replace(/^REVIEW:?\s*/, '')}</span>
                  </span>
                  <input type="number" step="any" min={0} max={COUNTS.has(s.name) ? undefined : 1} value={value(s)}
                    onChange={(e) => setEdits({ ...edits, [s.name]: e.target.value })}
                    className="min-h-10 w-full border-b-[1.5px] border-perf bg-transparent px-1 text-end font-mono text-[15px] tabular outline-none focus:border-ink" />
                  {num(s) !== s.value && <span className="col-span-2 -mt-1 text-end font-mono text-[11px] text-ink">edited · was {s.value}</span>}
                </label>
              ))}
              <p className="mt-3 text-[12px] text-carbon-soft">Concepts shown on the Similar page (mappings/style_concepts.csv, edit the file): {d.concepts.map((c) => c.concept).join(', ')}.</p>
            </section>
            <aside className="flex flex-col gap-4 lg:sticky lg:top-8 lg:self-start">
              <div className="ticket px-4 py-4">
                <p className="text-[14px] text-carbon">{changed.length ? `${changed.length} unsaved ${changed.length === 1 ? 'change' : 'changes'}` : 'No changes'}</p>
                {problems.length > 0 && <ul role="alert" className="mt-2 space-y-1 text-[13px] text-stamp-deep">{problems.map((p) => <li key={p}>{p}</li>)}</ul>}
                <Button className="mt-3 w-full" busy={saving} disabled={!changed.length || problems.length > 0} onClick={save}>Save to CSV</Button>
                {error ? <div className="mt-3"><ErrorNote error={error} /></div> : null}
                {saved?.note && !error && <p role="status" className="mt-3 text-[13px] text-carbon">{saved.note}</p>}
              </div>
            </aside>
          </div>
        </div>
      )}
    </>
  )
}
