# Listings: shop and friperie items in the app (DESIGN, for team review)

Status: **design only, nothing built yet.** Everything marked **REVIEW** is a team decision that is still open.

## 1. Goal

Show items that people can actually buy today in the app: friperie pieces and products from online shops. Our models label each item, so it can be filtered, compared with the user's wardrobe ("Should I buy this?") and shown in Similar pieces.

A scheduled job (the "collector") refreshes the shop listings every night. It is a plain script, not an LLM agent: it is predictable, costs no Gemini quota and is easy to test.

**Not goals:**
- Getting around bot protection (stealth plugins, rotating proxies, captcha solvers). When a site blocks us, we stop.
- Collecting from Facebook or Instagram friperie pages: their terms forbid automated collection. Those sellers can post in the app instead (section 6).
- Redistributing other people's pictures or catalogues. We keep a small thumbnail and always link to the original page.

## 2. Sources and the legal gate

The team owns one rules file, `mappings/listing_sources.csv` (rules live in CSVs, never in code):

| Column | Meaning |
|---|---|
| `source_id` | short id, also the listing id prefix (e.g. `ts1`) |
| `kind` | `upload`, `shopify`, `woocommerce`, `feed`, `inditex` |
| `base_url` | the shop's site or feed address |
| `enabled` | `yes` / `no` |
| `terms_checked_on` | date a team member read the site's terms and found collection allowed |
| `robots_ok` | `yes` if `robots.txt` allows the pages we read |
| `delay_s` | seconds between two requests (at least 2) |
| `contact` | who in the team is responsible for this source |
| `note` | free text; `REVIEW` = open decision |

The collector **refuses** any source that is not `enabled = yes` and has no `terms_checked_on` date.

The kinds of source:

- **`upload`:** friperie sellers post their own items in the app (section 6). Fully allowed, and it fits our users best (56% shop second-hand).
- **`shopify`:** many small Tunisian e-shops run on Shopify, which publishes a public product list at `/products.json?page=N`. We still check the terms and `robots.txt` per shop.
- **`woocommerce`:** WooCommerce shops publish their products through the Store API at `/wp-json/wc/store/v1/products`. Same checks.
- **`feed`:** a product feed given to us officially (affiliate programme or a brand that agrees), in CSV or XML (Google Merchant format). This needs a sign-up per brand.
- **`inditex`:** Zara / Bershka / Pull&Bear through the existing `src/scrape_shops.py --stock-only`. **Disabled, REVIEW:** it reverses the 2026-10-03 team decision, so it needs a team vote. Even then, it only runs with a large `--delay`, a few times a week at most, and the run stops at the first "Access Denied", as the script already does.

## 3. Connectors

One small file per kind: `src/listings/connectors/<kind>.py`. Each one has the same function:

```python
def fetch(source) -> Iterator[RawListing]
# RawListing: external_id, url, title, price_tnd, image_url, sizes, in_stock, raw
```

The untouched answers are saved under `data/raw/Listings/<source_id>/<date>/` (never committed). If a parser breaks, we fix it and re-run on the saved answers without downloading again, the same pattern as `scrape_shops.py`.

Adding a shop that already uses a known kind is then only a new line in `listing_sources.csv`.

## 4. The collector job

`src/collect_listings.py` runs every night: Windows Task Scheduler on the team machine, or cron. It runs as a separate process writing a log (rule for runs over 10 minutes).

For each enabled source:

1. **Be polite.** Read `robots.txt` with `urllib.robotparser` and skip forbidden pages. Send a User-Agent that names DressMe and a contact address. Wait `delay_s` (± 30%) between requests.
2. **Stop on a block.** A 403, a 429 or a captcha page marks the source `blocked` for this run, and it is reported on the admin page (section 7). We never retry it in the same run and never try to get around it.
3. **Label each new or changed item** with the same pipeline as a wardrobe upload: download the picture once, remove the background (`on_white` and the remover in `backend/app/background.py`), then `Analyzer.analyze` in `backend/app/ml.py` (classifier, colour model, FashionCLIP vector).
   - What the models say goes into `predicted`, like for uploads. These are predictions, never labels.
   - When a shop gives its own labels (type, colour), they are mapped only through rule files `mappings/listings_<source_id>_*.csv`, and the script fails on a value with no rule (same rule as the `map_*.py` scripts).
   - Unknown stays empty. Colour stays empty below 0.7 confidence (`colour_min_confidence`).
