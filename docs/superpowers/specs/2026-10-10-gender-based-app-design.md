# Gender-based app (men / women) — design

Date: 2026-10-10. Status: approved design, not implemented. Branch `feature/gender-based` (from main, after #56).

## Goal

Each user is a man or a woman, and the app adapts to it: what it shows from the
catalogue, the shops and the listings; the order of the label pickers; and the team's
compatibility rules, which can now differ per gender. Models are not retrained.

## Decisions (with the user, 2026-10-10)

1. Scope = profile + filtering + **gender-aware team rules** (no model retraining).
2. Gender is **required**: asked at sign-up; older accounts are asked once and cannot
   use gender-dependent pages until they answer. Editable in Profile.
3. **The wardrobe is never filtered.** Any piece can be saved and corrected; gender only
   changes defaults, what is suggested from outside the wardrobe, and the rules.
4. Rules use approach A: an optional `gender` column in the existing rule CSVs.
5. Chat: tools filter by gender on the server; prompts and tool signatures unchanged, so
   `dressme-chat-v3` needs no retrain. Gendered wording (fr / Darija agreement) is out of
   scope (it would need a prompt line + v4).

## Values

- User: `men` / `women`.
- Item: `men` / `women` / `unisex`. Fashion Product `Men` / `Women` / `Unisex` →
  `men` / `women` / `unisex`; `Boys` / `Girls` → empty (falls back to the table below).
  Local photos already use `Men` / `Women` / `Unisex` (same conversion).

## 1. Item gender

### `mappings/gender_sub_categories.csv` (new, team-owned, all rows REVIEW)

`sub_category,gender,note`, one row per value of `sub_category_vocabulary.csv`
(a test checks they match). Starting values:

- `women`: skirt, leggings, tunic, capris, dress, jumpsuit, cape, heels, flats, clutch,
  handbag, earrings, necklace, bracelet, brooch, hair-accessory, jewellery-set, swimsuit,
  kaftan.
- `men`: tie, cufflinks, suspenders, swim-shorts, jebba.
- `unisex`: everything else.

### `src/phase4/genders.py` (new; plural so it never clashes with a `gender` variable)

Also holds `for_gender(table, gender, key)`, the rule-merge helper of section 2.

- `GENDERS = ("men", "women")`.
- `normalise(value)` → `men` / `women` / `unisex` / `""` from any source spelling.
- `item_gender(item)` → the item's own normalised label if it has one, else the table's
  value for its `sub_category`, else `unisex`.
- `shown_for(user_gender, item)` → `item_gender(item) in {user_gender, "unisex"}`;
  `user_gender=None` → always true.

### Data

- `mappings/hm_index_group.csv` gets a `gender` column (Ladieswear → women,
  Menswear → men, Divided / Sport → empty). `src/phase3/map_hm.py` writes `gender` into
  `hm.csv` (empty = decided by the table at read time). Re-run `map_hm.py`; embeddings
  are unchanged (same ids).
- `dressme.csv` already has `gender` (Fashion Product, local). Phase 3 is not re-run.
- PolyVore / Fashionpedia have no label: `item_gender` decides.

## 2. Gender-aware rules

- Optional `gender` column (`men` / `women` / empty = both) in `outfit_structure.csv`,
  `sub_category_pairing.csv`, `item_seasons.csv`, `compatibility_weights.csv`,
  `style_concepts.csv`. A missing column = all rows neutral.
- Merge rule: keep neutral rows + the user's gender rows; a gendered row **overrides** the
  neutral row with the same key: category (structure), the unordered pair (pairing),
  `(kind, value)` (seasons), `name` (weights), `concept` (concepts). Rows of the other
  gender are ignored.
- Starter rows (REVIEW, examples for the team, small on purpose): in `style_concepts.csv`,
  gendered prompts for `formal` ("a photo of formal elegant menswear" / "...womenswear")
  and `modest`. Other files: column added, no gendered rows yet. Current behaviour is
  identical until the team adds rows.
- `compatibility.Rules(map_dir=MAP_DIR, gender=None)`; `rules_for(gender)` returns one
  cached `Rules` per `None` / `men` / `women`; `RULES` stays = `rules_for(None)`;
  `reload_rules` reloads all three in place. The evaluation scripts keep neutral rules,
  so the reported AUC / FITB numbers do not move.
- `Analyzer.concept_vectors(gender=None)` caches text vectors per gender
  (`explain_similarity` passes the user's gender).
- The admin settings editor (`PUT /admin/xai/settings`, weights) keeps writing the same
  files; gendered rows are edited in the CSVs.

## 3. Backend

### Profile

- `Register.gender: Literal["men", "women"]` (required → 422 if missing);
  `ProfileUpdate.gender` optional, same values. Stored in `user["profile"]["gender"]`.
- `profile_out` adds `gender` and `needs_gender` (true when it is empty).
- `security.user_gender(user)` → the gender; `security.gendered_user` dependency =
  `current_user` that answers **409 `{"detail": "gender_required"}`** when it is empty.
  Used by every route that depends on gender (outfits, insights, similar, listings
  search, buy advice, chat, sell). `/me`, `/items` CRUD, auth and admin stay on
  `current_user`.
- Demo seed and admin creation set a gender (demo = the demo wardrobe's gender: women,
  checked against the seed pieces).

### Rules

Every current use of `RULES` (`routers/outfits.py`, `insights.py`, `wardrobe.py`,
`resale.py`, `weather.py`, `agents/explainer.py`) passes
`rules=rules_for(user_gender(user))`. Wardrobe items are never filtered.

### Catalogue (`/similar`, look-alikes)

- `SimilarityIndex` fills a `gender` column on load (`item_gender` per row: `hm.csv` /
  `dressme.csv` label, else the table); `search(..., genders=None)` filters on it.
- `Catalog.search` / `search_shop(..., genders=None)`; the routes pass
  `{gender, "unisex"}`. `Catalog.mean_vector` stays the same for everyone.

### Listings

- `listings.save_listing` stores `gender` = normalised connector label, else
  `item_gender` from the predicted sub_category. Sell listings = the seller's gender.
- `GET /listings`, `ListingIndex` search, the `In shops now` row and the chat tools
  (`search_listings`, `find_similar`) filter `gender ∈ {user, unisex}`; listings with no
  stored gender are judged on read with `item_gender`.
- `GET /listings?gender=all` turns the filter off (Shop page "Show all").
- `listings.backfill_gender(db)` runs at API start-up and writes `gender` on listings that
  have none (idempotent), so the MongoDB filter stays a plain `$in`.

### Chat

Agents read the user's gender on the server (the tools already receive the user).
Prompts and tool schemas unchanged. `build_chat_dataset.py` gives its random users a
gender so future datasets match the tools; no rebuild / retrain now.

## 4. Frontend

- `AuthPage` sign-up: required choice Woman / Man (en / fr / ar strings in i18n).
- `ProfilePage`: same choice, editable.
- App shell: when `me.needs_gender`, the route `Gate` shows a one-question page with the
  same choice (PUT `/me`) instead of the app; the backend 409 stays as the safety net.
- Label pickers (`FieldRow`, Sell form): sub_categories for `{gender, unisex}` first,
  then a "More…" group with the rest (never blocked). The team table is served by a new
  public `GET /vocab/sub-category-gender` (`{sub_category: gender}`, read from the CSV) so
  the CSV stays the only source; the frontend's `i18n/vocab.ts` keeps the labels.
- Shop / Similar: a line "Showing women's + unisex · Show all" toggling `gender=all`.
- Remember: Tailwind's dev server misses classes of a NEW .tsx file until restarted.

## 5. Tests and docs

- `tests/test_genders.py` (src helpers): `normalise`, `item_gender` (label beats table,
  table beats default), `shown_for`; the table covers exactly the vocabulary.
- Rules: a gendered row overrides the neutral one, the other gender's rows are ignored,
  files without the column load; `rules_for(None)` equals today's `Rules()`;
  `reload_rules` refreshes all three.
- Backend: register without gender → 422; old user → 409 `gender_required` on a gendered
  route, 200 after PATCH `/me`; `/similar`, `/listings` and the chat tools return only
  `{gender, unisex}`; `?gender=all` returns both; the wardrobe and outfits still use every
  owned piece; a man's sell listing is stored as `men`. Fakes get a `gender` column.
- Regression: re-run `evaluate_compatibility.py` once; the numbers must be identical.
- Frontend: `npm run build`; a browser check of sign-up, the old-account modal, pickers
  and the Shop toggle.
- Docs: CLAUDE.md (schema table: `gender`; Phase 4 item), `AGENTS.md` (tools filter by
  gender), `LISTINGS.md` (gender field), notes on the new / changed mapping files as REVIEW.

## Out of scope

Gender prediction from pictures; per-gender compatibility weights learned from data;
gendered wording in chat answers (needs a v4 model); other genders / "prefer not to say"
(the user asked for male or female).
