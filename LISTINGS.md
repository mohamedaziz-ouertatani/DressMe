# Listings: shop and friperie items in the app

Status (2026-10-04): **phase 1 is built for the Inditex sites** (Zara, Bershka, Pull&Bear Tunisia), after the team vote of 2026-10-04 to retry them politely. Not run on the real sites yet. Shopify / WooCommerce shops, feeds and seller uploads are still designs. Everything marked **REVIEW** is a team decision that is still open.

## 0. What is built, and how to run it

| Part | File |
|---|---|
| Sources the team approved | `mappings/listing_sources.csv` |
| Collector job (nightly) | `src/collect_listings.py` |
| Inditex connector (runs `src/scrape_shops.py`) | `src/connectors/inditex.py` |
| Saving runs, search, sources table | `backend/app/listings.py` |
| API | `backend/app/routers/listings.py`, `listings` row in `/similar`, `/admin/sources` |
| App pages | `frontend/src/pages/ShopPage.tsx` (Shops + one listing with the verdict), Admin > Sources |
| Tests | `backend/tests/test_listings.py` (fake shop, fake models, no real site) |

```
pip install -r requirements-scraping.txt         # Playwright, once (see scrape_shops.py)
python src/collect_listings.py --list            # which sources would run, and why not
python src/collect_listings.py --source zara_tn --catalogue --limit 30   # smoke test first
python src/collect_listings.py > data/logs/listings.log 2>&1             # the real run (hours)
```

- **Schedule:** Windows Task Scheduler, every night at 02:00 (program = the venv's `python.exe`, arguments = `src\collect_listings.py`, start in = the project folder). Each source only runs when its last good run is older than `refresh_days` (2), and reads the whole catalogue every `catalogue_days` (7); the other runs only re-check stock, which is much lighter.
- **When a site blocks us:** the scraper stops at an "Access Denied" page or after 3 URLs in a row still refused (403 / 429) after its waits; the collector also stops after 5 pictures in a row that cannot be downloaded. The run is saved as `blocked` (Admin > Sources shows the message), nothing is marked gone, and the next scheduled run tries again days later. Never try to get around it; if it keeps happening, raise `delay_s` or switch the source off (`enabled = no`).
- **Labels:** our models only (category, sub_category, pattern, colour), like a wardrobe upload. The shop's own category words are not mapped yet (that needs `mappings/listings_<source>_*.csv` rules, see section 4).
- **In the app:** the Shops page (desktop rail, phone header icon, and a link on the Scan page) lists in-stock products with filters; a listing shows its price, its stock as far as we know it, a link to the shop, and "Should I buy this?", which turns it into a candidate and reuses `/buy-advice` unchanged. Similar pieces gets an "In shops now" row.

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
- **`inditex`:** Zara / Bershka / Pull&Bear through the existing `src/scrape_shops.py` (full catalogue weekly, `--stock-only` in between). **Approved by the team vote of 2026-10-04** (polite retry): `delay_s` = 5, a run every 2 days at most, and the run stops at the first block (section 0).

## 3. Connectors

One small file per kind: `src/connectors/<kind>.py`. Each one has the same function:

```python
def fetch(source, args) -> FetchResult(status, message, listings, mode)
# status: ok / blocked / error; listings: RawListing (backend/app/listings.py):
# external_id, url, title, image_url, brand, shop_colour, price_tnd, sizes, sizes_in_stock,
# in_stock, availability_level
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
- `GET /listings/{id}/image`: the thumbnail (loaded with the Authorization header, like the other images).
- `POST /listings/{id}/candidate`: "Should I buy this?" (see below).
- `GET /listings/sources`: the shops that have listings, for the filter chips.
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

1. Connector framework, the `listings` collection, the collector job, `GET /listings` + the Shop page: **done** (with the Inditex connector). Still to do: the `shopify` and `woocommerce` connectors, once the team has checked some shops.
2. Seller uploads and moderation.
3. Affiliate / official feeds, once the team has signed up for one.
4. ~~Inditex, only if the team votes to reopen it~~: voted 2026-10-04, built first (section 0).

## 10. Testing

- Fake connectors and a fake analyzer, in the style of `backend/tests/conftest.py`, on the `dressme_test` database.
- Recorded JSON answers per kind (a small Shopify page, a WooCommerce page, a feed file) as fixtures, so tests never touch a real site.
- Cases: a disabled source or one without a terms date is refused; a 403 / 429 stops the source and marks nothing as gone; a missing item becomes `gone` after a successful run; `source_id` + `external_id` stays unique; another user's seller listing answers 404.

## 11. Open team decisions (REVIEW)

1. Which Tunisian online shops to list. Each needs a team member to read its terms and fill its line in `listing_sources.csv`.
2. ~~Whether to reopen the Inditex sites~~: yes, polite retry (team vote 2026-10-04).
3. Which `source` value shop and seller items get (already open in `HANDOFF.md`).
4. Moderation rules for seller listings, and which contact details sellers may show.
5. How long a `gone` listing is kept before it is deleted.
