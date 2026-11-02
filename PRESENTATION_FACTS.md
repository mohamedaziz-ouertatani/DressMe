# DressMe: facts for the final technical presentation

Written 2026-11-02 from the repository on branch `chat/step-2-traps` (last commit `efc5070`). No code was changed.
Labels: **measured** = a number from a run or a report in the repo; **built, not measured** = the code exists and is
tested, but no accuracy or speed figure exists; **not built** = no code, or code deleted.
Where I could not find evidence in the repo, the line says so. I did not guess.

---

## 1. Agents and router

- **One agent is implemented: the Stylist.** Status: **built, measured** (trap set, section 2).
  - Definition: `mappings/agents.yaml` (`agents.stylist`), 6 tools: `list_wardrobe`, `search_wardrobe`, `get_weather`,
    `suggest_outfits`, `build_outfit`, `score_outfit`.
  - Validation at start-up: `backend/app/assistant/agents.py` (`load_agents`).
  - The loop: `backend/app/assistant/loop.py` `run_turn`. Tool registry: `tools.py` (`Registry.run`).
  - Tools: `tools_wardrobe.py`, `tools_stylist.py`.
  - Piece numbers: `ledger.py` (`PieceLedger`) and `placeholders.py` (the `{n}` rule).
- **Router: not built.** `routers/chat.py` takes `body.agent or next(iter(agents.agents))`, so it always picks the
  first agent. The code carries `TODO(step 3e)`. The `keywords` in `agents.yaml` are stored but never read.
- **The other four agents (planned in step 3e, names not fixed in the repo): not built.** The old five-agent chat was deleted in
  step 3a. It is readable only through the git tag `pre-chat-removal`. Do not present it as current.
- **Request flow today (`POST /chat`):**
  1. The user message goes to `routers/chat.py`, which rewrites any `{12}` the user typed to `12`, so the model
     cannot copy it as a piece number.
  2. `run_turn` calls the model with the shared rules + the Stylist instructions + the 6 tool schemas.
  3. If the model asks for a tool, `Registry.run` runs it. It never raises, and it refuses a tool the agent was not
     given. The tool calls the same function as the screen (for example `suggest_outfits` calls the Dress page's
     route). Results go back with refs 1, 2, 3 (never database ids).
  4. This repeats up to `max_rounds` (6). A repeated identical call stops with `repeat`. Then one last call with no
     tools.
  5. `{n}` markers the tools never gave are removed. The app shows the photos for the valid ones.
  6. One document per turn is saved in `chats`. An event with counts and times is saved, never the text.
- Limits: the message history is **not** sent to the model (every turn is independent). There is no streaming.

## 2. Chat assistant

- **Wired in today: the base `qwen3.5:4b` through Ollama.** Status: **built, measured.**
  - Client: `backend/app/assistant/ollama.py` `OllamaClient`. Settings `CHAT_MODEL` (default `qwen3.5:4b`) and
    `OLLAMA_URL`.
  - `GET /assistant/status` reports whether the model answers. Without Ollama, `/chat` answers 503.
  - The chat screen in the app is **not built**: `/assistant` is still a placeholder page (step 3f is not done).
- **`dressme-chat` (Qwen3-4B-Instruct-2507, QLoRA, Ollama): trained, but not wired in and never evaluated.**
  - It was built for the old chat. `models/llm/dressme-chat` to `-v4` hold the Modelfile and `training_log.json`.
  - Base `unsloth/Qwen3-4B-Instruct-2507`, rank 16, 1 epoch. Training sizes and final loss:

    | version | train conversations | train loss | minutes (Kaggle) |
    |---|---|---|---|
    | v1 | 3,000 | 0.413 | 137 |
    | v2 | 4,000 | 0.262 | 207 |
    | v3 | 4,500 | 0.249 | 256 |
    | v4 | 4,500 | 0.248 | 220 |

  - `dressme-chat-v4` is still in the local Ollama (2.5 GB). The new assistant does **not** use it. A teammate could
    set `CHAT_MODEL=dressme-chat-v4`, but no eval or trap result exists for it. Status: **built, not measured**.
  - The new fine-tune planned for step 3h (QLoRA on `qwen3.5:4b`): **not built**.
