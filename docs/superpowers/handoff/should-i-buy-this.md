# Hand-off: "Should I buy this?" (step 1)

Skeleton, not a finished feature: the data model, the API contracts and the screens are final; the
logic behind them is a first version, marked `TODO(<name>, step 1)` in the code.

## 1. Owner

`<name>`. Step 1 of the upgrade; branch `upgrade/step-1-buy-advice` (local, not pushed).
Plan: `docs/superpowers/plans/2026-10-23-step-1-buy-advice.md`. Manual click-through:
`docs/superpowers/manual-checks/step-1.md`.

## 2. What exists

### Endpoints

`compatibility.buy_advice` is untouched: the verdict (buy / think / skip) is the one the app always gave.
Step 1 adds a price, a confidence, reason codes and a decision log around it.

**`POST /analyze`** (photo) -> a scan (candidate), kept 24 hours. Unchanged.

**`POST /buy-advice`**

```json
{ "candidate_id": "5f0c02000000000000000003",
  "corrections": { "colour": "black" },
  "price_tnd": 89.9 }
```

`corrections` and `price_tnd` are optional. `price_tnd` must be > 0; missing = unknown (never 0).
Answer: the same fields as before, plus `confidence` and `codes`:

```json
{ "verdict": "think", "good_outfits": 2, "reasons": [],
  "confidence": "medium",
  "codes": [ {"code": "guessed_field", "params": {"field": "colour", "conf": 0.62}},
             {"code": "over_budget", "params": {"price": 89.9, "budget": 200.0, "share": 0.45}} ],
  "candidate": { "id": "...", "category": "top", "...": "..." },
  "best": [ { "score": 78.0, "items": ["..."] } ],
  "explanation": { "path": {"...": "..."}, "beats": [], "lost_to": [], "twins": [] } }
```

Codes (`src/phase4/verdict.py`): `small_wardrobe {owned, minimum}`, `no_pairing_piece {slot}`,
`guessed_field {field, conf}` lower the confidence; `fills_gap {slot}`, `far_from_style {similarity}`,
`over_budget {price, budget, share}` only inform. Confidence: `small_wardrobe` = low; otherwise
0 / 1 / 2+ lowering codes = high / medium / low.

The route saves what it showed on the scan as `last_advice` (verdict, good_outfits, codes, confidence,
thresholds, price, computed_at). Nothing is cached: every call recomputes.

**`POST /decisions`**

```json
{ "candidate_id": "5f0c02000000000000000003", "answer": "bought", "price_paid": 79.0 }
```

`answer` is `bought` or `left`; `price_paid` is optional. Answer (201):

```json
{ "id": "...", "candidate_id": "...", "listing_id": null, "answer": "bought",
  "price_tnd": 89.9, "price_paid": 79.0,
  "category": "top", "sub_category": "shirt", "colour": "black", "pattern": "solid",
  "last_advice": { "verdict": "think", "good_outfits": 2, "codes": [], "confidence": "high",
                   "thresholds": {"good_outfit": 60, "buy_min": 3, "think_min": 1},
                   "price_tnd": 89.9, "computed_at": "2026-10-23T18:00:00+00:00" },
  "item_id": "...", "created_at": "2026-10-23T18:00:05+00:00" }
```

| Case | Status |
|---|---|
| first answer | 201 |
| same answer again | 200, the first decision (no second item) |
| another answer for the same scan | 409 |
| no verdict shown yet for this scan | 409 |
| scan expired or not yours | 404 |

`bought` saves the scan into the wardrobe with `wardrobe_store.promote` (reuses the cleaned photo, labels
and vector; no second analysis). `GET /decisions` lists the user's decisions, newest first.

### Data

- `decisions` collection: one per user and scan (unique index). Keeps the labels, a copy of `last_advice`,
  `item_id` when bought, and never the photo. It is in `db.USER_COLLECTIONS`, so account deletion empties it.
