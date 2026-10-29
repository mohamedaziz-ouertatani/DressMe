# Price model — evaluation

Model: `src/phase4/price.py`, fitted by `src/phase4/train_price.py`.
Backbone: FashionCLIP (`patrickjohncyh/fashion-clip`), the same vectors the
backend stores for every item, candidate and listing.

## What the model is

A ridge regression over the 512-number FashionCLIP vector, trained on the log
of the asking price **with each channel's mean removed**. It learns which
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

| | value |
|---|---|
| Spearman, grouped 5-fold CV, both channels | 0.558 |
| typical error, friperie | **×1.53** |
| typical error, classified | ×1.99 |

"Typical error ×1.53" is the geometric mean of how far the estimate is from the
true price, as a ratio either way: the estimate is usually within a factor of
1.53 above or below. The card on the Worth
it? screen quotes the friperie figure because that is what users see; the
pooled figure (×1.94) is inflated by the 5–1800 TND spread of the ads.

### Against the current rule (`backend/app/resale.py`)

`resale.py` takes the median price of the 8 nearest look-alikes of the same
category. Same FashionCLIP vectors, same folds, same held-out items:

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

| trained on | Spearman |
|---|---|
| classified only | 0.333 |
| classified + friperie (shipped) | **0.401** |
| difference | **+0.066** [+0.014, +0.120] |

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

1. The ridge score becomes a rank among the training items.
2. That rank is read off the price distribution of the channel and category
   (`band_low_pct` to `band_high_pct`, 25th to 75th by default).
3. The band is then widened to at least `median ÷ error` to `median × error`,
   using the channel's own typical error.

Step 3 matters for categories whose prices sit close together. Without it, 10
friperie jackets, most priced 40–50 TND, gave a band of "40 to 50 TND" while the
line underneath said the estimate is typically off by ×1.53. For a median of
46 TND the headline now reads "30 to 70 TND", which is what the model actually
knows.

A category with fewer than `min_category_items` (8) priced pieces uses all of
its channel's prices instead, and the card says so. Friperie dresses (4 items)
are the current case. Training also drops categories under 8 items (hard-coded
in `train_price.py`), so lowering `min_category_items` in the csv brings
dresses back only after retraining.

## Limits

- **A hint, not a valuation.** Typical error ×1.53 on friperie.
- **Asking prices**, not sale prices.
- **Classified clothing has one price curve** for tops, bottoms, dresses and
  outerwear: the ads only separate clothing, shoes and bags.
- **No user has judged the estimates.** Every number here is measured against
  listed prices.
