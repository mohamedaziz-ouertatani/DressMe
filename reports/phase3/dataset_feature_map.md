# Datasets: features, how they are used, and how they map to the unified schema

One section per dataset. Each one gives:
- **Raw features:** what the dataset contains as downloaded, from its EDA report (`reports/phase3/eda_*.md`).
- **In the notebook:** what [notebooks/phase3_walkthrough.ipynb](../../notebooks/phase3_walkthrough.ipynb) shows about it.
- **Used for:** its role in the project (Phase 3 pipeline and Phase 4 prototype).
- **Mapping:** which source feature becomes which unified field. "—" = the dataset has no such information, so the field stays empty (never guessed).

Source of truth: the `src/phase3/map_*.py` scripts and their rule files in `mappings/`. Update this page when a mapping changes.

## Summary

| Dataset | Kind of pictures | Rows after mapping | Main role | EDA report |
|---|---|---:|---|---|
| Fashion Product (`fp_`) | 60×80 px catalogue shots on white | 35,432 | The only real colour / season / usage labels; trains the colour model | [eda_fashion_product.md](eda_fashion_product.md) |
| Fashionpedia (`fpd_`) | Street / runway photos, several items each | 160,080 | Real-life items, pattern, coverage, outfits from photos | [eda_fashionpedia.md](eda_fashionpedia.md) |
| PolyVore (`pv_`) | Product shots on white | 125,910 | Main outfit-compatibility source (31,333 user-made outfits) | [eda_polyvore.md](eda_polyvore.md) |
| Local photos (`lc_`) | Our own phone photos (wardrobe / friperie) | (growing) | Test set only: the real DressMe setting | none (guide: `LOCAL_PHOTOS.md`) |
| H&M (`hm_`) | Shop product photos (shrunk to 320 px) | 63k articles | Shop catalogue: "buy something similar" | none |
| Shop demo (`zr_` / `bk_` / `pb_`) | Zara / Bershka / Pull&Bear product photos | static snapshot | Frozen shop listings with price and stock | none |

The first four are merged into `data/processed/dressme.csv`, which `merge_and_split.py` builds with the train / val / test splits. H&M and the shop demo are catalogues and are never merged into it.

---

## 1. Fashion Product Images (Small), Kaggle

**Raw features (EDA):**
- `styles.csv` has 44,446 rows. Its columns are `id`, `gender`, `masterCategory`, `subCategory`, `articleType`, `baseColour`, `season`, `year`, `usage` and `productDisplayName`. There is one 60×80 px image per id.
- 44,441 products are usable (row + image).
- 22 rows were repaired because their product name contained commas.
- Missing values are few: `usage` 317, `season` 21, `baseColour` 15, `productDisplayName` 7, `year` 1.
- `gender`: Men 49.9%, Women 41.9%, Unisex 4.9%, Boys / Girls 3.4%.
- `masterCategory`: Apparel 48%, Accessories 25%, Footwear 21%. 2,430 rows (Personal Care, Home, Sporting Goods) are off-topic.
- `articleType`: 142 types, 72 of them with fewer than 50 images. The largest are Tshirts (7,069), Shirts, Casual Shoes and Watches.
- `baseColour`: 46 colour names (black 21.9%, white 12.5%, blue 11.1%). They are grouped into the 21-colour palette.
- `season`: Summer 48%, Fall 26%, Winter 19%, Spring 7%.
- `usage`: Casual 77%, Sports 9%, Ethnic 7%, Formal 5%.
- `year`: 2007–2019, mostly 2011–2012.

**In the notebook (section 2–3):**
- It is called "the only source with real labels" for colour, season, usage and gender.
- Indian ethnic wear is removed, which is why 35,432 rows remain after mapping: kurtas, sarees, dupattas, Nehru jackets, and every item with usage `Ethnic`.
- It provides the training labels for the colour model (section 4).

**Used for:**
- Training the EfficientNet classifier (category, sub_category, pattern) through `split`.
- Training the gradient-boosting colour model (`estimate_colours.py`, on its train split).
- FashionCLIP embeddings and probes.
- The `/similar` search catalogue (`Catalog.DATASETS`).

**Mapping:**

| Unified field | From |
|---|---|
| category / sub_category | `articleType` → [fashion_product_articletype.csv](../../mappings/fashion_product_articletype.csv). Words in `productDisplayName` can fix it ([fashion_product_name_rules.csv](../../mappings/fashion_product_name_rules.csv): swim cap → accessory, goggles dropped) |
| primary_colour | `baseColour` → [fashion_product_colour.csv](../../mappings/fashion_product_colour.csv) |
| pattern | Keywords in `productDisplayName` ([fashion_product_pattern_keywords.csv](../../mappings/fashion_product_pattern_keywords.csv)) |
| season | `season` → [fashion_product_season.csv](../../mappings/fashion_product_season.csv) |
| usage | `usage` → [fashion_product_usage.csv](../../mappings/fashion_product_usage.csv) (`Ethnic` items dropped) |
| secondary_colour, style, coverage | — |
| source | `public_dataset` |
| extra columns | `gender`, `original_label` (= `articleType`), `image_group` = `fp_` + the file's MD5 (a picture found twice with different labels is dropped) |

