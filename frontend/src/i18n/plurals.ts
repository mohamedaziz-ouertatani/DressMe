// Counted phrases with real plural rules (Intl.PluralRules). Arabic has six
// forms (zero, one, two, few, many, other); French treats 0 and 1 as "one".
import type { Language } from '../api/types'

type Forms = Partial<Record<Intl.LDMLPluralRule, string>> & { other: string }
type Table = Record<Language, Forms>

export const PLURALS = {
  pieces: {
    en: { one: '{n} piece', other: '{n} pieces' },
    fr: { one: '{n} pièce', other: '{n} pièces' },
    ar: { zero: 'لا قطع', one: 'قطعة واحدة', two: 'قطعتان', few: '{n} قطع', many: '{n} قطعة', other: '{n} قطعة' },
  },
  goodOutfits: {
    en: { one: '{n} good outfit', other: '{n} good outfits' },
    fr: { one: '{n} bonne tenue', other: '{n} bonnes tenues' },
    ar: { zero: 'لا لبسة جيدة', one: 'لبسة جيدة واحدة', two: 'لبستين جيدتين', few: '{n} لبسات جيدة', many: '{n} لبسة جيدة', other: '{n} لبسة جيدة' },
  },
  similarPieces: {
    en: { one: '{n} very similar {c} piece', other: '{n} very similar {c} pieces' },
    fr: { one: '{n} pièce très proche ({c})', other: '{n} pièces très proches ({c})' },
    ar: { one: 'قطعة مشابهة جدا ({c})', two: 'قطعتان مشابهتان جدا ({c})', few: '{n} قطع مشابهة جدا ({c})', many: '{n} قطعة مشابهة جدا ({c})', other: '{n} قطعة مشابهة جدا ({c})' },
  },
  sameCategory: {
    en: { one: '{n} piece of {c}', other: '{n} pieces of {c}' },
    fr: { one: '{n} pièce de type {c}', other: '{n} pièces de type {c}' },
    ar: { two: 'قطعتان من صنف {c}', few: '{n} قطع من صنف {c}', many: '{n} قطعة من صنف {c}', other: '{n} قطعة من صنف {c}' },
  },
} satisfies Record<string, Table>

const rules = new Map<Language, Intl.PluralRules>()

/** The phrase for `n` in `lang`, e.g. plural('pieces', 3, 'ar') -> "3 قطع". */
export function plural(key: keyof typeof PLURALS, n: number, lang: Language, vars: Record<string, string> = {}): string {
  let pr = rules.get(lang)
  if (!pr) {
    pr = new Intl.PluralRules(lang)
    rules.set(lang, pr)
  }
  const forms: Forms = PLURALS[key][lang]
  let s = forms[pr.select(n)] ?? forms.other
  s = s.replaceAll('{n}', new Intl.NumberFormat(lang === 'ar' ? 'ar-TN' : lang).format(n))
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v)
  return s
}
