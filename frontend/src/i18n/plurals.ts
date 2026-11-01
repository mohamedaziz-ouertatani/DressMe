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
  // the words under the verdict's big number (step H2): the count itself is printed apart
  goodOutfitsUnit: {
    en: { one: 'good outfit', other: 'good outfits' },
    fr: { one: 'bonne tenue', other: 'bonnes tenues' },
    ar: { one: 'إطلالة جيدة', two: 'إطلالتان جيدتان', few: 'إطلالات جيدة', other: 'إطلالة جيدة' },
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
  inOutfits: {
    en: { one: 'in {n} good outfit', other: 'in {n} good outfits' },
    fr: { one: 'dans {n} bonne tenue', other: 'dans {n} bonnes tenues' },
    ar: { one: 'في لبسة جيدة واحدة', two: 'في لبستين جيدتين', few: 'في {n} لبسات جيدة', many: 'في {n} لبسة جيدة', other: 'في {n} لبسة جيدة' },
  },
  newPairs: {
    en: { one: '{n} new pair', other: '{n} new pairs' },
    fr: { one: '{n} nouvelle paire', other: '{n} nouvelles paires' },
    ar: { zero: 'لا تركيبة جديدة', one: 'تركيبة جديدة واحدة', two: 'تركيبتان جديدتان', few: '{n} تركيبات جديدة', many: '{n} تركيبة جديدة', other: '{n} تركيبة جديدة' },
  },
  // the budget cap on the look-alike listings ({p} = the share of the budget, already formatted);
  // after من the counted noun is genitive: دينارين, 3-10 دنانير, 11-99 دينارا, 100+ and fractions دينار
  underBudget: {
    en: { other: 'Under {n} TND ({p}% of your budget)' },
    fr: { other: 'Moins de {n} TND ({p} % de ton budget)' },
    ar: { one: 'أقل من دينار واحد ({p} من ميزانيتك)', two: 'أقل من دينارين ({p} من ميزانيتك)', few: 'أقل من {n} دنانير ({p} من ميزانيتك)', many: 'أقل من {n} دينارا ({p} من ميزانيتك)', other: 'أقل من {n} دينار ({p} من ميزانيتك)' },
  },
  // the price band's range, counted on its SECOND number ({low} already formatted); after إلى the
  // noun is genitive, same forms as underBudget: دينارين, 3-10 دنانير, 11-99 دينارا, 100+ and fractions دينار
  priceRange: {
    en: { other: '{low} to {n} TND' },
    fr: { other: 'De {low} à {n} TND' },
    ar: { one: 'من {low} إلى دينار واحد', two: 'من {low} إلى دينارين', few: 'من {low} إلى {n} دنانير', many: 'من {low} إلى {n} دينارا', other: 'من {low} إلى {n} دينار' },
  },
  // the band's median (after حوالي the noun is genitive too)
  priceAbout: {
    en: { other: 'Most around {n} TND' },
    fr: { other: 'Le plus souvent autour de {n} TND' },
    ar: { one: 'غالبا حوالي دينار واحد', two: 'غالبا حوالي دينارين', few: 'غالبا حوالي {n} دنانير', many: 'غالبا حوالي {n} دينارا', other: 'غالبا حوالي {n} دينار' },
  },
  // under the price band: how many priced pieces it comes from (after من the dual is genitive: قطعتين)
  pricedPieces: {
    en: { one: 'From {n} priced piece of this kind.', other: 'From {n} priced pieces of this kind.' },
    fr: { one: 'Sur {n} pièce de ce type avec un prix.', other: 'Sur {n} pièces de ce type avec un prix.' },
    ar: { one: 'من قطعة واحدة من هذا النوع لها سعر.', two: 'من قطعتين من هذا النوع لهما سعر.', few: 'من {n} قطع من هذا النوع لها سعر.', many: 'من {n} قطعة من هذا النوع لها سعر.', other: 'من {n} قطعة من هذا النوع لها سعر.' },
  },
  pricedPiecesAll: {
    en: { one: 'From {n} priced piece of all kinds.', other: 'From {n} priced pieces of all kinds.' },
    fr: { one: 'Sur {n} pièce de tous types avec un prix.', other: 'Sur {n} pièces de tous types avec un prix.' },
    ar: { one: 'من قطعة واحدة من كل الأنواع لها سعر.', two: 'من قطعتين من كل الأنواع لهما سعر.', few: 'من {n} قطع من كل الأنواع لها سعر.', many: 'من {n} قطعة من كل الأنواع لها سعر.', other: 'من {n} قطعة من كل الأنواع لها سعر.' },
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
