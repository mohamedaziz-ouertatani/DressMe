import { Link } from 'react-router-dom'
import type { Listing } from '../api/types'
import { useI18n } from '../i18n'
import { ItemPhoto } from './ItemPhoto'
import { useListingFormat } from './listingText'

/** What we know about stock: per size only when the shop answered for this exact
 *  colour, and for a frozen snapshot only "on that date". */
export function StockLine({ listing }: { listing: Listing }) {
  const { t } = useI18n()
  const { day } = useListingFormat()
  if (listing.in_stock === false) return <>{t('outOfStock')}</>
  const sizes = listing.availability_level === 'colour' ? listing.sizes_in_stock : []
  if (listing.snapshot) {
    const on = t('inStockOn', { d: day(listing.checked_at) })
    return <>{sizes.length ? `${on}: ${sizes.join(' · ')}` : on}</>
  }
  if (sizes.length) return <>{t('sizesInStock', { s: sizes.join(' · ') })}</>
  return <>{t('stockSizesUnknown')}</>
}

/** A listing as a small ticket: picture, its name (as the shop wrote it), who sells it, price. */
export function ListingCard({ listing, note }: { listing: Listing; note?: string }) {
  const { price, name, who } = useListingFormat()
  return (
    <Link to={`/shop/${listing.id}`} className="ticket block p-2">
      <div className="flex justify-center"><ItemPhoto src={listing.image_url} alt={name(listing)} size={112} /></div>
      <p className="perf-h mt-2 truncate pt-2 text-[14px] font-medium text-carbon" dir="auto" title={name(listing)}>{name(listing)}</p>
      <p className="truncate font-mono text-[11px] text-ink-soft tabular">
        {who(listing)} · {note ?? price(listing.price_tnd, listing.price_original)}
      </p>
    </Link>
  )
}
