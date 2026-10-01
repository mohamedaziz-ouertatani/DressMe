# Colour estimation (PolyVore, Fashionpedia)

Model: gradient boosting on Lab colour histograms, trained on Fashion Product images (train split) with their real colour labels. Script: `src/estimate_colours.py`.

## Accuracy on Fashion Product (val + test, unseen images)

- All predictions: **64.0%** on 7095 images.

| minimum confidence | colour filled | accuracy |
|---:|---:|---:|
| 0.0 | 100% | 64.0% |
| 0.4 | 87% | 69.1% |
| 0.5 | 74% | 73.4% |
| 0.6 ← used | 61% | 78.8% |
| 0.7 | 49% | 82.5% |

Accuracy per true colour (confidence ≥ 0.6):

| colour | images | accuracy |
|---|---:|---:|
| black | 1133 | 84% |
| blue | 512 | 77% |
| white | 502 | 74% |
| brown | 353 | 85% |
| red | 282 | 79% |
| grey | 247 | 64% |
| green | 246 | 85% |
| pink | 191 | 82% |
| purple | 183 | 89% |
| navy | 161 | 65% |
| silver | 146 | 75% |
| yellow | 119 | 92% |
| gold | 61 | 75% |
| orange | 56 | 73% |
| beige | 49 | 37% |
| olive | 37 | 78% |
| burgundy | 30 | 67% |
| cream | 25 | 64% |
| teal | 11 | 55% |
| khaki | 9 | 67% |
| multicolour | 9 | 22% |

Fashion Product photos are tiny (60x80) and often show a model, so these numbers are a rough guide. PolyVore (product shots on white) should be similar; Fashionpedia (street photos, shadows) is probably lower: check the grids below.

## PolyVore

- Colour filled for **64.0%** of the 125910 items with pixels (confidence ≥ 0.6).
- Top colours: black 24.7%, blue 8.8%, white 8.5%, brown 8.1%, beige 6.3%, pink 6.1%, red 6.0%, gold 4.4%, grey 3.7%, green 3.5%

![PolyVore check](figures/colour/check_polyvore.png)

## Fashionpedia

- Colour filled for **62.7%** of the 104238 items with pixels (confidence ≥ 0.6).
- Top colours: black 25.1%, brown 15.2%, blue 10.5%, white 9.7%, navy 9.2%, purple 5.5%, red 5.5%, pink 4.0%, beige 2.7%, grey 2.7%

![Fashionpedia check](figures/colour/check_fashionpedia.png)
