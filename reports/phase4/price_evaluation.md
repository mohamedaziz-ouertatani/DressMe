# Price model — evaluation

Model: `src/phase4/price.py`, fitted by `src/phase4/train_price.py`.
Backbone: FashionCLIP (`patrickjohncyh/fashion-clip`), the same vectors the
backend stores for every item, candidate and listing.

## What the model is

An RBF-kernel SVR (`StandardScaler` + `SVR(kernel="rbf", gamma="scale")`) over
the 512-number FashionCLIP vector, trained on the log of the asking price
**with each channel's mean removed**. Until 1 Nov 2026 it was a ridge
regression; section "Model benchmark" explains the change. It learns which
garments are expensive *within* a market. The dinar level comes back
afterwards: the model's score is turned into a rank, and that rank is read off
the price distribution of the channel and category being priced.

`estimate()` always returns a band, never a single price, and returns `None`
for a channel it has no reference prices for. A caller that gets `None` shows
nothing rather than a guess.

## Data

| corpus | items | source | prices |
|---|---|---|---|
| classified | 1,523 | tayara.tn ads, "everyday" clothing, shoes, bags | asking price, TND |
| friperie | 183 | 23 Tunisian Instagram resale accounts, read from screenshots | asking price, TND |

Before this, the project had no priced second-hand data: `dressme.csv` and
`hm.csv` carry no price.

**These are asking prices, not sale prices.** An asking price is an upper bound
on what a garment fetched. Every number below inherits that.

Near-duplicate listings (cosine ≥ 0.99, mostly relisted items) are kept inside
one cross-validation fold, so a relisted garment can never be in both the
training and the test part.

## The two channels are different markets

| garment group | classified median | friperie median | ratio |
|---|---|---|---|
| shoes | 150 TND | 35 TND | 4.3× |
| bags / accessories | 90 TND | 35 TND | 2.6× |
| clothing | 70 TND | 25 TND | 2.8× |

The fitted channel offset is **×3.69**. A model trained on classified ads and
read in dinars would overprice everything a friperie shopper looks at by about
three times. That is why the level comes from each channel's own prices.

## Results

### Accuracy

| | SVR (shipped) | ridge (before) |
|---|---|---|
| Spearman, grouped 5-fold CV, both channels | **0.589** | 0.558 |
| typical error, friperie (served; the card) | **×1.42** | ×1.51 |
| typical error, classified (served) | **×1.90** | ×2.14 |
| friperie, mean of 5 fold assignments | ×1.44 | ×1.51 |
| *earlier measure, kept for the record:* friperie / classified | ×1.50 / ×1.94 | ×1.53 / ×1.99 |

"Typical error ×1.42" is the geometric mean of how far the estimate is from the
true price, as a ratio either way: the estimate is usually within a factor of
1.42 above or below. The card on the Worth
it? screen quotes the friperie figure because that is what users see; the
pooled figure (×1.84, ×2.06 with the ridge) is inflated by the 5–1800 TND
spread of the ads.

**What "typical error" measures (since 1 Nov 2026).** It is the error of what
`estimate()` serves. For each held-out item of the grouped CV, the model's score
is ranked among the training fold's scores, and that rank is read off the
training fold's prices of the item's own channel and category (the whole channel
below `min_category_items`). The result is rounded like the app rounds it, and
compared with the asking price. This is the same path the benchmark's "served
(rank map)" row measures. `train_price.py` stores it as
`error_factor_by_channel`, and the card and the band widening use it.

The earlier measure ranked every item within its channel and read it off the
whole channel's prices. It used no category curve and no training-fold split
of the prices. That is the ×1.53 the ridge used to show. It is kept in the
artifact's meta as `rank_map_error_factor_by_channel`. On the ads the two
measures differ more (×1.90 served against ×1.94), because the classified curves
are coarse (clothing / shoes / bags).

The first five numbers come from one fold assignment, which is what
`train_price.py` stores. Over five assignments the friperie served error
averages ×1.44 (from ×1.42 to ×1.44).

