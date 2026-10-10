// Shapes returned by the DressMe API (backend/app). Keep in sync with
// backend/app/wardrobe.py (item_out, outfit_out) and backend/app/routers/*.

export type Category =
  | 'top' | 'bottom' | 'dress' | 'outerwear' | 'shoes' | 'bag' | 'accessory' | 'traditional' | 'swimwear'
export type Pattern = 'solid' | 'striped' | 'checked' | 'floral' | 'printed'
export type Season = 'summer' | 'winter' | 'mid-season'
export type Occasion = 'casual' | 'formal' | 'sport' | 'wedding' | 'eid' | 'work'
export type Language = 'en' | 'fr' | 'ar'
export type Gender = 'men' | 'women'
export type Verdict = 'buy' | 'think' | 'skip'

export interface User {
  id: string
  email: string
  name: string
  role: 'user' | 'admin'
  demo: boolean               // demo account: wardrobe of public-dataset photos
  min_coverage: number | null
  language: Language
  gender: Gender | null
  needs_gender: boolean       // account from before the question: asked once
}

export interface Alternative {
  value: string
  conf: number
}

export interface Guess {
  value: string
  conf: number
  alternatives?: Alternative[]   // items analysed before the XAI layer have none
  unsure?: boolean
}

export type GuessField = 'category' | 'sub_category' | 'pattern' | 'colour'

/** GET /items/{id}/explain, /candidates/{id}/explain (backend/app/routers/explain.py) */
export interface ExplainField {
  shown: string                  // the answer the picture is for
  value: string                  // the model's stored answer
  conf: number | null
  alternatives: Alternative[]
  unsure: boolean
  corrected: boolean
  heatmap?: string               // data URL (category / sub_category / pattern)
  pixels?: string                // data URL (colour)
  share?: number
  reliable?: boolean
}

export interface Explanation {
  fields: Partial<Record<GuessField, ExplainField>>
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
  predicted: Partial<Record<GuessField, Guess>>
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
  contributions?: Contribution[]   // points per part (app routes only)
  explanations?: ExplainLine[]     // strengths (+) and problems (-) as codes
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
  explanation?: BuyExplanation
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

/** Why a look-alike came up (src/phase4/explain_similarity.py): shared / different labels
 *  and the concepts the picture model associates with both pictures. */
export interface SimilarWhy {
  shared: { field: 'category' | 'sub_category' | 'colour' | 'pattern'; value: string }[]
  differs: { field: 'category' | 'sub_category' | 'colour' | 'pattern'; a: string; b: string }[]
  both: string[]
  contrast: { a: string; b: string } | null
}

export interface Similar {
  wardrobe: (Item & { similarity: number; why?: SimilarWhy })[]
  catalog: (CatalogHit & { why?: SimilarWhy })[]
  shop?: (ShopHit & { why?: SimilarWhy })[]   // missing or empty when the server has no shop catalogue
  listings?: (ListingHit & { why?: SimilarWhy })[]   // shop listings in stock now (empty until the collector has run)
}

/** A shop product collected by src/phase4/collect_listings.py (backend/app/listings.py, listing_out).
 *  category / colour / ... are our models' predictions on its picture. */
export interface Listing {
  id: string
  source_id: string
  brand: string
  shop_name?: string     // the shop's display name from the sources table ("Hamadi Abid")
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
  gender?: 'all'              // unset = my gender + unisex
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
  agent?: string            // stylist, shopping, analyst, seller or explainer ('' for old messages)
  actions?: ChatAction[]
  routed_by?: '' | 'llm' | 'keywords'   // how the agent was chosen
  trace?: TraceStep[]       // "How I answered": the tool calls behind the answer
}

export interface TraceStep {
  tool: string
  args: Record<string, unknown>   // shortened by the server
  result: string                  // one line
}

/** Something the assistant prepared for the user to open (never done for them). */
export interface ChatAction {
  kind: 'sell' | 'explain'
  url: string               // sell: /sell?item=...&price=... (the Sell form, already filled);
                            // explain: /wardrobe/<id>?why=1 (the item's "Why these labels?" panel)
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

/** The read-only shop check (src/phase4/check_shop_source.py) run from Admin > Listings. */
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

// ---- outfit + buy advice explanations (src/phase4/explain_outfit.py)
export type PartName = 'style' | 'colour' | 'pattern' | 'structure'

export interface ExplainLine {
  code: string
  part: PartName
  sign: '+' | '-'
  params: Record<string, string | number | string[]>
}

export interface Contribution {
  part: PartName
  weight: number
  value: number | null
  counted: boolean
  points: number
  max_points: number
  why_not: null | 'no_vectors' | 'no_colours' | 'no_patterns' | 'no_items' | 'weight_zero'
}

export interface ShortItem {
  id: string
  category: Category
  sub_category: string
  colour: string
  image_url: string
}

/** POST /outfits/explain */
export interface OutfitExplanation {
  swaps: { item_id: string; gain: number; swap: ShortItem | null }[]
  weakest: string | null
  pair_map: { a: string; b: string; style: number | null; colour: number | null; pattern: number | null }[]
}

/** /buy-advice explanation */
export interface BuyExplanation {
  path: { good: number; buy_min: number; think_min: number; verdict: Verdict }
  beats: { item_ids: string[]; owned_id: string | null; owned: ShortItem | null; owned_score: number; margin: number }[]
  lost_to: { owned_id: string; owned: ShortItem; outfits: number }[]
  near_misses: number
  to_next_verdict: number | null
  twins: { item: ShortItem; similarity: number }[]
}

// ---- Admin > Explainability (backend/app/routers/admin_xai.py)
export interface XaiSetting {
  name: string
  value: number
  note: string
}

export interface AdminXai {
  evaluations: {
    labels: { missing?: true; date?: string; command: string; report?: string
      flag?: { field: string; sure_accuracy: number; unsure_accuracy: number; unsure_share: number }[]
      deletion?: { field: string; heatmap: number; shifted_region: number; scattered_pixels: number }[] }
    outfits: { missing?: true; date?: string; command: string; report?: string
      rows?: { dataset: string; outfits: number; hit: number; chance: number; points_add_up: string }[] }
    concepts: { missing?: true; date?: string; command: string; report?: string
      rows?: { concept: string; label: string; auc: number | null; with_label: number }[]; mean_auc?: number | null }
  }
  real_use: {
    items: number
    before_xai: number
    fields: { field: string; items: number; unsure: number; unsure_corrected: number; sure_corrected: number
      unsure_corrected_rate: number | null; sure_corrected_rate: number | null }[]
  }
  traces: {
    days: number
    answers: number
    tools: { tool: string; calls: number; errors: number; agents: string[] }[]
    explainer_answers: number
    explainer_without_tools: number
  }
  settings: XaiSetting[]
  concepts: { concept: string; prompt: string; group: string; check: string }[]
  file: string
  note?: string
}
