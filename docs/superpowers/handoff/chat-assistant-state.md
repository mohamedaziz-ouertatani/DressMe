# Chat assistant: state file

For a new Claude chat that has never seen this work. Branch `chat/step-3e-agents`, state at commit `c5743e4` (2026-11-03).
Design (source of truth): `docs/superpowers/plans/2026-11-02-step-3e-agents.md`. The old chat is readable only through the
git tag `pre-chat-removal` (ideas only, nothing is reused). **Update this file in the same commit as any chat change**
(rule in `CLAUDE.md`).

## What is built

**Router** (`backend/app/assistant/routing.py`, `choose_agent`). Order: the app names an agent (`body.agent`, how=`button`) ->
one model call with no tools, temperature 0, max 10 tokens, shown each agent's description and 3 examples, answers one word
(how=`model`) -> the agent whose `keywords` (en/fr/ar, `agents.yaml`) appear most (how=`keywords`) -> the first agent of the
file, stylist (how=`default`). A model that is down falls to the keywords. The first trace line of every turn is
`{"router": name, "how": ...}`. Router test, alone and fast: `backend/app/eval_router.py` on `bench/assistant/router_cases.yaml`
(51 labelled messages: **dev 32** for tuning, **test 19** run once per decision, never tuned on; a case may list
`acceptable_agents`). Descriptions start with what the agent handles and end with NOT; examples are never router test cases.

**Agents** (`mappings/agents.yaml`, validated at start-up by `assistant/agents.py`; max 9 tools each; numbers are REVIEW):

| Agent | Handles | Tools | Rounds |
| --- | --- | --- | --- |
| stylist | what to wear, combining pieces, finding pieces, weather, style advice | list_wardrobe, search_wardrobe, get_weather, suggest_outfits, build_outfit, score_outfit | 6 |
| general | greetings, thanks, things unrelated to clothes | none | 1 |
| wardrobe_analyst | the wardrobe as a whole: missing, balance, duplicates, counts | list_wardrobe, search_wardrobe, wardrobe_insights, near_twins | 4 |
| explainer | why an outfit got its score, weakest piece, how scoring works | list_wardrobe, search_wardrobe, score_outfit, explain_outfit, how_scoring_works | 4 |
| seller | selling own clothes: price range, which to sell | list_wardrobe, search_wardrobe, price_estimate, near_twins | 4 |
| shopping | shops: find listings, similar items, is a listing a good buy | search_listings, similar_pieces, buy_advice, price_estimate_listing, search_wardrobe | 4 |

`shared_rules` (added to every agent): facts only from tools of this turn, `{n}` only, one question at most, no body comments,
never push to buy, answer in the user's language, only the logged-in user's own wardrobe.

**Tools** (each wraps existing code, lists max 5, results are refs and coded fields, never ids; the user id comes from the
login, never from the model; `ToolError(code)` = an expected refusal; files `backend/app/assistant/tools_*.py`):

| Tool | Wraps |
| --- | --- |
| list_wardrobe | a Mongo query on the user's `items` (coded fields only) |
| search_wardrobe | `routers/search.py find_owned` (FashionCLIP text vector, the words cut) |
| get_weather | the weather engine at the default city |
| suggest_outfits / build_outfit | `routers/dress.py today` / `build` |
| score_outfit | `routers/outfits.py score` |
| wardrobe_insights | `routers/insights.py insights` |
| near_twins | `compatibility.near_twins` |
| explain_outfit | `routers/outfits.py explain_outfit_route` (weakest piece, max 3 swaps) |
| how_scoring_works | `compatibility.Rules.weights` as shares of the score, plus the "good" line |
| price_estimate | `routers/price.py price_estimate` for one piece (no model file -> `no_price_model`) |
| search_listings | `routers/listings.py list_listings` (the route's gender filter) |
| similar_pieces | `routers/outfits.py similar` (listings + the closest own piece) |
| buy_advice | `listing_candidate` (a candidate already made from that listing is reused), then `routers/outfits.py buy_advice` |
| price_estimate_listing | `routers/price.py price_estimate(listing_id=)`; only friperie sellers' listings get a band |

**Numbers and the `{n}` rule.** `PieceLedger` (`ledger.py`) lives for one turn: item id <-> ref 1, 2, 3; the model never sees an id,
tools take refs (`Tool.piece_args`), an unknown ref is `unknown_piece`. Listings are NOT pieces: `ToolContext.listings` is a second
ledger (`Tool.listing_args`, error `unknown_listing`); a listing is shown as `{listing, title, price_tnd, shop, category, colour}`,
never the seller's name, city or contact (a friperie seller's free-text title is hidden too), and the model names it in words,
never `{n}`. `placeholders.resolve`: a known `{n}` stays, an invented one is removed and logged (`unknown_refs`). Repair of the
user's own number: `chat.py` strips the braces of a `{12}` the user typed before the model sees it; if the model still writes it,
it is shown as plain text (`echoed_refs`), not deleted.

