import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Explanation, ExplainField, GuessField } from '../api/types'
import { useI18n } from '../i18n'
import type { StringKey } from '../i18n/strings'
import { CATEGORY_LABELS, COLOUR_LABELS, PATTERN_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { ErrorNote, Skeleton } from './states'

const ORDER: GuessField[] = ['category', 'sub_category', 'pattern', 'colour']
const TABLES = { category: CATEGORY_LABELS, sub_category: SUB_LABELS, pattern: PATTERN_LABELS, colour: COLOUR_LABELS }
const LABEL_KEY: Record<GuessField, StringKey> = { category: 'category', sub_category: 'type', pattern: 'pattern', colour: 'colour' }

/** "Why these labels?": where the classifier looked (heatmap), which pixels look
 *  like the colour, and the other answers it considered. Tapping another answer
 *  shows where the model would look for that one. Nothing is saved. */
export function ExplainPanel({ target }: { target: { itemId?: string; candidateId?: string } }) {
  const { t, lang } = useI18n()
  const [data, setData] = useState<Explanation | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState<GuessField | null>(null)

  useEffect(() => {
    let live = true
    api.explain(target).then((d) => { if (live) setData(d) }).catch((e) => { if (live) setError(e) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target.itemId, target.candidateId])

  const showOther = async (field: GuessField, value: string) => {
    setBusy(field)
    try {
      const d = await api.explain(target, field, value)
      setData((old) => old && { fields: { ...old.fields, [field]: d.fields[field] } })
    } catch (e) {
      setError(e)
    } finally {
      setBusy(null)
    }
  }

  if (error) return <ErrorNote error={error} />
  if (!data) return <Skeleton className="h-[320px]" />

  const label = (field: GuessField, v: string) => vocab(TABLES[field], v, lang)
  return (
    <div className="space-y-5">
      <p className="text-[13px] text-carbon-soft">{t('explainIntro')}</p>
      {ORDER.map((field) => {
        const f: ExplainField | undefined = data.fields[field]
        if (!f) return null
        const picture = f.heatmap ?? (f.reliable ? f.pixels : undefined)
        return (
          <div key={field} className="flex gap-4 max-sm:flex-col" aria-busy={busy === field || undefined}>
            {picture
              ? <img src={picture} alt="" className="size-[140px] shrink-0 border border-perf/60 bg-paper object-contain" />
              : <div className="size-[140px] shrink-0 border border-dashed border-perf/60" aria-hidden />}
            <div className="min-w-0 flex-1">
              <p className="text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t(LABEL_KEY[field])}</p>
              <p className="text-[15px] text-carbon">
                {field === 'colour'
                  ? f.reliable
                    ? t('explainColour', { value: label(field, f.shown), p: Math.round((f.share ?? 0) * 100) })
                    : t('explainColourUnreliable')
                  : t('explainLooked', { value: label(field, f.shown) })}
              </p>
              {field === 'colour' && f.reliable && <p className="text-[12px] text-carbon-soft">{t('explainColourNote')}</p>}
              {f.corrected && <p className="text-[12px] text-carbon-soft">{t('explainCorrected')}</p>}
              <p className="mt-2 text-[12px] text-carbon-soft">{t('explainAlternatives')}</p>
              <ul className="mt-1 space-y-1">
                {f.alternatives.map((a) => (
                  <li key={a.value}>
                    <button
                      type="button"
                      onClick={() => void showOther(field, a.value)}
                      aria-pressed={a.value === f.shown}
                      className={`flex min-h-8 w-full items-center gap-2 text-start text-[14px] ${a.value === f.shown ? 'font-semibold text-ink' : 'text-carbon'}`}
                    >
                      <span className="w-28 truncate">{label(field, a.value)}</span>
                      <span className="h-2 flex-1 bg-stock-deep" aria-hidden>
                        <span className="block h-2 bg-ink" style={{ width: `${Math.round(a.conf * 100)}%` }} />
                      </span>
                      <span className="w-10 text-end font-mono text-[11px] tabular">{Math.round(a.conf * 100)}%</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )
      })}
    </div>
  )
}
