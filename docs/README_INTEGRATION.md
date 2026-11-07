# Label check + condition hint: integration kit

Two small engines that sit next to `price.py`. Both take the **FashionCLIP vector
the backend already computes** for a scanned or listed piece. Neither needs a GPU
or a new model download.

| Engine | File | Artifact | What it returns |
|---|---|---|---|
| Label check | `src/phase4/label_check.py` | `models/checkpoints/brand_probe.joblib` (31 KB) | claimed brand, brands seen in the photo, price ratio, `action = "ask_label_photo"` or `None` |
| Condition hint | `src/phase4/condition_hint.py` | `models/checkpoints/condition_hint.joblib` (6 KB) | "looks new" score, percentile, `action = "confirm_condition"` or `None` |

Settings live in `mappings/label_check.csv`, the same pattern as `price_model.csv`.

## Copy into the repo (feature branch, never main)

```
git checkout -b feature/label-check
# copy src/phase4/*.py, mappings/label_check.csv, models/checkpoints/*.joblib, tests/
python -m pytest tests/test_label_check.py -q        # 6 passed
```

Retrain from the repo's own data (same results as the report):

```
python src/phase4/train_label_check.py   --emb <ta_fc.csv> --text <tayara_text.csv>
python src/phase4/train_condition_hint.py --emb <ta_fc.csv> --text <tayara_text.csv>
```

## Use

```python
from label_check import make_label_check
from condition_hint import make_condition_hint

label_check = make_label_check()        # None if the artifact is missing -> 503
condition_hint = make_condition_hint()

r = label_check.check(vector, title, description,
                      asking_price=price, estimate_median=estimate["median"])
if r["action"] == "ask_label_photo":
    show(r["message"])   # "This ad names Adidas. A photo that shows the label or logo clearly helps buyers trust it."

h = condition_hint.hint(vector)
if h["action"] == "confirm_condition":
    show(h["message"])   # "The photo suggests this piece may have been worn. Please check the condition you selected."
```

Where it fits:
- **Seller adds a listing:** run both. Show the label prompt before publishing; the condition hint stays in the API only (sellers have no condition selector).
- **Buyer sees a listing:** do NOT show anything about authenticity to buyers. The prompt goes to the seller only.

## Rules that must not change without new evidence

1. **Never say "fake", "counterfeit" or "not authentic".** The tests enforce it.
   There is no ground truth for fakes, so no verdict can be validated.
2. **Both signals are required** (`require_both = 1`): the photo does not support
   the claimed brand AND the price is under half the estimate. On 562 branded
   Tayara ads that fires on 7 (1.2%). With either signal alone it would fire on
   20%, which is too many prompts for honest sellers.
3. The condition hint **never sets the condition**. The seller chooses; the hint
   only asks them to double-check.

## Numbers (all grouped 5-fold CV, tuned inside training folds)

**Brand from the photo** (484 ads, 15 brands with at least 8 ads)
- top-1 **70%** (±2% across fold assignments), top-3 **89%**
- chance (always Nike) 34%; garment type alone 40%
- inside shoes only: 69% vs 44% for "most common shoe brand"
- stable whatever the duplicate grouping (cosine 0.92 to exact): 68–71%
- weakest brands: Bershka, Levi's, Mango (8–10 ads each, 20–25%)

**Label check signals** (562 branded ads)
- price under half the estimate: 10.9% (non-branded ads: 20.8%)
- claimed brand not in the photo's top 3: 12.2%
- both: 7 ads (1.2%). They co-occur no more than chance would give (7 vs 6.2),
  so there is no evidence yet that the pair catches anything specific. Only
  confirmed fakes could show that.
- misspelled brand names ("Abibas"-style) are almost absent from these ads
  (one "jordon", one "pumax"), so no spelling rule was added.

**Condition hint** (750 real ads with a condition in the text)
- new vs used (like-new left out): AUC **0.69** [0.65, 0.76]
- new/like-new vs good/used/defect: AUC **0.63** [0.60, 0.71]
- holds inside categories: shoes 0.67, bags 0.66, dresses 0.72; t-shirts and "other" at chance
- not a catalog-photo shortcut: 0.66 on ads whose photo appears nowhere else
- lowest 10% of scores: 33% worn vs 15% overall (×2.3)
- for comparison, YOLO trained on synthetic stains: AUC 0.53 on real ads
- **stains and tears are not detected**: only 10 real ads describe one

## A label fix found on the way

`tayara_condition_labels.csv` on disk is older than `condition_analysis.py`: 78 ads
have a stale grade, and 21 of its 28 "defect" ads are not defects (most say
"aucun défaut", no defect). The current code grades them correctly, and the shipped factors
(new with tags ×1.43 on 212 ads, like new ×1.20 on 232) match the current code.
Re-run `condition_analysis.py` to refresh the CSV, so nobody trains on the old file.

## The analysis scripts

`analysis/` holds the scripts behind every number above:
- `brand_probe.py`: grouped brand test
- `label_check_rates.py`: signal rates
- `condition_probe.py`: condition test
- `kaggle_style_test.py`: shows the public Kaggle "fake brand" labels can be
  predicted from photo style alone (AUC 0.84)

Their input paths point at the analysis folder; change `FC` at the top.