**Handoff** (`assistant/handoff.py`, tool `handoff(agent, note<=100 chars)` for every agent that has tools, not general): the tool
only records `{to, note}` in `ToolContext` (target must be ANOTHER agent of the file, one per turn; errors `invalid_target`,
`unknown_agent`, `already_handed_over`). The loop stops with `stop_reason: "handoff"` (the first agent still writes its own part in
the usual last no-tools call). `chat.py` then runs the target agent ONCE with the original message + the note, the SAME context
(same piece and listing ledgers), no handoff tool and no handoff instruction line (`second_run_agent`); the answer is the first
agent's words then the second's, `agent` in the response is the second one, the trace gets `{"handoff": {from, to, note}}` between the
two agents' lines, and the `chats` document keeps `agent` (the answering one), `agents` `[first, second]` and `handoff`. Each tool agent's
instructions have the line "If the user also asks something that belongs to another agent, call handoff ..." and its system prompt lists
the other agents (`handoff.menu`). **The 4B model never calls the tool** (traps h01 and h02, see Results).

**Model client and endpoints.** `assistant/ollama.py` `OllamaClient` calls Ollama `/api/chat` (stream off, tools only when the agent
has some, `<think>` stripped); any failure is `ModelUnavailable` -> `POST /chat` answers 503 `assistant_unavailable`. **Retries (step 4):** a connection
error or an HTTP 5xx on `/api/chat` is tried again twice (after 1 s, then 2 s) before `ModelUnavailable`; a timeout, a 4xx and a
broken answer are not retried, and neither is the `/api/show` status check (`worth_retrying`; `retry_delays` / `sleep` injectable). `GET /assistant/status` -> `{available, model}` (`/api/show`, cached 60 s). `POST /chat`
(`routers/chat.py`): `{message 1-1000, chat_id?, agent?}` -> `{chat_id, agent, answer, pieces: {"<n>": item}, trace, stop_reason, model}` (`agent` is the answering one: the second after a handoff);
422 `unknown_agent`. Only the user's own items appear in `pieces`; **listings are not in `pieces`**. One document per turn in the
`chats` collection (user_id, chat_id, created_at, agent, message, answer, item_ids, unknown_refs, echoed_refs, trace, stop_reason,
model, plus `agents` and `handoff`); event type `assistant` (agent, routed, rounds, stop_reason, n_tool_calls, n_unknown_refs, handed_from, ms; never the message). The
history is NOT sent to the model: every turn stands alone.

**Model.** `CHAT_MODEL=dressme-base` (set in the git-ignored `backend/.env`; the default in `config.py` is `qwen3.5:4b`).
`ollama list` shows `dressme-base:latest` and `qwen3.5:4b` with the same ID `d8b0f5e9760c` (3.3 GB), so they are the same weights.
Sampling is the `model:` block of `agents.yaml` (temperature 0.7, top_p 0.8, top_k 20, presence_penalty 1.5, num_ctx 8192,
keep_alive 10m, timeout 90 s, think false). `OLLAMA_URL` defaults to `http://host.docker.internal:11434` (Ollama runs on the PC).

**How to run and measure** (the repo is bind-mounted at `/app` in the backend container; in Git Bash prefix `MSYS_NO_PATHCONV=1`):
- After a change: YAML only -> `docker compose restart backend`; Python changed -> `docker compose up -d --build backend`; then wait
  for `healthy` (`docker inspect -f "{{.State.Health.Status}}" dressme-backend-1`).
- Trap set (55 traps in `bench/assistant/traps.yaml`: 36 en, 12 fr, 5 ar, 2 arabizi; default `--lang en`; the eval user gets the
  17-piece golden wardrobe; 5 fixed fake listings, marked `eval_fake: true`, are added at the start of a run only if `listings` is empty and deleted at the end):
  `docker exec dressme-backend-1 python -m app.eval_traps --repeat 10` (options `--only g01,e01`, `--agent stylist`, `--lang all`,
  `--rescore <file>.jsonl`). A trap may set `checks: {handoff: true|false}`; the report counts answers that used handoff, per trap;
  the router accuracy is the router's own pick (`routed`), not the answering agent. A run of 10+ minutes: `docker exec -d dressme-backend-1 sh -c "python -m app.eval_traps --repeat 10 > /app/bench/results/assistant/run-X.log 2>&1"`.
