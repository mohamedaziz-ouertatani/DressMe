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
  listings?: ListingHit[]   // shop listings in stock now (empty until the collector has run)
}

/** A shop product collected by src/collect_listings.py (backend/app/listings.py, listing_out).
 *  category / colour / ... are our models' predictions on its picture. */
export interface Listing {
  id: string
  source_id: string
  brand: string
  title: string          // the shop's own words, not translated
  shop_colour: string
  url: string            // the product page: always link to it
  price_tnd: number | null
  sizes: string[]
  sizes_in_stock: string[]
  in_stock: boolean | null
  availability_level: '' | 'colour' | 'product' | 'catalogue'
  category: Category | ''
  sub_category: string
  pattern: string
  colour: string
  status: 'active' | 'gone'
  seen_at: string | null
  image_url: string
}

export interface ListingHit extends Listing {
  score: number
}

export interface ListingPage {
  total: number
  page: number
  per_page: number
  items: Listing[]
}

export interface ListingFilters {
  category?: Category
  source?: string
  max_price?: number
  sort?: 'new' | 'price'
  page?: number
}

/** GET /admin/sources: one line of mappings/listing_sources.csv + its runs. */
export interface ListingRun {
  result: 'ok' | 'blocked' | 'error' | 'skipped'
  mode: string
  message: string
  counts: Record<string, number>
  started_at: string
  finished_at: string
}

export interface AdminSource {
  source_id: string
  kind: string
  brand: string
  country: string
  enabled: string
  approved_on: string
  delay_s: string
  refresh_days: string
  catalogue_days: string
  note: string
  refused: string        // why the collector may not run it ('' = it may)
  last_run: ListingRun | null
  last_ok: ListingRun | null
  active: number
  in_stock: number
}

/** GET /insights (backend/app/routers/insights.py). */
export interface Insights {
  total: number
  categories: { category: Category; count: number }[]
  colours: { colour: string; count: number; neutral: boolean }[]
  patterns: { pattern: Pattern; count: number }[]
  to_confirm: Record<'colour' | 'coverage' | 'season' | 'usage', number>
  outfits: { good: number; complete: boolean; good_score: number }
  versatile: (OutfitItem & { outfits: number })[]
  unmatched: OutfitItem[]
  filtered: number
  new_pairs: { top: number; bottom: number }
  missing: ('main' | 'top' | 'bottom' | 'shoes')[]
  twins: { items: [OutfitItem, OutfitItem]; similarity: number }[]
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
