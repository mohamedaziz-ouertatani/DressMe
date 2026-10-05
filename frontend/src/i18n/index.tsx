import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Language } from '../api/types'
import { plural } from './plurals'
import { STRINGS, type StringKey } from './strings'
import { CATEGORY_LABELS, COLOUR_LABELS, PATTERN_LABELS, SEASON_LABELS, OCCASION_LABELS, SUB_LABELS, vocab } from './vocab'

const LANG_KEY = 'dressme.lang'

interface I18n {
  lang: Language
  dir: 'ltr' | 'rtl'
  setLang: (lang: Language) => void
  t: (key: StringKey, vars?: Record<string, string | number>) => string
  reason: (text: string) => string
}

const Ctx = createContext<I18n | null>(null)

function storedLang(): Language {
  try {
    const v = localStorage.getItem(LANG_KEY)
    if (v === 'en' || v === 'fr' || v === 'ar') return v
  } catch {
    /* no storage: default */
  }
  return 'en'
}

// The compatibility formula (src/compatibility.py) explains scores in English.
// These patterns translate each kind of reason; unknown text stays as it is.
type Rule = [RegExp, (m: RegExpMatchArray, lang: Language) => string]
const REASONS: Rule[] = [
  [/^the pieces have quite different styles$/, (_, l) =>
    ({ en: 'The pieces have quite different styles', fr: 'Les pièces ont des styles assez différents', ar: 'القطع مختلفة الأسلوب' })[l]],
  [/^(\w+) and (\w+) clash$/, (m, l) => {
    const a = vocab(COLOUR_LABELS, m[1], l), b = vocab(COLOUR_LABELS, m[2], l)
    return ({ en: `${a} and ${b} clash`, fr: `${a} et ${b} jurent ensemble`, ar: `${a} و${b} لا يتناسقان` })[l]
  }],
  [/^many bold colours \((.+)\)$/, (m, l) => {
    const list = m[1].split(', ').map((c) => vocab(COLOUR_LABELS, c, l)).join(l === 'ar' ? '، ' : ', ')
    return ({ en: `Many bold colours (${list})`, fr: `Beaucoup de couleurs vives (${list})`, ar: `ألوان صارخة كثيرة (${list})` })[l]
  }],
  [/^two bold patterns \((\w+) \+ (\w+)\)$/, (m, l) => {
    const a = vocab(PATTERN_LABELS, m[1], l), b = vocab(PATTERN_LABELS, m[2], l)
    return ({ en: `Two bold patterns (${a} + ${b})`, fr: `Deux motifs forts (${a} + ${b})`, ar: `نقشتان قويتان (${a} + ${b})` })[l]
  }],
  [/^([\w-]+) and ([\w-]+) don't go together$/, (m, l) => {
    const a = vocab(SUB_LABELS, m[1], l), b = vocab(SUB_LABELS, m[2], l)
    return ({ en: `${a} and ${b} don't go together`, fr: `${a} et ${b} ne vont pas ensemble`, ar: `${a} و${b} لا يتماشيان` })[l]
  }],
  [/^([\w-]+) not for (\S+)$/, (m, l) => {
    const what = vocab(SUB_LABELS, m[1], l) || vocab(CATEGORY_LABELS, m[1], l)
    const v = vocab(SEASON_LABELS, m[2], l)
    return ({ en: `${what}: not for ${v.toLowerCase()}`, fr: `${what} : pas pour ${v.toLowerCase()}`, ar: `${what}: ليست لـ${v}` })[l]
  }],
  [/^no shoes$/, (_, l) => ({ en: 'No shoes', fr: 'Pas de chaussures', ar: 'بدون حذاء' })[l]],
  [/^missing a top or a bottom$/, (_, l) =>
    ({ en: 'Missing a top or a bottom', fr: 'Il manque un haut ou un bas', ar: 'تنقص قطعة علوية أو سفلية' })[l]],
  [/^no main piece$/, (_, l) => ({ en: 'No main piece', fr: 'Pas de pièce principale', ar: 'لا توجد قطعة أساسية' })[l]],
  [/^a full piece and a bottom together$/, (_, l) =>
    ({ en: 'A full piece and a bottom together', fr: 'Une pièce entière avec un bas', ar: 'قطعة كاملة مع قطعة سفلية' })[l]],
  [/^(\d+) items of (\w+)$/, (m, l) => {
    const c = vocab(CATEGORY_LABELS, m[2], l)
    return plural('sameCategory', Number(m[1]), l, { c: l === 'ar' ? c : c.toLowerCase() })
  }],
  [/^you already own (\d+) very similar (\w+) item\(s\)$/, (m, l) => {
    const c = vocab(CATEGORY_LABELS, m[2], l)
    const what = plural('similarPieces', Number(m[1]), l, { c: l === 'ar' ? c : c.toLowerCase() })
    return ({ en: `You already own ${what}`, fr: `Tu as déjà ${what}`, ar: `لديك ${what}` })[l]
  }],
  [/^coverage (\d) is below your level (\d)$/, (m, l) =>
    ({ en: `Coverage ${m[1]} is below your level ${m[2]}`, fr: `Couvrance ${m[1]}, sous ton niveau ${m[2]}`,
      ar: `درجة الستر ${m[1]} أقل من مستواك ${m[2]}` })[l]],
  [/^not for (\S+)$/, (m, l) => {
    const v = SEASON_LABELS[m[1]] ? vocab(SEASON_LABELS, m[1], l) : vocab(OCCASION_LABELS, m[1], l)
    return ({ en: `Not for ${v.toLowerCase()}`, fr: `Pas pour : ${v.toLowerCase()}`, ar: `ليست لـ${v}` })[l]
  }],
]

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Language>(storedLang)
  const dir = lang === 'ar' ? 'rtl' : 'ltr'

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = dir
  }, [lang, dir])

  const setLang = useCallback((l: Language) => {
    setLangState(l)
    try {
      localStorage.setItem(LANG_KEY, l)
    } catch {
      /* fine */
    }
  }, [])

  const t = useCallback((key: StringKey, vars?: Record<string, string | number>) => {
    let s = STRINGS[lang][key] ?? STRINGS.en[key]
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v))
    return s
  }, [lang])

  const reason = useCallback((text: string) => {
    for (const [re, fn] of REASONS) {
      const m = text.match(re)
      if (m) return fn(m, lang)
    }
    return text
  }, [lang])

  const value = useMemo(() => ({ lang, dir, setLang, t, reason }) as I18n, [lang, dir, setLang, t, reason])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useI18n(): I18n {
  const v = useContext(Ctx)
  if (!v) throw new Error('useI18n outside I18nProvider')
  return v
}
