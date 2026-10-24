# Step 2: the Dress skeleton (plan)

Branch `upgrade/step-2-dress-skeleton`, from `main`. A skeleton for a teammate's feature: final data model
and API contracts, simple first-version logic, wired screens (en / fr / ar), a hand-off. Not tuned.
Nothing is pushed.

## What does not change
- `src/phase4/compatibility.py` and the outfit scoring: the same outfits come back in the same order,
  `GET /outfits/suggest` stays a JSON list. Responses only gain fields.
- Goldens: the existing expected files may only gain keys (`label`, `confidence`); proven with a diff.

## Order of work (one small commit each)
1. **Goldens first, alone** (done): a second frozen wardrobe (`wardrobe_men.json`, a man, 14 pieces incl. a
   swimsuit) and `outfits_suggest_men.json` (the men's `/outfits/suggest` and `?beach=true`), recorded from
   today's behaviour, before any code change. The women's `wardrobe.json` is byte for byte the same.
2. **This plan.**
3. **Rules and pure logic**: `mappings/dress_rules.csv` (all REVIEW) and `src/phase4/dress.py`:
   `load_rules`, `label_outfits`, `tunis_date`, `recently_worn`, `apply_wear_penalty`. Data in, data out.
4. **Wear log**: collection `wear_log` (index `(user_id, worn_on)`, in `USER_COLLECTIONS`), `POST /wear`,
   `GET /wear`, `DELETE /wear/{id}`, event `wear`.
5. **Labels in the outfit routes**: `outfit_out` gains `label` and `confidence` for suggest / score / complete;
   the recent-wear penalty is wired into suggest (both values 0 = nothing changes). Goldens re-recorded and
   the diff shown: added keys only.
6. **Screens**: label chip, low-confidence badge and "I wore this" / "Worn today · Undo" on the outfit card
   (Today and Build); the empty Today screen says what is missing, from `GET /insights`.
7. **Hand-off and manual check list**; full suite; fast-forward `main`.

## Decisions taken in this plan
- **Cuts**: `safe_cut` / `bolder_cut` are chosen from the spread of outfit-to-taste cosine similarity on the
  frozen wardrobes (numbers in the hand-off). The labels use the user's taste vector (the one
  `routers/outfits.py` already builds); no taste vector = `label: null`.
- **Confidence** needs the usable wardrobe size: `label_outfits(outfits, items_by_id, taste_vector, rules)`
  keeps the given signature and takes the size as an optional keyword (`usable`).
- **Recent-wear penalty** without touching `compatibility.py`: the route asks `suggest_outfits` for a longer
  list and `apply_wear_penalty` re-orders it (stable sort on `score - points * worn pieces`), then cuts to `n`.
  The greedy "each piece in at most 2 outfits" rule means the first `n` of the longer list are the same
  outfits as before. With `wear_penalty_days` or `wear_penalty_points` at 0 the step is skipped entirely
  (no query, no re-order). The shown `score` is never changed.
- **`POST /wear` is idempotent for a day**: the same set of pieces on the same Tunis date returns the entry
  already there (200), so a double tap or a reload never doubles the log.
- **Dates**: `worn_on` is the date in `Africa/Tunis`, computed on the server (`zoneinfo`). `DELETE` works only
  on the entry's own day.
- **"Missing" is not redefined**: the empty Today screen calls `GET /insights` and reads `missing`; the
  sentences are the existing `insightsMissing_*` strings.

## Tests (about 3 new)
- The two golden cases (one test, two answers) already added.
- One contract test for `/wear` (POST, GET, DELETE, another user's item = 404, an old entry = 409).
- The existing goldens re-recorded; the diff must show only the added keys.
- No unit tests for the cuts or the confidence rule.
