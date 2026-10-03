# DressMe — Project context for Claude Code

## Project

DressMe is an AI personal fashion assistant (ESPRIT, Advanced Data Science project, team of 6). Target users: young Tunisians on a limited budget, shopping mostly second-hand (friperie), often with unlabelled items that can rarely be returned.

Phases 1 (Empathize), 2 (Ideate) and 3 (Data collection) are done. **Current phase: Phase 4 — full prototype**, built as five sub-projects, each designed, planned and built in turn: 1. FashionCLIP embeddings, 2. EfficientNet classifier, 3. compatibility formula, 4. FastAPI + MongoDB backend, 5. React frontend. Models train on the local GPU (RTX 2050, 4 GB); see `requirements-models.txt` for the CUDA PyTorch install.

## Tech stack (authoritative)

- **Frontend:** React + TailwindCSS
- **Backend:** FastAPI
- **Database:** MongoDB
- **Models:** EfficientNet (classification), FashionCLIP (embeddings, similarity), Gemini API (chat assistant)
- **Outfit compatibility:** custom weighted compatibility formula

## Local datasets

Paths are relative to `data/` (never committed to git).

- `data/raw/FashionProduct/`: Kaggle Fashion Product Images (Small), `styles.csv` + `images/<id>.jpg` (44,441 usable products, 60x80 px). `myntradataset/` inside it is a duplicate copy; ignore it. EDA: `src/eda_fashion_product.py` → `reports/eda_fashion_product.md`.
- `data/raw/MarylandPolyVore/Re-PolyVore/<folder>/<outfit_id>_<position>.jpg`: 126,927 product shots on white background in 20 category folders. Group by `outfit_id` across folders to rebuild the 31,333 outfits. There is no text, colour or official split. 276 files named `<number>.jpg` have no outfit link. About 24k exact-duplicate images exist, so keep all copies in the same split. Skip the junk files (`desktop.ini`, `.lnk`, `- Copy.jpg`). EDA: `src/eda_polyvore.py` → `reports/eda_polyvore.md`. The image info cache is `data/interim/polyvore_image_info.csv`.
- `data/raw/Fashionpedia/`: street/runway photos with several items per image. Annotations are `instances_attributes_train2020.json` / `_val2020.json` at the folder root (test set has no labels). Train images are in `train2020/train/`; val images are in `validation_and_test_images_2020/test/`. Category ids 0-26 are whole items and 27-45 are garment parts. There are no colour labels. Neckline and sleeve-length attributes sit on the part objects. Ids restart per split, so prefix them. EDA: `src/eda_fashionpedia.py` → `reports/eda_fashionpedia.md`.
- `data/raw/Local/`: our own phone photos (wardrobe / friperie), **test only**. `photos/<contributor>/*.jpg` (anonymous ids like `c01`, no faces) + `labels.csv` filled by hand. `src/map_local.py --init` adds rows for new photos; `src/map_local.py` checks every label against `mappings/` (stops with the line number) → `data/processed/local.csv` (ids `lc_`, `image_group` = `lc_` + MD5). `merge_and_split.py` reads it if present and puts local photos and their outfits in test. Phone rotation (EXIF) is applied in `load_item_image` for local rows only. Team guide: `LOCAL_PHOTOS.md`. The image cache, embeddings and evaluation scripts don't include `local` yet.
- `data/raw/DeepFashion2/`, `data/raw/DressCode/`: empty, pending access
- `data/raw/HM/`: H&M Personalized Fashion Recommendations (Kaggle competition, closed; rules accepted through the "Late Submission" button). This is the **shop catalogue** that replaces scraping (team decision 2026-10-03), not training data, so it is never merged into `dressme.csv`. `articles.csv` = 105k articles (one per product colour; `product_code` groups the colours) with type, colour and pattern ("graphical appearance") labels, no price. `src/map_hm.py` → `data/processed/hm.csv` (63k adult articles, ids `hm_`; rules in `mappings/hm_*.csv`; boots have no sub_category). The full pictures are ~30 GB (disks nearly full) and Kaggle allows only ~500 single-file downloads per period (429), so a **private** Kaggle notebook (`kaggle/hm_images/`, pushed with `kaggle kernels push -p kaggle/hm_images`; Kaggle mounts the data under a changing path, so it searches `/kaggle/input`) shrinks every adult picture to 320 px into one zip, and `src/fetch_hm_images.py` downloads and unpacks it into `images/`. `src/embed_hm.py` → `data/processed/embeddings/hm_fashionclip.*`. The Kaggle CLI uses `~/.kaggle/access_token` before `kaggle.json`; it must belong to the account that accepted the rules (mohameddazizz).
- `data/raw/Shops/<brand>_<cc>/`: Zara, Bershka and Pull&Bear catalogue (men + women) with stock, from `src/scrape_shops.py` (Playwright; `requirements-scraping.txt`). It writes `products.csv` (one row per product colour, ids `zr_` / `bk_` / `pb_`), `stock_history.csv` (one row per check; `--stock-only` re-checks) and the untouched API answers in `raw/`. These are private Inditex endpoints, so they can change; never redistribute the data. Not mapped to the unified schema yet: `source` has no value for shop items (team decision). Zara's bot protection (Akamai) sometimes answers "Access Denied" (2026-10-03: one run passed, the next was blocked, likely after too many requests), and the script then stops: wait hours, retry with a larger `--delay`, and never try to get around it (stealth plugins, rotating proxies). Bershka / Pull&Bear untested on the real sites. **Scraping is stopped (team decision 2026-10-03):** all three sites block it, so the rows already scraped are kept as a static demo, never refreshed. `src/freeze_shop_demo.py` → `data/processed/shop_demo.csv` + `shop_demo_images/` (pictures downloaded once). `availability_level` says how far stock can be trusted: `colour` = checked for that colour; `product` = rows scraped before the per-colour fix, where "in_stock" only means some colour / size of the product was.

