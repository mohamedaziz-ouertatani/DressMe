# DressMe codebase facts (read-only discovery, 2026-10-23)

Branch `feature/docker`, commit `4d85041`. Nothing in the repo was modified except this file.

## How this was measured

- **Tests and timings ran inside the running `dressme-backend-1` container** (Python 3.13.17, pymongo 4.13.2, FastAPI 0.161.1, pydantic 2.14.1, MongoDB 7.0.45 in `dressme-mongo-1`). The host cannot run them: the host Python (3.14.6) and the repo `.venv` (3.13.9) have no `fastapi` installed.
- The only database written to was `dressme_test` (the test suite's own database; a measurement script also created and dropped it). The main database `dressme` was only **read** (to copy the real 9-item wardrobe and the real scan candidate into `dressme_test` for the timing). Its document counts were identical before and after (users 1, items 9, candidates 1, chats 6, events 25).
- The measurement script lives outside the repo, in the session scratchpad. `git status` is clean apart from this report.
- Git Bash rewrites `/app/...` container paths (first attempt exit 128, nothing run); set `MSYS_NO_PATHCONV=1` or use PowerShell for `docker exec -w`.
- Line numbers are from the files as they are now. `UNKNOWN` = could not be determined; what was checked is written next to it.

---

## A. Repository and environment

**1. Git state**
- Branch: `feature/docker` (7 commits ahead of `main`; no `origin/feature/docker`, so not pushed).
- Last 5 commits:
  - `4d85041` 2026-10-23 Docker: README section, project notes, final spec and plan
  - `5084151` 2026-10-23 test_chat_dataset: connect with MONGO_URL like the other tests
  - `bc64377` 2026-10-23 Docker: compose with MongoDB, backend and frontend, health checks, GPU option
  - `dce7557` 2026-10-23 Docker: backend image (Python 3.13.17, PyTorch 2.14.1 CPU build, pinned versions)
  - `082d425` 2026-10-22 Docker: one-time setup script (backend/.env, chat model, file check)
- Uncommitted changes: none (`git status --porcelain` shows only the branch line, before and after the measurements). No stashes. Ignored folders present: `.venv/ .vscode/ backend/.env backend/storage/ data/ frontend/dist/ frontend/node_modules/ logs/ models/`.

**2. OS / shell, and DEMO.md**
- Windows 11, Windows PowerShell 5.1 as the main shell. Evidence: `docker/setup.ps1` (README:272-273 runs it with `powershell -ExecutionPolicy Bypass -File docker\setup.ps1`), DEMO.md assumes "MongoDB (Windows service)" and "Ollama (tray icon)" (DEMO.md:19), CLAUDE.md names the local RTX 2050 GPU.
- DEMO.md (55 lines), about an 8-minute jury demo on one laptop, the team drives, everything local:
  - **The day before (lines 7-15):** `git pull` on `main`, `python -m pytest` in `backend/` passes, `npm run build` in `frontend/` passes; `backend/.env` has `JWT_SECRET`, `CHAT_ENGINE=ollama`, `OLLAMA_MODEL=dressme-chat-v4`, `ollama list` shows the model, keep a Gemini key as backup; rehearse the chat; `python -m app.seed_demo` (API running) makes the demo wardrobe of 17 PolyVore pieces + admin account; pick 2 scan photos (A = near-twin, expect **skip**; B = gap filler, expect **buy/think**) and scan both once; write down 2 chat questions that worked.
  - **30 minutes before (lines 19-24):** start MongoDB and Ollama; `cd backend` then `uvicorn app.main:create_app --factory --port 8000` (models load in ~1 min, wait for "Application startup complete"); warm up the chat (first answer ~35 s) and check `ollama ps` PROCESSOR shows GPU; `cd frontend` then `npm run dev`, open http://localhost:5173 as `demo@example.com`; second window as `admin@example.com` on `/admin`; zoom ~125 %.
  - **Run order (lines 28-38), 9 steps:** Login (language switch) → Wardrobe → Scan photo A (skip) → Similar pieces → Scan photo B (buy/think + best outfits) → Assistant (chat, "how I answered") → Build (score, "Complete it with") → Today + Profile (modesty 4, Arabic RTL) → Admin (Overview, Model quality, Formula).
  - **Closing numbers (line 40):** classifier beats the FashionCLIP baseline on every field; outfit scoring 78.7 % AUC on street photos.
  - **If something goes wrong (lines 44-53):** server unreachable, chat off / slow / wrong, bad label, verdict differs, ports busy.
  - **Line 55:** do not press "Save to CSV" on Admin > Formula during the demo (rewrites `mappings/compatibility_weights.csv`).

**3. How things start**
- Backend: from `backend/`, `uvicorn app.main:create_app --factory --port 8000` (README:217, DEMO.md:20); docs at `/docs`. In Docker: `uvicorn ... --host 0.0.0.0 --port 8000` (`docker/backend.Dockerfile:35`).
- Frontend: from `frontend/`, `npm install` then `npm run dev` (README:241-242), port 5173; Vite proxies `/api` to `http://127.0.0.1:8000` and strips the prefix (`frontend/vite.config.ts:11-16`); `DRESSME_API` overrides the target.
- Docker (all three): `docker compose up`. Currently running and healthy for 11 h: `dressme-mongo-1` (mongo:7.0.45, :27017), `dressme-backend-1` (:8000), `dressme-frontend-1` (:5173). Ollama runs on the host (127.0.0.1:11434).

**4. Versions and where dependencies are declared**
- Python: `requirements.txt:1` says "Python 3.11+; tested with Python 3.13"; Docker pins `python:3.13.17-slim-trixie` (`docker/backend.Dockerfile:10`). Host default is 3.14.6; the repo `.venv` is 3.13.9 but lacks the backend packages.
- Node: no `engines` field in `frontend/package.json`; Docker uses `node:24.22.1-bookworm-slim` (`docker/frontend.Dockerfile:6`); host has Node v24.18.0, npm 11.16.0.
- Declared in: `requirements.txt` (pandas, numpy, scipy, scikit-learn, pillow, matplotlib, reportlab), `requirements-models.txt` (install GPU PyTorch first, per its header), `requirements-llm.txt` (unsloth), `requirements-scraping.txt`, `backend/requirements.txt` (fastapi>=0.115, pymongo>=4.9,<4.14, bcrypt, pyjwt, google-genai, gradio_client, rembg[cpu], pytest, httpx ...), `docker/constraints.txt` (exact pins used by Docker), `frontend/package.json` + `package-lock.json` (React ^19.2.8, Vite ^8.3.0, Tailwind ^4.3.3, TypeScript ~6.0.2, react-router-dom ^7.18.4).
- Running `backend/.env` in the container (non-secret keys only): `CHAT_ENGINE=ollama`, `ROUTER=llm`, `OLLAMA_MODEL=dressme-chat-v4`, `REMOVE_BACKGROUND=1`, `CLOTH_MODEL=u2net_cloth_seg`, `TRYON_ENGINE=space`, `WEATHER_ENGINE=open-meteo`.

---

## B. Testing setup

**5. `create_app` signature and injectable services** (`backend/app/main.py:29-30`)

```python
def create_app(settings=None, analyzer=None, catalog=None, chat_engine=None, remover=None,
               tryon_engine=None, weather_engine=None)
```

| Parameter | Used as (lifespan, `main.py:35-50`) |
|---|---|
| `settings` | `settings or Settings()`, then `settings.check()` (JWT secret ≥ 32 chars) |
| `analyzer` | `app.state.analyzer = analyzer or Analyzer()` |
| `catalog` | `app.state.catalog = catalog or Catalog()` (real `app.ml` is imported only if either is None, so passing only one still loads the other for real) |
| `remover` | `remover or load_remover(settings, classify_for_mask)`; `None` + `remove_background=False` = no cleaning |
| `chat_engine` | `chat_engine or make_engine(settings)` |
| `tryon_engine` | `tryon_engine or make_tryon(settings)` |
| `weather_engine` | `weather_engine or make_weather(settings)` |

**Not injectable** (always built): the database (`connect(settings)`, `main.py:37`, chosen by `settings.mongo_url` / `mongo_db`), `ListingIndex()` (`:48`), `JobRunner(db, storage_dir)` (`:50`), `backfill_gender(db)` (`:49`). Routers included at `:56-58`; `GET /health` defined inline at `:60-62`.

**6. Fakes and the test database** (`backend/tests/conftest.py`)
- Fakes: `FakeAnalyzer` (`:37-73`; reads the photo's mean colour: red→top/t-shirt, blue→bottom/jeans, black→shoes/sneakers, green→dress, white→bag; vector = `fake_vector(sum(rgb))`, all fairly similar), `FakeCatalog` (`:76-100`), `FakeChatEngine` (`:103-145`, calls tools by keyword in the message), `FakeTryOn` (`:148-165`), `FakeWeather` (`:168-179`, real engine with a canned Open-Meteo answer). Helpers `photo()`, `sign_up()`, `upload()`.
- Fixtures: `settings` (`:198-202`: `mongo_db="dressme_test"`, per-test `tmp_path/storage`, `gemini_api_key=""`, `remove_background=False`), `make_client` (`:205-222`), `client` (`:225-227`).
- Database lifecycle: `make_client` runs `MongoClient(url).drop_database("dressme_test")` **before** the test (`:207`) and again **after** (`:222`). It drops the whole database, not collection by collection; indexes are recreated by `connect()` when the app starts (`TestClient.__enter__`). Tests share the Mongo **server** with the dev data (different database name; `MONGO_URL` from the environment).
- Other database: `tests/test_chat_dataset.py:27-31` uses `dressme_test_chatsft` (dropped afterwards).
- Tests that edit CSVs use temporary copies: `test_admin.py:83-87` (`temp_mappings`), `test_source_check.py:15-18`, `test_gender_rules.py:14-16`.

**7. `DRESSME_SLOW=1` and the current run**
- `DRESSME_SLOW=1` only un-skips `tests/test_real_models.py` (`:14`, `pytestmark = skipif(DRESSME_SLOW != "1")`): `test_analyzer_on_test_photos` (`:23`), `test_catalog_search` (`:39`), `test_explain_on_a_test_photo` (`:46`). They load the real `app.ml.Analyzer` / `Catalog` and need `data/` + `models/`.
- Result of `docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q`: **307 passed, 3 skipped (the three real-model tests), 0 failed, 163.86 s** (wall 172 s). 310 tests collected. The timing-sensitive `test_jobs.py::test_run_to_the_end_with_log_and_progress` (flagged in CLAUDE.md) passed this time. CLAUDE.md says "~305 tests, ~3 min".

---

## C. Facts the upgrade depends on

**8. The save behind `POST /items`, and "Bought it"**
- It is **not a separate function**: the save is inline in the route handler `add_item` (`backend/app/routers/items.py:84-95`). Shared helpers: `read_photo` (`:27-31`) → `open_photo` (`:34-49`: size cap 413, not-a-picture 400, EXIF rotation, RGB, thumbnail to 1024 px) then `on_white(img, remover.mask(img))` if a remover exists; `analyse` (`:52-58`).
- What it writes:
  - **`items` document:** `user_id, category, sub_category, pattern, colour` (colour emptied if confidence < the cut, `wardrobe.py:13-20`), `predicted` {category, sub_category, pattern, colour → value, conf, alternatives, unsure}, `vector` (FashionCLIP, float16 `Binary`), `coverage: None`, `season: []`, `usage: []`, `corrected: []`, `created_at`, `_id` = new `ObjectId`.
  - **Photo file:** `<storage_dir>/<user_id>/<item_id>.jpg`, JPEG quality 85, the cleaned photo only (the original is not kept) (`items.py:90-92`).
  - **Event:** `log_event(db, "upload", user_id, category=...)` (`:94`).
  - Returns `item_out(doc)`.
- `POST /analyze` (`items.py:154-166`) uses the same `read_photo` + `analyse`, but stores a **`candidates`** document with the JPEG inside it (`photo` Binary), TTL 24 h (`db.py:30`), and logs `scan`.
- **"Bought it"** (`frontend/src/pages/ScanPage.tsx:76-87`, button `:200-202`, only shown after a verdict): `addToWardrobe` calls `api.addItem(file)` (= `POST /items` with the **original picked file**, `client.ts:108`), then `api.updateItem(item.id, patch)` (= `PATCH /items/{id}`) if the user made corrections on the Scan page, then navigates to `/wardrobe/:id`. So it is the **same backend save as Add, not a promotion of the candidate**: the photo goes through background removal and the models a second time (results can differ from the scan), no `candidate_id` is sent, the candidate stays until its TTL, and the event log gets an extra `upload` (plus `correction` if patched).

**9. Do response models drop new fields? Are TS types generated?**
- No route declares `response_model` (grep over `backend/app`: none). Routes return plain dicts, so extra keys reach the client automatically.
- **But the dicts are hand-built whitelists**, so a new field stored on a document is **not returned** unless added: `item_out` (`wardrobe.py:23-37`: id, category, sub_category, pattern, colour, coverage, season, usage, predicted, corrected, image_url), `describe` / `short_item` (`:54-65`), `outfit_out` (`:68-84`), `profile_out` (`routers/auth.py:14-18`).
- Request models (`backend/app/schemas.py`) are plain pydantic `BaseModel`s with no `model_config`: **unknown request fields are silently dropped** (verified: `ItemUpdate(colour='red', brand='x').model_dump(exclude_unset=True)` → `{'colour': 'red'}`; `BuyAdvice(candidate_id='a', foo=1)` ignores `foo`). So a new field must be added to `ItemUpdate` (`schemas.py:47-74`) to be patchable.
- Frontend types are **hand-written** (`frontend/src/api/types.ts:1-2`: "Keep in sync with backend/app/wardrobe.py ..."); no codegen (`frontend/scripts/` holds only `make-guilloche.mjs`; no openapi tool in `package.json`). `client.ts:67` casts `body as T` with no runtime validation, so extra JSON fields pass through at runtime but are invisible to TypeScript until the type is edited.

**10. Admin account deletion** (`backend/app/routers/admin.py:149-158`, `DELETE /admin/users/{user_id}`)
- Guard `other_user` (`:129-136`): 404 if missing, 400 if it is your own admin account.
- **Hard-coded** list: `for coll in ("items", "candidates", "chats", "events", "outfit_feedback"): db[coll].delete_many({"user_id": ...})` (`:153-154`). A new user-keyed collection is **not** deleted unless added there.
- Then `delete_seller_listings(db, storage_dir, user_id)` (`routers/listings.py:251-255`): unlinks `<storage>/listings/<id>.jpg` thumbnails of the user's seller listings (`source_id == SELLERS`, `seller_id == user`) and deletes those listings; `listing_index.invalidate()`; `users.delete_one`; `shutil.rmtree(<storage>/<user_id>, ignore_errors=True)` (`:158`), which removes item photos and the copied listing-candidate photos.
- Not touched (not per-user): `listing_runs`, `listing_jobs`, `source_checks`, other sources' listings. Not transactional (standalone Mongo). There is **no self-service account deletion** endpoint.

**11. `POST /buy-advice`**
- Route: `buy_advice` in `backend/app/routers/outfits.py:160-186`; engine: `compatibility.buy_advice` (`src/phase4/compatibility.py:447`) and `explain_outfit.buy_explanation` (`src/phase4/explain_outfit.py:139`).
- Input: `BuyAdvice {candidate_id: str, corrections: ItemUpdate | None}` (`schemas.py:91-93`); auth `gendered_user` (409 `gender_required`). Steps: `own_item(..., collection="candidates")` (404 otherwise) → if corrections, `apply_update` and **save them on the candidate** (`update_one $set`) → load wardrobe → `compatibility.buy_advice(to_compat(cand), wardrobe, user_profile(...), rules)` → `log_event("verdict", verdict=...)` → `buy_explanation`, decorate with `short_item`.
- Response (checked against a real call):

```
{ verdict: "buy"|"think"|"skip", good_outfits: int, reasons: [str],
  candidate: item_out(kind="candidates"),
  best: [ {score, parts{style,colour,pattern,structure}, reasons[], items[{id,category,sub_category,colour,image_url}],
           contributions[{part,weight,counted,value,points,max_points,why_not}],
           explanations[{code,part,sign,params}]} ]   // up to 3
  explanation: { path{good,buy_min,think_min,verdict},
                 beats[{item_ids,owned_id,owned_score,margin,owned|null}],
                 lost_to[{owned_id,outfits,owned}], near_misses:int,
                 to_next_verdict:int|null, twins[{item,similarity}] } }
```

  (`compatibility`'s internal `detail` is not in the response.)
- Stored? The **result is not stored anywhere**. Side effects: corrections on the `candidates` doc, and an `events` row `{type:"verdict", user_id, at, verdict}` (no candidate id, no score).
- **Timing** (in-process `TestClient`, fake analyzer; the buy-advice code path uses no model; DB `dressme_test`; wardrobe = copy of the real 9 items with real vectors; candidate = the real scan; verdict `skip`, 0 good outfits; excludes network and photo upload):
  - 9 items, 5 requests: **131, 47, 46, 47, 49 ms** (median 47 ms).
  - 18 items (3 runs): 89, 95, 92 ms. 36 items (3 runs): 256, 275, 269 ms.
  - Not measured: a wardrobe that yields many good outfits (the owned-piece scoring loop in `buy_advice` runs only for outfits scoring ≥ `good_outfit - 20`, so the cost can differ).

**12. Reason codes and events**
- **No enum or CSV.** Two layers, both in code:
  1. Free-text English `reasons` strings written inline in `compatibility.py` (e.g. "no shoes", "missing a top or a bottom", "a full piece and a bottom together", "N items of {cat}", "{a} and {b} don't go together", "you already own N very similar {category} item(s)", filter reasons "coverage X is below your level Y", "not for {season}"). The app translates them with a regex table `REASONS` (`frontend/src/i18n/index.tsx:32`, applied by `reason()` at `:104`); unknown text is shown as is.
  2. Structured lines `{code, part, sign, params}` built by `line()` (`compatibility.py:159`). Negative codes (`compatibility.py`, in `problems`): `style_unlike_you`, `style_mixed`, `colour_clash`, `colour_too_bold`, `pattern_clash`, `structure_no_shoes`, `structure_incomplete`, `structure_full_and_bottom`, `structure_over_limit`, `structure_pair`. Positive codes (`explain_outfit.strengths`, `explain_outfit.py:58-87`): `style_coherent`, `colour_pair`, `colour_neutral_base`, `pattern_one_bold`, `pattern_calm`, `structure_complete`. Sentences in en/fr/ar: `frontend/src/i18n/explain.ts` (`explainLine`, a `texts` map keyed by code; unknown code falls back to the code).
  - Verdicts are the strings `buy | think | skip` (`compatibility.buy_advice`; TS `Verdict`, `types.ts:11`).
- **Events** (`backend/app/events.py`): `log_event(db, kind, user_id, **extra)` (`:17-18`) inserts `{type, user_id, at (UTC), **extra}`; no validation of `kind`. `EVENT_TYPES = ["upload","scan","verdict","correction","chat","tryon"]` (`:14`), used only by `routers/admin.py:63,72` (stats). A type not in that list gets a key in the per-day row but is left out of `totals`. Index `(at, type)` (`db.py:32`).
- Existing events and where they are written: `upload` (`items.py:94`, category), `scan` (`items.py:165`, category; `listings.py:247`, category + `source="listing"`), `verdict` (`outfits.py:174`, verdict), `correction` (`items.py:116`, fields), `chat` (`chat.py:62`, tools + agent), `tryon` (`tryon.py:93`, garments). The chat tool `buy_advice_last_scan` does **not** log a `verdict`.

**13. MongoDB**
- Running: **MongoDB 7.0.45** in Docker (`docker-compose.yml`, `image: mongo:7.0.45`; `db.version()` = 7.0.45). pymongo in the container 4.13.2.
- **Standalone, not a replica set:** `rs.status()` → `NoReplicationEnabled`; `hello.setName` empty; command-line options only `net.bindIp "*"`. Multi-document transactions are therefore **not available** in the current setup.
- CLAUDE.md still says "local MongoDB 4.0" (the reason for `pymongo<4.14`). That is not what is running now. Whether a Windows MongoDB service exists on this PC for the jury demo: **UNKNOWN** (no `mongod` on PATH, `Get-Service *mongo*` found none; ports 27017/8000/5173 are owned by Docker).

**14. Scan vs Add**
- Frontend, shared: `ui/PhotoPicker` (`ScanPage.tsx:16,100`; `WardrobePage.tsx:15,65`), then `ui/Field` `FieldRow` and `ui/ExplainPanel` for the labels (Scan page, and the item page that Add navigates to). Both upload through `photoForm` (`client.ts:72-76`: form field `photo`).
- Different: Add = `api.addItem` → `POST /items` (`WardrobePage.tsx:36-45`), lands on `/wardrobe/:id`, corrections saved at once with `PATCH`; Scan = `api.analyze` → `POST /analyze`, corrections kept in local state (`ScanPage.tsx:23-29,161-164`) and sent with the verdict request.
- Backend, shared: `read_photo` / `open_photo` / `on_white`, `analyse()` (analyzer + `fields_from_analysis`), `item_out`. Different: collection (`items` vs `candidates`), photo storage (file vs bytes in the document + 24 h TTL), event type (`upload` vs `scan`).

**15. Do the other verdict paths call the same function?**
- `/buy-advice`: `ScanPage.askVerdict` (`ScanPage.tsx:63-74`) → `api.buyAdvice` (`client.ts:115`) → `POST /buy-advice` → `routers/outfits.py:160` → `compatibility.buy_advice` (`outfits.py:172`).
- **Chat tool `buy_advice_last_scan`:** `POST /chat` → `routers/chat.py:33` → Shopping advisor tool (`agents/shopping.py:55-70`) → `compatibility.buy_advice` **directly** (`shopping.py:63`), not through the route function. It takes the user's most recent candidate (`find_one(..., sort created_at desc)`), logs no `verdict` event, returns the short form (`outfit_out` without `explain`) and no `explanation`. Same helpers: `wardrobe()`, `user_profile()`, `to_compat()`, the user's `rules`. The Explainer's `explain_verdict` (`agents/explainer.py:215-237`) also calls `compatibility.buy_advice` directly (`:223`) plus `buy_explanation`.
- **Shops listing verdict:** `ShopPage.tsx:143-150` → `api.listingCandidate(id)` (`client.ts:169`) → `POST /listings/{id}/candidate` (`routers/listings.py:227-248`: copies the listing into `candidates`, logs `scan` with `source="listing"`) → `api.buyAdvice(cand.id)` → the **same `POST /buy-advice`**.
- All callers of `compatibility.buy_advice`: `routers/outfits.py:172`, `agents/shopping.py:63`, `agents/explainer.py:223`, `src/phase4/evaluate_compatibility.py:201`, and two tests (`test_outfit_explain.py:136,167`).

**16. Outfit endpoints for 0, 1 and 2 items, and per-outfit vectors**

Measured with the fake analyzer (so style/colour numbers are not realistic; the structural behaviour is):

| Wardrobe | `GET /outfits/suggest` | `POST /outfits/score` | `POST /outfits/complete` |
|---|---|---|---|
| 0 items | 200 `[]` | `[]` → 422 (`item_ids` min 1; `schemas.py:77`) | `[]` → 422 |
| 1 item (top) | 200 `[]` | `[top]` → 200, score 60.0, parts style null, colour null, pattern 1.0, structure 0.3, reason "missing a top or a bottom" | `[top]` → 200 `[]` |
| 2 items (top + bottom) | 200, 1 outfit, score 80.0, reason "no shoes" | `[top,bottom]` → 200, score 80.0 | `[top]` → 200, 1 result (the bottom), score 80.0 |
| 2 items (top + shoes) | 200 `[]` | `[top,shoes]` → 200, **score 86.0**, reason "missing a top or a bottom" | not run |

- `GET /insights` with 0 items: 200, `total 0`, `outfits.good 0`, `missing ["main","shoes"]`.
- Observation: an incomplete outfit can score above `good_outfit` (60) on `/outfits/score` (top + shoes = 86.0), because missing parts are left out and the weights rescaled; `suggest` and `buy_advice` avoid this by building outfits only from top+bottom or full-piece "cores".
- Per-outfit vector: **yes, it exists but is not exposed.** `compatibility.outfit_vector(items)` (`compatibility.py:149`) = normalised mean of the items' FashionCLIP vectors (None if none). It is used only by `POST /outfits/feedback` (`outfits.py:118`) and stored in `outfit_feedback.vector`. The taste vector is `compatibility.user_style_profile(items, feedback, rules)` (`:125`), a unit vector or None (needs ≥ `style_profile_min_items` = 3 vectors, or feedback), computed per request in `routers/outfits.py:47-62` and passed as `profile["style_vector"]`. `style_part` (`:187`) compares the taste vector with **each item** vector (mean dot product, blended by `style_personal_weight` 0.25), not with an outfit vector. API answers never include vectors (`outfit_out` whitelist).

**17. `wardrobe_insights` and the profile endpoint**
- `missing` (`compatibility.py:522`, `wardrobe_insights`), computed on the items left after the personal filters: `"main"` if there is no upper, lower or full piece; `"bottom"` if there are uppers but no lowers and no fulls; `"top"` if lowers but no uppers and no fulls; `"shoes"` if no item has category `shoes`. Slots come from `mappings/outfit_structure.csv`.
- There is no "unused" field; the equivalent is `unmatched` = main pieces (slot upper/lower/full) that appear in **no good outfit** (score ≥ `good_outfit` = 60) among the outfits `_outfits()` builds (only the best `TOP_CORES` = 60 cores are completed; `complete` is False when there were more). Shoes, bags and other extras are never listed as unmatched. Also returned: `versatile` (router keeps top 3, `routers/insights.py:22`), `new_pairs`, `filtered` (ids hidden by the modesty filter; the insights route passes no season/occasion), `twins`.
- Profile update: `PUT /me` (`routers/auth.py:53-58`), body `ProfileUpdate` (`schemas.py:25-36`): `name` (1-60), `min_coverage` (1-5), `language` (`fr|ar|en`, `vocab.py:25`), `gender` (`men|women`); only sent fields are written, as `users.profile.<field>`. `GET /me` returns `id, email, role, demo`, the profile fields and `needs_gender`. Registration creates `profile {name, gender, min_coverage: None, language: "en"}` (`auth.py:25-26`). Admin can also `PATCH /admin/users/{id}` (`disabled`, `role`). No other profile fields exist.

**18. Does cloth-seg keep every garment?** No: **only the largest one.** `backend/app/background.py`:
- `BackgroundRemover.mask` (`:48-55`) takes the U2-Net object mask; the cloth-seg step runs only if `use_cloth_mask` (`:97-99`): classifier category in `GARMENT_CATEGORIES` (top, bottom, dress, outerwear, traditional, swimwear; **not** shoes, bag, accessory) with confidence ≥ 0.55.
- `keep_garment` (`:73-94`): cloth-seg gives one class per pixel (1 upper, 2 lower, 3 full body; `clothes()` `:63-70`); it counts object pixels per class and keeps only the **argmax** class (`:77-79`). If that garment covers < 3 % of the photo or > 85 % of the object, the U2-Net mask is returned unchanged (`:81-82`). So in an outfit photo, the smaller garment (e.g. trousers under a bigger coat) is erased to white; shoes/bags/accessories have no cloth-seg class.
- `on_white` (`:102-115`) then crops around the mask (3 % minimum share, else keeps the original photo). Running config: `REMOVE_BACKGROUND=1`, `CLOTH_MODEL=u2net_cloth_seg`.

---

## D. Inventory of the existing chat (nothing deleted)

Legend for "Outside dependence": who outside the chat imports or relies on it.

### D1. Backend

| Item | Where | Outside dependence |
|---|---|---|
| Chat router: `POST /chat`, `GET /chat/history`, `DELETE /chat/history`; `NO_ANSWER` texts; `HISTORY = 20` | `backend/app/routers/chat.py` (82 lines) | Included in `main.py:56-57`; imports `AGENTS`, `route`, `answer_pictures`, `ChatMessage`, `log_event`. Nothing else imports it. |
| Engines: `ChatUnavailable/ChatBusy/ChatQuota` (`:32-41`), `make_engine` (`:44`), `GeminiEngine` (`:51`), `tool_schema` (`:131`), `run_tool` (`:146`), `clean_model_text` (`:167`), `OllamaEngine` (`:187`) | `backend/app/chat_engine.py` (282 lines) | `main.py:18,45` **builds an engine at every start-up** (no key needed to build it), `create_app(chat_engine=...)`; used by `agents/router.py:17`, `routers/chat.py:15`; `src/phase4/build_chat_dataset.py:68` (`tool_schema`), `evaluate_chat_e2e.py:32`; tests. |
| Agents package: `AGENTS` (5), `DEFAULT_AGENT = "stylist"` | `backend/app/agents/__init__.py` | `routers/chat.py`; `src/phase4/build_chat_dataset.py:66`, `evaluate_chat.py:45`, `evaluate_chat_e2e.py:31`; tests. |
| Shared agent code: `Agent`, `system_prompt`, `with_attachments`, `answer_pictures`, `chat_actions`, `list_wardrobe_tool`, trace helpers (`short_value`, `one_line`) | `agents/common.py` | Chat only (plus the dataset builder and tests). |
| Router: `route()`, `by_keywords`, `load_keywords`, `router_prompt` | `agents/router.py` | Chat only; reads `mappings/agent_keywords.csv` (`:21`). |
| Stylist: `suggest_outfits`, `score_outfit`, `complete_outfit`, `get_weather` | `agents/stylist.py` | Imports `routers.outfits` helpers and `weather.WeatherUnavailable`. |
| Shopping advisor: `buy_advice_last_scan`, `search_listings`, `find_similar` (+ `group_same`, `short_listing`) | `agents/shopping.py` | Imports `listings.listing_out/listing_query`, `routers.outfits` helpers. |
| Wardrobe analyst: `wardrobe_insights`, `wardrobe_stats`, `find_near_twins` | `agents/analyst.py` | Imports `routers.insights.wardrobe_counts` (a **screen** function reused by the agent). |
| Seller assistant: `pieces_to_sell`, `price_hint`, `my_listings`, `prepare_sell` | `agents/seller.py` | Imports `resale.py`, `listings.SELLERS`. |
| Explainer: `explain_outfit_tool`, `what_if`, `explain_labels`, `explain_verdict`, `explain_similarity`, `how_scoring_works` | `agents/explainer.py` | Imports `explain_outfit`, `explain_similarity`, `ml.unsure` (all also used by screens, see D3). |
| Resale price rule: `load_rules`, `price_range` | `backend/app/resale.py` (73 lines) + `mappings/resale_pricing.csv` | Used **only** by `agents/seller.py:14` and `tests/test_resale.py`. |
| Request schema `ChatMessage` | `backend/app/schemas.py:96-97` | Chat only. |
| Settings | `backend/app/config.py:50-59` (`chat_engine, router, ollama_url, ollama_model, ollama_num_ctx, gemini_api_key, gemini_model`), `:55-57` (`ollama_timeout, ollama_temperature, ollama_max_tokens`), docstring `:8-15` | Read by `make_engine`, `routers/chat.py`/`agents/router.py` (`settings.router`). |
| Dependency | `backend/requirements.txt` (`google-genai`) | Gemini only. |

**Collection and index:** `chats` (fields `user_id, role, text, tools, attachments, actions, agent, routed_by, trace, created_at`; written by `routers/chat.py:54-61`), index `user_id_1_created_at_1` (`db.py:31`). **Events:** type `chat` with `tools`, `agent` (`chat.py:62`; `events.py:14`).

**Outside code that touches chat data:**
- `routers/admin.py:153` deletes `chats` when a user is deleted; `admin.py:63,72` count `chat` events (stats key `chat`).
- `routers/admin_xai.py:63-90` reads `db.chats` traces (`trace_stats`, the `traces` key of `GET /admin/xai`).
- `main.py:18,45,56`.
- `seed_demo.py` and `xai_results.py`: no chat reference found.

### D2. Frontend

| Item | Where | Outside dependence |
|---|---|---|
| Chat page | `frontend/src/pages/ChatPage.tsx` (187 lines) | Route `App.tsx:11,74` (`/chat`); nav item `shell.tsx:15` (`navChat`, `MessageCircle`). |
| API calls `chat`, `chatHistory`, `clearChat` | `frontend/src/api/client.ts:178-183` | Chat page only. |
| Types `ChatTurn` (`types.ts:254`), `TraceStep`, `ChatAction` (`:272`), `ChatAttachment` (`:278`) | `frontend/src/api/types.ts` | Imported in `client.ts:4,6`. |
| **Admin stats** | `types.ts:294` `DayStats.chat` / `Stats.totals.chat` are **required** fields; `admin/AdminPages.tsx:16,84,107,132` show "chat messages" | Removing the `chat` event type would break these. |
| Admin XAI | `admin/XaiPage.tsx:2,120-126` ("Chat: what the agents' tools did"), `types.ts:~501` `traces` | Depends on `GET /admin/xai` `traces`. |
| i18n keys (en/fr/ar, all typed `Record<StringKey,string>`): `chatTitle, chatEmpty, chatPlaceholder, chatPictures, chatUnavailable, clearChat, howAnswered, send, navChat`, 5 × `agent_*` (stylist, shopping, analyst, seller, explainer), 21 × `tool_*` (list_wardrobe, suggest_outfits, score_outfit, buy_advice_last_scan, complete_outfit, get_weather, search_listings, find_similar, wardrobe_insights, wardrobe_stats, find_near_twins, pieces_to_sell, price_hint, my_listings, prepare_sell, explain_similarity, explain_outfit, what_if, explain_labels, explain_verdict, how_scoring_works) | `frontend/src/i18n/strings.ts` (`en` from line 4, `fr` 326, `ar` 636) | Checked: used by `ChatPage.tsx` only (and `navChat` by `shell.tsx`); `loading` is also used by `WardrobePage.tsx` and must stay. |
| Screens that chat actions open | `SellPage.tsx:28-50` (prefill from `?item=&price=&title=&size=`), `WardrobePage.tsx:122` (`?why=1`) | Normal screens; they work without the chat. |

### D3. Shared code the chat uses or that looks chat-only but is not

- **Used by both screens and the Explainer agent (do not remove):** `src/phase4/explain_outfit.py` (`routers/outfits.py:15`, `/outfits/*`, `/buy-advice`), `src/phase4/explain_similarity.py` (`outfits.py:17`, `/similar`), `src/phase4/explain.py` (`ml.py`, `routers/explain.py`), `routers.insights.wardrobe_counts` (Insights screen + Analyst), `routers.outfits.wardrobe/user_profile/rules_of/profile` (every route + all agents), `weather.py` (Today page + Stylist), `listings.py` helpers (Shop page + Shopping/Seller agents). Frontend `ExplainPanel`, `ScoreWhy`, `VerdictWhy`, `SimilarWhy` use REST endpoints, not the chat.
- **Chat only:** `chat_engine.py`, `agents/*`, `routers/chat.py`, `resale.py`, `ChatMessage`, the `chats` collection, the `chat` event type (but see D1/D2 for the admin screens that count it).

### D4. Mappings, environment, Docker

- **Mappings CSV (chat-owned):** `mappings/agent_keywords.csv`, `mappings/resale_pricing.csv`. (CSVs the chat reads but shared with screens: `weather_seasons.csv`, `xai_settings.csv`, `style_concepts.csv`, `gender_sub_categories.csv`, compatibility rule files.)
- **Environment variables:** `CHAT_ENGINE`, `ROUTER`, `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_NUM_CTX`, `GEMINI_API_KEY`, `GEMINI_MODEL` (`config.py`, `backend/.env.example`).
- **Docker / setup:** `docker-compose.yml:29` (`OLLAMA_URL: http://host.docker.internal:11434`) and its comment `:4`; `docker/setup.ps1:31-32` (sets `CHAT_ENGINE=ollama`, `OLLAMA_MODEL=dressme-chat-v4`) and `:38-56` (registers the model with `ollama create`).

### D5. Tests (310 collected in total; chat-owned: 109)

`test_chat.py` (28), `test_agents.py` (32), `test_explainer_agent.py` (12), `test_seller_agent.py` (10), `test_chat_trace.py` (3), `test_chat_dataset.py` (13), `test_resale.py` (11). **Indirect:** `conftest.py:103-145` (`FakeChatEngine`) and `:211-213` (every test client passes a chat engine to `create_app`); `test_admin.py:37,40` (posts to `/chat`, checks the `chat` total); `test_admin_xai.py:45-60` (seeds `chats` traces). Not exhaustively checked: gender tests that might call `/chat`.

### D6. Model training, data, evaluation, reports, docs

- **Kaggle notebook:** `kaggle/chat_finetune/` (`chat_finetune_kernel.py`, `kernel-metadata.json`). (`kaggle/hm_images/` is not chat.)
- **Scripts in `src/phase4/`:** `build_chat_dataset.py`, `chat_phrases.py`, `chat_phrases_agents.py`, `finetune_chat.py`, `make_ollama_model.py`, and the evaluation scripts `evaluate_chat.py`, `evaluate_chat_e2e.py`. `requirements-llm.txt` (unsloth).
- **Static references from other generators:** `build_phase4_report.py` (chat section `:44,570-654`), `build_xai_report.py` (`:222-260`, Explainer agent and trace sections).
- **Reports:** `reports/phase4/chat_evaluation.md`, `chat_evaluation.json`, `chat_e2e_evaluation.md`, `darija_review.md`.
- **Data / weights (git-ignored; per CLAUDE.md, not checked on disk):** `data/processed/chat_sft/`, `chat_sft_v1/`, `models/llm/`, `*.gguf` (`.gitignore:31-33`).
- **Docs:** `AGENTS.md`, `LLM.md`, DEMO.md step 6 and its troubleshooting rows, CLAUDE.md Phase 4 items 4, 5 and 7, README, HANDOFF.md, and in `docs/superpowers/`: specs `2026-10-08-ai-agents-design`, `2026-10-08-explainer-agent-design`, `2026-10-08-seller-agent-design`, `2026-10-09-similarity-trace-xai-design`, `2026-10-09-xai-report-admin-design` and plans `2026-10-08-ai-agents`, `2026-10-08-seller-agent` (several other specs mention chat in passing).

---

## E. Counts

**20.**
- **Routers:** 12 router modules in `backend/app/routers/` (auth, items, explain, outfits, insights, chat, listings, tryon, weather, vocab, admin, admin_xai), all included at `main.py:56-57`, plus one inline route `GET /health` (`main.py:60-62`).
- **Endpoints (from `app.openapi()`):** **49 paths, 59 operations**, including `/health`. FastAPI's automatic `/docs`, `/redoc`, `/openapi.json` are not counted. By tag: admin 19, outfits 10, listings 9, wardrobe 8, auth 4, chat 3, explain 2, try-on 1, vocab 1, weather 1, untagged 1 (`/health`). By method: 4 DELETE, 32 GET, 4 PATCH, 16 POST, 3 PUT (full list below).
- **MongoDB collections in use: 10** (`db.py:2-14`, all created with their indexes by `connect()` at start-up): `users` (1 doc now), `items` (9), `candidates` (1, TTL 24 h), `chats` (6), `events` (25), `outfit_feedback` (0), `listings` (0), `listing_runs` (0), `listing_jobs` (0), `source_checks` (0).
- **CSV files in `mappings/`: 34** (no other file types there).

<details><summary>All 59 operations</summary>

```
DELETE /admin/users/{user_id}      DELETE /chat/history               DELETE /items/{item_id}            DELETE /listings/{listing_id}
GET /admin/formula                 GET /admin/jobs                    GET /admin/jobs/{job_id}           GET /admin/jobs/{job_id}/log
GET /admin/listings                GET /admin/listings/overview       GET /admin/model-quality           GET /admin/sources
GET /admin/stats                   GET /admin/users                   GET /admin/xai
GET /candidates/{candidate_id}/explain                                GET /candidates/{candidate_id}/image
GET /catalog/{item_id}/image       GET /chat/history                  GET /health                        GET /insights
GET /items                         GET /items/{item_id}               GET /items/{item_id}/explain       GET /items/{item_id}/image
GET /listings                      GET /listings/mine                 GET /listings/sources              GET /listings/{listing_id}
GET /listings/{listing_id}/image   GET /me                            GET /outfits/limits                GET /outfits/suggest
GET /similar                       GET /vocab/sub-category-gender     GET /weather
PATCH /admin/listings/{listing_id} PATCH /admin/users/{user_id}       PATCH /items/{item_id}             PATCH /listings/{listing_id}
POST /admin/jobs                   POST /admin/jobs/{job_id}/stop     POST /admin/sources/{source_id}/check
POST /analyze                      POST /auth/login                   POST /auth/register                POST /buy-advice
POST /chat                         POST /items                        POST /listings/sell                POST /listings/{listing_id}/candidate
POST /outfits/complete             POST /outfits/explain              POST /outfits/feedback             POST /outfits/score
POST /tryon
PUT /admin/formula                 PUT /admin/xai/settings            PUT /me
```
</details>

---

## Things worth knowing before the upgrade

1. New stored fields do not reach the app until they are added to the hand-written `item_out` / `outfit_out` / `profile_out` and to the TS types; new request fields are dropped unless added to the pydantic models (C9).
2. "Bought it" re-uploads and re-analyses the original photo instead of promoting the candidate (C8).
3. No transactions are possible on the current standalone MongoDB; account deletion uses a hard-coded collection list (C10, C13).
4. `/outfits/score` can give a high score to an incomplete outfit (C16).
5. The tests can only be run in the Docker container on this PC; the host and `.venv` lack the backend packages (B7).
6. CLAUDE.md's "local MongoDB 4.0" and "~305 tests" are out of date against what runs now (MongoDB 7.0.45; 307 passed + 3 skipped).
7. Removing the chat touches more than the chat files: `main.py`, `conftest.py` (all test clients), the `chat` event/stat shown by the admin screens (required TS field), `admin_xai` traces, `delete_user`, the i18n key typing in three languages, and Docker setup (D1-D4).