- **Eval / trap results (base model only, English only): measured.**
  - Trap set: `bench/assistant/traps.yaml` (24 traps in 11 categories). Runner: `backend/app/eval_traps.py`. Results
    in `bench/results/assistant/`.
  - Latest run (`...T183124`, 10 runs of 24 traps = 240 answers, after prompt "Experiment B"):

    | Measure | Value |
    |---|---|
    | Answers passing every automatic check | **222 of 240 (92%)** |
    | Traps passing in all 10 runs | 17 of 24 |
    | Answers with made-up piece numbers | 1 |
    | Answers writing the user's own numbers as pieces | 7 |
    | Answers showing a forbidden / not-owned piece | 0 |
    | HTTP errors | 0 |
    | Seconds per answer: median / p90 / max | 1.3 / 3.0 / 5.9 |

  - Earlier runs, same set: 64/72 (89%) baseline, 59/72 (82%), 213/240 (89%), 218/240 (91%). The pass rate went up as
    the prompt rules and the user-number fix were added.
  - 100% categories: not_owned, other_user, buy_pressure, body, off_topic, general, small_talk, one_question.
  - Weak spots: `invented_ref` 65% (traps r01 / r02: the user types a piece number), `grounded` 85% (g01 asks "which
    occasion?" instead of calling `suggest_outfits`; g05 / g06 list the pieces without refs), `other_agent` 93% (x01
    once said "buy it" about a 45 dinar jacket).
  - **Limits of the numbers:** automatic checks only (tools, invented numbers, pieces, language, forbidden phrases).
    The human review sheet (tone, truth) is **empty**. French and Arabic runs: **not done** (only `en`). The
    Darija file `bench/assistant/darija_review.md` is a review note, not a result.
  - Earlier live check (8 questions, step 3d, `docs/learn/step-3d.md`): 7 right. The French interview question used
    no tool and invented pieces.
- **Gemini fallback: not in use and not in the code.** Grep finds no Gemini in `backend/`. It belonged to the old
  chat (the `HANDOFF.md` notes about it are old). No second provider exists. The fallback and retries were planned for
  step 3e and are **not built**.

## 3. Search

- **What is built:** `POST /search` (words or photo, never both), `src/phase4/search.py`, `routers/search.py`, the
  chat tool `search_wardrobe`, and the app's `SearchBox`. It uses FashionCLIP 2.0 vectors stored with each piece.
  Status: **built, measured.**
- **Measured precision and coverage on the frozen Encoder Lab exam, TEST split (cuts chosen on validation only):**

  | Track | Cut in force | Precision at the cut (test) | Coverage (test) |
  |---|---|---|---|
  | Words | 0.292 | **0.900** | 0.674 |
  | Photo | 0.792 | **0.772** (target 0.75, the highest reachable; 0.90 was not reachable) | 0.300 |

  Source: `mappings/search_rules.csv`, `reports/phase4/search_calibration_SUPERSEDED.md`, commit `5b7ecfd`. The exam:
  1,000 word questions and 1,000 photo questions per split, wardrobes of 30 pieces, about 30% with no right piece.
  Exam fingerprint: `08e61000...7377867`, `bench/results/phase3/phase3_report.json`.
- **Top-5 results (hit@5 / MRR on the test split): NOT FOUND in the repo.** The lab only left its rules
  (`bench/decision-rule.md`, `bench/tuning-rule.md`), the frozen questions and `phase3_report.json`. The scoring ran
  on Kaggle and its result files were not committed (`bench/exports/` is git-ignored and holds only the splits and
  the term table). Get these from the notebook outputs before the talk.
