# DressMe — Handoff (2026-10-02)

Paste this into a new Claude chat to pick up the project.

## What DressMe is

An AI personal fashion assistant built by a team of 6 for an ESPRIT Advanced Data Science project. It targets young Tunisians on a tight budget who mostly buy second-hand (friperie). Those items are often unlabelled and can rarely be returned.

- **Stack:** React + TailwindCSS, FastAPI, MongoDB.
- **Models:** EfficientNet for classification, FashionCLIP for embeddings and similarity, and the Gemini API for the chat assistant. Outfit compatibility comes from a custom weighted formula.
- **Survey (57 responses):** black dominates 84% of wardrobes, 56% shop second-hand, 40% are frustrated by fit, and 42% want "should I buy this?" advice.
- **Personas (Phase 1):** Amira, Youssef, Nour, Rania, Salma, Ines, Skander. The Phase 3 data collection plan (team PDF) maps each feature to a persona and a "How might we" question (H1–H9).

Phases 1 (Empathize) and 2 (Ideate) are finished. **Phase 3 (data collection) is done on the public data**; the local photo collection is still to do. **Phase 4 (full prototype) has started.** It is split into five sub-projects: embeddings (done), classifier (done), compatibility, backend, frontend.

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

None: every `REVIEW` row was settled on 2026-10-01 (see above).

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

## Next steps

1. **Local data collection** (can run alongside Phase 4; plan: wardrobes 500–1,000 items, friperie 150–300, local garments 50–100, fit-check subset 50–100, ~100 near-duplicate pairs). It needs signed consent and blurred faces. Add the photos with `source` = wardrobe / friperie; the split script puts them in test.
2. **Phase 4**, one design → plan → build cycle per sub-project:
   - ~~FashionCLIP embeddings~~ (done).
   - ~~EfficientNet classifier~~ (done: 95.7% category, 86.4% sub_category, 86.8% pattern).
   - **Next:** compatibility formula fitted on `outfit_split`.
   - FastAPI + MongoDB backend (classify, similar items, score an outfit, Gemini chat).
   - React + Tailwind frontend.
3. Add DeepFashion2 and DressCode when access is granted. ModaNet and VITON-HD are in the plan but not requested yet. The plan's Polyvore Outfits (68k) was replaced by the Maryland version.

## Project rules

- Never commit `data/` or model weights; datasets are for non-commercial academic use only.
- Scripts go in `src/`, exploration in `notebooks/`, and charts in `reports/figures/`.
- Keep the code simple and commented, because the team has mixed experience.
