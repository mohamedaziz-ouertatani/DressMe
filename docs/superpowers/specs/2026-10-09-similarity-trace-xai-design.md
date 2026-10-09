# Similarity + chat trace XAI — design (XAI sub-project 3 of 4)

Date: 2026-10-09. Status: implemented. Branch `xai-similarity`, on `xai-agent`
(PR #51, which now holds the chat engine v2 of PR #52).

## Goals

1. **Shared attributes** under each look-alike of `/similar`: what the two pieces
   have in common or not (category, type, colour, pattern), from stored labels
   only; a missing label is left out, never guessed.
2. **Concept probes**: what FashionCLIP associates with each picture, from a
   team-owned list of short texts (`mappings/style_concepts.csv`, REVIEW):
   "both read as streetwear and denim", and a contrast ("this one reads formal,
   yours sporty"). Shown as the picture model's associations, not facts.
3. **Chat answer trace**: under each chat answer, "How I answered": which agent
   and how it was chosen (model or keywords), and every tool call with short
   arguments and a one-line result.
4. Offline check that the probes read the vectors: for concepts that match an
   existing label, how well the concept score separates items with that label
   from the others (AUC, chance 0.5).

Not in scope: similarity bands (not chosen), the jury report (sub-project 4).

## Design

### `src/phase4/explain_similarity.py` (pure functions)

- `load_concepts(path)` → rows `{concept, prompt, group, check}` from
  `mappings/style_concepts.csv` (`concept,prompt,group,check,note`; ~20 rows,
  groups style / material / fit / other; `check` like `usage=formal`,
  `sub_category=jeans`, `pattern=floral`, or empty).
- `shared_attributes(a, b)` → `{"shared": [{"field", "value"}], "differs": [{"field", "a", "b"}]}`
  over category, sub_category, colour, pattern; a field empty on either side is skipped.
- `top_concepts(vector, concept_vectors, k=3)` → the k concepts with the highest
  similarity to the picture vector.
- `concept_overlap(va, vb, concept_vectors, k=3)` →
  `{"both": [...], "contrast": {"a": c1, "b": c2} | None}`: `both` = shared top-k
  concepts; contrast when a's top concept ranks in b's bottom half and b's top
  concept in a's bottom half.
- `explain_pair(a, b, va, vb, concept_vectors)` → `{**shared_attributes, **concept_overlap}`.

### Backend

- `Analyzer.concept_vectors()` → `{concept: unit vector}`, computed once with
  `fashionclip.embed_texts` from the CSV prompts (cached); the fake returns
  fixed random vectors.
- `Catalog.vector(item_id)` (dataset or H&M index), `ListingIndex.vector(db, id)`.
- `/similar`: every hit in `wardrobe`, `catalog`, `shop`, `listings` gets `why`
  (`explain_pair` against the query item). Vectors never leave the server.
- Explainer tool `explain_similarity(item_id, other_id)`: two of the user's
  pieces (or `last_scan`): similarity, shared / differs, concepts.

### Chat trace

- `agents/common.py`: the tool wrapper also appends to a `trace` list:
  `{"tool", "args", "result"}`; `args` = the call's arguments with every string
  cut to 60 characters and lists to 6 entries; `result` = one line:
  `error: …` / `score 71.9` / `verdict buy` / `8 items` / `keys: a, b, c`.
  Contacts are never recorded (the tools already never return them).
- `routers/chat.py`: `trace` and `routed_by` stored with the model message and
  returned by `/chat` and the history.
- Chat page: "How I answered" expander (agent + chosen by model / keywords,
  then one line per tool call). en / fr / ar.

### App

Similar page: chips under each look-alike: "same type · same colour · other
pattern" and "both: streetwear, denim" (en / fr / ar), with a one-line note
that concepts are what the picture model associates.

### Offline check

`src/phase4/evaluate_concepts.py` → `reports/phase4/concepts_evaluation.md`:
per concept with a `check`, AUC of the concept score (vector · text vector) for
items with that label vs without, on a test-split sample of Fashion Product /
PolyVore vectors; concepts without a label are listed as not checkable.

## Tests

`shared_attributes` with missing fields; `top_concepts` / `concept_overlap`
with hand-made vectors; `/similar` hits carry `why` (fakes); the Explainer tool
(privacy); the trace (arguments cut, one-line results, stored and returned by
`/chat` with the fake engine).

## Changes while building

- Concepts are ranked above the average picture (`concept_baseline`: dot product of each concept with
  the dataset's mean vector, `Catalog.mean_vector`). Without it, generic prompts ("trendy") topped
  nearly every piece on the real data.
- `explain_similarity` compares "my two X" (same description for both, exactly two matches); numbers and
  ordinals in descriptions are ignored. Found with `qwen3:4b-instruct`, which passed "pink jacket 1/2".
- `frontend/vite.config.ts` reads `DRESSME_API` (default `http://127.0.0.1:8000`), to check a second
  API copy in the browser.
- No separate plan document: the work followed the existing agent / route patterns, task by task with tests.
