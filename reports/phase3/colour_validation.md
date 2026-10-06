# Colour model: accuracy on hand-labelled items

395 items labelled by hand (val / test, crops >= 64 px), compared with the model's best colour.

| dataset | min. confidence | colour kept | accuracy (95% CI) |
|---|---:|---:|---:|
| Fashionpedia | 0.0 | 100% (195) | 49.7% (43–57) |
| Fashionpedia | 0.5 | 78% (153) | 56.9% (49–64) |
| Fashionpedia | 0.6 | 64% (124) | 61.3% (52–69) |
| Fashionpedia | 0.7 | 44% (85) | 65.9% (55–75) |
| PolyVore | 0.0 | 100% (200) | 63.0% (56–69) |
| PolyVore | 0.5 | 80% (159) | 71.7% (64–78) |
| PolyVore | 0.6 | 66% (133) | 74.4% (66–81) |
| PolyVore | 0.7 | 52% (103) | 76.7% (68–84) |

## Most frequent mistakes (true → predicted, all confidences)

- black → navy: 20
- black → brown: 19
- navy → blue: 8
- beige → brown: 6
- white → silver: 4
- white → grey: 4
- teal → green: 4
- orange → pink: 3
- khaki → pink: 3
- grey → navy: 3