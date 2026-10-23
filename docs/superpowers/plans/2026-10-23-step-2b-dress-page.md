# Step 2b: the Dress page (plan)

Branch `upgrade/step-2b-dress-page`, from `main` (01d8742). Local only, nothing pushed. Keeps everything of
step 2 that still fits: the goldens, `wear_log`, `/wear` and its idempotent POST, `WearButton`, `label_outfits`
and its cuts, the wear penalty and the empty-state logic. It only adds or replaces what the brief says.

## What does not change
- `src/phase4/compatibility.py`. `/outfits/suggest`, `/score`, `/complete`: the same outfits in the same order
  (suggest stays a list). Responses only gain fields. The `/wear` contract (`source` = `card` | `build`).
- Goldens: only the step-2 keys may change (`confidence` can become `medium`), plus the new key
  `confidence_reasons`. Proven with a diff.

## Backend (one function, two callers)
1. **`src/phase4/dress.py`** (pure): confidence in three levels with `confidence_reasons`
   (`small_wardrobe {owned, minimum}`, `guessed_field {item_id, field}`; the level is the number of reasons:
   0 high, 1 medium, 2+ low), `pick_three(outfits, seed, rules)`, `context_reasons(outfit, occasion, weather)`,
   plus the helpers they need: `make_seed` (sha256, never Python's salted `hash`), `calendar_season`,
   `load_occasions`, `merge_candidates`, `resolve_clashes`, `complete_fully`.
2. **Rules**: `pick_pool = 3` in `mappings/dress_rules.csv`; new `mappings/dress_occasions.csv` (chip,
   usage_values, mode, order, main, note), all REVIEW.
3. **`routers/outfits.py`**: the 20-candidate fetch of `suggest` (with the penalty) becomes one function,
   `ranked_suggestions`; `suggest` calls it and its own output does not change. `outfit_out` also copies
   `confidence_reasons`.
4. **`routers/dress.py`** (new): `GET /outfits/today?occasion&shuffle` and `POST /outfits/build`, both labelling
   candidates and calling `pick_three`; `GET /outfits/occasions` (the chips, from the CSV, so the app does not
   repeat the list).
   - Today: the seed is a hash of (user, date in Tunis, chip, shuffle). Candidates = `ranked_suggestions` for
     each usage value of the chip (merged, deduplicated), season from the weather (else the calendar); beach
     chip = beach mode in summer. `missing` comes from `wardrobe_insights`, only when nothing is returned.
   - Build: pieces must be the user's (404); clashes are swapped (the newest piece wins, like the Build page did)
     and reported as `notes`; if the pieces already make a complete outfit it comes first with `pick: true`;
     the others are completions (`complete_outfit`, extended piece by piece until the outfit is complete),
     labelled, then `pick_three` (2 when there is a pick: 3 in total).
5. **Tests (2 new)**: `/outfits/today` (same day + shuffle = same outfits, shuffle 1 valid, one outfit per
   label when candidates allow) and `/outfits/build` (the chosen piece in every outfit, 404 for another user's).

## Frontend
- One page **Dress** (`/dress`, `/dress/build`), a segmented switch "For today" | "Build"; `/`, `/today` and
  `/build` redirect (the app had no `/today`: Today was the index route). One nav item replaces Today and
  Build; the phone tab bar keeps 5 slots by moving Shops into it (it was in the header).
- New shared **`OutfitCard`** (label colour, confidence dots, photo collage, two reasons, "Wear this" =
  `WearButton`, ✦ details sheet). `OutfitStrip` stays for the verdict's best outfits and the other pages.
- Pieces: `ui/OutfitCard.tsx`, `ui/DetailsSheet.tsx`, `ui/dress.tsx` (pill chip / segmented control / pill
  button), `pages/DressPage.tsx`. `TodayPage.tsx` and `BuildPage.tsx` are removed.
- **Design tokens**: every colour, radius and spacing of the new look is a CSS variable in one block of
  `index.css` (`@theme`), used through Tailwind utilities. Other pages are not restyled.
- The like / dislike feedback of the old Today / Build pages moves into the details sheet, so the taste
  vector keeps learning from it.

## Docs and close
`TODO(step 2)` markers; `handoff/dress.md` and `manual-checks/step-2.md` updated for the new page; `CLAUDE.md`
for steps 1, 2 and 2b; full suite; goldens diff; build and lint; fast-forward `main`.
