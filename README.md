# DressMe — Personal Fashion Assistant

DressMe is an AI personal fashion assistant for young Tunisians on a limited budget who shop mostly second-hand (*friperie*), often buying unlabelled items that can rarely be returned. It helps them digitise their wardrobe, build outfits, and decide whether a piece is worth buying.

ESPRIT · Advanced Data Science project · team of 6: Mohamed Khalil, Asma Drissi, Ons Amorri, Meissa Cherni, Mohamed Aziz Ouertatani, Yassine Ben Cheikh.

| Phase | Status |
|---|---|
| 1. Empathize (survey of 57 people, personas) | done |
| 2. Ideate (14 features) | done |
| 3. Data collection | public data done; local photo collection in progress |
| 4. Full prototype | embeddings, classifier, compatibility, backend and frontend (+ admin) done |

**Planned stack:**
- Frontend: React + TailwindCSS.
- Backend and database: FastAPI and MongoDB.
- Models: EfficientNet (classification), FashionCLIP (embeddings and similarity), Gemini API or a local Qwen3 model served by Ollama (chat assistant).
- Outfit compatibility: a custom weighted formula.

## What this repository contains (Phase 3)

A reproducible pipeline that turns three public fashion datasets into **one dataset with a shared label schema** and leak-free train / val / test splits. It also builds the Phase 3 report.

- **Merged dataset:** 321,422 items (296,921 unique pictures / crops).
- **Splits:** 246,373 train, 36,750 val, 38,299 test.
- **Report:** [`reports/phase3_report.pdf`](reports/phase3_report.pdf), 18 pages. It covers EDA, label mapping, colour estimation, splits, decisions and next steps.

```
src/          pipeline scripts (EDA, mapping, colours, merge, report, embeddings, classifier, compatibility)
backend/      FastAPI + MongoDB API (app/, tests/)
frontend/     React + Vite + TypeScript app and admin dashboard
mappings/     every label rule, as editable CSV files
reports/      EDA reports (markdown), figures, Phase 3 PDF
notebooks/    exploration
data/         datasets and outputs (NOT in git, see below)
```

## Unified label schema

Every source is mapped to the same fields:

| Field | Values |
|---|---|
| `category` | top, bottom, dress, outerwear, shoes, bag, accessory, traditional, swimwear |
| `sub_category` | controlled list in `mappings/sub_category_vocabulary.csv` (t-shirt, jeans, jebba, kaftan…) |
| `primary_colour` / `secondary_colour` | 21-colour palette in `mappings/colour_palette.csv` |
| `pattern` | solid, striped, checked, floral, printed |
| `season` (multi) | summer, winter, mid-season |
| `usage` (multi) | casual, formal, sport, wedding, eid, work |
| `style` (multi) | classic, streetwear, modest, sporty, trendy |
| `coverage` | 1–5 (modesty level) |
| `source` | public_dataset, wardrobe, friperie |

Rules:
- Mapping rules live in `mappings/*.csv`, never in code. A script stops if a source value has no rule.
- Unknown values stay empty; we never guess them.
- Multi-value fields are joined with `|`.
- Rows marked `REVIEW` in a mapping's note column are open team decisions.

## Setup

```bash
pip install -r requirements.txt
```

The datasets are **not included** (licences: non-commercial academic use, no redistribution). Download them yourself and place them like this:

| Dataset | Where to put it |
|---|---|
| [Fashion Product Images (Small)](https://www.kaggle.com/datasets/paramaggarwal/fashion-product-images-small) | `data/raw/FashionProduct/styles.csv` and `data/raw/FashionProduct/images/<id>.jpg` |
| [Fashionpedia](https://fashionpedia.github.io/home/) | `data/raw/Fashionpedia/`: `instances_attributes_train2020.json` and `instances_attributes_val2020.json` at the root, train images in `train2020/train/`, val images in `validation_and_test_images_2020/test/` |
| [Maryland Polyvore](https://github.com/xthan/polyvore-dataset) (Re-PolyVore version) | `data/raw/MarylandPolyVore/Re-PolyVore/<category folder>/<outfit_id>_<position>.jpg` |
| [H&M Personalized Fashion Recommendations](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations) (shop catalogue, see "Phase 4: H&M shop catalogue") | `data/raw/HM/articles.csv`; pictures are fetched by `src/fetch_hm_images.py` |

DeepFashion2 and DressCode are requested but not available yet.

## Running the pipeline

Run from the project root, in this order:

```bash
# 1. EDA, once per dataset (also builds the PolyVore image cache used by step 2)
python src/eda_fashion_product.py
python src/eda_fashionpedia.py
python src/eda_polyvore.py

# 2. Map each dataset to the unified schema -> data/processed/<dataset>.csv
python src/map_fashion_product.py
python src/map_fashionpedia.py
python src/map_polyvore.py
python src/map_local.py            # our own photos, if any (see LOCAL_PHOTOS.md); test only

# 3. Estimate colours for PolyVore and Fashionpedia -> data/processed/colour_estimates.csv
python src/estimate_colours.py

# 4. Merge and split -> data/processed/dressme.csv
python src/merge_and_split.py

# 5. Build the report -> reports/phase3_report.pdf
python src/build_phase3_report.py
```

Notes:
- `map_fashionpedia.py`, `estimate_colours.py` and `eda_fashionpedia.py` read a 540 MB annotation file and need about 6 GB of RAM.
- The first colour run takes about 10 minutes. Later runs reuse the pixel features cached in `data/interim/`.
- After changing a rule in `mappings/`, re-run steps 2 to 5.

### Using `dressme.csv`

- **Classification:** use `split`, and drop rows where `duplicate` is True (extra copies of the same picture). All copies of a picture are always in the same split.
- **Outfit compatibility:** use `outfit_split`. For a strict evaluation, keep only val / test outfits with `outfit_clean` = True. Some PolyVore outfits share products across splits.
- **Fashionpedia items:** each row has a bounding box (`bbox_x`, `bbox_y`, `bbox_w`, `bbox_h`) to crop the item out of the photo.
- **Colour:** `colour_source` says whether a colour is a real label or an estimate.
  - Estimates are kept only when the model's confidence is at least 0.7 (`colour_confidence`).
  - On hand-labelled items they are about 77% accurate on PolyVore and 66% on Fashionpedia.
- **Local photos:** our own photos (`source` = wardrobe / friperie) always go to the test set.

### Walkthrough notebook

[`notebooks/phase3_walkthrough.ipynb`](notebooks/phase3_walkthrough.ipynb) tells the whole Phase 3 story. It covers the schema, the EDA highlights, mapping, colour accuracy, the leak checks re-run live, class balance, outfits and traditional items. It reads the pipeline outputs, so run the pipeline once first; it then runs in about a minute.

```bash
pip install notebook
jupyter notebook notebooks/phase3_walkthrough.ipynb
```

## Phase 4: FashionCLIP embeddings

Every picture gets a 512-number FashionCLIP vector. Similar items have similar vectors, which powers "find similar items" and gives the other models a strong starting point. A GPU is strongly recommended.

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements-models.txt

python src/embed_fashionclip.py --limit 500   # quick test (separate folder)
python src/embed_fashionclip.py               # all pictures, ~35 min -> data/processed/embeddings/
python src/evaluate_embeddings.py             # -> reports/embeddings_evaluation.md
```

- **What the vectors already know** (test split; full numbers in [`reports/embeddings_evaluation.md`](reports/embeddings_evaluation.md)):
  - A simple linear classifier on them reaches **88% on category** and **80% on sub_category**. The EfficientNet classifier has to beat that.
  - Street photo → product shot search works (see the grid in the report).
- **Colour:** for colour on PolyVore / Fashionpedia, the existing gradient-boosting model stays. A colour model on the vectors was worse on the hand-labelled items.
- **Similar-item search** from Python:

```python
from similarity import SimilarityIndex       # run from src/
index = SimilarityIndex.load()
index.search(index.vector("fpd_val_123"), k=5, datasets=["polyvore"])
```

- If you get a `MemoryError`, lower the loader processes with `DRESSME_WORKERS` (default 2).

## Phase 4: EfficientNet classifier

One picture in; category, sub_category and pattern out. EfficientNet-B0 is fine-tuned on the train split (about 2 h on an RTX 2050).

```bash
python src/build_image_cache.py      # once: every picture as a 224 px square, packed into one file (~35 min + packing)
python src/train_classifier.py       # ~5 x 20 min -> models/checkpoints/classifier_best.pt (not in git)
python src/evaluate_classifier.py    # -> reports/classifier_evaluation.md, reports/classifier_choice.json
```

Run long steps in a terminal you can leave open; training resumes from the last epoch if it stops.

| test accuracy | EfficientNet | FashionCLIP linear probe |
|---|---:|---:|
| category | **95.7%** | 88.3% |
| sub_category | **86.4%** | 79.7% |
| pattern | **86.8%** | 74.2% |

Using it from Python:

```python
from classifier import load_classifier, predict   # run from src/
from PIL import Image
model, device = load_classifier()
predict([Image.open("photo.jpg")], model, device)
# [{'category': 'top', 'category_conf': 0.99, 'sub_category': 'shirt', 'pattern': 'checked', ...}]
```

## Phase 4: outfit compatibility

A readable formula: **score = Σ weight × part**, from 0 to 100, with reasons. The four parts are style (FashionCLIP similarity), colour harmony, pattern mixing and outfit structure. The team sets the weights and every rule in `mappings/` (`compatibility_weights.csv`, `colour_groups.csv`, `colour_harmony.csv`, `pattern_mixing.csv`, `outfit_structure.csv`). The data only measures them.

```bash
python src/predict_item_attributes.py     # classifier predictions for every item (~10-30 min)
python src/evaluate_compatibility.py      # -> reports/compatibility_evaluation.md
python src/evaluate_compatibility.py --weights style=0.6,colour=0.2,pattern=0.1,structure=0.1   # quick try
```

| test set | AUC (real vs swapped item) | fill-in-the-blank (1 of 4) |
|---|---:|---:|
| PolyVore, 904 clean test outfits | 66.6% | 42.6% |
| Fashionpedia, 2,710 street photos | 78.7% | 59.5% |

```python
from compatibility import score_outfit, suggest_outfits, buy_advice, complete_outfit   # run from src/
item = {"category": "top", "colour": "black", "pattern": "striped", "vector": vec}   # vector = FashionCLIP
score_outfit([top, bottom, shoes])              # {'score': 78.5, 'parts': {...}, 'reasons': [...]}
buy_advice(new_item, wardrobe, profile={"min_coverage": 3})   # {'verdict': 'buy' | 'think' | 'skip', ...}
```

## Phase 4: backend API

FastAPI + MongoDB, in [`backend/`](backend/). It needs a running MongoDB (e.g. the local MongoDB service), the trained models (sections above), and `src/estimate_colours.py` run once, which saves the colour model.

```bash
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env      # then set JWT_SECRET (and GEMINI_API_KEY for the chat)
cd backend
uvicorn app.main:create_app --factory --port 8000    # docs: http://localhost:8000/docs
python -m pytest                                      # 25 fast tests (fake models, dressme_test database)
```

| endpoint | what it does |
|---|---|
| `POST /auth/register`, `POST /auth/login`, `GET/PUT /me` | account, profile (modesty level, language) |
| `POST /items`, `GET /items`, `PATCH /items/{id}`, `DELETE /items/{id}` | wardrobe: upload a photo (analysed), list, correct, delete |
| `POST /analyze`, `POST /buy-advice` | friperie photo → "should I buy this?" (buy / think / skip) |
| `POST /outfits/score`, `GET /outfits/suggest`, `POST /outfits/complete` | outfits from your wardrobe |
| `GET /similar` | look-alikes in your wardrobe + dataset inspiration + H&M products to buy (`shop`) |
| `POST /chat`, `GET/DELETE /chat/history` | Gemini or local Ollama assistant that uses your real wardrobe |

## Phase 4: the app (frontend + admin)

React + Vite + TypeScript + Tailwind, in [`frontend/`](frontend/). It talks to the backend API above.

```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173 (the API must run on :8000)
npm run build && npm run lint
```

```bash
cd backend
python -m app.seed_demo                  # demo user with 17 dataset pieces + an admin (passwords in backend/.env)
python -m app.make_admin you@example.com # give an existing account the admin role
```

- **What's in it:**
  - Today's outfit, Scan ("should I buy this?" with a stamped BUY / THINK / SKIP), Wardrobe (every predicted field correctable), Build, the Assistant chat, Similar pieces, and Profile (modesty level, language);
  - English, French and Arabic (right-to-left).
  - Admins also get `/admin`: usage stats, model quality (how often users correct each prediction), user management, and the formula editor.
- **Design:** the visual system ("Ticket & Recharge-Card Stock") is documented in [`DESIGN.md`](DESIGN.md), and the product brief in [`PRODUCT.md`](PRODUCT.md).
- **Demo data:** demo accounts show dataset photos and say so in the app; they are for the academic demo only.

## Phase 4: H&M shop catalogue

The shops block scraping (Zara / Bershka / Pull&Bear, team decision 2026-10-03), so the "buy something like this" suggestions come from the H&M catalogue published on Kaggle: real retail products with their type, colour and pattern. It is **not** merged into `dressme.csv`: it is not training data, it is what the user could buy. There is no price in the data.

1. On Kaggle, accept the competition rules (closed competition: the **Late Submission** button shows them; nothing needs to be submitted). The Kaggle API must use the same account: a `~/.kaggle/access_token` file takes priority over `kaggle.json`.
2. Run:

```bash
kaggle competitions download -c h-and-m-personalized-fashion-recommendations -f articles.csv -p data/raw/HM   # then unzip
python src/map_hm.py            # labels -> data/processed/hm.csv (63k adult products; children's wear dropped)
kaggle kernels push -p kaggle/hm_images     # private Kaggle notebook: shrinks the pictures to 320 px (~20 min on Kaggle)
python src/fetch_hm_images.py   # when the notebook is COMPLETE: download its zip (~850 MB) and unpack it
python src/embed_hm.py          # FashionCLIP vectors -> data/processed/embeddings/hm_fashionclip.*
```

The full picture set is ~30 GB and Kaggle allows only ~500 single-file downloads per period, so the pictures are shrunk on Kaggle by a **private** notebook ([`kaggle/hm_images/`](kaggle/hm_images/); change the account in `kernel-metadata.json` and `fetch_hm_images.py` if you use your own) and downloaded as one zip. The label rules are in `mappings/hm_*.csv`, with the same conventions as the other datasets (unknown stays empty; boots have no sub_category because the vocabulary has none).

### Colour validation (optional)

```bash
python src/make_colour_labelling_sheet.py   # 400 items + offline labelling page in data/interim/colour_labelling/
python src/evaluate_colour_labels.py        # after labelling: accuracy -> reports/colour_validation.*
```

## Datasets and licences

The datasets are used for non-commercial academic work only and are never redistributed through this repository; `data/` is git-ignored. The figures in `reports/` include small sample thumbnails used for analysis. Licence details are in section 2 of the report:
- Fashion Product: MIT, per the Kaggle page.
- Fashionpedia: annotations are CC BY 4.0; the images belong to their owners.
- Maryland Polyvore: the dataset repository is Apache-2.0; the images belong to Polyvore users.
- H&M Personalized Fashion Recommendations: Kaggle competition data, non-commercial use under the competition rules; the pictures belong to H&M.

## More context

- [`PRODUCT.md`](PRODUCT.md): users, purpose, constraints and principles of the app.
- [`DESIGN.md`](DESIGN.md): the visual system (colours, type, components and their rules).
- [`reports/`](reports/): every evaluation report (EDA, colours, embeddings, classifier, compatibility).