- `items.promoted_from` (`{kind: "candidate", id}`, null for an upload) and `items.analysed_by`
  (`{models, at}`): new fields, never back-filled. A unique partial index on `items.promoted_from.id` makes
  a scan an item only once. `GET /items` and `GET /items/{id}` return `promoted_from` only for an item saved from a scan (an upload's answer is unchanged, so the goldens did not move).
- `candidates.price_tnd`, `candidates.last_advice`. A shop-listing candidate copies the listing's price.
- Profile: optional `budget_tnd` (read by `over_budget`).

### Screens and components (`frontend/src/`)

- `ui/VerdictCard.tsx`: **one card for both screens.** Stamp and number of good outfits, confidence badge
  and the codes that lowered it, reasons, "Good to know" codes, Why this verdict?, best outfits, Similar,
  Try it on (`showTryOn`), and Bought it / Left it. The decision block has the states waiting, recorded
  (bought / left; the same answer again also shows as recorded), 409, 404 (offers `restart`), and failed
  (retry). Props: `onDecided` (optional), `restart`.
- `pages/ScanPage.tsx` (route `/scan`, title "Should I buy this?", short nav label `navScanShort` on the
  phone tab bar): photo -> analysing -> field check -> optional price -> verdict. `onDecided` opens the new
  item (bought) or starts a fresh scan (left).
- `pages/ShopPage.tsx` `ListingPage`: same card, price from the listing (shown, not editable), no
  `onDecided`: the card shows what was recorded and the user keeps browsing.
- `pages/WardrobePage.tsx` `ItemPage`: "Added from a scan" when `promoted_from` is set.
- `ui/VerdictExtras.tsx`: `ConfidenceBadge`, `CodeList`. Sentences for the codes: `i18n/explain.ts`
  `verdictCodeLine` (en / fr / ar). Types: `api/types.ts` (`BuyAdvice`, `Decision`, `Item.promoted_from`).

## 3. What is placeholder

| Where | What is simplified |
|---|---|
| `src/phase4/verdict.py` `assess` | The confidence rule (count of lowering codes). A full version could weigh the codes and use how close the verdict is to a cut. |
| `src/phase4/verdict.py` `assess` | The cut of every code: all values in `mappings/verdict_rules.csv` are first guesses. |
| `src/phase4/verdict.py` `assess` | No code moves the verdict. Verdict-moving rules are step 6; learned verdict weights come later, from `decisions`. |
| `backend/app/routers/decisions.py` | `price_paid` is accepted but no screen asks for it; a decision cannot be changed. |
| `frontend/src/ui/VerdictCard.tsx` `LOWERING_CODES` | Repeats the `LOWERING` list of `verdict.py`; the API should say which codes lowered the confidence. |

Find them all: `grep -rn "TODO(" backend src frontend/src`.

## 4. REVIEW rules (`mappings/verdict_rules.csv`)

All REVIEW: the team decides; the data only measures them.

| name | start value | meaning |
|---|---|---|
| `min_wardrobe_items` | 8 | Below this many usable pieces the confidence is low (`small_wardrobe`). |
| `far_from_style_cut` | 0.5 | Cosine similarity to the user's taste vector below which `far_from_style` shows. Informs only. Chosen on the golden wardrobe. |
| `budget_share` | 0.3 | A price above this share of `budget_tnd` gives `over_budget`. Informs only. |

Also relevant: `mappings/xai_settings.csv` (the "unsure" cuts behind `guessed_field`) and the compatibility
files that decide the verdict itself (`compatibility_weights.csv`: `buy_min_outfits`, `think_min_outfits`, `good_outfit`).

## 5. Tests

Backend, in the container (PowerShell; in Git Bash put `MSYS_NO_PATHCONV=1` in front):

```
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q
```

Expected: 401 passed, 3 skipped. Step 1 files:

```
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_verdict.py tests/test_verdict_routes.py tests/test_promote_decisions.py tests/test_golden.py tests/test_golden_codes.py tests/test_deletion_complete.py
```

Goldens (`backend/tests/golden/`, see its README) compare `/buy-advice`, the listing path, `/outfits/*` and
`/insights` with recorded answers. They depend on the team's `mappings/*.csv`: changing a weight changes
them on purpose. `GOLDEN_RECORD=1` rewrites them; only in a pull request that explains each difference.

Frontend: `cd frontend && npm run build && npm run lint` (the one warning in `BuildPage.tsx` is older).
There are no frontend tests: use `manual-checks/step-1.md`.

## 6. Suggested next tasks

1. Ask the price paid when the user taps Bought it (`price_paid` exists in the API) and show the decisions
   history somewhere (`GET /decisions`).
2. Tune the three numbers of section 4 with the team on real scans; decide if `far_from_style` and
   `over_budget` should ever move the verdict (step 6).
3. Let the API return which codes lowered the confidence, then delete `LOWERING_CODES` from the card.
4. A better confidence rule: weigh the codes, use the margin to the verdict's cut.
5. Allow changing an answer ("Left it" -> "Bought it" later) without breaking the unique decision per scan.
6. Review the Arabic and French sentences of `verdictCodeLine` and of the card with a native speaker.
