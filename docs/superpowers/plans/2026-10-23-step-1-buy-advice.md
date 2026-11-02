# Step 1: "Should I buy this?" (plan)

Goal: the verdict gains a **price**, a **confidence**, **reason codes**, a **decision log** and a
proper **save into the wardrobe (Promote)**. Nothing that works today changes.
Facts about the current code: `docs/superpowers/discovery/2026-10-23-codebase-facts.md`.
Safety net: `backend/tests/golden/README.md`.

## Rules (from the brief)

- `compatibility.buy_advice` (and all of `src/phase4/compatibility.py`) does not change.
  Check at the end: `git diff main -- src/phase4/compatibility.py` is empty.
- Responses only **gain** fields. No endpoint, field or type is removed or changed.
- New team-decided numbers live in `mappings/verdict_rules.csv` (every row REVIEW), never in code.
- New logic is in `src/phase4/` as pure functions (data in, data out, no MongoDB); only routes
  touch the database.
- No existing test is weakened or deleted. Golden expected files may only gain keys (a diff proves it).
- Tests run in the container. Everything stays local: no push, no PR.
- If a fact in the code contradicts the design: stop and ask.

## What I found before starting (nothing contradicts the design)

- **Listing prices are already in TND.** A listing stores `price_tnd` (it can be null); the
  sitemap connector converts foreign prices when it collects, with `mappings/currency_rates.csv`
  (`connectors/sitemap.py: to_tnd`), and keeps the original as text in `price_original`. So
  `POST /listings/{id}/candidate` copies `price_tnd` as it is; no conversion in the route.
- **"missing" is defined once**, in `compatibility.wardrobe_insights` (`missing`: `main`, `top`,
  `bottom`, `shoes`). The route calls it and hands the result to `verdict.assess`.
- **The taste vector** is `profile["style_vector"]` (from `compatibility.user_style_profile`, None
  when the wardrobe has fewer than 3 vectors and there is no feedback).
- The candidate's `predicted` entries already carry `unsure`; `corrected` lists what the user fixed.

## Interpretations (the brief leaves room; flag in the PR)

1. `promoted_from` is `null` for uploads (as the brief says), so `kind` is only ever `"candidate"`.
2. `over_budget.share` = price / budget (the part of the budget this piece takes), rounded to 2 decimals.
3. The slot labels in `fills_gap` and `no_pairing_piece` are the labels `wardrobe_insights` already
   uses (`main`, `top`, `bottom`, `shoes`), so the app translates them with words it has.
4. "Usable pieces" = the wardrobe after `compatibility.filter_items(wardrobe, profile, rules)`,
   the same filter `buy_advice` applies.

## Pieces, in order (small commits)

| # | Piece | Files |
|---|---|---|
| 1 | Plan | this file |
| 2 | **Rules + pure module.** `mappings/verdict_rules.csv` (min_wardrobe_items 8, far_from_style_cut chosen from the similarity distribution of the frozen wardrobe, budget_share 0.3; all REVIEW); `src/phase4/verdict.py` (`load_rules`, `assess`); unit tests for each code and confidence rule, missing price, missing budget, no taste vector. | `mappings/verdict_rules.csv`, `src/phase4/verdict.py`, `backend/tests/test_verdict.py` |
| 3 | **Price and budget in the schemas.** `price_tnd` on `BuyAdvice`; `budget_tnd` on `ProfileUpdate` / `profile_out` / TS `User`. | `schemas.py`, `routers/auth.py`, `types.ts` |
| 4 | **`/buy-advice` remembers.** Stores the price on the candidate, calls `assess`, returns `confidence` + `codes`, saves `last_advice` (verdict, good_outfits, codes, confidence, thresholds, price, computed_at). The listing candidate copies the listing's price. | `routers/outfits.py`, `routers/listings.py`, `wardrobe.py` |
| 5 | **Promote.** `backend/app/wardrobe_store.py: promote(...)`; `POST /items` calls it (same response, file, event); from a candidate it reuses the cleaned photo and the stored analysis (no second analysis); `promoted_from`, `analysed_by`; unique partial index on `items.promoted_from.id`; a second promote returns the existing item. | `wardrobe_store.py`, `routers/items.py`, `db.py`, `ml.py` (model names) |
| 6 | **Decision log.** `decisions` collection + unique index; `POST /decisions`, `GET /decisions`; `decision` event; `USER_COLLECTIONS` constant used by account deletion. | `routers/decisions.py`, `db.py`, `events.py`, `routers/admin.py`, `main.py` |
| 7 | **Goldens.** Re-record only to add `confidence` and `codes`; prove every existing value is identical; add golden cases that exercise the codes. README: known issue (a) is fixed. Deletion test also covers decisions. | `backend/tests/golden/...`, `test_deletion_complete.py` |
| 8 | **Frontend.** Price input, confidence badge, code sentences (en/fr/ar), "One piece per photo" tip, "Bought it" / "Left it" through `POST /decisions` (Scan and Shop), nav label and title, TS types. `npm run build` and lint pass. | `frontend/src/...` |
| 9 | PR text. | `docs/superpowers/prs/step-1-buy-advice.md` |

## Acceptance

- Full suite green in the container (the count is reported).
- Golden verdicts, counts and outfits identical; the diff of the expected files shows only added keys.
- `npm run build` and lint pass.
- `git diff main -- src/phase4/compatibility.py` is empty.
- The branch `upgrade/step-1-buy-advice` is not merged into `main`.
