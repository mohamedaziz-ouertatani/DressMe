# Step 3b: search the user's own pieces (words or a photo)

Branch `upgrade/step-3b-search`, from local `main` (`1119603`). Local only, nothing pushed.
Facts: `docs/superpowers/discovery/2026-10-25-step3-facts.md` section D. Baseline after 3a: 302 collected, 299 passed, 3 skipped.

**Goal:** one search function over the user's own wardrobe, used by the Wardrobe search box now and by the chat tool
`search_wardrobe` in 3d ("one function, two callers"). Words or a photo go through FashionCLIP into the same 512-number
space as the stored vectors of the pieces, and the best matches come back. No chat model is involved. Words and
photos get different cuts ("close" or not), set by a calibration run, so the app can say honestly "Nothing close".

## Part 0: read-only checks (done before any code)

| # | Question | Finding |
|---|---|---|
| 1 | Checkpoint; is the text encoder there? | `patrickjohncyh/fashion-clip`, a full `CLIPModel` (`ml.py:45`): the text encoder (63 M parameters) and the image encoder (87 M) are both in the object the backend already loads. **No extra loading, memory or start-up time.** `Analyzer.concept_vectors` already calls the text side. On this PC (CPU, float32): the whole model is +271 MB of process memory and loads in 9 s with a warm cache; one query is encoded in about **11 ms**. |
| 2 | Owned vectors | Field `items.vector`, BSON binary, **float16, 512 numbers, unit length** (norms 1.0000 to 1.0001). Dev DB: 9 of 9 items have one (0 without). `db.vector_from_bson` turns it into float32; `wardrobe()` (`routers/outfits.py:33`) loads `db.items.find({"user_id": ...})`; `near_twins` and `/similar` read the same way. Reused as is. |
| 3 | Photo path | `routers/items.py` `read_photo` = open (EXIF turn, 1024 px) + `remover.mask` + `on_white`: it returns a cleaned PIL image and **saves nothing**; the save happens later in `promote`. The vector then comes from `fashionclip.embed_images`. Measured on this PC (CPU): cleaning about 2.3 s, encoder about 0.05 s. The container is the CPU build. |
| 4 | Calibration data | The images are **not** on this PC (`data/raw/` is absent), but `data/processed/embeddings/fashionclip.npy` holds precomputed vectors for 306,636 pictures (`fashionclip_ids.csv`: `id`), and `dressme.csv` has `split` (train / val / test), `sub_category`, `primary_colour`, `colour_source`, `pattern`, `duplicate`. So the calibration can run. Colours are true labels only for Fashion Product (`colour_source = label`: 3,402 usable val rows and 3,548 test rows; PolyVore and Fashionpedia colours are our own estimates). |
| 5 | Label translations | `frontend/src/i18n/vocab.ts` (en / fr / ar for categories, sub-categories, colours, patterns). No CSV holds them. They seed `mappings/search_terms.csv`. |
| 6 | Test fakes | `FakeAnalyzer.analyze` returns `fake_vector(sum(rgb))` (a unit float32 vector from a seed; "all fairly similar"). It has no text or image encoder method: I add `embed_text` and `embed_image` the same way, so a photo of the same colour finds the same item at similarity 1.0. |

Nothing contradicts the design. Two small deviations, both flagged in the report: the calibration table is written to
`reports/phase4/search_calibration.csv` (the repo keeps reports per phase), and the calibration pool is Fashion Product
only (its colours are real labels, so "right" is not a guess).

## Design (as decided)

- `src/phase4/search.py`, pure (no MongoDB, no model): `normalise_query(text, terms)` and `rank_owned(query_vec, items, cut, limit)`,
  plus the two CSV loaders.
- `mappings/search_rules.csv` (`name,value,note`): `text_cut`, `photo_cut`, `target_precision` 0.9, `wardrobe_size` 30,
  `default_limit` 8, `closest_anyway` 3. `mappings/search_terms.csv` (`term,lang,en,note`): fr and ar words to English.
- `POST /search` (multipart): exactly one of `text` or `photo`; only the user's items are loaded; a photo is cleaned and
  encoded like "add item" but **nothing is saved**; event `search` with mode, count, nothing_close and milliseconds,
  never the query or the photo.
- `src/phase4/calibrate_search.py`: fake wardrobes of 30 pieces from the validation split, about 300 queries per mode,
  30 % with no right piece; the lowest cut with precision >= 0.9 on validation; reported on test.
- Frontend: a shared `SearchBox` (words, camera, results, "Nothing close", "Closest anyway"), the item card extracted
  from the Wardrobe grid so both use it; on the Wardrobe page and on the Assistant placeholder.

## Commits (small, in this order)

1. plan (this file)
2. `search.py`, the two CSVs (start cuts), unit tests of the logic
3. backend: `Analyzer.embed_text / embed_image`, `POST /search`, event type, fakes, contract tests
4. calibration script, its run, the cuts written into `search_rules.csv`, `reports/phase4/search_calibration.csv`
5. frontend: ItemCard, SearchBox, types, API call, Wardrobe + Assistant, words in en / fr / ar
6. docs: manual check, learning note, CLAUDE.md, README

## Verification

`docker compose up -d --build backend`, wait about a minute, run the suite in the container; `npm run build`, `npm run lint`;
goldens unchanged (`git diff` on `backend/tests/golden` is empty); median of 5 text and 5 photo searches on the golden wardrobe;
the pages checked in a headless browser at 390 px in en / fr / ar; fast-forward into local `main`.
