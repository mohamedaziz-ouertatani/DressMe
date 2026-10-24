# Hand-off: the Wardrobe view (step 5)

Skeleton, not a finished feature: the data model, the API contracts and the screens are final; the logic behind
them is a first version, marked `TODO(step 5)` (`grep -rn "TODO(step 5)" backend src frontend/src`; the one
`TODO(step 4)` is the hidden "To check" section). Branch `upgrade/step-5-wardrobe-view-skeleton`, plan
`docs/superpowers/plans/2026-10-23-step-5-wardrobe-view.md` (it holds the Part 0 findings). Local, not pushed.
Click-through: `docs/superpowers/manual-checks/step-5.md`.

What did NOT change: `src/phase4/compatibility.py`, the goldens, every existing endpoint (responses only gained
fields: `consent_at` in the profile; `POST /auth/register` accepts one more optional field).

## 1. What is built

The Insights page (`/insights`, reached from a link on the Wardrobe page, not in the nav) is now **the Wardrobe
view**, same route, same link, renamed "Wardrobe view" / "Vue de la garde-robe" / "نظرة على الخزانة". Sections, in order:

1. **To check**: hidden. `TODO(step 4)` in `WardrobeViewPage.tsx` where it renders (drafts do not exist).
2. **Worn**: worn lately, never worn (photos linking to the item page), the history (GET /wear, 20 shown).
3. **Bought and left**: GET /decisions, each with what was stored then: the verdict, its confidence, the price
   paid or the tag price, the date. Never recomputed.
4. **Wardrobe stats**: the old Insights page, unchanged (`InsightsPage.tsx` now only exports `StatsSection`).
5. **Profile**: budget (save, remove), the consent date, "Delete my account" (password dialog and a warning).

Each section loads on its own and has loading, empty, error (a translated message and Try again, the detail only in
the console: `ErrorNote message=`) and success. The look is the Dress one (tokens of `index.css`).

Consent and deletion are not on this page only: a **required checkbox** on the sign-up form, and a **one-time
dialog** (`ui/ConsentAsk.tsx`, after the gender question in `Gate`) for an account with no consent date: "I agree"
or "Log out", nothing else. The wording of the dialog is a first version nobody has checked (`TODO(step 5)`).

## 2. API contracts

**`POST /auth/register`** gains an optional `consent: true`; then `users.consent_at` = the creation time.

**Profile** (`GET /me`, `PUT /me`, login and register answers) gains **`consent_at`**: an ISO string, or `null`
for an account that never agreed.

**`POST /me/consent`**: sets `consent_at` to now for the caller if it is empty; a second call keeps the first date.
Returns the profile.

**`PUT /me`** already saved `budget_tnd` (step 1): `{"budget_tnd": 120.5}`; `null` clears it; `> 0` and at most
1,000,000 (the brief said "≥ 0": `0` is refused, a budget of 0 would flag every priced piece as over budget).

**`DELETE /me`** `{"password": "..."}`: 403 for a wrong password, 403 for the demo account (its password is public),
else 204 and the account is gone (the old token then answers 401). It calls `app/accounts.py` `delete_account`,
the same function the admin route (`DELETE /admin/users/{id}`) calls now: every collection of `db.USER_COLLECTIONS`
(items, candidates, chats, events, outfit_feedback, decisions, wear_log), the seller listings and their pictures,
the user document, the photo folder. **A new per-user collection goes in `USER_COLLECTIONS` and both deletions
follow.** `test_deletion_complete.py` checks both ways (it scans every collection and the folders).
**No last-admin guard** (academic scope): an admin can delete the only admin account here.
(`TODO(step 5)` in `routers/auth.py`.)

**`GET /wear/summary`**:

```json
{ "worn_lately": [ {"item_id": "6540...a1", "last_worn_on": "2026-10-22"} ],
  "never_worn": [ "6540...c3" ],
  "window_days": 14, "grace_days": 14 }
```

`worn_lately` = pieces whose last wear entry is within `window_days` days of today (Tunis date), most recent first.
`never_worn` = pieces with no wear entry at all that were added more than `grace_days` days ago, the longest-waiting
first. A piece worn only long ago is in neither list. Every query is filtered by `user_id`.

## 3. Code

- `src/phase4/wardrobe_view.py` (pure): `load_rules`, `worn_summary(items, wear_entries, today, window_days, grace_days)`.
- `mappings/wardrobe_view.csv`: `window_days` 14, `grace_days` 14 (both REVIEW, the team's to tune; no numbers in code).
- `backend/app/accounts.py` `delete_account`; routes in `routers/auth.py` (`/me/consent`, `DELETE /me`) and
  `routers/wear.py` (`/wear/summary`).
- Frontend: `pages/WardrobeViewPage.tsx`, `pages/InsightsPage.tsx` (`StatsSection`), `ui/ConsentAsk.tsx`,
  `pages/AuthPage.tsx` (checkbox), `auth.tsx` (`acceptConsent`, `deleteAccount`), `api/client.ts` / `api/types.ts`.
  Strings: `consent*` and `wv*` keys in `i18n/strings.ts` (en, fr, ar in Modern Standard Arabic).

## 4. What is placeholder (`TODO(step 5)`)

| Where | What is simplified |
|---|---|
| `wardrobe_view.py` `worn_summary` | A piece is "worn" when it is in a wear entry. No wear frequency, no cost per wear (the price paid is in `decisions`), no "sell suggestions" for never-worn pieces (the Seller assistant has `pieces_to_sell`), no rule for seasonal pieces that rest on purpose. |
| `WardrobeViewPage.tsx` history | Shows 20 entries (GET /wear returns at most 500): no paging. |
| `WardrobeViewPage.tsx` bought and left | Listed as stored: no photo of the bought piece, no cost per wear, no "you left 5 of 8 skips" summary. |
| `routers/auth.py` `DELETE /me` | No last-admin guard, no grace period before the data goes. |
| `ui/ConsentAsk.tsx` | The wording. Nobody who knows the rules has read it. |

## 5. How `wardrobe_insights` decides "missing" and "unused" (not changed)

`compatibility.wardrobe_insights` works on the pieces left after the personal filters (modesty level and so on):

- **missing**: `"main"` when there is no top, no bottom and no full piece (dress...); `"bottom"` when there are tops
  but no bottom and no full piece; `"top"` the other way round; plus `"shoes"` when no piece has the category shoes.
  The Wardrobe stats section turns them into the "What to add next" sentences.
- **There is no key called "unused".** The nearest are `unmatched` = main pieces (top, bottom, full piece) that are
  in no *good* outfit (a good outfit scores at least the team's `good_outfit`), and `outfit_use` / `versatile` (how
  many good outfits each piece is in). Shoes and bags are left out of `unmatched` because they fit almost every
  outfit. "Never worn" on this page is a different thing: it comes from the wear log, not from the formula.

## 6. Tests

```
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q
```

`test_wardrobe_view.py`: consent, the budget, the worn summary, DELETE /me (one contract test each).
`test_deletion_complete.py` gained a second user who deletes their own account with `DELETE /me` and the same
"nothing left in any collection or the photo folder" check (and `wear_log` is now among the collections the test
makes sure hold data). Frontend: `npm run build && npm run lint`; no frontend tests, use the manual checks.

## 7. Suggested next tasks

1. Have the consent wording read by someone who knows the rules; decide what the app keeps and for how long.
2. Wear frequency and cost per wear; a "never worn" action (sell it, or put it in an outfit).
3. The "To check" section once step 4 (drafts) exists.
4. A last-admin guard; paging for the history; a native review of the new French and Arabic sentences.
