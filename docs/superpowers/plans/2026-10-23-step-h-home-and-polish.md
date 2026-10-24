# Step H: a Home page and a light polish of the user pages (plan)

Branch `upgrade/step-h-home-and-polish`, from local `main` (e0466aa). Frontend only, local, nothing pushed.
References: `docs/superpowers/design/prototype-home-reference.md` and `dressme-prototype-tokens.json` (saved
from the brief's attachments; the full prototype markup `dressme-prototype.dc.html` was read from the brief and is
not copied into the repo). Names, dates, weather and pieces in the prototype are sample data and are never used.

## Part 0: what the code says (read-only)

a) **Theme.** `index.css` has ONE `@theme` block: the app's "ticket" theme (`stock` #e6f0ea ground with a
   guilloché SVG, `paper` #f5f9f6 ticket faces, `ink` #1e2e8e ultramarine, `ink-soft` #3a4796, `carbon` #14161a text,
   `carbon-soft` #3b4440, `perf` #9aa7a1, `stamp` #c8234f magenta, square corners, `shadow-ticket` / `shadow-lift`)
   plus the step-2b "Dress look" tokens (`label-safe` #d8eedb, `label-bolder` #f6eeb4, `label-experimental` #e4dbf4,
   `label-neutral`, `pill` #111312, `pill-text`, `pill-line`, `tile` #fff, `scrim`, `radius-card` 28px,
   `radius-sheet` 28px, `radius-tile` 16px, `radius-pill`, `spacing-card` 20px, `spacing-stack` 24px).
   Against the prototype tokens:
   - **Same role, same value:** `radius-card` = `radius-lg` (28px), `radius-pill` = `radius-full`, `tile` = `photo-on-tint` (#fff).
   - **Same role, different value, used only by Dress:** `label-safe/bolder/experimental` vs `tint-sage/butter/lilac`
     (a few points of hue apart), `radius-tile` 16px vs `radius-sm` 12px, `pill` #111312 vs `ink` #151413. Rule of
     the brief: only Dress / Home use them, so they take the prototype value.
   - **Same NAME, different meaning:** the prototype's `ink` is near-black (text and the main action) and its
     `accent` is a blue for links and focus; the app's `ink` is ultramarine and already plays the accent role. The app
     keeps its `ink`; the prototype's ink role maps to the existing `pill` (buttons, selected chip, active tab) and
     `carbon` (text, #14161a vs #151413). `ink-soft` (#3a4796 blue vs #5a5751 grey): the app keeps its own; secondary
     text in the new look uses `carbon-soft` (#3b4440, darker than the prototype's grey: more contrast on the tints).
   - **Missing:** `surface`, `sunken`, `line`, `line-strong`, `tint-peach`, `tint-sky`, `buy` / `buy-soft`, `unsure` /
     `unsure-soft`, `leave` / `leave-soft`, `radius-md`, `shadow-float`, the sizes (tap 48, button 56, chip 40, tab bar
     64), the display / text fonts.
   - **Ground:** the prototype's `ground` #f3f2ee vs the app's `stock` + guilloché: the app keeps its own ground.
   - **Fonts:** the whole app uses Readex Pro Variable (Latin + Arabic glyphs, from `@fontsource`) and JetBrains
     Mono for serial numbers. Bricolage Grotesque and Figtree have no Arabic glyphs, so Arabic keeps Readex Pro.
   - **Dark mode:** none (`color-scheme: light`). The prototype's dark values are not added.
b) **Navigation.** `shell.tsx`: one `NAV` list (Dress `/dress`, Wardrobe `/wardrobe`, Scan `/scan` "Worth it?" /
   short "Buy?", Shops `/shop`, Assistant `/chat`) drives both the desktop rail (264px, ticket stubs, plus Admin,
   Profile `/me` and Log out at the bottom) and the phone tab bar (fixed, full width, 5 columns, Scan as a raised
   centre slot). A phone header shows the wordmark plus Admin and Profile icons. `--tabbar-h` is measured from the
   bar with a ResizeObserver. After login `AuthPage` navigates to `/`, which redirects to `/dress`.
c) **Adding clothes.** `WardrobePage` (`/wardrobe`): `PhotoPicker` at the top (take a photo / choose one) →
   `POST /items` → the item page. One piece per photo (the Scan page says so too: `onePiecePerPhoto`).
d) **Endpoints Home can reuse.**
   - **Today's outfits:** Dress calls `GET /outfits/today?occasion=<chip>&shuffle=0[&lat&lon]`, where chip = the last
     chip remembered in localStorage (`dressme.dressChip`, else `everyday`) and the position the user shared
     (`dressme.weatherPlace`). Home makes exactly that call (the helpers move to one shared file), so both show the same
     outfits on the same day. Its answer already carries **today's weather** (`weather: {temp_c, condition}` or null),
     so Home needs no other weather call (`GET /weather` also exists).
   - **Items:** `GET /items` has no date field, but it is sorted by `created_at` ascending: newest first = the list reversed.
   - **`GET /insights`:** `missing` (`main`, `top`, `bottom`, `shoes`) and `total`.
   - **`GET /me`:** `name` (required at sign-up, 1-60 chars) and `email`.
e) **Shared UI.** `ErrorNote` (+ `message`), `Empty`, `Skeleton` (`ui/states.tsx`); `Button`, `Chip`, `TextField`
   (`ui/controls.tsx`, the ticket look, also used by Admin and the Assistant); `PillButton`, `PillChip`, `Segmented`
   (`ui/dress.tsx`); the Dress `Collage` (inside `ui/OutfitCard.tsx`, not exported yet); `ItemPhoto`; `VerdictCard`;
   `DetailsSheet`; `Page` (the ticket header, also used by the Assistant).

Nothing Home needs is missing, so no backend change.

## How the polish stays "light" and shared
A **soft look** is opted into per page: `Page look="soft"` (with an optional kicker line) gives the prototype page
header and wraps the page in a `look-soft` scope and a `LookContext`. Inside it, the shared pieces switch look in ONE
place each: `Button` (ink pill 56px / surface pill with a line-strong ring / underlined link), `Chip` (44px pill,
selected = ink fill), `TextField` (surface field, 20px radius), `Empty` (the prototype state card), `ErrorNote`, and
the CSS of `.ticket` / perforations (surface card, radius-lg, flat). Admin and the Assistant do not opt in, so they
keep the ticket look exactly. Fonts follow the same scope: Figtree text, Bricolage Grotesque headlines, Readex Pro
first under `lang="ar"`.

## Work
1. Tokens + fonts (`index.css`, `index.html`); the look scope (`ui/look.tsx`, `Page`, controls, states).
2. Home (`pages/HomePage.tsx`, route `/` and `/home`), the shared Dress prefs (`dressPrefs.ts`), `Collage` exported.
3. Nav: floating pill tab bar (Home, Dress, Buy?, Wardrobe, Assistant), `--tabbar-h` = the bar plus its offset,
   desktop rail with Home first; the phone header hidden on Home (its avatar takes over).
4. Polish: Wardrobe, item page, Wardrobe view, Buy? (scan + `VerdictCard` verdict colours), Shops (+ listing),
   login / sign-up, Dress (shares the header only).
5. Strings en / fr / ar; screenshots (scratchpad); `manual-checks/step-h.md`; `CLAUDE.md`; build, lint, backend suite.