- Router: `docker exec dressme-backend-1 python -m app.eval_router --repeat 5` (dev), `--split test --repeat 5` (once per decision).
- Tests: `docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_router.py tests/test_agents_yaml.py tests/test_chat.py tests/test_<agent>_tools.py`
  (assistant files: `test_assistant_engine`, `test_ollama_client`, `test_stylist_tools`, `test_analyst_tools`, `test_explainer_tools`,
  `test_seller_tools`, `test_shopping_tools`). Full suite ~3 min: 438 passed, 3 skipped at `c5743e4`; 458 passed, 3 skipped at step 4.
- Reports: `bench/results/assistant/traps-<model>-<UTC stamp>.md/.jsonl`, `router-<model>-<stamp>.md/.jsonl`, `run-*.log`. **`bench/results/`
  is not in git** (untracked): the reports exist only on the PC that ran them. Stamps look like UTC and commit times like UTC+1 (inferred from matching a commit to its run, not checked).

## Results so far

Trap set, English, base model. "Every run" = traps passing in all runs. Router = the trap run's router accuracy (agents that exist).

| Milestone | Scope | Answers passed | Traps every run | Made-up numbers | Router | Report (`traps-dressme-base-...`) |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline (`acbd031`, one agent) | 24 traps x3 | 64/72 (89%) | 19/24 | not counted | n/a | `T154855` (rescored with the fixed checker: 65/72, 20/24, 1) |
| Baseline re-run, checker that separates echoes | 24 x3 | 59/72 (82%) | 17/24 | 3 | n/a | `T162845` (what changed: unverified) |
| A: model never sees the user's `{n}` (`057b6b5`) | 24 x10 | 213/240 (89%) | 15/24 | 3 | n/a | `T173500`; a second run 218/240 (91%), 18/24, 2: `T174759` (which code state each had: unverified) |
| B: prompt rules (`efc5070`, reverted `450a994`) | 24 x10 | 222/240 (92%) | 17/24 | 1 | n/a | `T183124` (labelled "after Experiment B" in the untracked `PRESENTATION_FACTS.md`) |
| A2: user's number shown as plain text (`a499bc5`) | 24 x10 | 222/240 (92%) | 18/24 | 4 (8 repaired) | n/a | `T185121` (run is 7 min before the commit; it has the "repaired" counter: unverified) |
| 3e.1 router + general (`fe43a60`) | 24 x10 | 224/240 (93%) | 19/24 | 7 (12 repaired) | 170/190 (89%) | `T194605` (`run-3e1.log`) |
| 3e.1b router descriptions (`343fdea`) | 24 x10 | 228/240 (95%) | 18/24 | 4 (8) | 180/190 (95%) | `T200810` (`run-3e1b.log`) |
| 3e.2 wardrobe_analyst (`01700a9`) | 27 x10 | 259/270 (96%) | 21/27 | 3 (13) | 170/220 (77%, strict) | `T203104` (`run-3e2.log`) |
| Router test + examples + "no occasion" line (`4622fd8`) | 27 x10 | 264/270 (98%) | 23/27 | 2 (12) | 210/220 (95%, with `acceptable_agents`) | `T225249` (`run-3e3.log`); router test dev 85/85 `T223917`, test 50/50 `T223940` |
| 3e.3 explainer (`206bc9e`) | e01-e03 x5 | 13/15 | 1/3 | 0 | 15/15 | `T231235` (e03 answered in French 1 of 5 after an instruction line, was 2 of 5 in `T231054`; e02 once showed no piece); router dev 110/110 `T231051` |
| 3e.3 seller (`7e429d1`) | se01-se03 x5 | 15/15 | 3/3 | 0 | 10/15 (67%): se02 went to wardrobe_analyst 5/5, accepted since `9b93614` | `T231624`; router dev 135/135 `T231621`, test 80/80 `T231731` |
| Traps and wording (`9b93614`) | u01 x10, g01 x10 | 10/10, 10/10 | 1/1, 1/1 | 0 | u01 10/10 stylist | `T232139`, `T232158` |
| 3e.5 shopping (`c5743e4`) | sh01-sh03 x5 | 15/15 (first run 11/15: two of my own checks were wrong) | 3/3 | 0 | 15/15 | `T233037` (first `T232906`); router dev 160/160 `T232903`, test 95/95 `T233501` |
| 3e.6 handoff (`4d61dc6`) | h01, h02 x10 | 0/20 (both traps 0/10 twice; after the one allowed tune of the explainer's and shopping's line: still 0/20, no `handoff` call at all) | 0/2 | 0 | routed explainer 10/10, shopping 10/10 | `T234640`, after the tune `T234959` |
| Step 4 retry (this commit) | no model run (code only; tests with the httpx mock transport) | n/a | n/a | n/a | n/a | full suite 458 passed, 3 skipped; the 3-repeat trap and router runs after 3e.6 are still to do on the PC |

