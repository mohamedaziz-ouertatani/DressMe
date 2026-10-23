# Step 1: "Should I buy this?" gains a price, a confidence, reason codes, a decision log and a proper save

Branch `upgrade/step-1-buy-advice`, from `main` at `b2dbc2e` (step 0, the safety net). Not merged, not pushed.
Plan: `docs/superpowers/plans/2026-10-23-step-1-buy-advice.md`.

## Summary

The verdict itself does not change. `compatibility.buy_advice` is untouched
(`git diff main -- src/phase4/compatibility.py` is empty) and every golden verdict, outfit count,
outfit, score and reason is identical. Around it:

- **Price.** `POST /buy-advice` accepts an optional `price_tnd` (> 0; missing = null, never 0) and
  stores it on the scan. A listing scan copies the listing's price.
- **Confidence and reason codes.** The answer gains `confidence` (high / medium / low) and `codes`.
  `src/phase4/verdict.py` (`assess`, pure) makes them. Three codes lower the confidence:
  `small_wardrobe`, `no_pairing_piece`, `guessed_field`. Three only inform: `fills_gap`,
  `far_from_style`, `over_budget`. The numbers are the team's, in `mappings/verdict_rules.csv`
  (every row REVIEW).
- **Remember what was shown.** The scan keeps a `last_advice` snapshot (verdict, good outfits, codes,
  confidence, the thresholds used, price, time).
- **Promote.** `backend/app/wardrobe_store.py: promote` is now the only place an item is saved. `POST /items`
  calls it (same answer, photo file and event). From a scan it reuses the cleaned photo, the labels, the
  model's guesses, the corrections and the vector: **no second analysis**. New item fields
  `promoted_from` and `analysed_by`; a unique partial index makes a scan an item only once.
- **Decision log.** `POST /decisions` ("bought" / "left") and `GET /decisions`; collection `decisions`
  (labels, a copy of `last_advice`, the item made, never the photo).
- **Screens.** Scan and Shop show the confidence badge and the codes (en / fr / ar) and have
  "Bought it" / "Left it". Scan also has an optional price field and the tip "One piece per photo".
  The old "re-upload + PATCH" path is gone. The nav label is "Should I buy this?".
- **Profile.** Optional `budget_tnd` (backend only; no screen yet).

## Rules kept

| Rule | How it is shown |
|---|---|
| `compatibility.buy_advice` does not change | `git diff main -- src/phase4/compatibility.py` is empty; the only file added under `src/` is `verdict.py` |
| Responses only gain fields | the 4 existing verdict goldens differ by exactly 2 added lines each (`confidence`, `codes`); `/admin/stats` gains a `decision` key; `/me` gains `budget_tnd` |
| Team numbers in a CSV, REVIEW | `mappings/verdict_rules.csv` (`min_wardrobe_items` 8, `far_from_style_cut` 0.5, `budget_share` 0.3) |
| Pure logic in `src/phase4/`, DB only in routes | `verdict.py` takes data and returns data; the routes read and write MongoDB |
| No existing test weakened or deleted | two existing test files changed, both only strengthened or re-worded (see below) |
| Golden files change only by added keys | numbers below |

## Golden diff (against `main`)

```
buy_advice_near_twin.json   +2 -0     "confidence": "high", "codes": []
buy_advice_think.json       +2 -0     (same two lines)
buy_advice_buy.json         +2 -0     (same two lines)
buy_advice_listing.json     +2 -0     (same two lines, inside "advice")
insights.json, outfits_suggest.json, outfits_score.json, outfits_complete.json   not touched
wardrobe.json               +66 -0    a fourth scan, "far_style" (nothing else moved)
buy_advice_codes_*.json     5 new files (one answer per reason code)
```

`confidence` and `codes` sit right after `reasons` in the answer, so the diff is pure added lines.
The four existing scans all come out `high` with no code, which is why `tests/test_golden_codes.py`
adds cases built from parts of the same frozen data (a 5-piece wardrobe, tops and shoes only, a flagged
guess plus a price over budget, a piece far from the style).

