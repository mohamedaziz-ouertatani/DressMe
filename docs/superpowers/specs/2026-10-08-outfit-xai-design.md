# Outfit score + buy advice XAI — design (XAI sub-project 2 of 4)

Date: 2026-10-08. Status: approved in chat, waiting for spec review.

## Context

Sub-project 1 (item labels, PR #49) explains what the models see in one item.
This sub-project explains the two answers built on top of it: the outfit score
(`compatibility.score_outfit`, 0-100 from four weighted parts) and the
"should I buy this?" verdict (`compatibility.buy_advice`). Sub-project 3 covers
similarity + chat, sub-project 4 the jury report + Admin > Explainability.

Today:
- `score_outfit` returns `score`, `parts` (style, colour, pattern, structure,
  each 0-1 or None) and `reasons`, which only name problems ("X and Y clash",
  "no shoes"). An 82-point outfit has no explanation.
- `parts` reaches the API (`outfit_out`) but the app never shows it;
  `OutfitStrip` shows only `reasons`, translated by regex patterns (`i18n.reason`).
- `buy_advice` returns the verdict, the count of good outfits, the best 3 and a
  near-twin sentence; it does not say what the new piece beats or why the
  verdict is what it is.

## Goals

Outfit score:
1. **Points per part**: exact, signed share of each part in the score.
2. **Strengths too**: positive reasons next to the problems.
3. **Swaps**: for each piece, the best replacement from the wardrobe and its gain
   (the weakest piece = the biggest gain).
4. **Pair map**: style / colour / pattern score of every pair of pieces.

Buy advice:
5. **What it beats**: per good outfit, the owned piece it beats and by how much.
6. **Path to verdict**: good outfits vs the team's thresholds.
7. **Near twins shown**: the owned near twins as items (picture + similarity).
8. **What would change it**: outfits missing for the next verdict, near misses,
   and the owned pieces that beat it most often.

Offline: measure whether "weakest piece" finds a piece that does not belong.

## Non-goals

- Chat explanations (sub-project 3); the chat tools keep their output.
- Admin page / jury report (sub-project 4).
- Changing any weight or rule (the team's), or what `score_outfit` returns.

## Design

### 1. Structured explanations (new shape, old `reasons` kept)

Every explanation line is a dict:
`{"code": "colour_pair", "part": "colour", "sign": "+" | "-", "params": {...}}`.
The app has one template per code in en / fr / ar; `reasons` (English strings)
stays unchanged because the chat agents and `i18n.reason` read it.

Codes (params in brackets):

| part | sign | code | when |
|---|---|---|---|
| style | + | `style_coherent` | coherence ≥ `strength_style` |
| style | - | `style_mixed` | coherence < 0.3 (today's reason) |
| style | - | `style_unlike_you` | user fit < 0.3 (today's reason) |
| colour | + | `colour_pair` [a, b] | best pair score ≥ `strength_colour_pair` and no pair < 0.5 |
| colour | + | `colour_neutral_base` [n] | ≥ 2 neutral items and no clash |
| colour | - | `colour_clash` [a, b] | worst pair < 0.5 (today's reason) |
| colour | - | `colour_too_bold` [colours] | too many bold colours (today's reason) |
| pattern | + | `pattern_one_bold` [pattern] | exactly one non-solid clothing pattern |
| pattern | + | `pattern_calm` | all clothing patterns solid (≥ 2 known) |
| pattern | - | `pattern_clash` [a, b] | worst pair < 0.5 (today's reason) |
| structure | + | `structure_complete` | structure part = 1 |
| structure | - | `structure_no_shoes`, `structure_incomplete` [missing], `structure_full_and_bottom`, `structure_over_limit` [category, n], `structure_pair` [a, b] | today's reasons |

The strength thresholds are new team rows in `mappings/xai_settings.csv`
(REVIEW): `strength_style` = 0.7, `strength_colour_pair` = 0.8.

The part functions in `compatibility.py` keep their logic and now return
`(value, reasons, problems)`: `problems` are the "-" lines, built next to the
English reason they mirror (they already know the worst pair, the bold
colours...), so both come from one place. Only `score_outfit` calls them.
`score_outfit` adds `problems` to its result (one more key; nothing else
changes). Strengths are computed by `explain_outfit.strengths(...)` from the
same pair tables. `outfit_out` sends `explanations` = strengths + problems.

### 2. `src/phase4/explain_outfit.py` (new, pure functions)

- `contributions(result, weights) -> list` per part:
  `{"part", "points", "max_points", "weight", "value", "counted": bool, "why_not": str | None}`.
  points = 100 · w · value / Σw(counted); max_points = 100 · w / Σw(counted).
  Points are rounded to 0.1 with largest-remainder so they add up exactly to
  `result["score"]`. A part not counted has `why_not`: `no_vectors` (style),
  `no_colours`, `no_patterns`, or `weight_zero`.
- `strengths(items, parts, rules, settings)` -> the "+" lines of the table above (`settings` = `explain.load_settings()`).
- `swaps(items, wardrobe, rules, style_profile=None) -> list` per piece:
  `{"item_id", "best_swap_id" | None, "gain": float}` — every wardrobe item of
  the same category not already in the outfit, kept only if `clashes()` is
  empty, scored with `score_outfit`; gain = best score − current (≤ 0 → no swap).
  `weakest` = the piece with the largest positive gain.
- `pair_map(items, rules) -> list` of `{"a", "b", "style", "colour", "pattern"}`:
  style = the pair's rescaled FashionCLIP similarity (same `style_low/high`),
  colour = `rules.colour_score`, pattern = pattern pair score when both are
  clothes with a confident pattern; None when unknown.
- `buy_explanation(candidate, wardrobe, advice_detail, rules) -> dict` (section 3).

### 3. Buy advice

`compatibility.buy_advice` keeps its result and adds `detail` (computed in the
same loop, no extra scoring except what is noted):
- `beats`: per good outfit `{"outfit_index", "owned_id", "owned_score", "margin"}`
  (the best owned item of the same category in that outfit, or none owned).
- `lost_to`: per outfit ≥ `good_outfit` where an owned piece did as well or
  better: the owned piece's id. Grouped by `buy_explanation` into
  "your navy top beats it in 3 outfits".
- `near_misses`: outfits scoring in [`good_outfit` − `near_miss`, `good_outfit`)
  where the candidate would beat what you own; `near_miss` = 5 points, team row
  in `xai_settings.csv` (REVIEW).
- `twins`: `[{"id", "similarity"}]` (today only their count reaches the user).

`buy_explanation` turns it into:
`{"path": {"good": n, "buy_min": .., "think_min": .., "verdict": ..},
  "beats": [...], "lost_to": [{"owned_id", "outfits": n}], "near_misses": n,
  "to_next_verdict": k | None, "twins": [...]}`
(`to_next_verdict` = good outfits still missing for the next better verdict).

### 4. API

- Every outfit answer (`outfit_out`: score / suggest / complete / buy-advice
  best) gains `contributions` and `explanations`.
- `POST /outfits/explain {item_ids, candidate_id?}` → `{"swaps", "weakest", "pair_map"}`;
  swaps come from the user's own wardrobe (same profile filters as suggest);
  items of another user answer 404 like `/outfits/score`; a clash answers 422.
- `POST /buy-advice` gains `explanation` (section 3), with twins and owned items
  as `item_out`-style short items (id, category, sub_category, colour, image_url).

### 5. App

- `OutfitStrip`: a stacked points bar (4 segments, one per part, with the lost
  part greyed) under the score stamp, then strengths ("+") and problems ("−")
  rendered from codes. Today's reasons list is replaced by the coded lines.
- "Why this score?" expander (Build, Today): loads `/outfits/explain`; shows the
  weakest piece with its swap ("swap the shirt for your white tee: +7"), and on
  Build an "Apply swap" button; and the pair map as a small table.
- Scan and Shop: "Why this verdict?" section: the path ("3 good outfits; Buy
  needs 5"), what it beats per outfit, the owned pieces that beat it, near
  misses, and the near twins with pictures.
- en / fr / ar strings for every code.

### 6. Offline evaluation

`src/phase4/evaluate_outfit_explanations.py` →
`reports/phase4/outfit_explanations_evaluation.md`: on the clean PolyVore and
Fashionpedia test outfits (same data as `evaluate_compatibility.py`), replace
one piece by a random item of the same category; the swap analysis (candidates =
the outfit's own category pool from the test split) should name the intruder as
the weakest piece. Reported: top-1 accuracy vs chance (1 / pieces), per dataset.
Also checks that contributions add up to the score on every outfit.

### 7. Tests

- `contributions`: sums to the score, rescaling when a part is None, weight 0.
- each strength / problem code on small hand-made outfits; English reasons unchanged.
- `swaps`: never proposes a clash, gain sign, weakest piece.
- `pair_map` values and Nones.
- `buy_advice` detail: beats / lost_to / near_misses / twins on a fake wardrobe.
- API: new fields, `/outfits/explain` privacy (404), clash (422); fakes as today.

### 8. Documentation

`CLAUDE.md` Phase 4 item 7 (XAI) gets sub-project 2.

## Open questions for the team

- `strength_style`, `strength_colour_pair`, `near_miss` in `mappings/xai_settings.csv` (REVIEW).
