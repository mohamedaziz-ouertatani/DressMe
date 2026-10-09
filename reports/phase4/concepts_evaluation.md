# Concept probes: evaluation

Made by `src/phase4/evaluate_concepts.py`. The Similar page shows the concepts the picture model (FashionCLIP) associates with two pieces (`mappings/style_concepts.csv`, REVIEW). For concepts that match an existing label, AUC = how well the concept's score separates test pictures with that label from the others (15,471 test pictures of Fashion Product and PolyVore; only pictures whose field is known count). 0.5 = chance, 1 = perfect.

| concept | label | pictures | with the label | AUC |
|---|---|---:|---:|---:|
| formal | `usage=formal` | 3,543 | 225 | 0.875 |
| sporty | `usage=sport` | 3,543 | 377 | 0.857 |
| casual | `usage=casual` | 3,543 | 2,938 | 0.586 |
| denim | `sub_category=jeans` | 7,817 | 62 | 0.992 |
| knit | `sub_category=sweater` | 7,817 | 27 | 0.986 |
| floral | `pattern=floral` | 644 | 11 | 0.607 |
| striped | `pattern=striped` | 644 | 174 | 0.802 |
| checked | `pattern=checked` | 644 | 129 | 0.932 |
| traditional | `category=traditional` | 15,471 | 0 | too few |

Mean AUC over the 8 checkable concepts: 0.830.

Not checkable (no label in the data): streetwear, classic, modest, trendy, party, leather, lace, satin, oversized, fitted, vintage. These are shown in the app as what the picture model associates with a photo, never as facts.

The app ranks concepts above the average picture (`concept_baseline`); that shift is the same for every picture, so it does not change these AUCs.
