# Golden outputs: the safety net of the upgrade

Goal: prove, after every step of the upgrade, that **nothing that works today was broken**.
A small frozen wardrobe is sent through the real routes, and each answer is compared with the
answer recorded before the upgrade. If something changes, the test says exactly what.

- Tests: `backend/tests/test_golden.py` (read the comment at its top).
- Plan and reasons: `docs/superpowers/plans/2026-10-23-step-0-safety-net.md`.
- No real model runs and no photo is stored: the tests use the usual fakes, with the **real
  FashionCLIP vectors** and the **real classifier predictions** of the frozen pieces.

## The files

| File | What it is |
|---|---|
| `wardrobe.json` | The frozen data. 17 items (the PolyVore pieces `python -m app.seed_demo` uses: 5 tops, 3 bottoms, 2 dresses, 1 jacket, 1 scarf, 3 pairs of shoes, 2 bags), each with its labels, the model's `predicted` answers, `corrected` fields and the vector; 4 scans (candidates: `near_twin`, `think`, `buy`, and `far_style` added in step 1); 1 shop listing; the user (a woman, modesty level 2); the fixed inputs (`scenarios`); and what the generator checked (`checked`). Every item has a fixed id, so ids and their order in the answers are stable. |
| `make_wardrobe.py` | Builds `wardrobe.json` from `data/processed/`. Deterministic (running it twice gives the same bytes). `--search` shows how the scans were found. Run it in the container: `docker exec -w /app/backend dressme-backend-1 python tests/golden/make_wardrobe.py`. |
| `expected/buy_advice_near_twin.json` | `/buy-advice` for a top that looks like one you own (similarity 0.93): **skip**, 0 good outfits, "you already own 1 very similar top". |
| `expected/buy_advice_think.json` | `/buy-advice` for a shirt: **think**, 2 good outfits. |
| `expected/buy_advice_buy.json` | `/buy-advice` for a coat (the wardrobe has one jacket): **buy**, 12 good outfits. |
| `expected/buy_advice_listing.json` | The Shops path: `POST /listings/{id}/candidate`, then `/buy-advice`, for an H&M skirt: **think**, 1 good outfit. (The new candidate's id changes every run and is replaced by `<candidate>`.) |
| `expected/buy_advice_codes_*.json` | Step 1, `tests/test_golden_codes.py`: `/buy-advice` on parts of the same frozen data, so that each confidence and reason code shows in a recorded answer: `small_wardrobe` (5 pieces, the coat gives **think** instead of **buy**, confidence **low**), `no_pairing_piece` (tops and shoes only, **medium**), `fills_gap` (the skirt listing, informs), `guessed_and_over_budget` (a flagged colour guess and a price over 30 % of the budget, **medium**), `far_from_style` (a t-shirt at similarity 0.36, informs). |
| `expected/outfits_suggest.json` | `GET /outfits/suggest` for three fixed inputs: no filter, `season=summer&occasion=casual`, `occasion=formal`. |
| `expected/outfits_score.json` | `POST /outfits/score` for two fixed outfits, and the 422 answer for two tops. |
| `expected/outfits_complete.json` | `POST /outfits/complete` from a top, from a top + a bottom, and from a dress. |
| `expected/insights.json` | `GET /insights` for the whole wardrobe. |

Not covered on purpose: the chat, try-on, weather, listings browsing, the admin pages, outfit
feedback, swimwear / beach outfits (no swimsuit in the wardrobe). The wardrobe is a woman's:
the men's rules (`gender` rows in `mappings/`) are not exercised here.

## How answers are compared

| What | Rule |
|---|---|
| verdict, `good_outfits`, item ids **and their order**, reasons, explanation codes, every string, integer and list length | identical |
| scores and points (0-100) | may differ by 0.5 |
| part values, similarities and other 0-1 values | may differ by 0.005 (the same 0.5 points) |
| model confidences | may differ by 0.01 |
| any other number | identical |

A failure prints the list of differences, for example:

```
2 difference(s) from tests/golden/expected/buy_advice_buy.json (before -> now):
  verdict: "think" -> "buy"
  best[2].parts.colour: 1.02 -> 1.0 (moved 0.02, allowed 0.005)
```

Lists are compared in order everywhere: in three runs in a row no ordering moved, so no list
is compared order-independently.

## Run and record

Run (about 15 s):

```
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_golden.py
```

(PowerShell as it is; in Git Bash put `MSYS_NO_PATHCONV=1` in front.)

Record again (rewrites `expected/*.json` from the current answers):

```
docker exec -e GOLDEN_RECORD=1 dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_golden.py
```

### The rule

**Goldens are re-recorded only in a pull request that explains why each difference is intended.**
Re-record, then read `git diff backend/tests/golden/expected/`: every changed line must be
something the step meant to change, and the PR text says why. A difference nobody can explain is
a bug, not a new golden. Never re-record to make a red test green.

## What the answers depend on

- The code under test: `src/phase4/compatibility.py`, `explain_outfit.py`, the routes.
- **The team's rule files `mappings/*.csv`** (weights, colour harmony, pattern mixing, structure,
  sub-category pairing, item seasons, `xai_settings.csv`). Changing a weight changes the goldens
  on purpose; the diff shows how far. The test reloads the real files first, so a test that
  edited the formula earlier cannot leak into it.
- `wardrobe.json`. Not the models, not the database content, not the time.

## Why the verdicts cannot flip by accident

`make_wardrobe.py` refuses to write the file unless, for every fixed input:

- no outfit that decides a verdict scores within **1 point of the good-outfit line (60)**, or of
  the near-miss line (55), or within 1 point of the owned piece it is compared with, and no twin
  similarity is within 0.003 of the 0.9 cut;
- no two scores of a ranked list are closer than 0.15, so an order never depends on a tie.

For the three scans and the listing, the distance of the closest outfit to the good line is
recorded in `wardrobe.json` (`checked.candidates`); the scores of the other fixed inputs are in
`checked.scenario_scores`.

## Known, expected-to-change behaviour

Two tests document behaviour that is **known and expected to change** in a later step. They pass
today; the step that changes the behaviour updates them in its own pull request.

| Test | Today | Changed by |
|---|---|---|
| `test_known_issue_bought_it_reanalyses_the_photo` | **(a) Fixed in step 1.** "Bought it" used to upload the original photo again with `POST /items`: cleaned and analysed a second time, a new id, the scan left to expire, an extra `upload` in the log. The Scan page and the Shop page now call `POST /decisions`, which saves the scan with `promote` (the scan's cleaned photo, labels, guesses and vector, no second analysis; `tests/test_promote_decisions.py::test_bought_it_reuses_the_scan_and_never_analyses_again`). The test stays as it was: it still shows what uploading the same photo again does, which is what an upload is. | Step 1 |
| `test_known_issue_incomplete_outfit_scores_high` | `POST /outfits/score` rates a top + shoes outfit (no bottom) **86.0**, above the good-outfit line, because a part that cannot be computed is left out and the other weights are rescaled. `suggest` and `buy-advice` never build such outfits. | A later step on the formula, if the team decides |

## History of the expected files

| Step | What changed in `expected/` |
|---|---|
| 0 | Recorded. |
| 1 | `buy_advice_near_twin|think|buy|listing.json` gained two keys, `confidence` and `codes` (+2 lines each, no line removed or changed). The 4 other files did not change. New: `buy_advice_codes_*.json`. `wardrobe.json` gained a fourth scan (`far_style`); nothing else in it changed. |
