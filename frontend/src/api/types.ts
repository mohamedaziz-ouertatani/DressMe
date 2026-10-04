// Shapes returned by the DressMe API (backend/app). Keep in sync with
// backend/app/wardrobe.py (item_out, outfit_out) and backend/app/routers/*.

export type Category =
  | 'top' | 'bottom' | 'dress' | 'outerwear' | 'shoes' | 'bag' | 'accessory' | 'traditional' | 'swimwear'
export type Pattern = 'solid' | 'striped' | 'checked' | 'floral' | 'printed'
export type Season = 'summer' | 'winter' | 'mid-season'
export type Occasion = 'casual' | 'formal' | 'sport' | 'wedding' | 'eid' | 'work'
export type Language = 'en' | 'fr' | 'ar'
export type Verdict = 'buy' | 'think' | 'skip'

export interface User {
  id: string
  email: string
  name: string
  role: 'user' | 'admin'
  demo: boolean               // demo account: wardrobe of public-dataset photos
  min_coverage: number | null
  language: Language
}

export interface Guess {
  value: string
  conf: number
}

export interface Item {
  id: string
  category: Category
  sub_category: string
  pattern: string
  colour: string
  coverage: number | null
  season: Season[]
  usage: Occasion[]
  predicted: Partial<Record<'category' | 'sub_category' | 'pattern' | 'colour', Guess>>
  corrected: string[]
  image_url?: string
}

export type ItemPatch = Partial<Pick<Item, 'category' | 'sub_category' | 'pattern' | 'colour' | 'coverage' | 'season' | 'usage'>>

export interface OutfitItem {
  id: string
  category: Category
  sub_category: string
  colour: string
  image_url: string
}

export interface Outfit {
  score: number
  parts: Record<'style' | 'colour' | 'pattern' | 'structure', number | null>
  reasons: string[]
  items: OutfitItem[]
}

export type OutfitRating = 1 | -1

export interface Completion extends Outfit {
  item: Item
}

export interface BuyAdvice {
  verdict: Verdict
  good_outfits: number
  reasons: string[]
  candidate: Item
  best: Outfit[]
}

export interface CatalogHit {
  id: string
  category: Category
  sub_category: string
  colour: string
  score: number
  image_url: string
}

/** A product the user could buy (H&M catalogue): no price or stock in the data. */
export interface ShopHit extends CatalogHit {
  name: string
  shop: string
  department: string
}

export interface Similar {
  wardrobe: (Item & { similarity: number })[]
  catalog: CatalogHit[]
  shop?: ShopHit[]   // missing or empty when the server has no shop catalogue
}

export interface ChatTurn {
  role: 'user' | 'model'
  text: string
  tools_used: string[]
  attachments?: ChatAttachment[]
}

export interface ChatAttachment {
  id: string
  category: string
  sub_category: string
  colour: string
  image_url: string
  group?: string
}

// ---------------------------------------------------------------- admin
export interface DayStats {
  day: string
  upload: number
  scan: number
  verdict: number
  correction: number
  chat: number
}

export interface Stats {
  days: number
  per_day: DayStats[]
  totals: { users: number; active_users: number; items: number } & Omit<DayStats, 'day'>
  verdicts: Record<Verdict, number>
}

export interface FieldQuality {
  field: 'category' | 'sub_category' | 'pattern' | 'colour'
  items: number
  corrected: number
  rate: number | null
  mean_confidence: number | null
  top_changes: { predicted: string; corrected: string; n: number }[]
}

export interface ModelQuality {
  items: number
  fields: FieldQuality[]
  colour_below_cut: { items: number; rate: number | null; cut: number }
}

export interface AdminUser {
  id: string
  email: string
  name: string
  role: 'user' | 'admin'
  disabled: boolean
  items: number
  created_at: string
}

export interface FormulaSetting {
  name: string
  value: number
  note: string
}

export interface Formula {
  settings: FormulaSetting[]
  colour_harmony: { a: string; b: string; score: string; note: string }[]
  pattern_mixing: { a: string; b: string; score: string; note: string }[]
  file: string
  note?: string
}
