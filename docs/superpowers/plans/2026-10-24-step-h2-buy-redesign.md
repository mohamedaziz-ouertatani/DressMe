# Step H2: the Buy? page (scan start + verdict) in the Dress look (plan)

Branch `upgrade/step-h2-buy-redesign`, from local `main` (aa170dc). Frontend only, local, nothing pushed.
Reference: the prototype's `isBuyStart` and `isVerdict` blocks. `docs/superpowers/design/dressme-prototype.dc.html`
is NOT in the repo (step H kept only the home reference and the tokens); the markup was read again from the step-H
brief. Names, prices and numbers in it are sample data and are never used.

## Part 0: what the code says (read-only)

a) **Step H is in local `main`.** `main` = aa170dc (the IncompleteNote follow-up) on top of 12cd00b (step H docs),
   5ef8687, a7f4dd7, 6794fd0, ... Home, the floating tab bar, the soft look and the follow-up are all there.

b) **Wavy background, "№" serial, stamps, ticket stubs.**
   - **Wavy background:** the guilloché SVG `assets/guilloche.svg` on `body` (`index.css`, `@layer base`, with
     `--color-stock`). It is global, so **the Dress page shows it too** (and every page). Dress has no serial, stamp
     or stub.
   - **On Buy?** (`pages/ScanPage.tsx`): the scanned piece sits in a `Ticket` (`ui/ticket.tsx`, CSS `.ticket` +
     `.perf-v`; inside `.look-soft` already a flat surface card with a hairline) whose stub is `Serial` (`№ XXXX`,
     JetBrains Mono, `ui/serial.ts`). The verdict's best outfits are `OutfitStrip` (`ui/OutfitStrip.tsx`): one
     `Ticket` per piece with an `01/03` stub, a `Serial` per piece, `SecondLine`, and the score as a `Stamp`
     (`ui/Stamp.tsx`, `.stamp-land`). The start card and the field check are `.ticket` blocks; `VerdictWhy` opens a
     `.ticket` panel.
   - **Elsewhere:** `Stamp`: `AuthPage` (the DM logo stamp), `LandingPage`. `Serial`: `WardrobePage` (grid and list).
     `Ticket`: `WardrobePage` (list), `ShopPage` (listing header). `.ticket` class: `InsightsPage` (now the Wardrobe
     view's stats), `ExplainPanel`, `GenderChoice`, `ListingCard`, `ProfilePage`, `SellPage`, `SimilarPage`,
     `ChatPage`, `states.tsx`, admin. `OutfitStrip` is used ONLY by `VerdictCard`.

c) **Arabic name under the English one.** `SecondLine` (`ui/ticket.tsx`) prints `secondLine(table, value, lang)`
   (`i18n/vocab.ts`): column 2 (Arabic) of `SUB_LABELS` / `CATEGORY_LABELS` when the app is in en / fr, column 0
   (English) when it is in Arabic. Used by `ScanPage` (the piece), `OutfitStrip` (every piece), `WardrobePage` (grid
   and list).

d) **Dress components Buy? can reuse.** `OutfitCard` (`ui/OutfitCard.tsx`: tint by label, else `label-neutral`;
   `ConfidenceDots` (not exported); `Collage` (exported, `ItemPhoto` on `bg-tile`); `IncompleteNote`; `WearButton`;
   ✦ → `DetailsSheet` with `PointsBar`, `ScoreDetails`, `ExplainLines`, like / dislike, Try it on). `ErrorNote`
   (+ `message`), `Skeleton`, `Empty` (`ui/states.tsx`); `Button` (soft: 56 px pill), `TextField` (soft: surface,
   radius-photo) (`ui/controls.tsx`); `PillButton` (`ui/dress.tsx`). Two catches for a verdict outfit: (1) it holds
   the **scanned piece, which is not owned**: `WearButton` would POST `/wear` with it (404), and its `image_url`
   (`/items/<candidate id>/image`, from `describe`) does not exist, which is why `OutfitStrip` takes `photoOf`.
   (2) The verdict's best outfits carry **no `label` and no `confidence`** (`compatibility.buy_advice` does not label).

