# Hand-off: Dress (step 2)

Skeleton, not a finished feature: the data model, the API contracts and the screens are final; the
logic behind them is a first version, marked `TODO(step 2)` in the code
(`grep -rn "TODO(step 2)" backend src frontend/src`).

## 1. Branch and plan

Branch `upgrade/step-2-dress-skeleton` (local, not pushed). Plan:
`docs/superpowers/plans/2026-10-23-step-2-dress-skeleton.md`. Manual click-through:
`docs/superpowers/manual-checks/step-2.md`.

What did NOT change: `src/phase4/compatibility.py` and the scoring (the same outfits come back in the same
order), `GET /outfits/suggest` is still a JSON list, and no field was removed or retyped.

## 2. What exists

### Endpoints

**`POST /wear`** (201; 200 when the same pieces were already logged today)

```json
{ "item_ids": ["6540...a1", "6540...b2", "6540...c3"],
  "occasion": "casual", "event_name": null,
  "score_shown": 82.9, "label_shown": "safe", "source": "card" }
```

Only `item_ids` (1 to 10) and `source` (`card` | `build`) are required. Every piece must be the user's
own, otherwise 404 and nothing is written. Answer:

```json
{ "id": "6541...01", "item_ids": ["6540...a1", "6540...b2", "6540...c3"],
  "worn_on": "2026-10-23", "occasion": "casual", "event_name": null,
  "score_shown": 82.9, "label_shown": "safe", "source": "card",
  "created_at": "2026-10-23T20:14:05.123000+00:00" }
```

`worn_on` is the calendar date in **Africa/Tunis**, computed by the server, never sent by the app. The same
set of pieces on the same day is one entry (a double tap or a reload does not double the log). Logs a `wear`
event (`source`, `pieces`), counted in Admin stats.

**`GET /wear?from=2026-10-01&to=2026-10-31`** (both dates optional): the user's entries, newest first
(`worn_on`, then `created_at`), at most 500. Same shape as above, in a list.

**`DELETE /wear/{id}`**: 204. 409 when `worn_on` is not today in Tunis; 404 for an unknown id or another
user's entry.

**`GET /outfits/suggest`, `POST /outfits/score`, `POST /outfits/complete`** keep every key and gain two:

```json
{ "score": 82.9, "parts": {"style": 0.84, "colour": 0.93, "pattern": 1.0, "structure": 1.0},
  "reasons": [], "items": [ "..." ],
  "label": "bolder", "confidence": "high" }
```

- `label`: `safe` | `bolder` | `experimental`, or `null` when there is no taste vector yet (fewer than 3
  pieces with a picture vector and no outfit feedback).
- `confidence`: `low` when the usable wardrobe has fewer than `min_wardrobe_items` pieces, or a piece of
  the outfit has a label that is still an unsure model guess the user did not correct; otherwise `high`.
- The chat tools and `/buy-advice` do not carry them (they keep their short form).

### Data

- Collection **`wear_log`**: `user_id`, `item_ids` (strings), `worn_on` (`"YYYY-MM-DD"`, Tunis), `occasion`,
  `event_name`, `score_shown`, `label_shown`, `source`, `created_at`. Index `(user_id, worn_on)`. It is in
  `db.USER_COLLECTIONS`, so deleting an account empties it.
- Event type `wear` (`events.EVENT_TYPES`); the admin stats TS type has `wear?: number`.
- `zoneinfo` resolves `Africa/Tunis` in the backend container (system tzdata, and the pinned `tzdata` package
  from `docker/constraints.txt`): no new dependency.

### Code

- `src/phase4/dress.py` (pure, data in / data out): `load_rules`, `tunis_date`, `label_for`,
  `label_outfits(outfits, items_by_id, taste_vector, rules, usable=None)`, `outfit_confidence`,
  `penalty_active`, `recently_worn`, `apply_wear_penalty`.
- `backend/app/routers/wear.py`: the three routes. `backend/app/routers/outfits.py`: `labelled_outfits`
  (adds `label` and `confidence` to the three outfit routes) and the penalty step of `suggest`.
  `backend/app/wardrobe.py` `outfit_out` copies `label` and `confidence` when the result has them.
- **Recent-wear penalty**, wired but off: when both `wear_penalty_*` values are above 0, `suggest` asks
  for a longer list (20), `apply_wear_penalty` re-orders it (`score - points * pieces worn recently`) and
  cuts to `n`. The score shown never changes. With the start values (0) nothing is fetched or re-ordered
  (the goldens prove it).

### Screens and components (`frontend/src/`)

- `ui/OutfitStrip.tsx`: the label chip (Safe / Bolder / Experimental, hidden when `label` is null), the
  quiet "Confidence: low" badge (shown only when low) and, with the `wear` prop, the wear button.
