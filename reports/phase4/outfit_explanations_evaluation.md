# Outfit explanations: evaluation

Made by `src/phase4/evaluate_outfit_explanations.py`. One piece of each test outfit is replaced by a random test item of the same category; the swap analysis (pool: 30 random test items per category) should name that intruder as the weakest piece.

| dataset | outfits | weakest = intruder | chance | points add up |
|---|---:|---:|---:|---:|
| PolyVore | 500 | 40.0% [35.7, 44.3] | 32.6% | 500 / 500 |
| Fashionpedia | 500 | 31.0% [26.9, 35.1] | 25.3% | 500 / 500 |

Chance = 1 / number of pieces (mean over the outfits). The intruder is random, so it can fit by luck: 100% is not expected. A result well above chance means the swap analysis points at the piece that breaks the outfit.

How to read it: the swap analysis only re-uses the score, so it can point at an intruder only as well as the score itself tells a real outfit from one with a swapped piece (AUC in `reports/phase4/compatibility_evaluation.md`). A modest gain over chance here means the explanation is faithful to the formula, and that the formula's own signal is limited; improving it is a team decision on the weights and rules, not a change to the explanation.
