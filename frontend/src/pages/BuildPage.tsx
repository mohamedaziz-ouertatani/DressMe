import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, Plus, Sparkles } from 'lucide-react'
import { api } from '../api/client'
import type { Completion, Item, Outfit } from '../api/types'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import { Page } from '../shell'
import { ItemPhoto } from '../ui/ItemPhoto'
import { OutfitStrip } from '../ui/OutfitStrip'
import { Empty, ErrorNote, Skeleton } from '../ui/states'
import { useLoad } from '../useLoad'

export function BuildPage() {
  const { t, lang } = useI18n()
  const items = useLoad(() => api.items(), [])
  const limits = useLoad(() => api.outfitLimits(), [])
  const [picked, setPicked] = useState<string[]>([])
  const [outfit, setOutfit] = useState<Outfit | null>(null)
  const [completions, setCompletions] = useState<Completion[]>([])
  const [error, setError] = useState<unknown>(null)
  const [feedback, setFeedback] = useState<1 | -1>()

  useEffect(() => {
    setFeedback(undefined)
    if (!picked.length) return
    let stale = false
    Promise.all([api.score(picked), api.complete(picked, 4)])
      .then(([o, c]) => {
        if (stale) return
        setOutfit(o)
        setCompletions(c)
        setError(null)
      })
      .catch((e) => !stale && setError(e))
    return () => { stale = true }
  }, [picked])

  // An outfit never holds the same sub-category twice (two pairs of jeans) or more
  // pieces of a category than its limit (one top). Picking such a piece swaps it
  // in for the oldest clashing one instead of stacking them; the backend refuses clashes.
  const toggle = (id: string) =>
    setPicked((p) => {
      if (p.includes(id)) return p.filter((x) => x !== id)
      const byId = new Map((items.data ?? []).map((it) => [it.id, it]))
      const next = byId.get(id)
      if (!next) return [...p, id].slice(-8)
      let kept = p.filter((x) => !next.sub_category || byId.get(x)?.sub_category !== next.sub_category)
      const max = limits.data?.max_items[next.category] ?? 1
      const sameCat = kept.filter((x) => byId.get(x)?.category === next.category)
      const drop = new Set(sameCat.slice(0, Math.max(0, sameCat.length - (max - 1))))
      kept = kept.filter((x) => !drop.has(x))
      return [...kept, id].slice(-8)
    })
  const label = (it: Item) => vocab(SUB_LABELS, it.sub_category, lang) || vocab(CATEGORY_LABELS, it.category, lang)

  const shownOutfit = picked.length ? outfit : null
  const shownCompletions = picked.length ? completions : []
  // shown twice: in the aside on desktop, under the pieces on phones (one at a time)
  const result = (
    <div>
      {error ? <ErrorNote error={error} /> : null}
      {shownOutfit ? (
        <div className="pt-6">
          <OutfitStrip
            outfit={shownOutfit}
            compact
            feedback={feedback}
            onFeedback={(rating) => {
              const previous = feedback
              setFeedback(rating)
              api.feedback(shownOutfit.items.map((item) => item.id), rating).catch((error) => {
                setFeedback(previous)
                setError(error)
              })
            }}
          />
          <Link to={`/tryon?items=${picked.join(',')}`} className="mt-4 inline-flex min-h-11 items-center gap-2 border-[1.5px] border-ink bg-paper px-4 text-[15px] font-medium text-ink">
            <Sparkles className="size-4" aria-hidden /> {t('tryOnBtn')}
          </Link>
          {shownCompletions.length > 0 && (
            <div className="mt-6">
              <h2 className="mb-2 text-[13px] font-medium uppercase tracking-[0.06em] text-carbon-soft">{t('completeWith')}</h2>
              <ul className="flex flex-col gap-2">
                {shownCompletions.map((c) => (
                  <li key={c.item.id}>
                    <button onClick={() => toggle(c.item.id)} className="ticket flex w-full items-end gap-3 p-2 text-start hover:[box-shadow:var(--shadow-lift)]">
                      <ItemPhoto src={c.item.image_url} alt={label(c.item)} size={56} />
                      <span className="flex-1 pb-1 text-[14px] text-carbon">{label(c.item)}</span>
                      <span className="pb-1 font-mono text-[13px] text-ink tabular" dir="ltr">{Math.round(c.score)}</span>
                      <Plus className="mb-1.5 size-4 text-ink" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <p className="ticket px-4 py-4 text-[14px] text-carbon-soft">{t('pickAtLeast')}</p>
      )}
    </div>
  )

  return (
    <Page title={t('buildTitle')} aside={<div className="hidden lg:sticky lg:top-10 lg:block">{result}</div>}>
      <p className="mb-4 max-w-[60ch] text-[15px] text-carbon-soft">{t('buildHint')}</p>
      {items.error ? (
        <ErrorNote error={items.error} onRetry={items.reload} />
      ) : !items.data ? (
        <Skeleton className="h-64" />
      ) : items.data.length === 0 ? (
        <Empty title={t('wardrobeEmptyTitle')} body={t('wardrobeEmptyBody')} />
      ) : (
        // one section per category (vocab order), so a top and its alternatives sit together
        <div className="flex flex-col gap-6">
          {Object.keys(CATEGORY_LABELS).map((cat) => {
            const group = items.data!.filter((it) => it.category === cat)
            if (!group.length) return null
            return (
              <section key={cat} aria-labelledby={`build-${cat}`}>
                <h2 id={`build-${cat}`} className="mb-2 text-[13px] font-medium uppercase tracking-[0.06em] text-carbon-soft">
                  {vocab(CATEGORY_LABELS, cat, lang)} <span className="font-mono tabular" dir="ltr">· {group.length}</span>
                </h2>
                <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 xl:grid-cols-5">
                  {group.map((it) => {
                    const on = picked.includes(it.id)
                    return (
                      <li key={it.id}>
                        <button
                          aria-pressed={on}
                          onClick={() => toggle(it.id)}
                          className={`relative block w-full p-1.5 transition-shadow duration-150 ${on ? 'bg-paper outline-[2px] outline-ink [outline-style:solid]' : 'ticket'}`}
                        >
                          <div className="flex justify-center"><ItemPhoto src={it.image_url} alt={label(it)} size={88} /></div>
                          <span className="mt-1 block truncate text-[12px] text-carbon">{label(it)}</span>
                          {on && (
                            <span className="absolute end-1.5 top-1.5 grid size-6 place-items-center rounded-full bg-ink text-paper">
                              <Check className="size-3.5" aria-hidden />
                            </span>
                          )}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </section>
            )
          })}
        </div>
      )}
      <div className="mt-8 lg:hidden">{result}</div>
    </Page>
  )
}
