// One sentence per explanation code of the outfit formula (src/phase4/compatibility.py
// and explain_outfit.py), in en / fr / ar. Unknown codes fall back to the code itself.
import type { ExplainLine, Language, VerdictCode } from '../api/types'
import { CATEGORY_LABELS, COLOUR_LABELS, PATTERN_LABELS, SUB_LABELS, vocab } from './vocab'

type T = Record<Language, string>
const sep = (l: Language) => (l === 'ar' ? '، ' : ', ')

export function explainLine(line: ExplainLine, l: Language): string {
  const p = line.params
  const col = (k: string) => vocab(COLOUR_LABELS, String(p[k]), l)
  const sub = (k: string) => vocab(SUB_LABELS, String(p[k]), l)
  const pat = (k: string) => vocab(PATTERN_LABELS, String(p[k]), l)
  const texts: Record<string, () => T> = {
    style_coherent: () => ({ en: 'The pieces share one style', fr: 'Les pièces partagent un même style', ar: 'القطع بأسلوب واحد' }),
    style_mixed: () => ({ en: 'The pieces have quite different styles', fr: 'Les pièces ont des styles assez différents', ar: 'القطع مختلفة الأسلوب' }),
    style_unlike_you: () => ({ en: 'Unlike your usual style', fr: 'Différent de ton style habituel', ar: 'مختلف عن أسلوبك المعتاد' }),
    colour_pair: () => ({ en: `${col('a')} and ${col('b')} go together`, fr: `${col('a')} et ${col('b')} vont bien ensemble`, ar: `${col('a')} و${col('b')} يتناسقان` }),
    colour_neutral_base: () => ({ en: `A calm base of ${p.n} neutral colours`, fr: `Une base calme de ${p.n} couleurs neutres`, ar: `قاعدة هادئة من ${p.n} ألوان محايدة` }),
    colour_clash: () => ({ en: `${col('a')} and ${col('b')} clash`, fr: `${col('a')} et ${col('b')} jurent ensemble`, ar: `${col('a')} و${col('b')} لا يتناسقان` }),
    colour_too_bold: () => {
      const list = (p.colours as string[]).map((c) => vocab(COLOUR_LABELS, c, l)).join(sep(l))
      return { en: `Many bold colours (${list})`, fr: `Beaucoup de couleurs vives (${list})`, ar: `ألوان صارخة كثيرة (${list})` }
    },
    pattern_one_bold: () => ({ en: `One statement pattern (${pat('pattern')})`, fr: `Un seul motif fort (${pat('pattern')})`, ar: `نقشة بارزة واحدة (${pat('pattern')})` }),
    pattern_calm: () => ({ en: 'Calm, plain pieces', fr: 'Des pièces unies et calmes', ar: 'قطع سادة هادئة' }),
    pattern_clash: () => ({ en: `Two bold patterns (${pat('a')} + ${pat('b')})`, fr: `Deux motifs forts (${pat('a')} + ${pat('b')})`, ar: `نقشتان قويتان (${pat('a')} + ${pat('b')})` }),
    structure_complete: () => ({ en: 'Complete outfit, shoes included', fr: 'Tenue complète, chaussures comprises', ar: 'إطلالة كاملة مع الحذاء' }),
    structure_no_shoes: () => ({ en: 'No shoes', fr: 'Pas de chaussures', ar: 'بدون حذاء' }),
    structure_incomplete: () => p.missing === 'main_piece'
      ? { en: 'No main piece', fr: 'Pas de pièce principale', ar: 'لا توجد قطعة أساسية' }
      : { en: 'Missing a top or a bottom', fr: 'Il manque un haut ou un bas', ar: 'تنقص قطعة علوية أو سفلية' },
    structure_full_and_bottom: () => ({ en: 'A full piece and a bottom together', fr: 'Une pièce entière et un bas ensemble', ar: 'قطعة كاملة مع قطعة سفلية' }),
    structure_over_limit: () => {
      const c = vocab(CATEGORY_LABELS, String(p.category), l)
      return { en: `${p.n} pieces of ${c}`, fr: `${p.n} pièces de type ${c}`, ar: `${p.n} قطع من ${c}` }
    },
    structure_pair: () => ({ en: `${sub('a')} and ${sub('b')} don't go together`, fr: `${sub('a')} et ${sub('b')} ne vont pas ensemble`, ar: `${sub('a')} و${sub('b')} لا يتماشيان` }),
  }
  return texts[line.code]?.()[l] ?? line.code
}