4. **Mark what disappeared.** A listing that was not seen in a *successful* run of its source becomes `gone`. A blocked run marks nothing as gone.

Pictures are only re-analysed when the image URL changes, so a nightly run of an unchanged shop is quick.

## 5. Storage (MongoDB)

A new `listings` collection (to document in `backend/app/db.py`):

| Field | Notes |
|---|---|
| `source_id`, `external_id` | unique together |
| `url`, `title`, `price_tnd`, `sizes`, `in_stock` | from the source |
| `availability_level` | how far stock can be trusted (`colour` / `product` / `unknown`), as in the shop demo |
| `category`, `sub_category`, `pattern`, `primary_colour` | unified schema |
| `predicted` | the models' guesses with confidence |
| `vector` | FashionCLIP, stored with `vector_to_bson` (1 KB) |
| `seen_at`, `created_at` | dates |
| `status` | `active`, `gone`, `pending` (seller upload waiting), `rejected` |
| `seller_id`, `city`, `contact` | seller uploads only |

The thumbnail (≤ 320 px) is stored under `STORAGE_DIR/listings/`. The full picture is never kept.

## 6. Seller uploads

- `POST /listings`: photo + price + size + city + a contact handle the seller chooses. It reuses `read_photo` and `analyse` from `backend/app/routers/items.py`, so the seller sees the same analysis and can correct it.
- New seller listings start as `pending`. An admin approves or rejects them in a new tab of the admin pages (`current_admin`).
- A seller can edit or delete only their own listings. Another user's listing answers 404, the same privacy rule as wardrobe items.
- **REVIEW:** moderation rules, and whether sellers may show a phone number or only an Instagram / WhatsApp handle.

## 7. API

- `GET /listings`: active listings, with filters on category, sub_category, colour, max price, size, source and in stock. Paginated.
- `GET /listings/{id}/image`: the thumbnail (also `?token=` for `<img>` tags, like the other image endpoints).
- `/similar`: a new `listings` row next to `shop` (H&M).
- **Search:** brute-force numpy over the vectors of active listings, kept in memory and reloaded after each collector run. This is fine up to ~100k listings; `src/similarity.py` (`SimilarityIndex`) can take over if we grow past that.
- "Should I buy this?" on a listing turns it into a candidate (as `/analyze` does) and reuses `/buy-advice` unchanged.
- `GET /admin/sources`: per source, the last run, its result (ok / blocked / error) and how many listings were added, updated or marked gone.

## 8. Frontend

- `pages/ShopPage.tsx`: a grid of listings with filters, a link to the original page and a "Should I buy this?" button.
- A "Sell" form for seller uploads.
- Two admin tabs: moderation (pending listings) and sources (the table from `/admin/sources`).
- Every new text in en / fr / ar in `i18n/strings.ts`, following `DESIGN.md`.

## 9. Building it in phases

1. Connector framework, `shopify` and `woocommerce` connectors, the `listings` collection, the collector job and `GET /listings` + the Shop page. Start with the shops the team has checked.
2. Seller uploads and moderation.
3. Affiliate / official feeds, once the team has signed up for one.
4. Inditex, only if the team votes to reopen it (section 2).

## 10. Testing

- Fake connectors and a fake analyzer, in the style of `backend/tests/conftest.py`, on the `dressme_test` database.
- Recorded JSON answers per kind (a small Shopify page, a WooCommerce page, a feed file) as fixtures, so tests never touch a real site.
- Cases: a disabled source or one without a terms date is refused; a 403 / 429 stops the source and marks nothing as gone; a missing item becomes `gone` after a successful run; `source_id` + `external_id` stays unique; another user's seller listing answers 404.

## 11. Open team decisions (REVIEW)

1. Which Tunisian online shops to list. Each needs a team member to read its terms and fill its line in `listing_sources.csv`.
2. Whether to reopen the Inditex sites (reverses the 2026-10-03 decision).
3. Which `source` value shop and seller items get (already open in `HANDOFF.md`).
4. Moderation rules for seller listings, and which contact details sellers may show.
5. How long a `gone` listing is kept before it is deleted.