- **Model comparison (FashionCLIP 2.0 vs Marqo-FashionSigLIP, SigLIP 2, ZooClaw, OpenAI CLIP): the scores are not in
  the repo.** Status for the slide: **result claimed, evidence missing.**
  - What the repo proves: a decision rule was committed **before** scoring (`4d84265`). Requirements: open weights,
    academic licence, at most 500M parameters, sanity grid. Main score: MRR on test, English words. Paired bootstrap,
    1,000 resamples. Model names were revealed only after the winner was computed.
  - `CLAUDE.md` states the outcome: "FashionCLIP 2.0 kept" (decision rule `4d84265`, tuning rule `1fa3bca`).
  - The names Marqo-FashionSigLIP, SigLIP 2, ZooClaw and OpenAI CLIP appear nowhere in the repo. Only
    "Marqo-FashionCLIP" is mentioned, in `docs/learn/step-3b.md`, as a possible future replacement. Do not put
    scores for these models on a slide unless you have the Kaggle output.
- **FashionCLIP tuning (rule `1fa3bca`):** image preparation (crop vs white padding), text prompt, float16 vs
  float32. Chosen on validation. The result of each choice: **not in the repo.**
- **Speed:** words 22 ms, photo 2.9 s (2.3 s of it is background cleaning). Measured on the golden wardrobe, CPU in
  Docker (`docs/learn/step-3b.md`).
- **Limit:** the old step 3b method gave cuts 0.297 / 0.823; those are superseded.

## 4. "Should I buy this?" verdict

Status: **built, tested, partly measured.**

- **Inputs:** the candidate (photo analysed like an upload, or a shop listing), the user's wardrobe, the profile
  (modesty `min_coverage`, optional `budget_tnd`, gender), optional `price_tnd`, the weather season.
- **Rules** (`src/phase4/compatibility.py` `buy_advice`, numbers in `mappings/compatibility_weights.csv`):
  1. Build every outfit that includes the new piece. Score it 0-100 (style / colour / pattern / structure).
  2. An outfit counts as **good** if its score is at least **60** AND the new piece beats every owned piece of the
     same category in that outfit.
  3. Verdict: **buy** if at least **5** good outfits, **think** if at least **1**, otherwise **skip**.
  4. Near twin: FashionCLIP similarity of at least **0.9** to an owned piece of the same category gives the reason
     "you already own N very similar...".
- **Confidence and codes** (`src/phase4/verdict.py` `assess`, `mappings/verdict_rules.csv`):
  - `small_wardrobe` (under 8 pieces), `no_pairing_piece`, `guessed_field` lower the confidence.
  - `fills_gap`, `far_from_style` (cut 0.5), `over_budget` (more than 30% of the budget) only inform.
  - The price estimate (`/price-estimate`) is shown as a range, never a single number.
- **Tested:** 14 golden answer files, including 5 reason codes (section 5).
- **Not measured:** the verdict has **no accuracy figure**. Only the compatibility formula under it was measured:
  PolyVore AUC 66.6% / FITB 42.6%, Fashionpedia 78.7% / 59.5%. Style alone scores better (72.9% / 84.6% AUC). Say so
  if asked.
- **Decision log: built.** The `decisions` collection stores "bought" or "left" (`POST /decisions`,
  `GET /decisions`) with the labels, a copy of the advice shown, and the price paid. Never the photo. It is shown in
  the Wardrobe view.
- **Logistic regression: not built.** Nothing in `backend/` or `src/` learns from the decisions. The verdict is
  rule-based and the thresholds are team-set (all marked REVIEW). **How many decisions are logged: cannot be known
  from the repo** (it lives in MongoDB, not in files). Query it with `db.decisions.countDocuments({})`. Only the
  test database was reachable by me and I did not query the real one.

## 5. Tests

