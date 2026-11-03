import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useI18n } from '../i18n'
import { CATEGORY_LABELS, SUB_LABELS, vocab } from '../i18n/vocab'
import type { Item } from '../api/types'
import { ItemPhoto } from './ItemPhoto'
import { Serial } from './ticket'

const GUESSABLE = ['category', 'sub_category', 'pattern', 'colour'] as const

/** How many of the four labels are still the model's guess (not confirmed or corrected by the user). */
function guessedCount(it: Item) {
  return GUESSABLE.filter((f) => it.predicted[f] && !it.corrected.includes(f)).length
}

/** One wardrobe piece as a card that opens its page: the Wardrobe grid and the search results use it.
 *  `muted`: drawn faded, for a piece that is only the nearest one, not a match (search).
 *  `badge`: a small mark under the name (search: "Close match"). */
export function ItemCard({ item, muted = false, badge }: { item: Item; muted?: boolean; badge?: ReactNode }) {
  const { lang } = useI18n()
  const guessed = guessedCount(item)
  const name = vocab(SUB_LABELS, item.sub_category, lang) || vocab(CATEGORY_LABELS, item.category, lang)
  return (
    <Link
      to={`/wardrobe/${item.id}`}
      className={`ticket block h-full p-2 transition-shadow duration-150 hover:[box-shadow:var(--shadow-lift)] ${muted ? 'opacity-60' : ''}`}
    >
      <div className="flex justify-center"><ItemPhoto src={item.image_url} alt={vocab(SUB_LABELS, item.sub_category, lang)} size={128} /></div>
      <div className="perf-h mt-2 pt-2">
        <p className={`truncate pb-0.5 text-[15px] font-semibold text-carbon ${guessed ? 'field-guess' : 'field-sure'} inline-block max-w-full`}>
          {name}
        </p>
        {badge && <div className="mt-1">{badge}</div>}
        <Serial id={item.id} className="mt-1 block" />
      </div>
    </Link>
  )
}
