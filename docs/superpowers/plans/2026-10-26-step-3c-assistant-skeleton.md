# Step 3c: the walking skeleton of the new assistant

Branch `upgrade/step-3c-skeleton`, from local `main` (`4b7a8d5`). Local only, nothing pushed.
Baseline before this step: 314 collected, 311 passed, 3 skipped (225 s).

**Goal:** prove the whole chat path end to end with a scripted FAKE model and ONE real tool, `list_wardrobe`, on the
golden wardrobe: tools, registry, piece ledger, agents from YAML, model interface, the loop, the `{n}` rule, the
`chats` collection and `POST /chat`. No real model (Ollama is step 3d, the other four agents and the router 3e, the
screen 3f, the traps 3g, our fine-tune 3h). Nothing visible changes in the app: `/assistant` stays a placeholder.

## Part 0: read-only checks (done before any code)

| # | Question | Finding |
|---|---|---|
| 1 | PyYAML? pydantic? | PyYAML 6.0.3 and pydantic 2.14.1 (v2) are in the backend container (PyYAML only through another package, so I add `pyyaml` to `backend/requirements.txt`; the exact pin is already in `docker/constraints.txt`, so no new download). |
| 2 | Current user, db, injection | `Depends(security.current_user)` gives the user document (`user["_id"]`); the db is `request.app.state.db`. `create_app(settings, analyzer, catalog, remover, tryon_engine, weather_engine)` stores each engine on `app.state` in the lifespan; `conftest.make_client(remover=, tryon=, weather=)` passes fakes to it. `chat_model` is added the same way (`app.state.chat_model`, default `NoModel`, and `make_client(chat_model=)`). No other caller of `create_app` needs changing. |
| 3 | `item_out` | `id, category, sub_category, pattern, colour, coverage, season[], usage[], predicted, corrected, image_url` (+ `promoted_from`). **Every item field is coded: an item has no name, notes or any free text**, so nothing typed by the user can reach the model through `list_wardrobe`. The brief's "type" is the `sub_category`. |
| 4 | Events | `events.EVENT_TYPES` (a list; the admin stats route builds its per-day and total counts from it, so a new type shows up there by itself) and `log_event(db, kind, user_id, **extra)`. The TS `DayStats` has optional fields per type: `assistant?: number` is added. |
| 5 | Deletion | `db.USER_COLLECTIONS` is the only list `accounts.delete_account` uses. `test_deletion_complete.py` scans every collection for the user's id after deleting; I add `chats` to `MUST_HOLD_DATA` and a `/chat` call to `leave_data_everywhere`. |
| 6 | Golden wardrobe | `tests/test_golden.py` fixture `golden` seeds `wardrobe.json` (17 items) straight into `dressme_test` for the user `WARDROBE["user"]` (signed up through the API). The chat test reuses that fixture. |

Nothing contradicts the design. Small notes: (a) items have no free text, so the "coded fields only" rule is true by
construction; (b) the frontend turns an error into a text with a plain key in `i18n/strings.ts`, so `assistantUnavailable`
is added in en / fr / ar; (c) a route that gets `ModelUnavailable` answers `HTTPException(503, "assistant_unavailable")`, the
same "code as detail" habit as `/search`.

## Design (as decided)

`backend/app/assistant/`, short files, no framework:

| File | What |
|---|---|
| `model.py` | `ToolCall`, `ModelReply`, the `ModelClient` protocol, `ModelUnavailable`, `FakeModel(script)`, `NoModel` |
| `ledger.py` | `PieceLedger`: ref numbers 1, 2, 3 for item ids, per turn |
| `tools.py` | `Tool`, `ToolContext`, `ToolResult`, `Registry` (schemas, run) |
| `tools_wardrobe.py` | the tool `list_wardrobe` |
| `agents.py` | `mappings/agents.yaml` loaded and validated at start-up |
| `placeholders.py` | the `{n}` rule |
| `loop.py` | `run_turn` |
| `__init__.py` | `default_registry()` |

Plus `mappings/agents.yaml`, `routers/chat.py` (`POST /chat`), the `chats` collection (`USER_COLLECTIONS`, index
`(user_id, created_at)`), event type `assistant`, `create_app(chat_model=)`.

Decisions made inside the brief (it was silent):

- A tool argument that names pieces is listed in `Tool.piece_args`. The registry translates those refs to item ids
  through the ledger before `fn` runs, and an unknown ref is an error result, so `fn` never sees a ref it cannot trust.
- The message history is NOT sent to the model in 3c (messages = system + this user message). `chat_id` only groups the saved turns.
- On a repeated call the tool message answers `repeat` (so the transcript stays valid for a real model), then the forced final answer follows.
- The default agent is the first one of the file (`stylist`). TODO(step 3e): the router picks the agent from its keywords.
- The route is a plain `def` (FastAPI runs it in a thread), because the real model of 3d blocks.

## Commits (small, in this order)

1. plan (this file)
2. model, ledger, placeholders, tools + registry, with unit tests (`test_assistant_engine.py`, first part)
3. the loop and its tests (repeat, max_rounds, invalid arguments)
4. `agents.yaml`, `agents.py`, `test_agents_yaml.py`
5. `list_wardrobe`, the `chats` collection, event type, `POST /chat`, `create_app(chat_model=)`, conftest, `test_chat.py`, deletion test
6. frontend: `assistantUnavailable` in en / fr / ar, the `/chat` types, `assistant?` in `DayStats`
7. docs: manual check, learning note, CLAUDE.md

## Verification

`docker compose up -d --build backend`, wait about a minute, the whole suite in the container; `npm run build`,
`npm run lint`; `git diff main -- backend/tests/golden` is empty (goldens identical); `compatibility.py` untouched;
fast-forward into local `main`.