The g01 test of "the Stylist got worse?" (stylist forced, 30 runs): at `540ebaa` 23/30 (`T224311`), A2 code 27/30 (`T224531`), with the
"If the user gives no occasion, call suggest_outfits without one" line 28/30 (`T224839`, line kept).
Not measured since 3e.2: the full 10-run trap set with the explainer, seller and shopping traps; French and Arabic (only `en` was ever run);
the human review column of the reports is empty (tone and truth are not judged yet).

What we learned:
- **Luck threshold:** a difference under about 4 of 10 runs, or 7 of 30, is noise. g01 got 23/30 and 27/30 on two codes that should behave the same.
  Two 30-run measurements of g01, g04, x03 (`T201635` 77/90, `T202033` 66/90) also differ by 11 answers (what differed: unverified).
- **Code guarantees beat prompt rules:** prompt rules for piece numbers (B) did not clearly help and were reverted; what holds are the ledgers,
  the `{n}` resolver, the tool whitelist and "no seller contact", because the model cannot break them.
- **Test the router alone, on a dev/test split.** It is one short call (0.14 to 0.2 s), so it can be tuned in seconds without touching the test split.
  It is at 100% on both splits, so only a regression can show. Inside the trap set it scores lower where two agents may both answer: use `acceptable_agents`.
- **Automatic checks are not truth.** Two of my own checks were wrong (a regex escaped as a backspace character; a required piece ref). Read the answers.
- **Known weakness:** the model answers an English question in French now and then (s01, e03); not fixed.

## Plan

Chat assistant only, next step first. Tick when done.
- [x] Router + general, wardrobe_analyst, explainer, seller, shopping (3e.1 to 3e.5)
- [~] **Handoff:** built and tested (tool, loop stop, second run with the same ledgers, trace line, both agents saved), but the model never calls it (h01/h02 0/20 after one tune). Decide: trigger it in code (e.g. a second question to the router), or accept and drop
- [~] **Fallback:** retry done (step 4: connection error / 5xx twice, 1 s then 2 s; not timeouts). Still to do: a message with shortcut buttons instead of the bare 503, and a second provider (`TODO(step 3e)` in `assistant/ollama.py`)
- [ ] **Measure after 3e.6 + step 4** (needs Ollama on the PC): `eval_traps --repeat 3` (all English traps) and `eval_router --repeat 3`; compare Totals with 3e.2, handoff count per trap, any trap down more than 2 of 3
- [x] **Chat screen** (`frontend/src/pages/AssistantPage.tsx`, step 3f): turns kept in the page only (the page says every question stands alone), 4 suggestion chips, each `{n}` a link to the piece + the pieces as cards, "How I answered" (router agent, handoff, tools called; a refused call struck through), a short note for `max_rounds` / `repeat`, model off (status false or a 503) = a card with shortcuts (Dress, Buy?, Wardrobe, Shops) and Check again, the wardrobe search folded under it. Listings stay in words (not in `pieces`). Checked in a browser with a scripted fake model (en, phone and desktop); not yet with the real model
- [ ] **Final measurement:** the full 10-run trap set (all 6 agents), a set of fresh questions never used before, and the router test split once; full suite once
- [ ] **Arabic and French** measured once (`--lang fr,ar,arabizi`), then the Darija review (`bench/assistant/darija_review.md`)
- [ ] **Price model:** `models/checkpoints/price_model.joblib` is missing on this PC, so the seller says it cannot estimate a price; it needs the teammate's two CSVs and `train_price.py` (see `README.md`)
- [ ] Presentation and demo script
- [ ] **Pull request to main.** `merge/virtual-tryon-into-3e` holds Asma's try-on commit `70aa9b0` and merge `3655c17`, which this branch does not have
- Skipped on purpose: photos in chat, history, Gemini, fine-tuning (step 3h)