// ---- the reason codes of "Should I buy this?" (src/phase4/verdict.py), same mechanism: one sentence
// per code in en / fr / ar; an unknown code falls back to the code itself.
const FIELD_WORDS: Record<string, T> = {
  category: { en: 'category', fr: 'de la catégorie', ar: 'الصنف' },
  sub_category: { en: 'type', fr: 'du type', ar: 'النوع' },
  pattern: { en: 'pattern', fr: 'du motif', ar: 'النقشة' },
  colour: { en: 'colour', fr: 'de la couleur', ar: 'اللون' },
}

// what the wardrobe lacks: the labels of wardrobe_insights ("main" = no top, bottom or dress at all)
const SLOT_MISSING: Record<string, T> = {
  top: { en: 'you have no top', fr: "tu n'as pas de haut", ar: 'ما عندك قطعة علوية' },
  bottom: { en: 'you have no bottom', fr: "tu n'as pas de bas", ar: 'ما عندك قطعة سفلية' },
  main: { en: 'you have no top, bottom or dress yet', fr: "tu n'as encore ni haut, ni bas, ni robe", ar: 'ما عندك بعد قطعة علوية أو سفلية أو فستان' },
  shoes: { en: 'you have no shoes yet', fr: "tu n'as pas encore de chaussures", ar: 'ما عندك أحذية بعد' },
}

export function verdictCodeLine(c: VerdictCode, l: Language): string {
  const p = c.params
  const pct = Math.round(Number(p.share ?? p.conf ?? 0) * 100)
  const slot = (key: string) => SLOT_MISSING[String(p[key])]?.[l] ?? String(p[key])
  const texts: Record<string, () => T> = {
    small_wardrobe: () => ({
      en: `You only have ${p.owned} usable pieces: DressMe needs about ${p.minimum} to judge well.`,
      fr: `Tu n'as que ${p.owned} pièces utilisables : DressMe en veut environ ${p.minimum} pour bien juger.`,
      ar: `عندك ${p.owned} قطع فقط: DressMe يحتاج حوالي ${p.minimum} ليحكم جيدا.`,
    }),
    no_pairing_piece: () => ({
      en: `Nothing to wear it with: ${slot('slot')}.`,
      fr: `Rien pour la porter : ${slot('slot')}.`,
      ar: `لا شيء تلبسها معه: ${slot('slot')}.`,
    }),
    guessed_field: () => {
      const f = FIELD_WORDS[String(p.field)] ?? { en: String(p.field), fr: String(p.field), ar: String(p.field) }
      return {
        en: `DressMe is not sure of the ${f.en} (${pct}%): check it above.`,
        fr: `DressMe n'est pas sûr ${f.fr} (${pct} %) : vérifie plus haut.`,
        ar: `DressMe غير متأكد من ${f.ar} (${pct}%): تحقق من ذلك أعلاه.`,
      }
    },
    fills_gap: () => ({
      en: `It fills a gap: ${slot('slot')}.`,
      fr: `Elle comble un manque : ${slot('slot')}.`,
      ar: `تسدّ نقصا: ${slot('slot')}.`,
    }),
    far_from_style: () => ({
      en: 'It looks quite different from what you usually own.',
      fr: "Elle ressemble peu à ce que tu portes d'habitude.",
      ar: 'تبدو مختلفة كثيرا عمّا تملكه عادة.',
    }),
    over_budget: () => ({
      en: `At ${p.price} TND it takes ${pct}% of your budget.`,
      fr: `À ${p.price} TND, elle prend ${pct} % de ton budget.`,
      ar: `بسعر ${p.price} دينار تأخذ ${pct}% من ميزانيتك.`,
    }),
  }
  return texts[c.code]?.()[l] ?? c.code
}
