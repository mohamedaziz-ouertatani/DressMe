import { useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import type { Item, ItemPatch } from '../api/types'
import { useI18n } from '../i18n'
import type { StringKey } from '../i18n/strings'
import {
  CATEGORY_LABELS, COLOUR_HEX, COLOUR_LABELS, COVERAGE_LABELS, OCCASION_LABELS, PATTERN_LABELS,
  SEASON_LABELS, SUB_LABELS, vocab,
} from '../i18n/vocab'
import { Chip, Swatch } from './controls'

type Single = 'category' | 'sub_category' | 'pattern' | 'colour' | 'coverage'
type Multi = 'season' | 'usage'

const SUB_PARENT: Record<string, string> = {
  shirt: 'top', sweater: 'top', sweatshirt: 'top', 't-shirt': 'top', top: 'top', tunic: 'top',
  capris: 'bottom', jeans: 'bottom', leggings: 'bottom', shorts: 'bottom', skirt: 'bottom',
  'track-pants': 'bottom', trousers: 'bottom', dress: 'dress', jumpsuit: 'dress', blazer: 'outerwear',
  cape: 'outerwear', cardigan: 'outerwear', coat: 'outerwear', jacket: 'outerwear', waistcoat: 'outerwear',
  'casual-shoes': 'shoes', flats: 'shoes', 'flip-flops': 'shoes', 'formal-shoes': 'shoes', heels: 'shoes',
  sandals: 'shoes', sneakers: 'shoes', backpack: 'bag', clutch: 'bag', 'duffel-bag': 'bag', handbag: 'bag',
  'laptop-bag': 'bag', 'messenger-bag': 'bag', 'waist-bag': 'bag', belt: 'accessory', bracelet: 'accessory',
  brooch: 'accessory', cap: 'accessory', cufflinks: 'accessory', earrings: 'accessory', glasses: 'accessory',
  gloves: 'accessory', 'hair-accessory': 'accessory', hat: 'accessory', 'jewellery-set': 'accessory',
  necklace: 'accessory', ring: 'accessory', scarf: 'accessory', sunglasses: 'accessory', suspenders: 'accessory',
  tie: 'accessory', wallet: 'accessory', watch: 'accessory', 'swim-shorts': 'swimwear', swimsuit: 'swimwear',
  jebba: 'traditional', kaftan: 'traditional',
}

const LABEL_KEY: Record<Single | Multi, StringKey> = {
  category: 'category', sub_category: 'type', pattern: 'pattern', colour: 'colour',
  coverage: 'coverage', season: 'seasons', usage: 'occasions',
}

const TABLES = {
  category: CATEGORY_LABELS, sub_category: SUB_LABELS, pattern: PATTERN_LABELS, colour: COLOUR_LABELS,
  coverage: COVERAGE_LABELS, season: SEASON_LABELS, usage: OCCASION_LABELS,
}

function options(field: Single | Multi, item: Item): string[] {
  if (field === 'sub_category') return Object.keys(SUB_PARENT).filter((s) => SUB_PARENT[s] === item.category)
  return Object.keys(TABLES[field])
}

/** One printed field of a ticket. Dashed rule = the model's guess; solid = the
 *  user confirmed or corrected it. Tapping opens the choices right below. */
export function FieldRow({ item, field, onSave, saving }: {
  item: Item
  field: Single | Multi
  onSave: (patch: ItemPatch) => Promise<void>
  saving?: boolean
}) {
  const { t, lang } = useI18n()
  const [open, setOpen] = useState(false)
  const table = TABLES[field]
  const multi = field === 'season' || field === 'usage'
  const raw = item[field as keyof Item]
  const values: string[] = multi ? (raw as string[]) : raw === null || raw === '' ? [] : [String(raw)]
  const guess = item.predicted[field as 'category']
  const sure = item.corrected.includes(field) || (!guess && values.length > 0)
  const empty = values.length === 0
  const id = `field-${item.id}-${field}`

  const choose = async (v: string) => {
    if (multi) {
      const next = values.includes(v) ? values.filter((x) => x !== v) : [...values, v]
      await onSave({ [field]: next } as ItemPatch)
    } else {
      await onSave({ [field]: field === 'coverage' ? Number(v) : v } as ItemPatch)
      setOpen(false)
    }
  }

  return (
    <div className="py-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className="flex w-full items-baseline gap-3 text-start"
      >
        <span className="w-24 shrink-0 text-[12px] font-medium uppercase tracking-[0.06em] text-carbon-soft">
          {t(LABEL_KEY[field])}
        </span>
        <span className={`flex min-w-0 flex-1 items-center gap-2 pb-1 text-[16px] ${sure ? 'field-sure' : 'field-guess'}`}>
          {field === 'colour' && !empty && <Swatch hex={COLOUR_HEX[values[0]] ?? '#ccc'} />}
          <span className={`truncate ${empty ? 'text-carbon-soft' : 'text-carbon'}`}>
            {empty
              ? field === 'colour' && guess ? t('colourMissing') : t('notSet')
              : values.map((v) => vocab(table, v, lang)).join(lang === 'ar' ? '، ' : ', ')}
          </span>
          <span className="ms-auto shrink-0 font-mono text-[11px] text-ink-soft tabular">
            {sure ? t('confirmed') : guess ? t('guessed', { p: Math.round(guess.conf * 100) }) : ''}
          </span>
          <ChevronDown className={`size-4 shrink-0 text-ink transition-transform duration-150 ${open ? 'rotate-180' : ''}`} aria-hidden />
        </span>
      </button>
      {open && (
        <div id={id} className="mt-2 flex flex-wrap gap-2 ps-[108px] max-sm:ps-0" aria-busy={saving || undefined}>
          {options(field, item).map((v) => (
            <Chip key={v} selected={values.includes(v)} onClick={() => void choose(v)}>
              <span className="inline-flex items-center gap-1.5">
                {field === 'colour' && <Swatch hex={COLOUR_HEX[v]} size={12} />}
                {vocab(table, v, lang)}
                {values.includes(v) && <Check className="size-3.5" aria-hidden />}
              </span>
            </Chip>
          ))}
        </div>
      )}
    </div>
  )
}