## Unified label schema (target for all sources)

| Field | Values |
|---|---|
| `category` | top, bottom, dress, outerwear, shoes, bag, accessory, traditional, swimwear |
| `sub_category` | t-shirt, shirt, jeans, jebba, sneakers, ...: allowed values and their parent category in `mappings/sub_category_vocabulary.csv` (shared; map to the coarsest value every dataset can produce, e.g. polo → t-shirt) |
| `primary_colour` / `secondary_colour` | fixed palette of 21 colours, defined in `mappings/colour_palette.csv` (shared by all datasets) |
| `pattern` | solid, striped, checked, floral, printed |
| `season` | summer, winter, mid-season (multi) |
| `usage` | casual, formal, sport, wedding, eid, work (multi) |
| `style` | classic, streetwear, modest, sporty, trendy (multi) |
| `coverage` | 1–5 (modesty level) |
| `source` | public_dataset, wardrobe, friperie |

## Phase 3 goals

1. EDA per dataset: size, class balance, missing values, colour distribution.
2. Label mapping from each dataset to the unified schema (`mappings/*.csv`). Rules live in CSVs, never hard-coded; the apply script (e.g. `src/map_fashion_product.py`) fails if a source value has no rule. Multi-value fields use `|`. Unknown stays empty (never guess, e.g. pattern). Output goes to `data/processed/<dataset>.csv`, with ids prefixed per dataset (`fp_`, ...). Rows marked `REVIEW` in a mapping's note column are open team decisions (the label mappings have none since 2026-10-01; the compatibility rule files of Phase 4 are all REVIEW until the team tunes them). Fashionpedia (`src/map_fashionpedia.py` → `data/processed/fashionpedia.csv`) has one row per worn item, with a bbox to crop and `outfit_id` = the photo. Its coverage is the minimum over length, nickname, and the linked sleeve / neckline parts, and `coverage_from` lists the sources used. Sleeveless items have no sleeve part, so coverage can be overestimated when `sleeve` is not in `coverage_from`. PolyVore (`src/map_polyvore.py` → `data/processed/polyvore.csv`, needs the EDA cache) maps by folder only. `image_group` = the file's MD5, and rows sharing it must stay in one split. Pictures found in two different folders are dropped as label conflicts. Fashion Product articleTypes that mix things (Swimwear holds swimming caps and goggles) are fixed by keywords in `mappings/fashion_product_name_rules.csv`.
3. Merged, cleaned dataset with train / val / test splits (local photos reserved for test). Colour for PolyVore / Fashionpedia comes from `src/estimate_colours.py` → `data/processed/colour_estimates.csv` + `reports/colour_estimation.md`. It is a gradient-boosting model on Lab histograms, trained on Fashion Product's train split; snapping pixels to the nearest palette colour was only 25-36% accurate. The colour stays empty below confidence 0.7 (team decision) and for Fashionpedia crops under 64 px. Gold and silver are never predicted for clothes. Features are cached in `data/interim/colour_features_*.pkl`; delete them after changing `features()`. Pipeline order: map_*.py → estimate_colours.py → merge_and_split.py → build_phase3_report.py. `src/merge_and_split.py` → `data/processed/dressme.csv` (run after the map scripts; `local.csv` is optional). The splits are 80/10/10, decided by a hash of the group id, so they are stable. `split` is per picture (`image_group`) and is used for classification. `outfit_split` is per outfit and is used for compatibility. A picture used in a test outfit goes to test. `outfit_clean` = False marks outfits that share a picture with another split; use clean ones for strict evaluation. `duplicate` = True marks extra copies of a file; drop them for classification. Fashionpedia's `image_group` is the photo. Fashion Product pictures that appear twice with different labels are dropped in `map_fashion_product.py`, which also writes `image_group`.
4. EDA report for the Phase 3 validation.

