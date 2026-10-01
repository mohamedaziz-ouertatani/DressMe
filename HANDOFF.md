# DressMe — Handoff (2026-10-01)

Paste this into a new Claude chat to pick up the project.

## What DressMe is

An AI personal fashion assistant built by a team of 6 for an ESPRIT Advanced Data Science project. It targets young Tunisians on a tight budget who mostly buy second-hand (friperie). Those items are often unlabelled and can rarely be returned.

- **Stack:** React + TailwindCSS, FastAPI, MongoDB.
- **Models:** EfficientNet for classification, FashionCLIP for embeddings and similarity, and the Gemini API for the chat assistant. Outfit compatibility comes from a custom weighted formula.
- **Survey (57 responses):** black dominates 84% of wardrobes, 56% shop second-hand, 40% are frustrated by fit, and 42% want "should I buy this?" advice.
- **Personas (Phase 1):** Amira, Youssef, Nour, Rania, Salma, Ines, Skander. The Phase 3 data collection plan (team PDF) maps each feature to a persona and a "How might we" question (H1–H9).

Phases 1 (Empathize) and 2 (Ideate) are finished. **Phase 3 (data collection) is done on the public data.** What is left is the local photo collection.

## Unified label schema (the target for every dataset)

| Field | Values |
|---|---|
| category | top, bottom, dress, outerwear, shoes, bag, accessory, traditional |
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

**Merged file `data/processed/dressme.csv`:** 324,018 rows (299,514 unique pictures / crops).

| Dataset | Rows | Notes |
|---|---:|---|
| Fashion Product | 38,081 | Product shots at 60x80 px. The only source with real labels for colour, season, usage and gender. 2,430 off-topic rows dropped. 4 pictures that appear twice with different labels are dropped in the mapping, which also writes `image_group` (file MD5). Pattern is read from product-name keywords. |
| Fashionpedia | 160,027 | One row per worn item, with a bbox to crop; `outfit_id` = the photo. Coverage is the lowest score over length, nickname, sleeve and neckline (`coverage_from` lists the sources). The official test set has no labels, so our splits use its train + val images only. |
| PolyVore (Maryland) | 125,910 | Product shots on white, in 31,333 outfits. Labelled by folder only. About 24k exact duplicates; `image_group` = MD5. Pictures found in two folders are dropped. |

- **Categories:** shoes 77,260 · accessory 66,845 · top 58,946 · bottom 37,368 · bag 31,694 · dress 28,164 · outerwear 23,617 · traditional 124 (Fashionpedia kaftans).
- **Splits (80/10/10, from a hash of the group id, so they are stable):** train 248,440 · val 37,008 · test 38,570.
  - `split` is per picture (`image_group`) and is used for classification. For Fashionpedia, `image_group` is the photo.
  - `outfit_split` is per outfit and is used for compatibility. A picture used in a test outfit goes to test.
  - In PolyVore, 61% of rows form one chain of outfits linked by shared products, so outfits and pictures cannot both be kept apart. `outfit_clean = False` marks outfits that share a picture with another split; use only clean val / test outfits for a strict evaluation (1,064 clean PolyVore test outfits).
  - `duplicate = True` marks extra copies of a file (24,504); drop them when training a classifier.
  - Local photos (`source` = wardrobe / friperie) always go to test.

**Colour:**

- Labels: real for Fashion Product, estimated for PolyVore and Fashionpedia (`colour_source` = label / estimated, plus `colour_confidence` and, in the estimates file, `predicted_colour` before the cut).
- Model: gradient boosting on Lab colour histograms, trained on Fashion Product's train split. The simple "nearest palette colour" rule was only 25–36% accurate.
- Confidence cut **0.6** (team decision): 78.5% accurate on unseen Fashion Product images. Hand labels (395 items) gave **77% on PolyVore** (colour kept for 61%) and **69% on Fashionpedia** (kept for 55%).
- Main error: black read as navy or brown.
- Colour stays empty for Fashionpedia crops under 64 px or without a polygon mask. Gold and silver are never predicted for clothes.
- Features are cached in `data/interim/colour_features_*.pkl` (only the pixel features are reused; labels are re-read each run). Delete the cache after changing `features()`.

## Decisions taken

- **Kaftan → `traditional`** (sub_category `kaftan`). Nickname rules now have an optional `category` column in `mappings/fashionpedia_nickname.csv` to move an item to another category.
- **Colour confidence cut = 0.6.**
- **Metallic colours** are not allowed for clothes (estimates only).
- **PolyVore outfits sharing a picture** are kept and flagged (`outfit_clean`).

## Open team decisions (11 `REVIEW` rows)

- **Indian ethnic wear (Fashion Product):** Kurtas and Kurtis → tunic. Churidar, Salwar and Patiala → trousers. Sarees and Swimwear are dropped. The "Ethnic" usage → formal, though it could be eid or wedding.
- **Herringbone:** currently checked, could be solid.
- **Glasses / eyewear (Fashionpedia, PolyVore):** sunglasses and eyeglasses are merged into one value, but Kaggle only has sunglasses.

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

## Next steps

1. **Local data collection** (plan: wardrobes 500–1,000 items, friperie 150–300, local garments 50–100, fit-check subset 50–100, ~100 near-duplicate pairs). It needs signed consent and blurred faces. Add the photos with `source` = wardrobe / friperie; the split script puts them in test.
2. Settle the remaining REVIEW rows, then re-run the pipeline (steps 2 → 5).
3. **Phase 4:**
   - Train EfficientNet on `split` (without duplicates).
   - Compute FashionCLIP embeddings.
   - Fit the compatibility formula on `outfit_split`.
   - Try a colour model on the embeddings to fix the black / navy / brown confusion, and compare it on the same hand labels.
4. Add DeepFashion2 and DressCode when access is granted. ModaNet and VITON-HD are in the plan but not requested yet. The plan's Polyvore Outfits (68k) was replaced by the Maryland version.

## Project rules

- Never commit `data/` or model weights; datasets are for non-commercial academic use only.
- Scripts go in `src/`, exploration in `notebooks/`, and charts in `reports/figures/`.
- Keep the code simple and commented, because the team has mixed experience.
