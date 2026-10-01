# Colour model: accuracy on hand-labelled items

395 items labelled by hand (val / test, crops >= 64 px), compared with the model's best colour.

| dataset | min. confidence | colour kept | accuracy (95% CI) |
|---|---:|---:|---:|
| Fashionpedia | 0.0 | 100% (195) | 54.4% (47–61) |
| Fashionpedia | 0.5 | 76% (148) | 59.5% (51–67) |
| Fashionpedia | 0.6 | 55% (108) | 69.4% (60–77) |
| Fashionpedia | 0.7 | 42% (82) | 75.6% (65–84) |
| PolyVore | 0.0 | 100% (200) | 59.5% (53–66) |
| PolyVore | 0.5 | 74% (147) | 69.4% (62–76) |
| PolyVore | 0.6 | 61% (122) | 77.0% (69–84) |
| PolyVore | 0.7 | 48% (95) | 77.9% (69–85) |

## Most frequent mistakes (true → predicted, all confidences)

- black → navy: 19
- black → brown: 16
- navy → blue: 6
- white → silver: 5
- burgundy → red: 4
- beige → brown: 4
- white → grey: 4
- blue → navy: 4
- teal → green: 4
- khaki → beige: 4