- `ui/WearButton.tsx`: "I wore this" -> `POST /wear` -> "Worn today · Undo" (`DELETE /wear/{id}`). States:
  checking (looks for an entry made earlier today, so a reload still shows it), waiting, done, error with
  retry, and "no longer the same day" when the undo answers 409.
- `pages/TodayPage.tsx` (source `card`, the picked occasion is sent) and `pages/BuildPage.tsx` (source
  `build`). When Today has no outfit it calls the existing `GET /insights` and shows what is missing
  (`insights.missing`, with the existing `insightsMissing_*` sentences) and a link to add pieces.
- Types: `api/types.ts` (`OutfitLabel`, `Outfit.label` / `confidence`, `WearEntry`, `DayStats.wear`); client:
  `api.wear`, `api.wearList`, `api.unwear`.
- No wear history screen: it comes with the Wardrobe view (step 5).

## 3. What is placeholder

| Where | What is simplified |
|---|---|
| `dress.py` `label_for` | One similarity (outfit vs taste vector) and two cuts. No per-piece "bold part", no occasion. |
| `dress.py` `outfit_confidence` | Small wardrobe or one unsure label. No count of unsure labels, no model confidences. |
| `dress.py` `apply_wear_penalty` | A flat number of points per piece worn recently, only to re-order; does not fade with the days, treats every category alike, never changes the shown score. |
| `routers/outfits.py` `suggest` | Penalty values start at 0 (off). |
| `routers/wear.py` | No history screen; the app never asks `occasion` / `event_name`; `GET /wear` stops at 500; one entry per set of pieces and day. |
| `ui/WearButton.tsx` | One `GET /wear` per card shown. |
| `pages/TodayPage.tsx` | The empty message reuses "Your first outfit is three photos away" as its title, whatever is missing. |

## 4. REVIEW rules (`mappings/dress_rules.csv`)

All REVIEW: the team decides; the data only measures them.

| name | start value | meaning |
|---|---|---|
| `safe_cut` | 0.892 | Outfit-to-taste cosine similarity from which an outfit is `safe`. |
| `bolder_cut` | 0.777 | From here to `safe_cut` it is `bolder`; below it, `experimental`. |
| `min_wardrobe_items` | 8 | Fewer usable pieces than this = low confidence (same start value as `verdict_rules.csv`). |
| `wear_penalty_days` | 0 | Pieces worn in the last N days (today included, Tunis time) are penalised. 0 = off. |
| `wear_penalty_points` | 0 | Points (0-100 scale) per such piece when ranking. 0 = off. |

Where the two cuts come from: on the frozen golden wardrobe (17 pieces, 16 usable), the 12 completed
outfits have a similarity of 0.85 to 0.93 (33rd percentile 0.90), and the outfits the goldens show range
from 0.73 to 0.93. Each cut sits in the middle of the largest gap between two shown values (0.888 / 0.896
and 0.763 / 0.791), so no label flips on rounding and all three labels appear. On the man's frozen
wardrobe: 0.94 safe, 0.87 bolder, 0.62 experimental (a lone swimsuit).

## 5. Tests

In the container (PowerShell; in Git Bash put `MSYS_NO_PATHCONV=1` in front):

```
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_wear.py tests/test_golden.py
```

- `tests/test_wear.py`: the `/wear` contract (POST, GET, DELETE, another user's piece or entry = 404, an
  older entry = 409).
- `tests/test_golden.py`: the goldens. Step 2 added a second frozen wardrobe, `wardrobe_men.json` (a man,
  built by `tests/golden/make_wardrobe.py`), and `outfits_suggest_men.json` (his `/outfits/suggest` and
  `?beach=true`), recorded **before** the code change. The existing outfit goldens gained only the keys
  `label` and `confidence` (44 lines added, none removed). Re-record only with `GOLDEN_RECORD=1`, in a pull
  request that explains each difference (`tests/golden/README.md`).
- Frontend: `cd frontend && npm run build && npm run lint` (the one warning in `BuildPage.tsx` is older).
  No frontend tests: use `manual-checks/step-2.md`.

## 6. Suggested next tasks

1. Pick the three numbers of section 4 with the team on real wardrobes, then turn the penalty on (try
   `wear_penalty_days` 3 and `wear_penalty_points` 20 and look at how the suggestions rotate).
2. Decide whether the shown score should include the penalty, and make it fade with the days.
3. The wear history screen, with the Wardrobe view (step 5); ask `occasion` / `event_name` there.
4. Load today's entries once per page instead of once per card.
5. A better confidence rule (count of unsure labels, model confidences) and per-piece labels.
6. Review the French and Arabic sentences of the new strings with a native speaker.
