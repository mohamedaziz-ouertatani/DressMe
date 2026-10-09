import type { Language, SimilarWhy as Why } from '../api/types'
import { useI18n } from '../i18n'
import type { StringKey } from '../i18n/strings'

// The team's concepts (mappings/style_concepts.csv) in the three languages.
const CONCEPTS: Record<string, Record<Language, string>> = {
  streetwear: { en: 'streetwear', fr: 'streetwear', ar: 'ستريت وير' },
  formal: { en: 'formal', fr: 'habillé', ar: 'رسمي' },
  sporty: { en: 'sporty', fr: 'sport', ar: 'رياضي' },
  casual: { en: 'casual', fr: 'décontracté', ar: 'يومي' },
  classic: { en: 'classic', fr: 'classique', ar: 'كلاسيكي' },
  modest: { en: 'modest', fr: 'couvrant', ar: 'محتشم' },
  trendy: { en: 'trendy', fr: 'tendance', ar: 'عصري' },
  party: { en: 'party', fr: 'soirée', ar: 'سهرة' },
  denim: { en: 'denim', fr: 'jean', ar: 'جينز' },
  leather: { en: 'leather', fr: 'cuir', ar: 'جلد' },
  knit: { en: 'knit', fr: 'tricot', ar: 'تريكو' },
  lace: { en: 'lace', fr: 'dentelle', ar: 'دانتيل' },
  satin: { en: 'satin', fr: 'satin', ar: 'ساتان' },
  oversized: { en: 'oversized', fr: 'oversize', ar: 'واسع' },
  fitted: { en: 'fitted', fr: 'ajusté', ar: 'ضيّق' },
  floral: { en: 'floral', fr: 'fleuri', ar: 'مورّد' },
  striped: { en: 'striped', fr: 'rayé', ar: 'مخطّط' },
  checked: { en: 'checked', fr: 'à carreaux', ar: 'مربّعات' },
  vintage: { en: 'vintage', fr: 'vintage', ar: 'قديم الطراز' },
  traditional: { en: 'traditional', fr: 'traditionnel', ar: 'تقليدي' },
}

const FIELD_KEY: Record<Why['shared'][number]['field'], StringKey> = {
  category: 'category', sub_category: 'type', colour: 'colour', pattern: 'pattern',
}

/** Two short lines under a look-alike: the labels both pieces share, and what the
 *  picture model associates with both (or how they differ). */
export function SimilarWhy({ why }: { why?: Why }) {
  const { t, lang } = useI18n()
  if (!why) return null
  const concept = (c: string) => CONCEPTS[c]?.[lang] ?? c
  const sep = lang === 'ar' ? '، ' : ', '
  return (
    <div className="mt-1 space-y-0.5 text-[11px] leading-snug text-carbon-soft">
      {why.shared.length > 0 && (
        <p>{t('simSame')}: {why.shared.map((s) => t(FIELD_KEY[s.field]).toLowerCase()).join(sep)}</p>
      )}
      {why.both.length > 0 ? (
        <p>{t('simBoth')} {why.both.map(concept).join(sep)}</p>
      ) : why.contrast ? (
        <p>{t('simContrast', { a: concept(why.contrast.b), b: concept(why.contrast.a) })}</p>
      ) : null}
    </div>
  )
}

