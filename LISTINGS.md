# Listings: shop and friperie items in the app

Status (2026-10-04, after the first real run):
- **Inditex (Zara, Bershka, Pull&Bear): OFF.** The first run got "Access Denied" on the very first page, so the sites refuse the automated browser itself (no delay would help). They are switched off in the sources table; never work around it.
- **Frozen snapshot: ON.** The rows scraped before the block (`data/processed/shop_demo.csv`) are listed as a dated snapshot, never refreshed.
- **Tunisian shops: connectors built, shops not enabled yet.** Shopify and WooCommerce connectors are ready. Exist, Hamadi Abid and Zen are in the table, switched off until someone checks them (section 0).
- **Friperie sellers: built.** Sellers post items in the app; an admin approves them first.
- Official feeds: still a design. Everything marked **REVIEW** is a team decision that is still open.

## 0. What is built, and how to run it

| Part | File |
|---|---|
| Sources the team approved | `mappings/listing_sources.csv` |
| Collector job (nightly) | `src/collect_listings.py` |
| Connectors | `src/connectors/`: `shopify.py`, `woocommerce.py` (through the polite client `http.py`), `snapshot.py`, `inditex.py` (runs `src/scrape_shops.py`; off) |
| Check a shop before adding it | `src/check_shop_source.py` |
| Saving runs, search, sources table | `backend/app/listings.py` |
| API | `backend/app/routers/listings.py` (browse, sell, seller edits, "Should I buy this?"), `listings` row in `/similar`, `/admin/sources`, `/admin/listings` (moderation) |
| App pages | `ShopPage.tsx` (Shops + one listing with the verdict), `SellPage.tsx` (sell + my listings), Admin > Sources and Admin > Moderation |
| Tests | `backend/tests/test_listings.py`, `test_connectors.py` (recorded answers in `tests/fixtures/`), `test_sellers.py`; never a real site |

**Frozen snapshot:** run `inditex_snapshot` (Admin > Listings, "Run now", or `python src/collect_listings.py --source inditex_snapshot`). If `data/processed/shop_demo.csv` is missing, the run builds it first from the rows scraped on 2026-10-03 (`data/raw/Shops/*/products.csv`, through `freeze_shop_demo.freeze`), saving each picture once with our own User-Agent; a picture that could not be saved is tried once more by the collector. If no rows were ever scraped on this computer, the run says so: there is then no snapshot to show. To rebuild it after a change, delete `shop_demo.csv` and run it with "ignore refresh_days" (`--force`).

**Adding a Tunisian shop (Exist, Hamadi Abid, Zen, ...):**
1. `python src/check_shop_source.py https://<the shop's site> exist_tn`: reads robots.txt and one product, says whether the shop runs Shopify or WooCommerce, shows a price to confirm it is in TND, and prints the CSV line. A shop whose robots.txt forbids those paths is not listed.
2. A team member reads the shop's terms of use. If nothing forbids it, fill `kind` and `base_url`, set `enabled = yes` and `approved_on` = that date.
3. Smoke test: `python src/collect_listings.py --source exist_tn --limit 30` (a `--limit` run never marks anything gone).
4. The nightly job then refreshes it every `refresh_days` (2).

**From the app (Admin > Listings):** admins see the listing counts, every source (can it run, why not, its last run) and two charts (listed by category, source runs per day). They can **start a run** (chosen sources or every due one, with the same options as the command line: whole catalogue, ignore refresh_days, limit), **follow it live** (phase, progress bar, results per source, the log) and **stop it**. `backend/app/jobs.py` starts `src/collect_listings.py` as a separate process with `--status-file` / `--stop-file` (`src/job_progress.py`), logs under `STORAGE_DIR/jobs/`, one document per run in MongoDB `listing_jobs`.
- One run at a time (the models need the GPU memory, and a shop must never get two of us at once); the same gate as the command line (enabled + approved only).
- Stop is polite: the run finishes its current item, keeps what it saved and marks nothing gone (result `stopped`). If it has not ended after 30 s, the whole process tree (scraper and browser too) is ended.
- A run whose heartbeat (every 10 s) is older than 2 minutes, e.g. after the backend restarted, is shown as `lost`.