### Against the current rule (`backend/app/resale.py`)

`resale.py` takes the median price of the 8 nearest look-alikes of the same
category. Same FashionCLIP vectors, same folds, same held-out items:

Measured with the ridge, before the switch:

| corpus | k-NN median (`resale.py`) | trained ridge | ridge − k-NN, mean \|log error\| |
|---|---|---|---|
| classified | 0.507 | **0.585** | **−0.032** [−0.051, −0.012] |
| friperie | 0.239 | **0.408** | −0.021 [−0.049, +0.007] |

On the ads the ridge is better and the interval excludes zero. On friperie it
ranks much better but the error interval includes zero: 183 items cannot
settle it.

This compares the **method**. `resale.py` in the app prices against the
`listings` collection, which this evaluation does not use.

### Training on both channels helps friperie

Predicting friperie garments:

| trained on | SVR | ridge |
|---|---|---|
| classified only | 0.319 | 0.333 |
| classified + friperie (shipped) | **0.448** | 0.401 |
| difference | **+0.128** [+0.049, +0.208] | +0.066 [+0.014, +0.120] |

## Model benchmark

On 1 Nov 2026 the ridge was compared with ten other models. The scripts are in
`src/phase4/benchmark/` and the results in `reports/phase4/benchmark/` (with a
README listing the inputs). The protocol is the shipped one: the same vectors,
the same demeaned target, the same pooled training, and a grouped 5-fold CV
with near-duplicates kept in one fold, repeated over 3 fold assignments.
Every hyperparameter is tuned by an inner grouped CV inside the training fold.

### Main table (FashionCLIP)

Δ is the change in mean |log error| against the ridge, with a 95% bootstrap
interval over items. Negative is better.

| model | friperie Spearman | friperie error | Δ friperie | classified Spearman | classified error | Δ classified |
|---|---|---|---|---|---|---|
| no image: global mean | −0.08 | ×1.46 | | −0.04 | ×2.13 | |
| no image: category mean | 0.21 | ×1.44 | | 0.31 | ×2.02 | |
| ridge (was shipped) | 0.40 | ×1.50 | | 0.57 | ×1.84 | |
| lasso | 0.41 | ×1.48 | −0.015 [−0.040, +0.008] | 0.55 | ×1.86 | +0.014 (worse) |
| PCA + ridge | 0.41 | ×1.50 | 0.000 | 0.57 | ×1.84 | +0.001 |
| ridge + category one-hot | 0.37 | ×1.50 | −0.002 | 0.58 | ×1.83 | −0.003 [−0.004, −0.002] |
| k-NN (cosine) | 0.37 | ×1.48 | −0.013 [−0.056, +0.031] | 0.53 | ×1.87 | +0.017 (worse) |
| **SVR (RBF)** | **0.42** | **×1.46** | **−0.027 [−0.049, −0.007]** | **0.60** | **×1.79** | **−0.023 [−0.032, −0.014]** |
| random forest | 0.45 | ×1.44 | −0.040 [−0.077, −0.005] | 0.56 | ×1.88 | +0.022 (worse) |
| LightGBM | 0.37 | ×1.49 | −0.005 | 0.58 | ×1.82 | −0.007 [−0.017, +0.002] |
| MLP (1×256) | 0.31 | ×1.62 | +0.076 (worse) | 0.53 | ×1.89 | +0.027 (worse) |

These are raw errors after adding the channel mean back, not after the rank
map. That is why the ridge row reads ×1.50 and not ×1.53.

The SVR is the only model better than the ridge on **both** channels with both
intervals clear of zero. The random forest is better on friperie but worse on
the ads. Its predictions also spread far less than the true prices (standard
deviation 0.19 against 0.49 on friperie), so a lot of its friperie gain comes
from predicting close to the mean. On OpenAI CLIP vectors the SVR is again the
best on the ads (0.60) but not significantly better on friperie, so FashionCLIP
stays.