- **Latest full run (today, 2026-11-02, I ran it):** `docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q`
  gives **393 passed, 3 skipped in 166.6 s** (396 collected). Status: **measured.**
- The 3 skipped are the real-model tests (`tests/test_real_models.py`, set `DRESSME_SLOW=1` to run them). I did not
  run those.
- 45 test files in `backend/tests/`. The `CLAUDE.md` figure (314 collected) is **out of date**.
- **Golden outputs** (`backend/tests/golden/`): two frozen wardrobes (`wardrobe.json`: 17 items; `wardrobe_men.json`).
  14 expected answers in `expected/`: `buy_advice_buy`, `_think`, `_near_twin`, `_listing`, 5 `buy_advice_codes_*`,
  `insights`, `outfits_suggest`, `outfits_suggest_men`, `outfits_score`, `outfits_complete`. Compared by
  `test_golden.py` and `test_golden_codes.py` (verdicts, ids, order and reasons exactly; scores within 0.5).
  `GOLDEN_RECORD=1` rewrites them, only in a PR that explains why.
- **Other safety nets:** `test_deletion_complete.py` (deleting an account leaves nothing in any collection),
  `test_search_logic.py` (fails if the search cuts change by accident), `test_agents_yaml.py`.
- **OpenAPI checks: not built.** No test or script validates the OpenAPI schema or a contract. FastAPI serves
  `/docs` and `/openapi.json` automatically, nothing checks them. One mention of "openapi" exists in a report
  builder only.
- Known flaky test: `test_jobs.py::test_run_to_the_end_with_log_and_progress` is timing-sensitive (passed today).
- Frontend tests: none found. `npm run build` is the only check.

## 6. Real phone-photo tests