**The nightly job:** `python src/collect_listings.py > data/logs/listings.log 2>&1`, from Windows Task Scheduler every night at 02:00 (program = the venv's `python.exe`, arguments = `src\collect_listings.py`, start in = the project folder). `--list` shows which sources would run, and why not.

- **When a site blocks us:** a 403, a 429, or an HTML page (bot check) where JSON was expected stops the source; the collector also stops after 5 pictures in a row that cannot be downloaded. The run is saved as `blocked` (Admin > Sources shows the message) and nothing is marked gone. Never try to get around it; if it happens again, switch the source off (`enabled = no`). The connectors also ask robots.txt before every path and never read a forbidden one.
- **Labels:** our models only (category, sub_category, pattern, colour), like a wardrobe upload. The shops' own category words are not mapped yet (that needs `mappings/listings_<source>_*.csv` rules, see section 4).
- **Stock:** Shopify gives stock per size and colour (`availability_level = colour`), WooCommerce only per product (`product`). The snapshot shows "in stock on <date>" and "snapshot from <date>", never as live.
- **In the app:** the Shops page (desktop rail, phone header icon, and links on the Scan page) lists in-stock products from every source, with filters; a listing shows its price, its stock as far as we know it, a link to the shop (or the seller's city and contact), and "Should I buy this?", which turns it into a candidate and reuses `/buy-advice` unchanged. Similar pieces gets an "In shops now" row.

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
| `source_id` | short id (e.g. `exist_tn`) |
| `kind` | `shopify`, `woocommerce`, `snapshot`, `inditex` (empty until `check_shop_source.py` has run) |
| `brand`, `country` | shown in the app; `country` is `tn` |
| `base_url` | the shop's site (Shopify / WooCommerce) |
| `enabled` | `yes` / `no` |
| `approved_on` | date a team member read the site's terms and found nothing against it |
| `delay_s` | seconds between two requests (5) |
| `refresh_days` | a source runs at most this often (2) |
| `catalogue_days` | Inditex only: full catalogue this often, stock-only in between |
| `contact` | who in the team is responsible for this source |
| `note` | free text: why it is on or off |

The collector **refuses** any source that is not `enabled = yes`, has no `approved_on` date, or has no connector for its `kind`. Friperie sellers are not a row here: they post in the app (section 6).

The kinds of source:

- **Friperie sellers** (`source_id = sellers`): they post their own items in the app (section 6). Fully allowed, and it fits our users best (56% shop second-hand).
- **`shopify`:** many small Tunisian e-shops run on Shopify, which publishes a public product list at `/products.json?page=N`. We still check the terms and `robots.txt` per shop.
- **`snapshot`:** the Inditex rows scraped before the block, frozen (`src/connectors/snapshot.py`). Never contacts a site.
- **`woocommerce`:** WooCommerce shops publish their products through the Store API at `/wp-json/wc/store/v1/products`. Same checks.
- **`feed`:** a product feed given to us officially (affiliate programme or a brand that agrees), in CSV or XML (Google Merchant format). This needs a sign-up per brand.
- **`inditex`:** Zara / Bershka / Pull&Bear through the existing `src/scrape_shops.py` (full catalogue weekly, `--stock-only` in between). Approved by the team vote of 2026-10-04 (polite retry), but **switched off the same day**: the first run got "Access Denied" on the home page. Do not switch it on again without a team decision.

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

- `POST /listings/sell`: photo + price + size + city + one free-text contact (an Instagram @name or a WhatsApp number, at most 60 characters; team choice 2026-10-04) + an optional name. It reuses `read_photo` and `analyse` from `backend/app/routers/items.py`, so the seller sees the same analysis and corrects it on the Sell page. The cleaned photo is kept at 640 px (it is the only picture buyers get).
- New seller listings start as `pending`, at most 20 per seller. An admin approves or rejects them (with an optional note to the seller) in Admin > Moderation (`/admin/listings`). Pending and rejected listings answer 404 to everyone but their seller and the admins.
- `GET /listings/mine`, `PATCH /listings/{id}` (fields, price, size, or `sold`), `DELETE /listings/{id}`: the seller's own listings only; another user's answers 404, the same privacy rule as wardrobe items. Changing the name, city or contact sends the listing back to review. Deleting an account deletes its listings.
- The contact is shown only to logged-in users, on the listing page.
- **REVIEW:** the moderation rules (Admin > Moderation shows the current checklist: one piece per photo, no face or person, a plain contact).

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

1. Connector framework, the `listings` collection, the collector job, `GET /listings` + the Shop page: **done**. The `shopify` and `woocommerce` connectors are **done**; Exist, Hamadi Abid and Zen wait for their check (section 0).
2. Seller uploads and moderation: **done**.
3. Affiliate / official feeds, once the team has signed up for one.
4. Inditex: voted 2026-10-04, built, then **switched off** the same day (Access Denied on the first page). Only the frozen snapshot is shown.

## 10. Testing

- Fake connectors and a fake analyzer, in the style of `backend/tests/conftest.py`, on the `dressme_test` database.
- Recorded JSON answers per kind (a small Shopify page, a WooCommerce page, a feed file) as fixtures, so tests never touch a real site.
- Cases: a disabled source or one without a terms date is refused; a 403 / 429 stops the source and marks nothing as gone; a missing item becomes `gone` after a successful run; `source_id` + `external_id` stays unique; another user's seller listing answers 404.

## 11. Open team decisions (REVIEW)

1. Which Tunisian online shops to list: Exist, Hamadi Abid and Zen chosen (2026-10-04). Each still needs `check_shop_source.py` and a team member to read its terms before `enabled = yes`.
2. ~~Whether to reopen the Inditex sites~~: yes, polite retry (team vote 2026-10-04); they refused our browser on the first page, so they are off again.
3. Which `source` value shop and seller items get (already open in `HANDOFF.md`).
4. Moderation rules for seller listings. (~~Which contact details sellers may show~~: one free-text handle, 2026-10-04.)
5. How long a `gone` listing is kept before it is deleted.
