# Colour model: accuracy on hand-labelled items

395 items labelled by hand (val / test, crops >= 64 px), compared with the model's best colour.

| dataset | min. confidence | colour kept | accuracy (95% CI) |
|---|---:|---:|---:|
| Fashionpedia | 0.0 | 100% (195) | 52.3% (45–59) |
| Fashionpedia | 0.5 | 78% (153) | 58.8% (51–66) |
| Fashionpedia | 0.6 | 64% (125) | 64.0% (55–72) |
| Fashionpedia | 0.7 | 48% (93) | 68.8% (59–77) |
| PolyVore | 0.0 | 100% (200) | 62.5% (56–69) |
| PolyVore | 0.5 | 78% (156) | 71.2% (64–78) |
| PolyVore | 0.6 | 66% (133) | 72.9% (65–80) |
| PolyVore | 0.7 | 55% (110) | 78.2% (70–85) |

## Most frequent mistakes (true → predicted, all confidences)

- black → brown: 18
- black → navy: 18
- navy → blue: 9
- beige → brown: 7
- white → silver: 5
- beige → gold: 4
- white → grey: 4
- teal → green: 4
- gold → beige: 4
- white → cream: 3