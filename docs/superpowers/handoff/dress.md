# Hand-off: Dress (steps 2 and 2b)

Skeleton, not a finished feature: the data model, the API contracts and the screens are final; the
logic behind them is a first version, marked `TODO(step 2)` in the code
(`grep -rn "TODO(step 2)" backend src frontend/src`).

## 1. Branch and plan

Step 2 (labels, wear log): `upgrade/step-2-dress-skeleton`, plan
`docs/superpowers/plans/2026-10-23-step-2-dress-skeleton.md`. Step 2b (the Dress page):
`upgrade/step-2b-dress-page`, plan `docs/superpowers/plans/2026-10-23-step-2b-dress-page.md`. Local, not pushed.
Click-through: `docs/superpowers/manual-checks/step-2.md`.

What did NOT change: `src/phase4/compatibility.py` and the scoring (the same outfits come back in the same
order), `GET /outfits/suggest` is still a JSON list, no field was removed or retyped, the `/wear` contract.

## 2. What exists

### Endpoints

**`GET /outfits/today?occasion=everyday&shuffle=0`** (optional `lat`, `lon`, rounded like `/weather`)

```json
{ "date": "2026-10-23", "occasion": "everyday", "season": "mid-season",
  "weather": { "temp_c": 22, "condition": "clear", "season": "mid-season" },
  "outfits": [ { "score": 82.9, "parts": {"style": 0.84, "colour": 0.93, "pattern": 1.0, "structure": 1.0},
                 "reasons": [], "items": [ "..." ],
                 "contributions": [ "..." ],
                 "explanations": [ {"code": "style_coherent", "part": "style", "sign": "+", "params": {}},
                                   {"code": "fits_context", "part": "context", "sign": "+",
                                    "params": {"occasion": "everyday", "temp_c": 22}} ],
                 "label": "safe", "confidence": "medium",
                 "confidence_reasons": [ {"code": "guessed_field", "params": {"item_id": "6540...a1", "field": "colour"}} ] } ],
  "missing": [] }
```

- `occasion` is a chip of `mappings/dress_occasions.csv` (else 422). The seed is a sha256 of (user, today's
  date in Tunis, chip, `shuffle`): the same day gives the same outfits, `shuffle + 1` gives others.
- Candidates are `ranked_suggestions` (the function `GET /outfits/suggest` also uses, 20 outfits per usage value of
  the chip, merged), with the season from the weather, else the calendar. Beach = outfits around a swimsuit, in summer.
- `outfits`: up to 3, labelled, chosen by `dress.pick_three`. `weather` is null when the weather is off or
  unreachable (`season` then comes from the calendar). `missing` (the labels of `wardrobe_insights`) only when
  `outfits` is empty.

**`POST /outfits/build`** `{ "item_ids": ["..."], "occasion": null, "shuffle": 0 }`: 404 if a piece is not the
user's. Answer: `{ "occasion", "outfits": [... + "pick"], "notes": [...], "used_item_ids": [...] }`.
A piece that clashes with an earlier one (same sub_category, or a category over its limit) replaces it and a
note `{"code": "clash_swapped", "params": {"dropped": id, "kept": id}}` says so. If the pieces already make a
complete outfit (main piece + shoes) it comes first with `"pick": true`. The others are completions
(`compatibility.complete_outfit`, extended piece by piece until the outfit is complete), labelled, chosen with
`pick_three`: up to 3 in total.

**`GET /outfits/occasions`**: `[{"chip": "everyday", "main": true}, ...]`, in the team's order.

**`GET /outfits/suggest`, `POST /outfits/score`, `POST /outfits/complete`** keep every key and gain three:
`label` (`safe` | `bolder` | `experimental` | `null` without a taste vector), `confidence` (`high` | `medium` |
`low`) and `confidence_reasons` (`small_wardrobe {owned, minimum}`, `guessed_field {item_id, field}`). The level
is the number of reasons: 0 high, 1 medium, 2 or more low. The chat tools and `/buy-advice` do not carry them.

