// Small text helpers for listings (Shops, Sell and Similar pages).
import type { Listing } from '../api/types'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'

const BRANDS: Record<string, string> = { zara: 'Zara', bershka: 'Bershka', pullandbear: 'Pull&Bear', inditex: 'Inditex' }
export const brandName = (b: string) => BRANDS[b] ?? b

/** Prices and dates in the user's language. */
export function useListingFormat() {
  const { t, lang } = useI18n()
  const locale = lang === 'ar' ? 'ar-TN' : lang === 'en' ? 'en-GB' : lang
  return {
    price: (p: number | null) =>
      p === null ? '' : t('priceTnd', { p: p.toLocaleString(locale, { maximumFractionDigits: 3 }) }),
    day: (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(locale) : ''),
    /** The shop's own product name, else what the piece is (seller listings may have no name). */
    name: (l: Listing) => l.title || vocab(SUB_LABELS, l.sub_category, lang) || vocab(CATEGORY_LABELS, l.category, lang),
    /** Who sells it: the brand, or the friperie seller's city. */
    who: (l: Listing) => (l.seller ? t('sellerCity', { c: l.seller.city }) : brandName(l.brand)),
  }
}
