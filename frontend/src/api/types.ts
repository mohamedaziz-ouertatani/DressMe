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
  price_original: string     // the shop's own price when it is not in TND, e.g. "29.99 EUR"
  sizes: string[]
  sizes_in_stock: string[]
  in_stock: boolean | null
  availability_level: '' | 'colour' | 'product' | 'catalogue'
  category: Category | ''
  sub_category: string
  pattern: string
  colour: string
  predicted: Item['predicted']
  corrected: string[]
  status: 'active' | 'gone' | 'pending' | 'rejected'
  seen_at: string | null
  checked_at: string | null   // when price and stock were really checked
  snapshot: boolean           // a frozen copy: price and stock only true on checked_at
  image_url: string
  seller: { city: string; contact: string; review_note: string } | null   // friperie sellers only
}

/** PATCH /listings/{id}: what a seller may change on their own listing. */
export type ListingPatch = ItemPatch & {
  price_tnd?: number
  size?: string
  city?: string
  contact?: string
  title?: string
  sold?: boolean
}

export interface SellForm {
  price_tnd: number
  size: string
  city: string
  contact: string
  title: string
}

/** GET /admin/listings: the review queue. */
export interface ReviewListing extends Listing {
  seller_email: string
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
  tryon?: number
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

export interface TryOnResult {
  image: string                // data: URL (JPEG), never stored by the backend
  applied: string[]            // ids put on, in dressing order
  failed: string[]             // ids not put on because the AI stopped mid-way
  skipped: { id: string; reason: 'unsupported' }[]   // shoes, bags, accessories
}

/** GET /weather (backend/app/weather.py, Open-Meteo). */
export type WeatherCondition = 'clear' | 'cloudy' | 'fog' | 'rain' | 'snow' | 'storm'
export interface Weather {
  temperature: number
  feels_like: number
  min: number
  max: number
  condition: WeatherCondition | null
  rain_probability: number | null
  rain_likely: boolean
  season: Season                 // the season to dress for today
  place: string                  // 'here' (the user's rounded position) or the default place's name
  lat: number
  lon: number
}

/** A collector run started from Admin > Listings (backend/app/jobs.py). */
export type JobStatus = 'running' | 'stopping' | 'finished' | 'failed' | 'stopped' | 'lost'
export interface Job {
  id: string
  status: JobStatus
  sources: string[]          // empty = every source that may run and is due
  catalogue: boolean
  force: boolean
  limit: number
  started_by: string
  started_at: string | null
  finished_at: string | null
  exit_code: number | null
  results: Record<string, string>   // source -> running / ok / blocked / error / stopped / not started
  plan: Record<string, string>      // source -> "run" or why it is skipped
  progress: { phase: string | null; source: string | null; done: number | null; total: number | null; heartbeat: string | null }
}

export interface JobStart {
  sources: string[]
  catalogue: boolean
  force: boolean
  limit: number
}

export interface OverviewSource {
  source_id: string
  kind: string
  brand: string
  enabled: string
  approved_on: string
  refused: string
  note: string
  active: number
  in_stock: number
  gone: number
  last_run: ListingRun | null
  last_ok: ListingRun | null
  checkable: boolean         // a shop the read-only check can look at (POST /admin/sources/{id}/check)
  last_check: SourceCheck | null
}

/** The read-only shop check (src/check_shop_source.py) run from Admin > Listings. */
export interface SourceCheck {
  lines: string[]            // what the check printed
  kind: string               // shopify / woocommerce / sitemap, '' = nothing supported
  saved: boolean             // the kind was written into listing_sources.csv (the shop stays off)
  checked_at: string
  by: string
  note?: string
}

/** GET /admin/listings/overview: the Listings dashboard. */
export interface ListingsOverview {
  totals: { active: number; in_stock: number; gone: number; pending: number; rejected: number;
    sellers_active: number; sources_on: number; sources_total: number }
  sources: OverviewSource[]
  categories: { category: string; count: number }[]
  runs_by_day: ({ day: string } & Record<string, number | string>)[]
  running: Job | null
  last_job: Job | null
}