- **No measured result.** Status: **not built / not measured.**
- `data/raw/Local/` (the team's phone photos, test-only) **does not exist on this computer**. The pipeline
  (`map_local.py`, `LOCAL_PHOTOS.md`) is built, but the embeddings, the classifier evaluation and the compatibility
  evaluation do **not** include `local` yet (`CLAUDE.md`, `reports/phase4/xai_report.md` line 103).
- All reported accuracy numbers use catalogue product shots (Fashion Product, PolyVore, Fashionpedia). Say this on
  the limits slide: real friperie photos are untested.
- Only qualitative evidence: the demo scan photos picked by hand (`DEMO.md`), and the background-removal step built
  for phone photos (section 8).

## 7. The demo

**Works end to end (built, checked by tests, not by me in a browser today):**
login in en / fr / ar, add a piece (photo cleaned and analysed), correct labels, Wardrobe search, Scan with the
verdict and "Why this verdict?", "Bought it / Left it", Similar pieces and H&M look-alikes, Dress (For today / Build),
"Wear this", Wardrobe view, Shops snapshot, Sell, price estimate, Admin. The chat page shows a placeholder.

**Not safe to demo:** the Assistant screen (no chat UI), live shop scraping (blocked, snapshot only), virtual try-on
(needs the internet and a free Hugging Face Space; one broke on 2026-10-04; it falls back to a 2D overlay), the
weather (needs the internet; falls back to the calendar season).

**Steps for "Should I buy this?"** (from `DEMO.md`, `README.md` and `scripts/check_demo.ps1`; the Docker details
come from `CLAUDE.md`):
1. Start Docker Desktop, then in the project root: `docker compose up -d`. Wait about a minute for the models.
2. Run `scripts/check_demo.ps1` (read-only: containers healthy, `/health`, frontend).
3. Make sure the demo wardrobe exists: `python -m app.seed_demo` (the API must be running; 17 PolyVore pieces; the
   passwords are the `DEMO_*` lines in `backend/.env`). Log in as `demo@example.com` at http://localhost:5173.
4. **Prepare two photos the day before** and test them once: **A** a near twin of something owned, expect **skip**
   with "you already own N similar pieces"; **B** a gap filler, expect **buy** or **think**. The golden wardrobe has 3
   scans giving skip / think / buy, but those are in the test files, not photos.
5. Open Buy? (Scan), upload photo A, check the fields, tap Get the verdict. Show the badge, the codes, the big number
   (`good_outfits`), "Why this verdict?", and the price range if a price is entered.
6. Repeat with photo B. Show "Best outfits with it", then tap Bought it or Left it. Show the entry in the Wardrobe
   view under "Bought and left".
7. Do not press Save in Admin > Formula during the demo (it rewrites the weights file).
- `DEMO.md` is partly outdated (it still says `python -m pytest` on the host and `uvicorn` by hand). The Assistant
  line there is still right.

## 8. Measured speeds

| Step | Value | Status / source |
|---|---|---|
| Photo cleaning (resize, U2-Net background removal, cloth-seg crop) | about 2.3 s on CPU in Docker; 3-5 s per photo when cloth-seg runs | measured (`docs/learn/step-3b.md`) / stated (`CLAUDE.md`) |
| Words search | 22 ms median | measured |
| Photo search | 2.9 s median (2.3 s cleaning) | measured |
| Classification of one upload | no per-photo figure | **not measured**. Training ran at about 200 img/s on the GPU (about 20 min per epoch), which is not inference speed |
| Chat answer (base `qwen3.5:4b`, GPU) | 1.3 s median, 3.0 s p90, 5.9 s max over 240 trap answers; earlier hand check 3-10 s | measured |
| Chat model cold load | about 13 s; 170 s for the first call after a reboot (so it can give a 503) | measured once (`docs/learn/step-3d.md`) |
| Chat model memory | 3.4 GB, 100% GPU, `num_ctx` 8192 | measured (`ollama ps`) |
| Virtual try-on | no timing in the repo; depends on the hosted Space and its queue | **not measured** |
| API start-up | about 1 minute until the models are loaded (health becomes healthy) | stated, not timed |
| Full test suite | 166.6 s | measured today |

## 9. API endpoints and MongoDB collections

**Collections (12, from `db.py` and the code):** `users`, `items`, `candidates` (scans, deleted after 24 h),
`decisions`, `wear_log`, `chats`, `events`, `outfit_feedback`, `listings`, `listing_runs`, `listing_jobs`,
`source_checks`. Per-user collections emptied on account deletion (`USER_COLLECTIONS`): items, candidates, events,
outfit_feedback, decisions, wear_log, chats.

**Endpoints:**
- Auth and profile: `POST /auth/register`, `POST /auth/login`, `GET|PUT /me`, `DELETE /me`, `POST /me/consent`.
- Wardrobe: `GET|POST /items`, `GET|PATCH|DELETE /items/{id}`, `/items/{id}/image`, `/items/{id}/explain`, `POST /analyze`,
  `/candidates/{id}/image|explain`, `GET /insights`, `GET /vocab/sub-category-gender`.
- Verdict and money: `POST /buy-advice`, `POST|GET /decisions`, `GET /price-estimate`.
- Outfits: `GET /outfits/suggest|today|occasions|limits`, `POST /outfits/score|complete|build|explain|feedback`.
- Wear: `POST|GET /wear`, `DELETE /wear/{id}`, `GET /wear/summary`.
- Search and similar: `POST /search`, `GET /similar`, `GET /catalog/{id}/image`.
- Shops: `GET /listings`, `/listings/sources`, `/listings/{id}`, `/listings/{id}/image`, `POST /listings/{id}/candidate`;
  seller: `POST /listings/sell`, `GET /listings/mine`, `PATCH|DELETE /listings/{id}`.
- Assistant and extras: `POST /chat`, `GET /assistant/status`, `POST /tryon`, `GET /weather`.
- Admin (prefix `/admin`): users, stats, model-quality, formula (`GET|PUT`), xai (`GET`, `PUT /xai/settings`), listings
  overview, sources (+ `POST /{id}/check`), jobs (start, stop, log).
- Removed: the old chat routes (`/chat/history`). Today `/chat` is the new Stylist turn.
- I counted about 70 route decorators. Open http://localhost:8000/docs for the exact list.

## 10. Known bugs and limits

- **`closest_anyway`: it IS applied in the code.** `find_owned` (`routers/search.py`) cuts the results to 3 when
  nothing is close. Tests check it for the route (`test_search.py`) and for the chat tool (`test_stylist_tools.py`).
  I found no evidence that it is ignored. Check what you saw: in the app the nearest pieces show faded under "No sure
  match", and the chat tool returns them with `close: false`. If you saw more or fewer than 3, tell me where.
- **Router and 4 agents missing**; the chat UI is a placeholder (sections 1, 2).
- **Chat weaknesses (measured):** it sometimes asks "which occasion?" instead of calling a tool (g01); it lists
  pieces without refs (g05, g06); it mishandles piece numbers typed by the user (r01, r02); once it hinted at buying
  (x01). English only is tested; French and Arabic are not. The French interview question was seen to invent pieces.
- **Photo search is the weak one:** precision 0.77, coverage 0.30, and the 0.90 target was not reachable
  (blue / navy and flats / casual shoes look alike).
- **Search model comparison evidence is missing from the repo** (section 3).
- **Verdict:** rule-based, thresholds are unreviewed start values (REVIEW); no accuracy figure; no learning from the
  decisions.
- **Classifier:** traditional (3 of 7 right) and swimwear (1 of 5) are too rare to learn; traditional is read as a
  dress. A colour below 0.7 confidence is left empty on purpose.
- **Compatibility:** colour, pattern and structure add no signal in the swap test; style alone does better. Weights
  are set by the team, so the app deliberately does not use the better number.
- **Real photos untested** (section 6). **Prices** are asking prices from 1,523 classified ads and 183 friperie
  posts; Spearman 0.589, "typical error" about a factor of 2.
- **Shops:** Zara, Bershka and Pull&Bear block scraping, so the app shows a frozen snapshot. H&M France product pages
  answer 403. Exist, Hamadi Abid are approved but their runs were never verified from here.
- **Try-on** depends on free hosted Spaces; the adapters were written from public code and could not be run from the
  cloud container.
- **Flaky:** `test_jobs.py` timing test. The shared Docker volume and `host.docker.internal` need Docker Desktop
  running, and Ollama must be started separately on the PC.
- **Untracked files** in the working tree: `bench/results/`, `bench/phase3_questions.ipynb`, `claude-handoff.md`.
  The trap results are not committed yet.

## 11. The models (what runs in the app)

| Model | Job | Status | Numbers |
|---|---|---|---|
| **EfficientNet-B0** (ImageNet weights, three heads) | category, sub_category, pattern of a photo | built, **measured** | test: category **95.7%**, sub_category **86.4%**, pattern **86.8%**; FashionCLIP linear probe: 88.3 / 79.7 / 74.2. 5 epochs, `models/checkpoints/classifier_best.pt`. Small classes: traditional 3/7, swimwear 1/5 |
| **Colour model** (gradient boosting on Lab histograms, trained on Fashion Product) | primary colour; empty below 0.7 confidence | built, measured (`reports/phase3/colour_estimation.md`) | snapping pixels to the palette was only 25-36% accurate, so this model replaced it. The headline % is in that report, not repeated here |
| **FashionCLIP 2.0** (`patrickjohncyh/fashion-clip`, 512-d) | embeddings, similarity, search, style score, price input | built, measured | search cuts in section 3; used for 306,636 catalogue vectors; kept after the Encoder Lab |
| **Compatibility formula** (weighted: style, colour, pattern, structure) | outfit score 0-100 + verdict | built, measured | PolyVore AUC 66.6% / FITB 42.6%; Fashionpedia 78.7% / 59.5% |
| **Price model** (RBF-kernel SVR over FashionCLIP, rank mapped to the channel's price distribution) | price band for friperie / classified | built, measured (`reports/phase4/price_evaluation.md`) | Spearman 0.589 grouped 5-fold CV; condition factors: new with tags x1.43, like new x1.20, stained x0.55, torn x0.21 |
| **rembg U2-Net + cloth-seg** | remove the background, crop worn items | built, speed measured, accuracy **not measured** | 2.3 s to 5 s per photo on CPU |
| **Qwen3.5-4B** (`qwen3.5:4b`, Q4_K_M, via Ollama) | the Stylist's language model | built, measured (traps) | 222 / 240 automatic checks (92%); 3.4 GB on the GPU |
| **dressme-chat v1-v4** (Qwen3-4B-Instruct-2507 + QLoRA) | old chat | trained, **not wired in**, not evaluated | see section 2 |
| **Virtual try-on** (CatVTON / Kolors / IDM-VTON / OOTDiffusion Spaces) | picture of the user wearing the pieces | built, **not measured** | needs internet |
| Open-Meteo | weather | built | not a model, an API |
| Grad-CAM, colour map, concept probes (XAI) | "Why these labels?", "Why similar?" | built, measured | unsure flag calibration in `explanations_evaluation.md`; concept probes mean AUC 0.83 |

The Encoder Lab candidates (Marqo-FashionSigLIP, SigLIP 2, ZooClaw, OpenAI CLIP) are **not** in the app.

---

## 12. Extra information that will help the presentation

**Safe claims (have numbers and a source):**
- 95.7 / 86.4 / 86.8% classifier, beating the FashionCLIP probe on all three fields.
- Search words precision 0.90 on test, and the rule written before the scores (commits `4d84265`, `1fa3bca`).
- 393 tests pass; golden answers freeze the verdicts.
- 222 of 240 trap answers pass, 0 forbidden pieces shown, 0 errors, median 1.3 s.
- Privacy: every query filters by `user_id`; the assistant never sees a database id; the deletion test scans every
  collection.

**Claims to avoid or soften:**
- "We compared 5 encoders": true by the rule, but I cannot show the scores. Show the rule and the outcome only.
- "The assistant has agents and a router": it has one agent. Say "the architecture supports more, and the config
  validates them".
- "dressme-chat is deployed": it is not.
- "The verdict is accurate": no accuracy exists. Say "explainable and reproducible".
- "Tested on real photos": no.

**Survey numbers (57 responses) for the opening:** black in 84% of wardrobes, 56% shop second-hand, 40% frustrated
by fit, 42% want "should I buy this?" advice.

**Data sizes:** Fashion Product 44,441 products; PolyVore 126,927 images / 31,333 outfits; H&M catalogue 63k adult
articles; classifier test 29,633 pictures; price data 1,523 + 183.

**Method points juries like:** pre-registered decision rule before scoring; val for settings and test opened once;
duplicates kept in one split; the formula weights belong to the team and are not tuned from data; the
"unsure" flag and "Why this score?" explanations.

**Questions to expect, with honest answers:**
- Why not fine-tune now? A fine-tune existed (v1-v4) but was built for the old chat; the new one waits for the
  traps baseline (that is what the trap set is for).
- Why is photo search weaker? A photo is compared with photos, so many near matches look alike; precision 0.77.
- Is the chat safe? Tools only read the user's own data; the user id is never a tool argument; the trap set has 10
  "other user", 20 "buy pressure" and 10 "body" runs, all passed.

**Three things to do before the talk** (all outside this task):
1. Get the Encoder Lab scores (hit@5, MRR, the five models) from the Kaggle notebook and commit them.
2. Count the real `decisions` documents and the users in MongoDB.
3. Commit `bench/results/assistant/` and rehearse the demo with the two scan photos.
