# Step 3b, in plain words: searching your own wardrobe

## What was built
A search box on the Wardrobe page (and under the Assistant placeholder). Type words ("black jeans", "pantalon noir",
"جينز أسود") or take a photo: your own pieces come back in order of how much they look like it. It says **Close match**
only when sure enough, and **Nothing close** when not. A photo search saves nothing.

## The path of a query
```
words -> English "a photo of black jeans" -> text vector --+
                                                           +-> compare with each owned piece's vector -> above the cut? -> results
photo -> background removed --------------> photo vector --+       (cosine similarity)                    (close or not)
```

## The files that matter
- `src/phase4/search.py`: the logic, with no database and no model (`normalise_query`, `rank_owned`).
- `backend/app/routers/search.py`: `POST /search`; loads only your pieces; never saves.
- `mappings/search_rules.csv` (the cuts) and `search_terms.csv` (French / Arabic words to English).
- `src/phase4/calibrate_search.py`: measures the cuts. `frontend/src/ui/SearchBox.tsx`: the box.

## Embeddings, cosine similarity, the cut
An **embedding** is a list of 512 numbers FashionCLIP gives to a picture or a sentence; similar things get similar lists.
Every piece you own already has one. **Cosine similarity** says whether two lists point the same way (1 = same, 0 =
unrelated). With 2 numbers: a = (3, 4), b = (4, 3): (3x4 + 4x3) / (5 x 5) = 24/25 = **0.96**; a and c = (-4, 3): (-12 + 12) / 25 =
**0**. Real lists have 512 numbers, same arithmetic. The **cut** is the similarity from which we call a piece "close".

## Words and photos need different cuts
A photo is compared with pictures, so a true match scores high (median 0.76). Words reach pictures through a bridge FashionCLIP
learned, so a true match scores lower (median 0.31). So: **words 0.297, photos 0.823**.

## Set on validation, reported on test
The cut is chosen on the **validation** questions and then measured once on the **test** ones it never saw; judging it on the
questions it was tuned on would be marking my own homework.

| split | mode | cut | queries | precision | in top 5 | honest "nothing" |
|---|---|---|---|---|---|---|
| validation | words | 0.297 | 300 | 0.901 | 0.991 | 0.955 |
| test | words | 0.297 | 300 | 0.872 | 0.995 | 0.910 |
| validation | photo | 0.823 | 300 | 0.907 | 0.973 | 0.988 |
| test | photo | 0.823 | 300 | 0.800 | 0.969 | 0.953 |

Precision = how often the best result shown as close is right (target 0.9). Words get close; photos do not (0.80): with other
random draws the photo cut moves (0.82 to 0.86), and look-alike labels (blue / navy) fool it. The fake wardrobes use catalogue
pictures, so a real wardrobe will be harder.

## Five teacher questions
- **Why not search the labels?** They can be wrong or empty, and a photo has none; vectors compare what pieces look like.
- **Why two cuts?** The two kinds of query score in different ranges.
- **How do you know it shows only your pieces and saves nothing?** The user filter is in the database query; tests check it, that items, scans and files are unchanged after a photo search, and that the log holds no words.
- **Why say "Nothing close"?** A wrong piece shown as a match is worse; with no right piece in the wardrobe, 91-95% of queries said so.
- **Why only 0.80 precision for photos?** Look-alike pieces with another label rank first and the cut cannot tell them apart.

## Left out, and why
- A **multilingual encoder**, **Marqo-FashionCLIP**: they replace FashionCLIP, so every stored vector (and 306,636 catalogue ones) must be recomputed and the app re-measured.
- **Darija**: the word table is French and Modern Standard Arabic; Darija needs a native review.
- A **vector database**: a wardrobe has tens of pieces, so comparing all of them takes microseconds.
