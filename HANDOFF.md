# DressMe — Handoff (2026-10-03, updated 14:00 after the full app walkthrough)

Paste this file into a new Claude Code session on your machine to pick up the project. Read the first six sections first (state, branches, commands, next steps); everything after "Reference" is the detailed record of what was built and decided.

## 1. Current context (2026-10-03)

- **Phase 3 (data) is done on the public data.** Three datasets are mapped to the unified schema by rules in `mappings/*.csv` and merged into `data/processed/dressme.csv` (321,422 rows, stable 80/10/10 splits):
  - **Fashion Product** (`src/map_fashion_product.py` → `fashion_product.csv`, 35,432 rows): the only source with real colour / season / usage labels. Indian ethnic wear removed; mixed articleTypes (e.g. Swimwear holding caps and goggles) fixed by name keywords in `mappings/fashion_product_name_rules.csv`.
  - **Fashionpedia** (`src/map_fashionpedia.py` → `fashionpedia.csv`, 160,080 rows): one row per worn item with a bbox; `outfit_id` = the photo; coverage = minimum over length / nickname / sleeve / neckline (`coverage_from` lists the sources).
  - **PolyVore** (`src/map_polyvore.py` → `polyvore.csv`, 125,910 rows): labelled by folder only; `image_group` = file MD5; pictures found in two folders dropped.
  - Colours for PolyVore / Fashionpedia come from `src/estimate_colours.py` (gradient boosting on Lab histograms, kept only at confidence ≥ 0.7).
  - The local photo collection (wardrobe / friperie): the pipeline is ready (`src/map_local.py`, `LOCAL_PHOTOS.md`, #13), but `data/raw/Local/photos/` is still **empty**.
- **Phase 4: all five sub-projects are done and on `main`:** embeddings, classifier, compatibility formula, backend, and the React frontend + admin dashboard (#8).
- **Shop catalogue = H&M (#9).** Scraping Zara / Bershka / Pull&Bear is stopped (all three block it; team decision: never get around it). Instead, "buy something like this" uses the **H&M catalogue from Kaggle**: 63,005 adult products mapped to the schema, 62,741 searchable with FashionCLIP. `/similar` returns them as `shop`, and the app's **Similar pieces** screen shows them in a "Buy something like this" row. See "H&M shop catalogue" in the Reference part.
- The Zara rows scraped before the block stay a **static demo** (`src/freeze_shop_demo.py` → `data/processed/shop_demo.csv`), not used by the app.
- **`/chat` fix (#9):** `gemini-2.5-flash` no longer works with new API keys (404, shown as 503); the default model is now `gemini-3.8-flash`.
- **Since then (#11–#18):**
  - Phase 4 PDF report (`src/build_phase4_report.py` → `reports/phase4_report.pdf`, updated in #18);
  - jury demo script `DEMO.md` (#12);
  - phone photo rotation fix + local photo pipeline (#13);
  - **background removal** on every upload (rembg U2-Net, then U2-Net cloth-seg keeps only the biggest garment when the item is worn; #14, #17);
  - **outfit clash rule**: never the same sub_category twice or a category over its limit (`/outfits/score|complete` answer 422; the Build page swaps the piece; #15);
  - Build page groups the wardrobe by category (#16).
- **Full walkthrough done on 2026-10-03** (section 5): everything works end to end except the chat. Gemini overload and quota errors are now retried / explained in the app. The real limit is the **free Gemini key: 20 requests a day** (see `DEMO.md`).

## 2. Branches and pull requests

Everything is on **`main`**; only ImgBot PR #1 is still open (optional). Every branch of #10–#18 was squash-merged, so these leftovers can be deleted (locally and on GitHub): `build-group-by-category`, `outfit-clash-rule`, `handoff-update`, `claude/practical-hawking-na1oqs`, `claude/lucid-hamilton-jvxg37`.

| PR | What | State |
|---|---|---|
| #1 | ImgBot: optimise images | **open**, optional |
| #2, #3, #5, #6 | compatibility, backend, scraper, scraper fixes + this file | merged (squashed) |
| #4 | frontend; merged into `phase4-backend` *after* that branch had gone into `main`, so it missed `main` | landed on `main` through #8 |
| #7 | accidental revert of #6 | closed, not merged |
| #8 | frontend + admin dashboard → `main` | merged |
| #9 | H&M shop catalogue + `/chat` model fix | merged |
| #10 | this file after #8 / #9 | merged |
| #11, #18 | Phase 4 PDF report, then its update with #12–#17 | merged |
| #12, #13 | pre-demo fixes, `DEMO.md`, phone photo rotation, local photo pipeline | merged |
| #14, #17 | background removal on uploads, then garment-only cut for worn items | merged |
| #15 | outfit clash rule (no sub_category twice, category limits) | merged |
| #16 | Build page grouped by category | merged |

**Lessons, to avoid repeating them:**
- With stacked PRs (B based on A), merge B into A *before* A goes into `main`, or retarget B to `main` first. Otherwise B lands on a dead branch (#4).
- After a squash merge, the old branch can't be merged again (git sees "added on both sides" conflicts). Start new work from a fresh `main`.
- Two Claude sessions in the same folder leave half-finished merges behind. Before switching branches, run `git status`; if a merge is in progress, check what it would change (`git diff --cached --stat HEAD`) before aborting.

## 3. Step-by-step local commands (Windows, from `C:\dev\DressMe`)

```bash
# 0. get the code
git checkout main && git pull origin main

# 1. virtual environment (once)
python -m venv .venv
.venv\Scripts\activate                  # bash on Windows: source .venv/Scripts/activate
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126   # GPU build FIRST
pip install -r requirements-models.txt
pip install -r backend/requirements.txt

# 2. backend (needs the local MongoDB service running)
copy backend\.env.example backend\.env      # then set JWT_SECRET (and GEMINI_API_KEY for /chat)
cd backend
python -m pytest                            # 36 fast tests, ~20 s
uvicorn app.main:create_app --factory --port 8000   # http://localhost:8000/docs, models load in ~1 min
python -m app.seed_demo                     # once, with the API running: demo + admin accounts, passwords written to backend/.env
python -m app.make_admin you@example.com    # optional: make an existing account admin

# 3. frontend (second terminal)
cd frontend
npm install                                 # first time only
npm run dev                                 # http://localhost:5173, forwards /api to :8000
```

Demo login: `demo@example.com` (admin: `admin@example.com`); the passwords are on the `DEMO_PASSWORD` / `DEMO_ADMIN_PASSWORD` lines of `backend/.env`.

**Restart the backend after rebuilding any vectors** (`embed_fashionclip.py`, `embed_hm.py`): it loads the catalogues only at start-up. Also restart it after every `git pull` that touches `backend/` or `src/`: there is no auto-reload, and during the walkthrough an old server was still running the code from before #17.

In the Claude desktop app, `.claude/launch.json` starts both servers (`api`, `web`) from the preview pane.

Do NOT run `src/scrape_shops.py` again: all three shops block it, and retrying makes the block last longer.

## 4. Data state and conventions

Nothing under `data/` or `models/` is in git; it exists only on your machine. Datasets are for non-commercial academic use, never redistributed.

| File (in `data/processed/`) | Made by | Notes |
|---|---|---|
| `fashion_product.csv`, `fashionpedia.csv`, `polyvore.csv` | `src/map_*.py` | one per dataset, ids `fp_`, `fpd_`, `pv_` |
| `colour_estimates.csv` | `src/estimate_colours.py` | colour + confidence for PolyVore / Fashionpedia; empty below 0.7 |
| `dressme.csv` | `src/merge_and_split.py` | the merged dataset: `split` (per picture, for classification), `outfit_split` (per outfit), `outfit_clean`, `duplicate` |
| `embeddings/fashionclip.npy` + `fashionclip_ids.csv` | `src/embed_fashionclip.py` | 306,636 × 512 float16 |
| `predicted_attributes.csv` | `src/predict_item_attributes.py` | classifier predictions, never labels |
| `hm.csv` | `src/map_hm.py` | **H&M shop catalogue**, 63,005 rows, ids `hm_`; not part of `dressme.csv` |
| `embeddings/hm_fashionclip.npy` + `hm_fashionclip_ids.csv` | `src/embed_hm.py` | 62,741 × 512 float16 (the shop search) |
| `shop_demo.csv` + `shop_demo_images/` | `src/freeze_shop_demo.py` | **static** Zara demo snapshot (2026-10-03), not used by the app |

Raw H&M data: `data/raw/HM/articles.csv` + `images/<article_id>.jpg` (70,521 pictures, 320 px). Raw shop data: `data/raw/Shops/<brand>_tn/` (see "Shop data" in the Reference part).

**`shop_demo.csv` caveat:** `availability_level` = `product` for all current Zara rows: "in_stock" only means *some colour or size* of the product was in stock on 2026-10-03.

Shop items (H&M and Zara) have no `source` value yet: a team decision.

**Rule files in `mappings/`** (rules live in CSVs, never in code; the apply scripts fail when a source value has no rule; multi-value fields use `|`; unknown stays empty):
- label mappings: `fashion_product_*.csv`, `fashionpedia_*.csv`, `polyvore_folder.csv`, `hm_*.csv`, shared `sub_category_vocabulary.csv` and `colour_palette.csv`. No open `REVIEW` rows.
- compatibility rules (set by the TEAM, all `REVIEW` until tuned): `compatibility_weights.csv`, `colour_groups.csv`, `colour_harmony.csv`, `pattern_mixing.csv`, `outfit_structure.csv`. Never change the weights from the data without the team; the frontend's admin formula editor rewrites `compatibility_weights.csv`.

## 5. Immediate next steps

1. **What the walkthrough found** (fixes in the `handoff-walkthrough` PR: items 1, 7 and 8; the rest is still open). The full walkthrough ran on 2026-10-03 on `main` at #17: the backend tests (31) and `npm run build` pass; demo + admin accounts; English / French / Arabic; desktop and a 375 px phone screen. No page scrolls sideways on the phone, the Arabic layout mirrors correctly, and no console errors appeared. These work: log-in, Today, Wardrobe + correcting a field, Scan of a product shot (SKIP) and a street photo (dress found, colour left for the user, THINK after setting it), Similar pieces with the H&M row, Build with the swap rule, Profile, and the four admin tabs. Found, most important first:
   1. **Chat failed, with the wrong message (FIXED).** Gemini answered `503 UNAVAILABLE: model is currently experiencing high demand`, and the app said "The team needs to add the Gemini key" although the key is set. Then the key hit `429 RESOURCE_EXHAUSTED`, quota `GenerateRequestsPerDayPerProjectPerModel-FreeTier` = **20 requests a day**; one chat answer with tools costs 2 to 7 of them (automatic function calling, `maximum_remote_calls=6`), so a few test messages use up the day. Now `chat_engine.py` retries 500 / 503 twice (1 s, 3 s) and never retries 429; `/chat` answers 503 = no key, 502 = Gemini busy, 429 = quota used up; `ChatPage.tsx` shows a message for each (en / fr / ar), and the typed question stays in the box. Still the biggest risk for the jury demo (step 6): save the quota on demo day, or use a key with billing on (`DEMO.md`).
   2. **The demo wardrobe has the same jacket twice.** Item `6ac0ccce0263af6b3ffa2138` was uploaded at 09:37 on top of the 17 seeded pieces. It shows twice in Similar pieces and in Build's "Complete it with". Delete it before the demo.
   3. **Modesty and occasion change nothing in the demo.** None of the demo pieces has coverage, season or occasion set, and unknown fields always pass, so step 8 of `DEMO.md` (modesty 4 → different suggestions) shows the exact same outfit. Fix: have `app/seed_demo.py` set coverage / season / usage on the demo pieces (by hand, a team choice: PolyVore has no such labels), or change the demo script.
   4. **The scan shows the original photo, not the cut-out the models read.** For a worn item, the user can't see which garment cloth-seg kept. Candidates (`/analyze`) don't keep the cleaned picture; consider saving it for 24 h like the candidate and showing it.
   5. **SKIP gives only a generic line.** The pink tee got "It does not beat what you already own", `reasons` empty and no near-twin warning, although 2 pink tops are owned (best wardrobe match 63%, under `similar_item`). Maybe fine (team threshold), but the verdict could say which owned piece beats it.
   6. **Near-identical outfits.** "Best outfits with it" showed two outfits that differ only by the bottom (shorts vs skirt; same shoes, jacket and bag).
   7. **Similar pieces repeated itself (FIXED).** The H&M row showed one product in several colours; `SimilarityIndex.load_shop` now groups by `product_code`, so each product appears once. The "Inspiration" row showed the demo item itself at 100% (the demo pieces come from PolyVore); `Catalog.search` now leaves out matches ≥ 0.99.
   8. **French (FIXED):** `casual-shoes` was "Chaussures de ville" (dress shoes); now "Chaussures décontractées".
   9. **Stamp wording:** the stamp around a SKIP verdict says "VALIDÉ · مصادق" ("approved"), which reads oddly next to SKIP.
2. **Local photo collection (team):** the biggest gap. Every result so far is on public datasets; even 100–200 friperie / wardrobe photos (consent, blurred faces; `source` = wardrobe / friperie, always in test) would show whether the classifier and colour model hold up on real use. The pipeline is ready (`src/map_local.py --init`, then `src/map_local.py`, then `merge_and_split.py`); the image cache, embeddings and evaluation scripts still have to learn to read `local`.
3. **Team decisions still open:** tune the compatibility weights (style alone scores better: 72.9% vs 66.6% AUC on PolyVore), pick a `source` value for shop items, and fill the *[to fill]* parts of the Phase 3 report (who labels the local photos, collection dates).
4. **Dropped:** tagging the Zara demo pictures with the classifier (old prompt B). H&M gives 62k products with real labels, so it's no longer worth it.
5. Optional tidy-up: close or merge ImgBot PR #1; delete the merged branches listed in section 2.

## 6. Ready-to-paste prompts for the new session

**Prompt A: the remaining walkthrough findings**

> Read CLAUDE.md and HANDOFF.md, section 5 item 1 (walkthrough findings; 1, 7 and 8 are fixed). Start a branch from a fresh `main`. Before the demo: delete the duplicate jacket from the demo wardrobe (item 2) and give the demo pieces coverage / season / occasion in `app/seed_demo.py` so the modesty and occasion filters visibly change Today (item 3): ask me which values to use. Then propose fixes for items 4 (show the cut-out on Scan), 6 (more varied outfits) and 9 (stamp wording). Don't change the verdict thresholds or weights (team decisions). Run `python -m pytest` in `backend/` and `npm run build` in `frontend/`, then check the screens in the browser, sending as few chat messages as possible (20 Gemini requests a day).

**Prompt B: rebuild the H&M catalogue on another machine**

> Read CLAUDE.md and HANDOFF.md, section "H&M shop catalogue". On this machine `data/raw/HM/` is empty. Check that my Kaggle API account accepted the H&M competition rules, then run the four steps (articles.csv, `map_hm.py`, the private notebook + `fetch_hm_images.py`, `embed_hm.py`) and confirm `/similar` returns a `shop` list. Watch the disk space (~1.7 GB needed while unzipping).

---

# Reference (detailed record)

## What DressMe is

An AI personal fashion assistant built by a team of 6 for an ESPRIT Advanced Data Science project. It targets young Tunisians on a tight budget who mostly buy second-hand (friperie). Those items are often unlabelled and can rarely be returned.

- **Stack:** React + TailwindCSS, FastAPI, MongoDB.
- **Models:** EfficientNet for classification, FashionCLIP for embeddings and similarity, and the Gemini API for the chat assistant. Outfit compatibility comes from a custom weighted formula.
- **Survey (57 responses):** black dominates 84% of wardrobes, 56% shop second-hand, 40% are frustrated by fit, and 42% want "should I buy this?" advice.
- **Personas (Phase 1):** Amira, Youssef, Nour, Rania, Salma, Ines, Skander. The Phase 3 data collection plan (team PDF) maps each feature to a persona and a "How might we" question (H1–H9).

Phases 1 (Empathize) and 2 (Ideate) are finished. **Phase 3 (data collection) is done on the public data**; the local photo collection is still to do. **Phase 4 (full prototype) is done:** five sub-projects, all on `main`: embeddings, classifier, compatibility, backend, frontend (+ the H&M shop catalogue).

## Unified label schema (the target for every dataset)

| Field | Values |
|---|---|
| category | top, bottom, dress, outerwear, shoes, bag, accessory, traditional, swimwear |
| sub_category | controlled list in `mappings/sub_category_vocabulary.csv`; each dataset maps to the coarsest shared value (e.g. polo → t-shirt) |
| primary / secondary_colour | fixed 21-colour palette in `mappings/colour_palette.csv` |
| pattern | solid, striped, checked, floral, printed |
| season | summer, winter, mid-season (multi) |
| usage | casual, formal, sport, wedding, eid, work (multi) |
| style | classic, streetwear, modest, sporty, trendy (multi) |
| coverage | 1–5 (modesty level) |
| source | public_dataset, wardrobe, friperie |

**Conventions**

- Rules live in `mappings/*.csv`, never in code. The apply scripts fail when a source value has no rule.
- Multi-value fields are joined with `|`.
- An unknown value stays empty; we never guess one.
- Every id carries a dataset prefix: `fp_`, `fpd_`, `pv_`.
- A note column marked `REVIEW` means the team still has to decide.

## The pipeline

Run in this order (all from the project root). Everything it writes under `data/` is never committed.

| Step | Script | Output |
|---|---|---|
| 1. EDA (once per dataset) | `src/eda_fashion_product.py`, `src/eda_fashionpedia.py`, `src/eda_polyvore.py` | `reports/eda_*.md`, `reports/figures/<dataset>/` |
| 2. Mapping | `src/map_fashion_product.py`, `src/map_fashionpedia.py`, `src/map_polyvore.py` | `data/processed/<dataset>.csv` |
| 3. Colour estimation | `src/estimate_colours.py` | `data/processed/colour_estimates.csv`, `reports/colour_estimation.md` |
| 4. Merge + splits | `src/merge_and_split.py` | `data/processed/dressme.csv` |
| 5. Report | `src/build_phase3_report.py` | `reports/phase3_report.pdf` (18 pages) |

Helpers: `src/colour_utils.py` handles the Lab colour space and palette matching, and `src/plot_style.py` holds the DressMe chart colours (rust #8E4420, gold #C9A063, cream #F2E8DA, dark #23201C).

Colour validation (already done): `src/make_colour_labelling_sheet.py` → `data/interim/colour_labelling/` (400 items and an offline labelling page), then `src/evaluate_colour_labels.py` → `reports/colour_validation.csv/.md`.

## Where the data stands

**Merged file `data/processed/dressme.csv`:** 321,422 rows (296,921 unique pictures / crops).

| Dataset | Rows | Notes |
|---|---:|---|
| Fashion Product | 35,432 | Product shots at 60x80 px. The only source with real labels for colour, season, usage and gender. 2,430 off-topic rows dropped, and all Indian ethnic wear removed (garment types such as kurtas and sarees, plus every item with usage "Ethnic"). 4 pictures that appear twice with different labels are dropped in the mapping, which also writes `image_group` (file MD5). Pattern is read from product-name keywords. |
| Fashionpedia | 160,080 | One row per worn item, with a bbox to crop; `outfit_id` = the photo. Coverage is the lowest score over length, nickname, sleeve and neckline (`coverage_from` lists the sources). The official test set has no labels, so our splits use its train + val images only. |
| PolyVore (Maryland) | 125,910 | Product shots on white, in 31,333 outfits. Labelled by folder only. About 24k exact duplicates; `image_group` = MD5. Pictures found in two folders are dropped. |

- **Categories:** shoes 77,237 · accessory 66,532 · top 56,782 · bottom 37,226 · bag 31,690 · dress 28,164 · outerwear 23,598 · traditional 124 (Fashionpedia kaftans) · swimwear 69 (10 Fashion Product swimsuits, 59 Fashionpedia swim-shorts).
- **Splits (80/10/10, from a hash of the group id, so they are stable):** train 246,373 · val 36,750 · test 38,299.
  - `split` is per picture (`image_group`) and is used for classification. For Fashionpedia, `image_group` is the photo.
  - `outfit_split` is per outfit and is used for compatibility. A picture used in a test outfit goes to test.
  - In PolyVore, 61% of rows form one chain of outfits linked by shared products, so outfits and pictures cannot both be kept apart. `outfit_clean = False` marks outfits that share a picture with another split; use only clean val / test outfits for a strict evaluation (1,064 clean PolyVore test outfits).
  - `duplicate = True` marks extra copies of a file (24,501); drop them when training a classifier.
  - Local photos (`source` = wardrobe / friperie) always go to test.

**Colour:**

- Labels: real for Fashion Product, estimated for PolyVore and Fashionpedia (`colour_source` = label / estimated, plus `colour_confidence` and, in the estimates file, `predicted_colour` before the cut).
- Model: gradient boosting on Lab colour histograms, trained on Fashion Product's train split. The simple "nearest palette colour" rule was only 25–36% accurate.
- Confidence cut **0.7** (team decision): 83.1% accurate on unseen Fashion Product images (colour given to 49%). Hand labels (395 items) gave **77% on PolyVore** (colour kept for 52%) and **66% on Fashionpedia** (kept for 44%), against 74% / 61% at 0.6. With ~100 items per dataset the 95% intervals are about ±8 points, so the gain is a trend, not proof. Over the whole data, PolyVore has a colour for 52% of rows and Fashionpedia for 32% (small crops get none).
- Main error: black read as navy or brown.
- Colour stays empty for Fashionpedia crops under 64 px or without a polygon mask. Gold and silver are never predicted for clothes.
- Features are cached in `data/interim/colour_features_*.pkl` (only the pixel features are reused; labels are re-read each run). Delete the cache after changing `features()`.

## Decisions taken

- **Indian ethnic wear removed** (Fashion Product: kurtas, kurtis, churidar, salwar, patiala, dupatta, sarees, lehenga, Nehru jackets, and every item with usage "Ethnic"; Fashionpedia: Nehru jackets). `mappings/fashion_product_usage.csv` has a new `keep` column for this.
- **Kaftan → `traditional`** (sub_category `kaftan`). Nickname rules now have an optional `category` column in `mappings/fashionpedia_nickname.csv` to move an item to another category.
- **Colour confidence cut = 0.7** (raised from 0.6 on 2026-10-01: on the hand labels it gives 77% / 66% instead of 74% / 61%, and we have enough data to afford fewer colours).
- **Swimwear included** as a 9th category, `swimwear` (sub_categories `swimsuit` and `swim-shorts`): Fashion Product swimsuits and Fashionpedia trunks / boardshorts. Swimming caps filed under Swimwear become accessory / cap and goggles are dropped, through the new `mappings/fashion_product_name_rules.csv` (keywords in the product name). There are under 100 public items, so local photos (including modest swimwear) are needed.
- **Herringbone → pattern left empty** (a fine zigzag weave, neither checked nor solid). It keeps priority 3, so "herringbone + plain" stays empty while "herringbone + floral" is floral.
- **Glasses / eyewear:** sunglasses and eyeglasses stay merged into `glasses`, because neither Fashionpedia nor PolyVore separates them.
- **Metallic colours** are not allowed for clothes (estimates only).
- **PolyVore outfits sharing a picture** are kept and flagged (`outfit_clean`).

## Open team decisions

None in the label mappings: every `REVIEW` row there was settled on 2026-10-01 (see above). Still open: the compatibility weights and rules (all `REVIEW`), a `source` value for shop items (H&M and Zara), and the Phase 3 report's *[to fill]* parts (see section 5).

## The report

`reports/phase3_report.pdf` (rebuilt by `src/build_phase3_report.py`, which reads the pipeline outputs, so the numbers stay correct):

- context, dataset inventory with licences, and traceability (data → features → personas · HMW);
- schema, the three EDAs, and label mapping;
- colour estimation, including the hand-label check;
- merged dataset and splits (the validation EDA);
- local data collection, open decisions, risks, and next steps;
- Appendix A (project files) and Appendix B (code excerpts).

Sections are numbered automatically from the `SECTIONS` list in the script.

**Still marked *[to fill]* in the report:** who labels the local photos (and how they are double-checked), and the planned collection dates.

## Phase 4: FashionCLIP embeddings (sub-project 1, done)

- **Setup:** the CUDA build of PyTorch for the RTX 2050 (4 GB), installed as described in `requirements-models.txt`. The model is `patrickjohncyh/fashion-clip`, loaded with `transformers`.
- **Scripts:**
  - `src/fashionclip.py`: shared helpers (load the model, crop a Fashionpedia item with 5% padding, embed images / texts).
  - `src/embed_fashionclip.py`: the one-off pass over the data.
  - `src/similarity.py`: `SimilarityIndex`, nearest-neighbour search with dataset / category filters and `exclude_ids`.
  - `src/evaluate_embeddings.py`: the evaluation.
- **Output:** `data/processed/embeddings/fashionclip.npy` (306,636 × 512 float16, unit length) and `fashionclip_ids.csv`.
  - Each picture is embedded once (282,135 distinct pictures); duplicate copies share their vector.
  - The 14,786 Fashionpedia crops under 32 px have no vector.
  - The run takes about 35 min with `DRESSME_WORKERS=4`. Image loading is the bottleneck (about 140 img/s); the GPU could do 680/s.
- **Results** (`reports/embeddings_evaluation.md`, test split, duplicates left out):
  - **Zero-shot** (no training): 72% category, 60% sub_category.
  - **Linear probe** on the vectors: **88% category** (96% Fashion Product, 95% PolyVore, 81% Fashionpedia), **80% sub_category**, 74% pattern. **This is the bar for the EfficientNet classifier.**
  - **Colour from the vectors:** better on Fashion Product (71% vs 64.5%), but clearly worse on the hand-labelled PolyVore / Fashionpedia items (63% vs 77% and 42% vs 66% at equal coverage). **Decision: keep the gradient-boosting colour model.**
  - **Street → shop retrieval:** 65% of the 5 nearest product shots share the street item's category, and the picture grid looks right.
- **Lessons:**
  - Commands longer than 10 min must run as a separate process writing a log, because background tool commands are killed at 10 min. That is how the first PyTorch install got cut off.
  - sklearn's LogisticRegression was far too slow on this machine (25 s for 3,000 vectors), so the probes train on the GPU instead (`Probe` in `evaluate_embeddings.py`).

## Phase 4: EfficientNet classifier (sub-project 2, done)

- **Model:** EfficientNet-B0 with ImageNet weights, fine-tuned with three heads (category, sub_category, pattern).
  - A picture only trains the heads it has a label for (PolyVore has no pattern).
  - Classes are weighted 1/√frequency.
- **Scripts:**
  - `src/item_images.py`: shared picture helpers, PIL only.
  - `src/build_image_cache.py`: the one-off image cache.
  - `src/classifier.py`: the model, GPU batch decoding, and `predict()` for the API.
  - `src/train_classifier.py`: training.
  - `src/evaluate_classifier.py`: the evaluation.
- **Image cache:** each distinct picture, letterboxed to a 224 px white square, packed into a single file `data/interim/image_cache_224.bin` (2.6 GB) with an index. The first version kept 282k small files, and training crawled at 49 img/s, because Windows opens small files at only ~300/s. With the packed file and GPU JPEG decoding, training runs at ~200 img/s and the GPU is the limit.
- **Training:**
  - 5 epochs of ~20 min each.
  - AdamW, cosine schedule, mixed precision, batch size 64.
  - Augmentation: crop, flip, brightness / contrast. No hue change, so colours stay true.
  - The weights go to `models/checkpoints/classifier_best.pt` (git-ignored). The per-epoch log is `reports/classifier_training_log.csv`.
- **Test results** (`reports/classifier_evaluation.md`; the FashionCLIP probe was scored on the same pictures):

| field | EfficientNet | FashionCLIP probe | Fashionpedia (street crops), EfficientNet vs probe |
|---|---:|---:|---:|
| category | **95.7%** | 88.3% | 93.2% vs 80.8% |
| sub_category | **86.4%** | 79.7% | 81.2% vs 69.1% |
| pattern | **86.8%** | 74.2% | 87.1% vs 74.4% |

- **Model choice:** under the team rule (whichever is better), **EfficientNet is used for all three fields** (`reports/classifier_choice.json`, read by the API).
- **Weak spots:**
  - `traditional` (kaftans; mostly read as dress) and `swimwear` have too few public pictures to learn. Local photos are needed.
  - Small sub_categories are weaker; balanced accuracy is about 80%.
  - `predict()` always gives a pattern and sub_category with a confidence, even for items like shoes, so the app should show the confidence or hide low-confidence answers.

## Phase 4: compatibility formula (sub-project 3, done)

- **The formula** (`src/compatibility.py`): **score = Σ weight × part**, shown from 0 to 100 with short reasons ("red and pink clash", "two bold patterns", "no shoes").
  - **The four parts** (0 = bad, 1 = good):
    - style: average FashionCLIP similarity of the items;
    - colour: pair table from colour groups + specific pairs, and a penalty above 3 bold colours;
    - pattern: the worst pattern pair among the clothes;
    - structure: wearable outfit + category limits.
  - **Unknown parts** (e.g. no colours known) are left out and the other weights are rescaled.
- **Set by the team** (team decision 2026-10-02: hand-tuned, the data only measures):
  - the starting weights style 0.35 / colour 0.30 / pattern 0.15 / structure 0.20;
  - every rule, in `mappings/compatibility_weights.csv`, `colour_groups.csv`, `colour_harmony.csv`, `pattern_mixing.csv` and `outfit_structure.csv`.

  All are marked REVIEW.
- **Personal filters on top** (team decision): `filter_items(items, profile)` drops items below the user's modesty (coverage) level, or not for the season / occasion. Unknown fields always pass.
- **App functions:**
  - `score_outfit`;
  - `suggest_outfits`: best cores, completed with shoes / outerwear / bag / accessory; each item appears in at most 2 suggestions;
  - `buy_advice`: buy / think / skip, from the good outfits where the new item **beats every item of its category you already own**, and it warns about near-twins you already own;
  - `complete_outfit`.
- **Classifier predictions:** `src/predict_item_attributes.py` → `data/processed/predicted_attributes.csv` (306,636 rows). PolyVore has no pattern labels, so the formula uses the predicted pattern above confidence 0.6.
- **Evaluation** (`reports/compatibility_evaluation.md`; to try other weights: `python src/evaluate_compatibility.py --weights style=..,colour=..,pattern=..,structure=..`):

| test set | team weights AUC / FITB | style alone AUC / FITB |
|---|---:|---:|
| PolyVore, 904 clean test outfits | 66.6% / 42.6% | 72.9% / 49.7% |
| Fashionpedia, 2,710 test photos | 78.7% / 59.5% | 84.6% / 70.0% |

  AUC chance = 50%, FITB chance = 25%.
  - **Colour and pattern** add no measurable signal in this test (about 51%); half of PolyVore items have no colour.
  - **Structure** can't add any, by design: a swap keeps the category.
  - The learned reference puts about 95% of the weight on style.
  - **For the team:** consider raising the style weight. Colour and pattern still give users readable reasons.
- **Style scale:** real outfits average 0.35–0.55 FashionCLIP similarity. The CSV maps 0.2 → 0 and 0.8 → 1. A narrower scale made scores pile up at 100 (ties).
- **Checks of `buy_advice`:**
  - removing the best outfit's top / bottom / shoes from a mock wardrobe and offering it back gives "buy" (5–7 winning outfits);
  - an exact copy of an owned item gives "skip", with the near-twin warning.
- **Limit:** PolyVore taste (online collages) and Fashionpedia (runway / street) aren't Tunisian friperie wardrobes. The local photos and user feedback are the real test.

## Phase 4: backend (sub-project 4, done)

- **Stack:** FastAPI + MongoDB (the local MongoDB 4.0 service, so pymongo is pinned below 4.14), in `backend/`. It reuses the src/ models through `app/ml.py` instead of copying them.
- **Run it:**
  1. copy `backend/.env.example` to `backend/.env` and set `JWT_SECRET`;
  2. from `backend/`: `uvicorn app.main:create_app --factory --port 8000`;
  3. open http://localhost:8000/docs.

  The models load in about a minute.
- **Team decisions (2026-10-02):**
  - real accounts (email + password; bcrypt + JWT);
  - a Gemini chat **with tools**;
  - similar items from the wardrobe **and** the public datasets, served only locally to logged-in users for the academic demo.
- **Endpoints:**
  - sign-up / log-in, and the profile (name, modesty level `min_coverage`, language fr / ar / en);
  - wardrobe upload (analysed: category, sub_category, pattern, colour + FashionCLIP vector; photos shrunk to 1024 px);
  - **user corrections** (`PATCH /items/{id}`; the model's guesses stay in `predicted`, corrected fields are listed in `corrected`);
  - `/analyze` for friperie photos (not saved; the candidate is deleted after 24 h);
  - `/buy-advice`, outfit score / suggest / complete, `/similar`;
  - `/chat`, with history per user.
- **Chat:** Gemini automatic function calling with four tools bound to the user (`list_wardrobe`, `suggest_outfits`, `score_outfit`, `buy_advice_last_scan`). The system prompt asks it to use the real wardrobe, answer in the user's language and respect their modesty level. **It needs `GEMINI_API_KEY` in `backend/.env`** (set since 2026-10-03); without it `/chat` answers 503. Gemini overload (500 / 503) is retried twice, then answers 502; a used-up quota answers 429 (the free key allows 20 requests a day); see section 5.
- **Colour model:** `src/estimate_colours.py` now saves the trained model to `models/checkpoints/colour_model.joblib`, which the backend uses for uploads. Re-running it gave byte-identical estimates.
- **Tests** (`backend/tests/`):
  - 19 fast tests at the time (36 now, after the frontend, H&M, background removal, clash-rule and chat-retry work) with fake models / Gemini on a `dressme_test` database (~12 s). They cover auth, validation, privacy (other users' items → 404), uploads, corrections, outfits, buy advice, similar items and chat.
  - `DRESSME_SLOW=1` adds 2 tests of the real models (category right on at least 36 of 40 test photos; catalog search).
- **Background removal (#14, #17):** `app/background.py` shrinks every upload (`/items`, `/analyze`) to 1024 px, removes the background with rembg (U2-Net), pastes it on white and crops around the item, so it looks like the product shots the models learned from. When the item is worn, U2-Net keeps the whole person, so U2-Net cloth-seg cuts it down to the biggest garment (only when that garment is under 85% of the main object). ~3-5 s per photo on the CPU. Switches: `REMOVE_BACKGROUND=0`, `CLOTH_MODEL=` (empty). The original photo is not kept.
- **Live check** of the real server: 8 real photos uploaded, **8/8 categories right**. Suggest, buy advice, similar, catalog images and chat (503 without a key) all work. Colours: 3 of 8 were confident (one of them wrong: navy read as black), and 5 were left for the user to confirm, so **the frontend must make colour easy to confirm**.

## Phase 4: frontend and admin dashboard (sub-project 5, done)

- `frontend/`: React 19 + Vite + TypeScript + Tailwind 4 (see `frontend/README.md`; `DESIGN.md` for the visual system "Ticket & Recharge-Card Stock"; `PRODUCT.md` for the brief).
- Screens: Today's outfit, Scan ("should I buy this?" with a stamped BUY / THINK / SKIP), Wardrobe (every predicted field correctable; dashed = guessed, solid = confirmed), Build, Assistant chat, Similar pieces (wardrobe look-alikes, H&M products to buy, dataset inspiration), Profile. English, French, Arabic (right-to-left).
- Admins get `/admin`: usage stats, model quality (how often users correct each prediction), user management, and the formula editor (rewrites `mappings/compatibility_weights.csv`).
- Images are loaded with the `Authorization` header (blob URLs), not `?token=` links.
- It reached `main` through #8 (see section 2 for why #4 missed it).

## H&M shop catalogue (2026-10-03, #9)

- **Why:** the shops block scraping, so the "buy something like this" suggestions come from H&M Personalized Fashion Recommendations (Kaggle competition, closed). Real retail products with type, colour and pattern labels; **no price, no stock**. Licence: non-commercial use under the competition rules; the pictures belong to H&M. It is a shop catalogue, **not** training data: never merge it into `dressme.csv`.
- **Kaggle access:** the account must have accepted the rules (closed competition: the **Late Submission** button shows them; nothing to submit). The Kaggle CLI reads `~/.kaggle/access_token` **before** `kaggle.json`: both must belong to that account (mohameddazizz). A 403 means the wrong account, a 401 an expired key.
- **Labels:** `src/map_hm.py` + `mappings/hm_*.csv` → `data/processed/hm.csv`: 105,542 articles → 63,005 adult products (children's wear, underwear, nightwear, socks and non-clothing dropped). Notable rules: blouse → shirt (like Fashionpedia), polo → t-shirt, denim trousers → jeans and men's swimwear bottoms → swim-shorts (`hm_refine_rules.csv`), "Greenish Khaki" → olive, boots → shoes with no sub_category (not in the vocabulary). Pattern comes from "graphical appearance", with keywords in the name / description where it's unclear; textures (lace, sequin…) stay empty.
- **Pictures:** the full set is ~30 GB, and Kaggle allows only ~500 single-file downloads per period (429 Too Many Requests, then pauses of 12–40 min), so downloading one by one would take days. Instead a **private** Kaggle notebook (`kaggle/hm_images/`, `kaggle kernels push -p kaggle/hm_images`) shrinks the 70,521 adult pictures to 320 px into one zip (670 MB, 15 min on Kaggle), and `src/fetch_hm_images.py` downloads and unpacks it. Kaggle mounts the competition data under a path that changes, so the notebook searches `/kaggle/input`. Keep the notebook private.
- **Vectors:** `src/embed_hm.py` → `embeddings/hm_fashionclip.*` (62,741 products, ~5 min on the GPU once the pictures are in the disk cache). It writes `.new` files and then swaps them in: on Windows a running backend used to hold the old file open, and a whole run was lost. The backend now reads this file into memory (64 MB) instead of keeping it open.
- **API and app:** `SimilarityIndex.load_shop()`, `Catalog.search_shop()`; `/similar` returns `shop` (name, department, colour, score, picture at `/catalog/hm_<id>/image`) in the item's category, or an empty list if the H&M files are missing. The app shows them on Similar pieces.
- **Quality check:** with Fashion Product items as queries, the closest H&M product has the same category 93.6% of the time even without the category filter (500 items). Navy jeans → blue / navy skinny jeans (0.78–0.80), white sneakers → white runners, green tee → green / teal tees. Weakest: colour on dresses (the shape matches better than the colour).

## Shop data: scraper and static demo (2026-10-03)

- `src/scrape_shops.py` opens each shop's Tunisia site in Chromium (Playwright) and calls the site's own JSON endpoints: Zara `/categories?ajax=true`, `/category/<id>/products?ajax=true`, product page `?ajax=true` (sizes + SKUs per colour) and `/itxrest/1/catalog/store/<store>/product/id/<id>/availability`; Bershka / Pull&Bear `/itxrest/2|3/catalog/store/<store>/<catalog>/...`. These are private Inditex endpoints.
- Fixes made after the first real run: Zara's store id is caught from a product page (the home page makes no `/itxrest/` call); stock is filtered to the row's colour (Zara's answer covers every colour); the script stops on a block page; every run saves `debug_home.html/.png` + `debug_requests.txt`.
- What happened: one Zara run succeeded (prices in TND = raw / 100, checked); then Zara, Bershka and Pull&Bear all answered Akamai "Access Denied". Decision: stop scraping, keep the rows as a static demo (`src/freeze_shop_demo.py`), never use stealth plugins or rotating proxies.
- Alternatives if more shop data is needed: a public Kaggle catalogue dataset (no Tunisian stock), a small hand-collected sheet of Tunisian shop / friperie items, or asking Inditex Tunisia for academic access.

## Project rules

- Never commit `data/` or model weights; datasets are for non-commercial academic use only.
- Scripts go in `src/`, exploration in `notebooks/`, and charts in `reports/figures/`.
- Keep the code simple and commented, because the team has mixed experience.