**`POST /wear`** (201; 200 when the same pieces were already logged today), **`GET /wear?from&to`**,
**`DELETE /wear/{id}`** (204; 409 after the day; 404 for another user's):

```json
{ "item_ids": ["6540...a1", "6540...b2"], "occasion": "casual", "score_shown": 82.9, "label_shown": "safe", "source": "card" }
```

`source` is `card` (the Dress page, For today) or `build` (Build mode). `worn_on` is the date in Africa/Tunis,
computed by the server. Logs a `wear` event.

### Data

- Collection **`wear_log`**: `user_id`, `item_ids`, `worn_on` (`"YYYY-MM-DD"`), `occasion`, `event_name`,
  `score_shown`, `label_shown`, `source`, `created_at`. Index `(user_id, worn_on)`. In `db.USER_COLLECTIONS`.
- `zoneinfo` resolves `Africa/Tunis` in the backend container: no new dependency.

### Code

- `src/phase4/dress.py` (pure): `load_rules`, `load_occasions`, `label_outfits`, `confidence_reasons`,
  `pick_three(outfits, seed, rules, n=3, exclude_keys=(), skip_labels=())`, `context_reasons`, `make_seed`,
  `calendar_season`, `merge_candidates`, `resolve_clashes`, `is_complete`, `complete_fully`, `penalty_active`,
  `recently_worn`, `apply_wear_penalty`.
- `backend/app/routers/dress.py` (the three new routes), `routers/wear.py`, `routers/outfits.py`
  (`ranked_suggestions`, `labelled_outfits`), `wardrobe.py` `outfit_out` (copies the three keys).
- **Recent-wear penalty**, wired but off: with both `wear_penalty_*` above 0, `ranked_suggestions` asks for a longer
  list and `apply_wear_penalty` re-orders it; a score never changes. With the start values (0) nothing happens.

### Screens and components (`frontend/src/`)

- `pages/DressPage.tsx`: `/dress` (For today) and `/dress/build` (Build). `/`, `/today` and `/build` redirect.
  For today: context line ("Everyday · today · 22° and clear", the season when there is no weather), the title
  "Three outfits", the chips (Everyday, Work, University, Outing, and "More" with Eid, Wedding, Beach; the last
  chip is remembered in localStorage), three cards, "New outfits". Empty: what is missing (from the route's
  `missing`, with the `insightsMissing_*` sentences) and an Add button. Without a taste vector: the hint
  "Add a few more pieces so we learn your style" and the cards are titled Outfit 1 / 2 / 3.
  Build: a picker by category, a sticky "Build outfits (n)" above the tab bar, up to 3 cards ("Your pick" first),
  "New outfits", and a short note for a clash.
- `ui/OutfitCard.tsx`: the shared card (label tint, confidence as five dots and a word, a photo collage with
  main pieces large and accessories small, two reasons at most, "Wear this" = `ui/WearButton.tsx`, ✦ details).
  `ui/DetailsSheet.tsx`: the sheet (score and points, why the confidence, weakest piece and swap from
  `/outfits/explain`, all reasons, like / dislike, Try it on). `ui/dress.tsx`: pill button, pill chip, switch.
- `OutfitStrip` stays for the verdict's best outfits (Scan, Shop). `TodayPage.tsx` and `BuildPage.tsx` are gone.
  The nav has one item, Dress (Shops moved into the phone tab bar).
- **Design tokens:** one `@theme` block "The Dress look" in `index.css` holds every colour, radius and spacing of
  the new look (`--color-label-safe`, `--radius-card`, `--spacing-card` ...), used as Tailwind utilities
  (`bg-label-safe`, `rounded-card`, `p-card`). To give the whole app this look, change those values and use the
  same utilities in the other pages (they are not restyled yet).
- Types: `api/types.ts` (`OutfitLabel`, `Outfit.label` / `confidence` / `confidence_reasons` / `pick`,
  `TodayOutfits`, `BuildResult`, `OccasionChip`, `WearEntry`); client: `api.outfitsToday`, `api.buildOutfits`,
  `api.occasions`, `api.wear`, `api.wearList`, `api.unwear`.

## 3. What is placeholder

| Where | What is simplified |
|---|---|
| `dress.py` `pick_three` | One outfit per label, a seeded draw among the `pick_pool` best, no weighting by score, no memory of earlier days. |
| `dress.py` `load_occasions` / `mappings/dress_occasions.csv` | A first mapping from a chip to usage values (university = everyday). |
| `dress.py` `context_reasons` | One fixed sentence: right for <occasion> at <temp>. |
| `dress.py` `label_for` | One similarity and two cuts; no per-piece label. |
| `dress.py` `confidence_reasons` | Small wardrobe + every unsure label; no weighting. |
| `dress.py` `apply_wear_penalty`, `routers/outfits.py` | Flat points per piece, values 0 (off). |
| `routers/wear.py` | No history screen (step 5); `occasion` is the chip's usage, `event_name` is never asked; `GET /wear` stops at 500. |
| `ui/WearButton.tsx` | One `GET /wear` per card shown. |
| `routers/dress.py` build | Completions are greedy; no season filter in Build; the chip is not sent from the Build mode. |

## 4. REVIEW rules

`mappings/dress_rules.csv`: `safe_cut` 0.892, `bolder_cut` 0.777 (an outfit's similarity to the taste vector; each cut sits
in the middle of the largest gap between values shown by the frozen wardrobe, so all three labels appear),
`min_wardrobe_items` 8 (fewer usable pieces = a lowering reason), `wear_penalty_days` 0, `wear_penalty_points` 0,
`pick_pool` 3. `mappings/dress_occasions.csv`: everyday casual; work work|formal; university casual;
outing casual|formal (the four main chips); eid eid; wedding wedding; beach (mode beach) under "More".
All REVIEW: the team decides, the data only measures them.

## 5. Tests

In the container (PowerShell; in Git Bash put `MSYS_NO_PATHCONV=1` in front):

```
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_wear.py tests/test_dress_page.py tests/test_golden.py
```

Expected: 405 passed, 3 skipped. `test_wear.py`: the `/wear` contract. `test_dress_page.py`: `/outfits/today`
(stable for a day and a shuffle, one outfit per label when the candidates allow it) and `/outfits/build` (the
chosen piece in every outfit, 404 for another user's, a pick, a clash note). Goldens: a second frozen wardrobe
(`wardrobe_men.json`, a man) records the men's and the beach `/outfits/suggest`; the existing outfit goldens
gained only `label`, `confidence` and `confidence_reasons` (all 22 outfit confidences are `high`; the
`medium` / `low` in the buy-advice goldens are the verdict's own). Frontend: `npm run build && npm run lint`;
no frontend tests: use `manual-checks/step-2.md`.

## 6. Suggested next tasks

1. Pick the numbers of section 4 on real wardrobes (most outfits of the frozen wardrobe are "safe": the cuts decide
   how often the other two labels show), then turn the penalty on.
2. A better `pick_three` (weigh by score, rotate pieces across days with the wear log, let the user pin one).
3. A richer context reason (what in the outfit fits the weather, the rain chance) and a real occasion mapping.
4. The wear history screen with the Wardrobe view (step 5); ask `occasion` / `event_name` there.
5. Load today's entries once per page; send the chip from Build; a season filter in Build.
6. Apply the Dress look (tokens) to the other pages, and review the new French and Arabic sentences with a native speaker.
