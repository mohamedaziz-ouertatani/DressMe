# Colour estimation (PolyVore, Fashionpedia)

Model: gradient boosting on Lab colour histograms, trained on Fashion Product images (train split) with their real colour labels. Script: `src/estimate_colours.py`.

## Accuracy on Fashion Product (val + test, unseen images)

- All predictions: **64.5%** on 7100 images.

| minimum confidence | colour filled | accuracy |
|---:|---:|---:|
| 0.0 | 100% | 64.5% |
| 0.4 | 87% | 69.5% |
| 0.5 | 75% | 74.1% |
| 0.6 | 62% | 79.1% |
| 0.7 ← used | 49% | 83.1% |

Accuracy per true colour (confidence ≥ 0.7):

| colour | images | accuracy |
|---|---:|---:|
| black | 946 | 88% |
| blue | 422 | 82% |
| white | 369 | 79% |
| brown | 268 | 88% |
| red | 253 | 85% |
| green | 224 | 88% |
| grey | 180 | 64% |
| pink | 157 | 85% |
| purple | 149 | 96% |
| navy | 116 | 68% |
| yellow | 107 | 96% |
| silver | 105 | 76% |
| orange | 50 | 78% |
| gold | 44 | 75% |
| olive | 32 | 84% |
| burgundy | 26 | 65% |
| beige | 23 | 35% |
| cream | 19 | 53% |
| teal | 9 | 56% |
| multicolour | 4 | 0% |
| khaki | 2 | 100% |

Fashion Product photos are tiny (60x80) and often show a model, so these numbers are a rough guide. PolyVore (product shots on white) should be similar; Fashionpedia (street photos, shadows) is probably lower: check the grids below.

## PolyVore

- Colour filled for **52.3%** of the 125910 items with pixels (confidence ≥ 0.7).
- Top colours: black 26.4%, white 9.3%, blue 9.0%, brown 7.0%, pink 6.7%, red 6.6%, beige 5.3%, gold 3.9%, green 3.8%, yellow 3.7%

![PolyVore check](figures/colour/check_polyvore.png)

## Fashionpedia

- Colour filled for **49.4%** of the 104301 items with pixels (confidence ≥ 0.7).
- Top colours: black 24.8%, brown 15.6%, white 10.9%, navy 10.5%, blue 9.6%, red 5.9%, purple 5.5%, pink 4.0%, green 2.4%, yellow 2.2%

![Fashionpedia check](figures/colour/check_fashionpedia.png)