Not used: `masterCategory` and `subCategory` (only to drop off-topic rows), and `year`.

---

## 2. Fashionpedia

**Raw features (EDA):**
- 45,623 train and 1,158 val photos with labels. The 2,044 test photos have no labels.
- Images have a median size of 682×1024 px.
- Objects: 46 categories, of which 27 are whole items (ids 0–26) and 19 are garment parts (ids 27–45: sleeve, neckline, pocket…). Each object has a bounding box and a segmentation mask (3.4% are stored as RLE).
- There are 294 attributes in 11 groups. The share of whole items carrying each group:
  - silhouette 44.8%
  - textile finishing 44.8%
  - **textile pattern** 44.3%
  - material 43.7%
  - **length** 40.1%
  - waistline 37.1%
  - **nickname** 30.1%
  - opening type 27.3%
- Neckline types and sleeve lengths are on the *part* objects (35,187 necklines), not on the garment.
- Items per photo: median 3, maximum 20. Each photo is a full outfit.
- Shoes are labelled one per foot (47,940 shoe objects in 24,758 images).
- 33.8% of item crops are shorter than 64 px (watches 93%, socks 90%, glasses 87%).
- There is **no colour label**. An estimate from pixels gives black 25.1% and navy 19.2%.

**In the notebook (section 2–3, 6–7):**
- Coverage is computed from parts: each sleeve or neckline is linked to the one garment whose box contains it, and the lowest score wins. `coverage_from` records the sources.
- Kaftan → `traditional`. These are the only public traditional items (124).
- One photo is shown with its item boxes as an example outfit.

**Used for:**
- Classifier training (cropped items).
- Colour estimation target (hand-checked: 65.9% accurate at the 0.7 cut).
- The compatibility evaluation (AUC / FITB on the test photos).
- Street → shop retrieval in the embeddings evaluation.

**Mapping:**

| Unified field | From |
|---|---|
| category | `category_id` 0–26 → [fashionpedia_category.csv](../../mappings/fashionpedia_category.csv). A nickname can move it (kaftan → traditional) |
| sub_category | Category default, refined by the `nickname` attribute ([fashionpedia_nickname.csv](../../mappings/fashionpedia_nickname.csv)). Empty when nicknames contradict each other |
| pattern | `textile pattern` attribute → [fashionpedia_pattern.csv](../../mappings/fashionpedia_pattern.csv) (lowest priority number wins; herringbone → empty) |
| usage | From the nickname (e.g. wedding) |
| coverage | Lowest score among item `length`, nickname, and linked sleeve / neckline parts ([fashionpedia_coverage.csv](../../mappings/fashionpedia_coverage.csv)) |
| primary_colour | — (estimated at merge) |
| secondary_colour, season, style | — |
| source | `public_dataset` |
| extra columns | `bbox_x/y/w/h` (one row per worn item), `outfit_id` = the photo, `coverage_from`, `original_split`, `original_label` (category name + nicknames). At merge, `image_group` = the photo |

Not used: silhouette, textile finishing, material, waistline, opening type, and the masks (the boxes are enough for cropping).

---

## 3. Maryland PolyVore (Re-PolyVore)

**Raw features (EDA):**
- 126,927 images in 20 category folders. The file name `<outfit_id>_<position>.jpg` is the only other information.
- 276 files named `<number>.jpg` belong to no outfit.
- 22 junk files (`desktop.ini`, `.lnk`, `- Copy.jpg`).
- There is **no text, no colour and no official split**.
- Pictures have a median size of 340×400 px, and 99% have a white background.
- Folders: bag 16.8%, shoes 15.9%, top 15.3%, outwear 8.0%, pants 7.1%, dress 5.9%, and jewellery / eyewear / hats for the rest. Folders are coarse: `pants` also holds shorts, and `top` holds shirt-jackets.
- 24,273 extra copies are exact duplicates. 304 duplicate groups span two folders, which makes them label conflicts.
- 31,333 outfits with a median of 4 items:
  - 39.1% have clothes and shoes;
  - 9.8% have two items of the same category.
- Colour estimate from pixels: black 16.2% overall, black 19.5% for clothes. White items are read as silver.

**In the notebook (section 2, 6):**
- It is called "the main source for outfit compatibility".
- 61% of its rows form one long chain of shared products, which is why there are two split columns and the `outfit_clean` flag.
- One clean test outfit is shown item by item.

**Used for:**
- Classifier training (categories only).
- Colour estimation target (hand-checked).
- The compatibility evaluation: PolyVore AUC 66.6% / FITB 42.6% with the team weights, on the clean test outfits.
- The `/similar` search catalogue.

**Mapping:**

