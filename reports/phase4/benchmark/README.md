# Price model benchmark (1 Nov 2026)

Why the price model is an RBF-kernel SVR and not a ridge. The summary and the
decision are in [`../price_evaluation.md`](../price_evaluation.md), section
"Model benchmark". The scripts are in
[`src/phase4/benchmark/`](../../../src/phase4/benchmark/), and the CSVs in this
folder are their results.

## Protocol

It is the same as `src/phase4/train_price.py`. Each garment is one 512-d image
vector, the target is the log asking price with each channel's mean removed,
and the model trains on the 1,523 tayara ads and the 183 friperie items
together. The evaluation is a grouped 5-fold CV, with near-duplicates
(cosine ≥ 0.99) kept in one fold, repeated over several fold assignments.
Hyperparameters are tuned inside each training fold (inner grouped CV) and
never on the test fold.

## Files

| script | what it measures | output here |
|---|---|---|
| `benchmark_models.py` | 11 models on 2 backbones (FashionCLIP, OpenAI CLIP) | `model_benchmark_all.csv` |
| `benchmark_calibration.py` | the served pipeline (rank map) against no-image baselines, ridge | `calibration_benchmark_ridge.csv` |
| `benchmark_calibration.py svr` | the same, with the SVR | `calibration_benchmark_svr.csv` |
| `diagnostics.py` | loss × kernel 2×2, ridge alpha / SVR C / k-NN k curves, prediction spread | `diagnostics.csv` |

Run them from the project root, inside the backend container, which has the
same scikit-learn version as the app:

```bash
docker exec -w /app dressme-backend-1 python src/phase4/benchmark/diagnostics.py
docker exec -w /app dressme-backend-1 python src/phase4/benchmark/benchmark_calibration.py svr
docker exec -w /app dressme-backend-1 python src/phase4/benchmark/benchmark_models.py
```

`benchmark_models.py` needs the OpenAI CLIP files (see below). Pass words to
run only the models whose name contains them, e.g. `benchmark_models.py svr ridge`.
That run writes `model_benchmark_svr_ridge.csv`.

## Inputs (gitignored, in `data/processed/`)

| file | needed by |
|---|---|
| `tayara_fashionclip.csv`, `friperie_fashionclip.csv` | all three scripts (the same files `train_price.py` reads) |
| `tayara_openaiclip.csv`, `friperie_openaiclip.csv` | `benchmark_models.py` only (the OpenAI CLIP rows) |

The two `*_openaiclip.csv` files are **not on the team PC** as of 1 Nov 2026.
`benchmark_models.py` stops and names the missing file. Until they are added,
`model_benchmark_all.csv` is kept as the record of that run. Each file has
the same rows as its FashionCLIP twin, in the same order, with
`openai/clip-vit-base-patch32` vectors in the `e000`-`e511` columns. Ask
Yassine for them.

## Notes

- The bundle shipped only the ridge version of `benchmark_calibration.py`. The
  `svr` argument was added when the scripts moved into the repo. It uses
  `SVR(C=3, epsilon=0.1, gamma="scale")`, the setting the inner CV of
  `benchmark_models.py` picked most often (13 of 15 folds). A re-run on
  1 Nov 2026 gave the same friperie error (served ×1.44, raw ×1.46).
- `price_evaluation.md` quotes these CSVs. `train_price.py` prints its own
  numbers for the shipped model, using one fold assignment and a choice of
  C ∈ {1, 3} and epsilon ∈ {0.05, 0.1, 0.2}.