e) **What `POST /buy-advice` answers** (`routers/outfits.py`, goldens `tests/golden/expected/buy_advice_*.json`):
   - `verdict` (buy / think / skip), `good_outfits` (a count), `reasons` (English strings, e.g. "you already own 1
     very similar top item(s)", translated by `reason()`), `confidence`, `codes`, `candidate` (the item, **no
     price**), `best` (up to 3 outfits), `explanation`.
   - **There is no verdict score and no parts.** The verdict comes from counting good outfits against
     `buy_min` / `think_min` (`explanation.path`). A score 0-100 with `style / colour / pattern / structure` points and
     their max (`contributions[].points / max_points`, e.g. `19.0 / 35.0`) exists only **per best outfit**. With no
     best outfit (`no_pairing_piece`) there is no score at all.
   - **Codes and their params:** `small_wardrobe {owned, minimum}`, `no_pairing_piece {slot}`,
     `guessed_field {field, conf}` (lower the confidence); `fills_gap {slot}`, `far_from_style {similarity}`,
     `over_budget {price, budget, share}` (inform). **No code carries an item id.** Owned pieces with photos are in
     `explanation`: `twins[].item` (the near-twin reason), `lost_to[].owned`, `beats[].owned` (`ShortItem` with
     `image_url`).
   - **Price:** sent by the page (Scan: the tag price; Shop: the listing's `price_tnd`), not echoed back; only
     `over_budget` repeats it.
   - **Best outfits:** `score`, `parts`, `reasons`, `items`, `contributions`, `explanations`, `complete`, `missing`;
     no `label`, no `confidence`.
   - **Bought it / Left it:** `POST /decisions` (201, or 200 for the same answer again; 409 another answer recorded;
     404 the scan is gone). **There is no undo** (no `DELETE /decisions`). On Scan, Bought it opens the new item
     (`/wardrobe/<id>`) right away and Left it goes back to the start; on Shops the card shows what was recorded.

f) **`VerdictCard`** is used by `ScanPage` (with `onDecided`, try-on) and `ShopPage`'s listing page (no
   `onDecided`, `restart` = Check again). Nowhere else.

## Where the brief and the code disagree (asked before building)

1. The big score (~80 px, "out of 100") and the four part bars ("19 / 35"): the verdict has neither (e).
2. "Plain ground, as on Dress": Dress shows the wavy guilloché ground (b).
3. "After a tap: a check disc, Saved title + one line": on Scan both answers leave the verdict at once (e), so the
   saved state is only seen on Shops unless Scan changes what it does after a tap.

Undo: none exists, so the saved state shows no Undo (as the brief says).

## Work (after the answers)

1. `SecondLine` / `secondLine` print nothing in the current-language-only rule: removed from the shared component and
   its callers (Scan, Wardrobe grid + list, OutfitStrip), so no page shows the other script under a name.
2. Shared pieces: export `ConfidenceDots`; `Collage` and `OutfitCard` take an optional `photoOf` and an
   `actions={false}` mode (no Wear this, no like / dislike: the piece is not owned yet), so the verdict reuses the
   Dress card itself rather than a copy.
3. Scan start: headline + sentence, the ink camera frame (radius 32, white corner marks, hint, the sweep while
   analysing, off under reduced motion), PhotoPicker under it, the field check and price (soft `TextField`).
4. `VerdictCard` rebuilt: back button + name, the verdict card (photo tile, pill, number, bars, dots), the low-confidence
   banner (from the lowering codes), "Why" rows (For / Against discs, translated sentences, thumbnails from
   `explanation`), "Why this verdict?", best outfits as `OutfitCard`, the fixed decision bar (tab bar hidden on the
   verdict view only, content padded).
5. Buy?: no `Ticket`, `Serial`, `Stamp` or stub left on the page; Shops' listing gets the same card.
6. Strings en / fr / ar (MSA); build, lint; headless Chrome before / after at 390 px; `manual-checks/step-h2.md`;
   `CLAUDE.md`.
