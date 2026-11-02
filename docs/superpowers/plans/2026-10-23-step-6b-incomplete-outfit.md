# Step 6b: flag incomplete outfits (plan)

Branch `upgrade/step-6b-incomplete-outfit`, from local `main` (cd90508). Local only, nothing pushed. The known
issue: `POST /outfits/score` rates a top + shoes outfit (no bottom) 86, above the good-outfit line, because a part
that cannot be computed is left out and the other weights are rescaled. The score does NOT change; the response
says the outfit is incomplete and the app shows a note.

## Part 0: what the code says (read-only)

a) **The rule that exists.** `src/phase4/dress.py` `is_complete(items, rules)`: `slots = {rules.slot[category]}`;
   main = `"full" in slots or {"upper", "lower"} <= slots`; then it also requires shoes (`"feet"`) unless there is a
   swimsuit. `rules.slot` is `compatibility.Rules.slot`, read from `mappings/outfit_structure.csv` (column `slot`:
   top = upper, bottom = lower, dress / traditional / swimwear = full, outerwear = layer, shoes = feet, bag /
   accessory = extra). `compatibility.score_outfit` has its own copy of the same slot test (the "missing a top or a
   bottom" reason), untouched. The new function reuses the slots of the same CSV through the same `Rules`, and
   drops the shoes requirement (shoes and accessories are not required); `is_complete` then calls it for its main
   piece test, so there is one definition of "a main piece". A swimsuit counts as a full piece (the CSV says so).
b) **Where a user sees the score of an outfit they picked.**
   - `POST /outfits/score` (`routers/outfits.py`): the only route that scores EXACTLY the pieces sent. The app does
     not call it any more (`api.score` is unused since the Dress page replaced Build).
   - `POST /outfits/build` (`routers/dress.py`): it does **not** score a top + shoes pick as it is. A complete
     choice (main piece + shoes) comes first as the pick; otherwise `complete_fully` adds pieces until the outfit has
     a main piece and shoes. So an incomplete outfit shows up on Build only when the wardrobe has nothing to
     complete it with (e.g. no bottom at all). That case is what the manual check uses.
   - The Dress cards (`OutfitCard`, For today and Build) and their details sheet ("Score 83 / 100", "Why this
     score?"): they show whatever the route returned. `OutfitStrip` (the verdict's best outfits on Scan / Shop) too.
   - `POST /outfits/complete` (the user's pieces + one more) can also return outfits that are still incomplete.
c) **The golden.** None records the top + shoes 86. It is `tests/test_golden.py`
   `test_known_issue_incomplete_outfit_scores_high` (its own tiny wardrobe, asserts 86.0 +- 0.5 and the reason).
   `expected/outfits_score.json` records two other fixed outfits.

No finding contradicts the design. One thing to know: because Build completes the pick, "pick a top and shoes only
and see the note" shows the note only on a wardrobe without a bottom; the manual check says so.

## Design
- `dress.outfit_completeness(items, rules=C.RULES)` (pure) -> `{complete: bool, missing: None | "bottom" | "top" |
  "core"}`: a top and a bottom, or a full piece = complete; `missing` = `"bottom"` (an upper piece, no lower, no
  full), `"top"` (a lower piece, no upper, no full), `"core"` (neither: only shoes, a layer, extras). No constants.
- `outfit_out(..., explain=True)` (every app route that returns an outfit) adds `complete` and `missing`. The chat
  tools keep the short form. The score does not change.
- Goldens gain only those two keys (diff shown); the top + shoes test keeps its 86 and gains the flag assertions.
- Frontend: `ui/IncompleteNote.tsx` ("Incomplete: add a bottom" / "add a top" / "add a top and a bottom, or a
  dress") next to the score in the details sheet, on the card and on the verdict strip; types updated.

## Docs
CLAUDE.md (known issue flagged), Dress hand-off "Future work" (swap test ties), `manual-checks/step-6b.md`.