| Unified field | From |
|---|---|
| category / sub_category | Folder name → [polyvore_folder.csv](../../mappings/polyvore_folder.csv) (sub_category empty for mixed folders) |
| primary_colour | — (estimated at merge) |
| secondary_colour, pattern, season, usage, style, coverage | — (pattern is later *predicted* by the classifier in `predicted_attributes.csv`, never as a label) |
| source | `public_dataset` |
| extra columns | `outfit_id` and `position` (from the file name), `image_group` = the file's MD5, `original_label` = the folder |

Pictures found in two different folders are dropped as label conflicts.

---

## 4. Local photos (our own)

**Raw features:**
- `data/raw/Local/photos/<contributor>/*.jpg` holds one item per photo, with no faces. Photos under 224 px are refused.
- `labels.csv` is filled by hand. Its columns are `file`, `contributor`, `source`, `category`, `sub_category`, `primary_colour`, `secondary_colour`, `pattern`, `season`, `usage`, `style`, `coverage`, `gender`, `outfit_id`, `labelled_by`, `checked_by` and `note`.
- `map_local.py` checks every value against the same vocabularies (it stops with the line number).
- There is no EDA report.

**In the notebook (sections 7–8):**
- It is the planned source for `traditional` items (jebba, sefsari…), friperie photos and real wardrobes.
- Its goal is to measure the gap between the public data and real users. The planned size is 500–1,000 wardrobe items, 150–300 friperie items and 50–100 local garments.

**Used for:** the **test set only**. `merge_and_split.py` puts these photos and their outfits in test. The image cache, embeddings and evaluation scripts don't include them yet.

**Mapping:** every unified field comes from its hand label. `source` = `wardrobe` / `friperie`. Extra columns: `gender`, `outfit_id` (prefixed with the contributor), `coverage_from` = `label`, `image_group` = `lc_` + MD5.

---

## 5. H&M Personalized Fashion Recommendations (shop catalogue)

**Raw features:**
- `articles.csv` has 105k articles (one per product colour), with `product_code` grouping the colours of a product.
- Its labels:
  - `product_type_name`
  - `colour_group_name`
  - `graphical_appearance_name` (pattern)
  - `index_group_name` / `section_name` / `garment_group_name`
  - `prod_name`
  - `detail_desc`
- There is **no price**.
- The pictures are shrunk to 320 px by the private Kaggle notebook (`kaggle/hm_images/`).
- There is no EDA report.

**Used for:**
- The "shop" row of `/similar`, through `Catalog.search_shop`, with embeddings from `embed_hm.py`.
- Never used as training data.

**Mapping:**

| Unified field | From |
|---|---|
| category / sub_category | `product_type_name` → [hm_product_type.csv](../../mappings/hm_product_type.csv), then [hm_refine_rules.csv](../../mappings/hm_refine_rules.csv) (denim trousers → jeans). Boots have no sub_category |
| primary_colour | `colour_group_name` → [hm_colour.csv](../../mappings/hm_colour.csv) |
| pattern | `graphical_appearance_name` → [hm_pattern.csv](../../mappings/hm_pattern.csv). Where that is unclear: keywords in `prod_name` + `detail_desc` ([hm_pattern_keywords.csv](../../mappings/hm_pattern_keywords.csv)) |
| usage | `index_group_name` → [hm_index_group.csv](../../mappings/hm_index_group.csv) (Baby / Children dropped) |
| secondary_colour, season, style, coverage | — |
| source | empty (team decision for shop items) |
| extra columns | `name`, `description`, `product_code`, `department`, `original_label` / `original_colour` / `original_pattern` |

---

## 6. Shop demo (Zara, Bershka, Pull&Bear)

**Raw features:**
- `data/raw/Shops/<brand>_<cc>/products.csv` has one row per product colour. It comes from `scrape_shops.py`.
- `stock_history.csv` has one row per stock check.
- The untouched API answers are kept in `raw/`.

**Used for:**
- A static demo of shop listings. Scraping is stopped, because all three sites block it.
- `freeze_shop_demo.py` writes `shop_demo.csv` and the pictures, and the `snapshot` listings connector shows them as "snapshot from <date>".

**Mapping:** it is not mapped to the unified schema. It keeps its shop fields: `brand`, `country`, `gender`, `name`, `colour_name`, `category_paths`, `price_tnd`, `url`, `image_url`, `image_path`, `sizes`, `availability`, `availability_level` (`colour` / `product`), `sizes_in_stock`, `checked_at`. Never redistribute this data.

---

## Shared rules for all mapped datasets

- Every category is checked against the schema, every sub_category against [sub_category_vocabulary.csv](../../mappings/sub_category_vocabulary.csv), and every colour against [colour_palette.csv](../../mappings/colour_palette.csv). A source value with no rule stops the script.
- **Colour estimation:** for rows with no colour label (PolyVore, Fashionpedia), `merge_and_split.py` fills `primary_colour` from `data/processed/colour_estimates.csv` (see [colour_estimation.md](colour_estimation.md)) when confidence is at least 0.7. Those rows get `colour_source` = `estimated` and a `colour_confidence`; labelled colours get `colour_source` = `label`.
- **Fill rates (notebook section 5):** `style` is empty in every public dataset, and `season` / `usage` come almost only from Fashion Product.
