# DressMe — Project context for Claude Code

## Project

DressMe is an AI personal fashion assistant (ESPRIT, Advanced Data Science project, team of 6). Target users: young Tunisians on a limited budget, shopping mostly second-hand (friperie), often with unlabelled items that can rarely be returned.

Phases 1 (Empathize) and 2 (Ideate) are done. **Current phase: Phase 3 — Data collection.**

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
- `data/raw/DeepFashion2/`, `data/raw/DressCode/`: empty, pending access

## Unified label schema (target for all sources)

| Field | Values |
|---|---|
| `category` | top, bottom, dress, outerwear, shoes, bag, accessory, traditional |
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
2. Label mapping from each dataset to the unified schema (`mappings/*.csv`). Rules live in CSVs, never hard-coded; the apply script (e.g. `src/map_fashion_product.py`) fails if a source value has no rule. Multi-value fields use `|`. Unknown stays empty (never guess, e.g. pattern). Output goes to `data/processed/<dataset>.csv`, with ids prefixed per dataset (`fp_`, ...). Rows marked `REVIEW` in a mapping's note column are open team decisions. Fashionpedia (`src/map_fashionpedia.py` → `data/processed/fashionpedia.csv`) has one row per worn item, with a bbox to crop and `outfit_id` = the photo. Its coverage is the minimum over length, nickname, and the linked sleeve / neckline parts, and `coverage_from` lists the sources used. Sleeveless items have no sleeve part, so coverage can be overestimated when `sleeve` is not in `coverage_from`. PolyVore (`src/map_polyvore.py` → `data/processed/polyvore.csv`, needs the EDA cache) maps by folder only. `image_group` = the file's MD5, and rows sharing it must stay in one split. Pictures found in two different folders are dropped as label conflicts.
3. Merged, cleaned dataset with train / val / test splits (local photos reserved for test). Colour for PolyVore / Fashionpedia comes from `src/estimate_colours.py` → `data/processed/colour_estimates.csv` + `reports/colour_estimation.md`. It is a gradient-boosting model on Lab histograms, trained on Fashion Product's train split; snapping pixels to the nearest palette colour was only 25-36% accurate. The colour stays empty below confidence 0.6 (team decision) and for Fashionpedia crops under 64 px. Gold and silver are never predicted for clothes. Features are cached in `data/interim/colour_features_*.pkl`; delete them after changing `features()`. Pipeline order: map_*.py → estimate_colours.py → merge_and_split.py → build_phase3_report.py. `src/merge_and_split.py` → `data/processed/dressme.csv` (run after the three map scripts). The splits are 80/10/10, decided by a hash of the group id, so they are stable. `split` is per picture (`image_group`) and is used for classification. `outfit_split` is per outfit and is used for compatibility. A picture used in a test outfit goes to test. `outfit_clean` = False marks outfits that share a picture with another split; use clean ones for strict evaluation. `duplicate` = True marks extra copies of a file; drop them for classification. Fashionpedia's `image_group` is the photo. Fashion Product pictures that appear twice with different labels are dropped in `map_fashion_product.py`, which also writes `image_group`.
4. EDA report for the Phase 3 validation.

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