## Changes to existing tests

- `test_deletion_complete.py`: `decisions` is now required to hold data before the deletion, and the user
  leaves two decisions behind. It passed unchanged first.
- `test_golden.py`: only the docstring of `test_known_issue_bought_it_reanalyses_the_photo`
  (the issue is fixed in the app; the test body is untouched).

## Test counts (in the backend container)

| | Passed | Skipped | Failed |
|---|---|---|---|
| `main` (step 0) | 318 | 3 | 0 |
| This branch | **401** | 3 | 0 |

83 new tests: `test_verdict.py` 36, `test_verdict_routes.py` 18, `test_promote_decisions.py` 24,
`test_golden_codes.py` 5. `npm run build` and `npm run lint` pass (one older warning in `BuildPage.tsx`).
I also ran the real models once on a second backend with a throwaway database: the full flow works, and
`analysed_by` records the real model files.

## How to run

```
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q            # everything (~5 min)
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_verdict.py tests/test_promote_decisions.py
cd frontend && npm run build && npm run lint
```

(In Git Bash put `MSYS_NO_PATHCONV=1` in front of `docker exec`.) The live backend needs
`docker compose restart backend` to serve the new routes (no auto-reload).

## Choices the brief left open (please confirm or change)

1. `promoted_from` is `null` for uploads, as written, so its `kind` is only ever `"candidate"`.
2. `over_budget.share` is price / budget (the part of the budget the piece takes), rounded to 2 decimals.
3. The slot names in `fills_gap` and `no_pairing_piece` are the ones `wardrobe_insights` already uses
   (`top`, `bottom`, `main`, `shoes`).
4. "Usable pieces" are the wardrobe after the user's modesty / season / occasion filters, the same filter
   `buy_advice` applies.
5. `no_pairing_piece` takes `buy_advice`'s own answer as the truth: no outfit with the piece in it (and the
   piece not removed by the user's filters) means nothing could be paired.
6. `far_from_style_cut` = 0.5. On the golden wardrobe the 17 owned pieces have similarity 0.55-0.79 to the taste
   vector (median 0.67) and the 3 scans 0.70-0.74; 3000 other PolyVore pieces have a median of 0.62. 0.50 flags none
   of the owned pieces and about 7% of the others. It only informs and is REVIEW.
7. `price_paid` is accepted with "left" too (it is just stored).
8. A scan promoted to an item logs an `upload` event marked `source: "candidate"`.
9. `analysed_by.models` holds the model file names with the day they were written; it is null for fakes and for listings.

## Things to know

- **Cost.** `/buy-advice` now also runs `wardrobe_insights` (to reuse its definition of "missing"). On the
  17-item golden wardrobe that is about 120-135 ms, against 26-29 ms (or 126 ms for the coat) for `buy_advice`
  itself; `assess` is 5-7 ms. It does not depend on the scan, so it could be cached per wardrobe if it ever matters.
- **Not looked at in a browser.** The screens were type-checked, built and linted, and the API behind them was run
  with the real models, but nobody has clicked through the new Scan / Shop screens. The longer nav label wraps on
  the phone tab bar (the centre button now allows two lines).
- **Arabic and French sentences** for the new codes and buttons are my wording: a native speaker should read them.
- The real-model smoke test used drawn pictures: the photo datasets are not on this PC.

## Files

43 files, +3466 / -68 against `main`. New: `src/phase4/verdict.py`, `mappings/verdict_rules.csv`,
`backend/app/wardrobe_store.py`, `backend/app/routers/decisions.py`, `frontend/src/ui/VerdictExtras.tsx`, four
test files, five golden files. Changed: `schemas.py`, `db.py`, `events.py`, `main.py`, `ml.py`, `wardrobe.py`,
`routers/{admin,auth,items,listings,outfits}.py`, the Scan and Shop pages, the API types and client, the
translations, `CLAUDE.md`, the golden README, the golden generator and `wardrobe.json`.
