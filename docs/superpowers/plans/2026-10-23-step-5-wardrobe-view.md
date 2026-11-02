# Step 5: the Wardrobe view (skeleton plan)

Branch `upgrade/step-5-wardrobe-view-skeleton`, from local `main` (e2a8667). Local only, nothing pushed. A
teammate feature: final data model and API contracts, a simple first version of the logic, wired screens,
`TODO(step 5)` markers, a hand-off doc. Step 4 (drafts, "To check") is skipped.

## Part 0: what the code says (read-only, before building)

a) **Profile update.** `PUT /me` (`routers/auth.py` `update_me`, body `schemas.ProfileUpdate`, `exclude_unset`)
   is the only endpoint. It **already saves `budget_tnd`** (added in step 1): `float`, `> 0` and `<= 1,000,000`,
   `null` clears it. Only the bound differs from the brief ("number >= 0"): `0` is refused today. I keep
   `> 0` (a budget of 0 would flag every priced piece as over budget; `null` is "no budget"). `api.updateMe`
   in the app already takes `budget_tnd`; no screen sets it yet. So: no endpoint to add, nothing to extend.
b) **Account deletion.** It is the route `delete_user` in `backend/app/routers/admin.py` (`DELETE /admin/users/{id}`).
   It does loop over `db.USER_COLLECTIONS` (`items, candidates, chats, events, outfit_feedback, decisions,
   wear_log`), then `delete_seller_listings(...)`, `listing_index.invalidate()`, the user document and
   `rmtree(storage_dir/<user id>)`. **But there is no function to call**: the code is the body of the route, behind
   `other_user()` (which refuses an admin deleting themselves). To reuse it without copying it, I move the body
   into `backend/app/accounts.py` `delete_account(request, user)`; the admin route and the new `DELETE /me` both
   call it. Behaviour of the admin route does not change (`test_deletion_complete.py` covers it).
c) **Insights page.** Route `/insights` (`App.tsx`, `pages/InsightsPage.tsx`), reached only from a link on the
   Wardrobe page (`WardrobePage.tsx`, string `insightsLink`). It is not in the nav. The page becomes the Wardrobe
   view on the same route; no new tab.
d) **"missing" and "unused"** (`compatibility.wardrobe_insights`, not changed): `missing` = after the personal
   filters, `"main"` when there is no top, bottom or full piece; `"bottom"` when there are tops but no bottom and no
   full piece; `"top"` the other way round; plus `"shoes"` when no piece has the category shoes. There is **no key
   called "unused"**: the nearest are `unmatched` (main pieces, i.e. tops / bottoms / full pieces, that are in no
   good outfit, `good_outfit` = the team's score cut) and `outfit_use` (good outfits per piece). The Wardrobe view
   keeps showing those; the new "never worn" list is a different thing (it comes from the wear log).
e) **Sign-up and login.** `pages/AuthPage.tsx` (one form for both, `mode`), `auth.tsx` (`register`, `login`,
   `logout`, `updateProfile`; `Gate` in `App.tsx` already shows `GenderAsk`, a full-page one-time question, when
   `user.needs_gender`). The consent checkbox goes in the sign-up form; the one-time dialog goes in `Gate`, right
   after the gender question, in the same style.

No finding contradicts the design. Two small differences to flag in the report: the `> 0` budget bound (a) and
the extraction in (b).

## Backend
1. `schemas.Register` gains `consent: bool | None = None`; new `DeleteMe {password}`.
2. `users.consent_at` (top level of the user document): null/missing for existing users. `register` sets it when
   `consent` is true. `profile_out` gains `consent_at` (ISO string or null).
3. `POST /me/consent`: sets `consent_at = now` only if it is empty (the second call keeps the first date); returns
   the profile.
4. `DELETE /me` {password}: wrong password 403; the demo account 403 (a safeguard: its password is public); else
   `accounts.delete_account` and 204. No last-admin guard (academic scope; said in the hand-off).
5. `mappings/wardrobe_view.csv` (`window_days` 14, `grace_days` 14, both REVIEW) and `src/phase4/wardrobe_view.py`
   (pure): `load_rules`, `worn_summary(items, wear_entries, today, window_days, grace_days)`.
6. `GET /wear/summary` in `routers/wear.py`: the user's items and wear log (every query filtered by `user_id`), the
   Tunis date, the CSV rules, the pure function.
7. Tests: one contract test each (consent, wear summary, budget, DELETE /me) and one extra assertion in the
   deletion test (DELETE /me leaves nothing in any collection or the photo folder).

## Frontend
- Types and client: `User.consent_at`, `WearSummary`; `api.consent`, `api.deleteMe`, `api.wearSummary`,
  `api.decisions`; `register` sends `consent: true`.
- `AuthPage`: required consent checkbox on sign-up. `Gate`: a one-time consent dialog ("I agree" / "Log out",
  not dismissible) when `consent_at` is null.
- `pages/InsightsPage.tsx` becomes the **Wardrobe view** (same route): To check (hidden, `TODO(step 4)`), Worn
  (lately, never worn, history), Bought and left, Wardrobe stats (today's Insights, unchanged), Profile (budget,
  consent date, delete my account). Each section has loading, empty, error (translated `ErrorNote message=`) and
  success. The Dress tokens of `index.css`; en/fr/ar (Arabic in Modern Standard Arabic); 390 px; above the tab bar.

## Docs and close
`handoff/wardrobe-view.md`, `manual-checks/step-5.md` (a throwaway account for the deletion; never the demo
account), one line in `CLAUDE.md`; full suite, goldens identical, build, lint; fast-forward local `main`.