## Phase 4 (in progress)

1. **Embeddings (done):** `src/fashionclip.py` holds the shared helpers: load the model, crop a Fashionpedia item, embed images / texts. `src/embed_fashionclip.py` → `data/processed/embeddings/fashionclip.npy` (N x 512 float16, unit length) + `fashionclip_ids.csv` (row ↔ id). It runs once per picture: per `image_group` for product shots, per item for Fashionpedia crops ≥ 32 px. It is resumable (one shard per dataset), and `DRESSME_WORKERS` sets the loader processes. `src/similarity.py` (`SimilarityIndex`) does nearest-neighbour search and is reused by the API later. `src/evaluate_embeddings.py` → `reports/embeddings_evaluation.md`: zero-shot, linear probes (the baseline the classifier must beat), colour from vectors vs the gradient-boosting model, and street → shop retrieval. Headline results: the linear probe reaches 88% category and 80% sub_category (the bar for EfficientNet). Colour from the vectors is worse on the hand labels, so the gradient-boosting colour model stays. The probes train on the GPU (`Probe` class), because sklearn LogisticRegression is far too slow on this machine. Long runs (> 10 min) must be launched as a separate process writing a log, not as a background tool command.
2. **Classifier (done):** EfficientNet-B0 (ImageNet weights) with three heads: category, sub_category, pattern. Each picture only trains the heads it has a label for, and classes are weighted 1/sqrt(freq). `src/item_images.py` holds the light, PIL-only picture helpers (`picture_key`, `jobs_for`, `load_item_image`, `letterbox`) shared by every script. `src/build_image_cache.py` → `data/interim/image_cache_224.bin` + `_index.csv`: every distinct picture letterboxed to a 224 px white square, packed into ONE file, because opening 282k small files on Windows ran at ~300/s. `src/classifier.py` has the model, `gpu_batch` (GPU JPEG decode + augmentation, no hue change), and `load_classifier` / `predict(pil_images)` for the API. `predict` keeps the sub_category inside the predicted category. `src/train_classifier.py` → `models/checkpoints/classifier_best.pt` (git-ignored): 5 epochs, ~20 min each at ~200 img/s (GPU-bound), resumable, `--limit` for smoke tests. `src/evaluate_classifier.py` → `reports/classifier_evaluation.md` + `reports/classifier_choice.json`: which model the app uses per field (team rule: whichever is better; EfficientNet won all three). It also saves the FashionCLIP probes to `models/checkpoints/fashionclip_probe.pt`. Test results: category 95.7%, sub_category 86.4%, pattern 86.8%, against 88.3 / 79.7 / 74.2 for the probe. Traditional and swimwear are too small to learn (traditional is read as dress).
3. **Compatibility formula (done):** `src/compatibility.py`: score = weighted sum of four parts from 0 to 1, shown as 0-100 with reasons. A part that can't be computed is left out and the other weights are rescaled.
   - **The parts:** style (mean FashionCLIP similarity, rescaled with `style_low` / `style_high`), colour (pair table + a bold-colour penalty), pattern (the worst clothing pattern pair), structure (top + bottom or a full piece, plus shoes and category limits).
   - **Weights and rules are set by the TEAM** in `mappings/compatibility_weights.csv`, `colour_groups.csv`, `colour_harmony.csv`, `pattern_mixing.csv` and `outfit_structure.csv`. The data only measures them; never change the weights from the data without the team.
   - **Functions:** `filter_items` (profile: min_coverage / season / occasion; unknown fields pass), `suggest_outfits`, `buy_advice` (only counts good outfits where the new item beats every owned item of its category, and flags near-twins), and `complete_outfit`.
   - **Predicted attributes:** `src/predict_item_attributes.py` → `data/processed/predicted_attributes.csv`, the classifier's predictions for every row (PolyVore has no pattern labels). These are predictions, never labels.
   - **Evaluation:** `src/evaluate_compatibility.py` → `reports/compatibility_evaluation.md`: AUC (real outfit vs one item swapped within its category) and FITB on the clean PolyVore test outfits and the Fashionpedia test photos, plus a demo figure. Use `--weights style=..,colour=..` for quick tries.
   - **Results with the team weights:** PolyVore AUC 66.6% / FITB 42.6%; Fashionpedia 78.7% / 59.5%. Style alone does better (72.9% / 84.6% AUC), and colour, pattern and structure add no signal in the swap test (structure can't, by design).

4. **Backend (done):** `backend/` (FastAPI + pymongo, local MongoDB 4.0, so pymongo is pinned below 4.14). Run it from `backend/` with `uvicorn app.main:create_app --factory --port 8000`; the docs are at `/docs`.
   - **Settings:** `backend/.env` (git-ignored; see `.env.example`): `JWT_SECRET` (required), `GEMINI_API_KEY`, `GEMINI_MODEL`.
   - **`app/ml.py`:** wraps the src/ models (`Analyzer`: classifier + colour model + FashionCLIP; `Catalog`: `SimilarityIndex` on PolyVore / Fashion Product). `src/estimate_colours.py` now also saves `models/checkpoints/colour_model.joblib`; re-running it gave identical estimates.
   - **Auth:** email + password, bcrypt + JWT. Image endpoints also accept `?token=`, for `<img>` tags.
   - **Endpoints:**
     - `/auth/*`, `/me` (profile: name, `min_coverage`, language);
     - `/items` (upload → analysed; PATCH = user corrections, tracked in `corrected`; the model's guesses stay in `predicted`);
     - `/analyze` (candidate, not saved, deleted after 24 h);
     - `/buy-advice`, `/outfits/score|suggest|complete`, `/similar`, `/catalog/{id}/image`;
     - `/chat` (Gemini with function calling: `list_wardrobe`, `suggest_outfits`, `score_outfit`, `buy_advice_last_scan`; history per user).
   - **Privacy:** every query is filtered by `user_id`, and another user's item answers 404.
   - **Tests:** `python -m pytest` in `backend/`, using fakes and the `dressme_test` database (25 tests, ~15 s). `DRESSME_SLOW=1` adds the real-model tests.
   - **Colour on uploads:** a colour below 0.7 confidence is left empty (the guess is kept in `predicted`), so the UI must let the user confirm it.
   - **Shop:** `/similar` also returns `shop` = the nearest H&M products (`Catalog.search_shop`, `SimilarityIndex.load_shop`), images at `/catalog/hm_<id>/image`; empty if the H&M files are missing.

## Rules

- Never commit anything under `data/` or model weights; keep them in `.gitignore`.
- Datasets are for non-commercial academic use only; never redistribute them.
- Prefer scripts in `src/` and exploration in `notebooks/`; save charts to `reports/figures/`.
- Keep code simple and commented: the team has mixed experience.

## Survey reference numbers (57 responses)

- Black dominates 84% of wardrobes.
- 56% shop second-hand.
- 40% are frustrated by fit.
- 42% want "should I buy this?" advice.