### Where the gain comes from: the kernel, not the loss

The SVR changes two things at once: an RBF kernel instead of a linear model,
and a robust (epsilon-insensitive) loss instead of the squared loss. The 2×2
below separates them (`diagnostics.csv`, 3 fold assignments):

| | linear | RBF kernel |
|---|---|---|
| **squared loss** | ridge: 0.40 / ×1.50 · 0.57 / ×1.84 | kernel ridge: **0.45 / ×1.45 · 0.60 / ×1.80** |
| **robust loss** | linear SVR: 0.38 / ×1.50 · 0.56 / ×1.85 (Huber: 0.37 / ×1.52) | SVR: **0.43 / ×1.46 · 0.60 / ×1.80** |

Each cell is the friperie Spearman / error, then the classified Spearman / error.
Changing the loss with a linear model gains nothing. Adding the kernel gains
with either loss. The SVR was kept over the kernel ridge because the two score
about the same here, and the benchmark tuned and calibrated the SVR.

### Parameter choices

- **gamma = "scale"** (1 / (512 × the input variance), sklearn's default): it
  was not tuned. The inputs are standardised first.
- **C**: the curve flattens from C = 3 (C = 10 and C = 100 give the same model).
  C = 0.1 has a lower friperie error (×1.43), but it gets there by shrinking:
  its predictions spread only 0.18 against 0.49 for the true prices, and the
  ads get worse (×1.92). C = 1 and C = 3 are in the shipped grid.
- **epsilon**: the benchmark tried 0.1 and 0.3 and always picked 0.1. The
  shipped grid is {0.05, 0.1, 0.2}. The training data picks 0.05 in every fold,
  and C = 3 (C = 1 in 2 of 5 folds).
- **Ridge alpha, for comparison**: alpha = 10,000 lowers the friperie error
  in the same way C = 0.1 does, by shrinking (prediction spread 0.21), and it
  costs ranking on the ads. RidgeCV picks about 1,000.
- The choice is made by the training data each time (inner grouped 3-fold CV,
  mean absolute error), never by the test fold.

### At the dinar level: against no image

`benchmark_calibration.py` compares the served path (rank map) with a price
that ignores the photo: the median price of the item's channel and category.
Mean of 5 fold assignments:

| friperie | Spearman | typical error | Δ vs category median |
|---|---|---|---|
| category median (no image) | 0.16 | ×1.45 | |
| ridge, served | 0.38 | ×1.50 | +0.035 [−0.007, +0.078] |
| SVR, served | 0.38 | **×1.44** | −0.010 [−0.036, +0.015] |

| classified | Spearman | typical error | Δ vs category median |
|---|---|---|---|
| category median (no image) | 0.33 | ×2.02 | |
| ridge, served | 0.57 | ×2.13 | +0.054 [+0.020, +0.086] (worse) |
| SVR, served | 0.58 | **×1.90** | **−0.062 [−0.087, −0.036]** |

This is the honest limit. On friperie the photo more than doubles the ranking,
but in dinars no model beats "the usual price of this category" by more than
noise yet: 183 items cannot show it. The ridge was slightly behind that
baseline, and the SVR is level with it or a little ahead. On the ads the SVR is
the first served model that clearly beats the no-image price. The ridge's rank
map lost to it.

### Decision

Ship the RBF SVR (`train_price.py --model svr`, the default). It is better on
both channels in ranking and in error. The gain has a mechanism (the kernel)
that the 2×2 confirms. It no longer falls behind the no-image price on either
channel. The costs:

| | ridge | SVR |
|---|---|---|
| artifact size | 40 KB | 6.4 MB (the support vectors) |
| `estimate()` per item (backend running) | about 0.15 ms | about 1.3 ms |
| scikit-learn version | any (plain numbers) | must match the version that trained it: train in the backend container |

`--model ridge` still trains the earlier model, and an artifact written before
the change (no `kind`) still loads as the ridge.

### Effect on the Shops tag

The listing tag (`price_tag`, `tag_factor` 2) on the 183 friperie items at
their own asking price, from grouped-CV estimates (mean of 5 fold
assignments):

| | good deal | above the usual price |
|---|---|---|
| ridge | 6.7% | 9.3% |
| SVR | 6.8% | **3.9%** |

"Above the usual price" fires less than half as often. With the SVR, a
friperie item at a normal price is rarely flagged as dear.

Moving the card to the served error (×1.50 to ×1.42) changes nothing here. The
tag is measured from the band's median, and the error factor only widens the
band's edges. Re-measured after the change: the same 6.6% / 2.7% on the
stored fold assignment.

## Things tested and not changed

### FashionCLIP against OpenAI CLIP

The work started on `openai/clip-vit-base-patch32`. Both models give 512
numbers, so mixing their vectors raises no error and returns a believable,
meaningless price. Everything was re-measured on FashionCLIP:

| | OpenAI CLIP | FashionCLIP | |
|---|---|---|---|
| classified Spearman | 0.564 ± 0.005 | **0.577 ± 0.007** | wins 15 of 15 fold assignments |
| classified → friperie | 0.357 | 0.333 | [−0.120, +0.073]: no real difference |
| same brand in the 10 nearest | 0.515 | **0.636** | +0.121 [+0.030, +0.242] |

### Photo background

The backend cuts every uploaded photo out onto white before embedding it
(`backend/app/background.py`); the training photos keep their backgrounds. The
183 friperie photos were run through `background.py` unchanged and compared:

| | value |
|---|---|
| ranking cost of serving cut-outs to a model trained on raw photos | −0.041 [−0.134, +0.055] |

The interval includes zero, so the model is trained on photos as they are. The
interval is wide: a cost up to −0.13 is not ruled out.

### One model per garment group

Separate models for clothing / shoes / bags, against the single model, over 10
random fold assignments:

| channel | group | items | single | separate | wins |
|---|---|---|---|---|---|
| classified | bags | 277 | 0.531 | 0.590 | 10/10 |
| classified | shoes | 665 | 0.465 | 0.511 | 10/10 |
| classified | clothing | 581 | 0.448 | 0.409 | 0/10 |
| friperie | clothing | 140 | 0.325 | 0.405 | 10/10 |
| friperie | bags | 27 | 0.682 | 0.435 | too few items |
| friperie | shoes | 16 | 0.019 | −0.256 | too few items |

Separate models win three cells and lose three. Choosing a model per cell after
seeing these scores would fit the choice to the test data, so the single model
is kept. Worth revisiting with more friperie data, deciding the rule first.

## How the band is built

1. The model's score becomes a rank among the training items.
2. That rank is read off the price distribution of the channel and category
   (`band_low_pct` to `band_high_pct`, 25th to 75th by default).
3. The band is then widened to at least `median ÷ error` to `median × error`,
   using the channel's own typical error.

Step 3 matters for categories whose prices sit close together. Without it, 10
friperie jackets, most priced 40–50 TND, gave a band of "40 to 50 TND" while the
line underneath said the estimate is typically off by ×1.53 (the ridge; ×1.42 now). For a median of
46 TND the headline now reads "30 to 70 TND", which is what the model actually
knows.

A category with fewer than `min_category_items` (8) priced pieces uses all of
its channel's prices instead, and the card says so. Friperie dresses (4 items)
are the current case. Training reads the same setting and leaves out smaller
categories, so lowering `min_category_items` brings dresses back only after
retraining.

## Limits

- **A hint, not a valuation.** Typical error ×1.42 on friperie, and not
  clearly better than the category's usual price in dinars (see "At the dinar
  level").
- **Asking prices**, not sale prices.
- **Classified clothing has one price curve** for tops, bottoms, dresses and
  outerwear: the ads only separate clothing, shoes and bags.
- **No user has judged the estimates.** Every number here is measured against
  listed prices.
