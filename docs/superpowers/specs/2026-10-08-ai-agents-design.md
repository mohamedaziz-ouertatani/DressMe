# DressMe AI agents — design

Date: 2026-10-08 · Status: approved in chat, awaiting spec review

## Goal

The project must introduce **at least three AI agents, each with its own tools**. Today DressMe has one:
the `/chat` assistant (`backend/app/routers/chat.py`), an LLM (Gemini, or the local Qwen through Ollama)
with four tools. This design splits it into **three specialist agents** and adds a **router** that sends
each user message to the right one. Every agent is a real LLM tool-calling loop: it decides which tools
to call, reads their results and answers.

Non-goals: agents calling each other (orchestrator), new UI pages, retraining the local chat model.

## The agents

An agent = a name, a system prompt and a set of tools bound to the current user. All three run on the
existing chat engine (`engine.reply(system, history, message, tools)`), so Gemini and Ollama both work
unchanged.

| Agent (`name`) | Job | Tools |
|---|---|---|
| Stylist (`stylist`) | "What do I wear today / for this occasion?" | `list_wardrobe`, `suggest_outfits`, `score_outfit`, `complete_outfit`, `get_weather` |
| Shopping advisor (`shopping`) | "Should I buy this? Where can I find one?" | `buy_advice_last_scan`, `search_listings`, `find_similar` |
| Wardrobe analyst (`analyst`) | "What's missing? What do I have too much of?" | `wardrobe_insights`, `wardrobe_stats`, `find_near_twins` |

### Tools (each wraps code that already exists)

All tools are closures bound to `(request, user)`; every database read is filtered by `user["_id"]`,
and ids that are not the user's are ignored (never an error that leaks existence).

- `list_wardrobe(category="")`, `suggest_outfits(season="", occasion="", n=1)`, `score_outfit(item_ids)`,
  `buy_advice_last_scan()`: moved unchanged from `chat.py`.
- `complete_outfit(item_ids, k=3)`: the user's chosen items + the rest of the wardrobe →
  `compatibility.complete_outfit`; returns the best completions via `outfit_out`. Clashing input →
  `{"error": ...}` like `score_outfit`.
- `get_weather()`: `request.app.state.weather.today(WEATHER_LAT, WEATHER_LON)` (default place, the
  agent never receives a user position) → temperature, condition, rain chance and `season`. Weather off /
  unreachable → `{"error": "weather unavailable"}`, so the agent falls back to asking or to the calendar.
- `search_listings(category="", sub_category="", colour="", max_price=0, n=5)`: the same query as
  `GET /listings` (active, in stock, approved; seller listings only when approved). The query is moved
  from `routers/listings.py` into a shared helper `listings.listing_query(...)` that both use. Returns
  `listing_out` rows (title, price in TND, shop / city, image URL).
- `find_similar(item_id="", n=5)`: the vector of the user's item, or of the last scan when `item_id` is
  empty → `Catalog.search_shop` (H&M) + `ListingIndex.search` (shops now). Returns both lists. No vector /
  no candidate → `{"error": ...}`.
- `wardrobe_insights()`: `compatibility.wardrobe_insights` with the user's profile (same call as
  `/insights`), trimmed to the counts and the top few entries of each list so the prompt stays small.
- `wardrobe_stats()`: the category / colour (neutral share) / pattern counts and empty fields that
  `/insights` returns; the counting moves from `routers/insights.py` into a helper both use.
- `find_near_twins()`: `compatibility.near_twins` on the wardrobe → pairs of item descriptions + ids.

### Prompts

One shared base (language rule, modesty rule, "never invent items", short / kind / budget-aware), taken
from today's `SYSTEM`, plus a few lines per agent describing its job and when to use each tool. Each agent
is told what the others do, so it can say "ask me about outfits instead" rather than guess.

## Router

`agents/router.py`: `route(engine, message) -> (agent_name, how)` where `how` is `llm` or `keywords`.

1. **LLM step** (unless `ROUTER=keywords`): `engine.classify(system, message, labels)` — a new method on
   both engines: one call, no tools, a tiny prompt listing the three agents with one-line descriptions,
   output capped to a few tokens. The answer is lower-cased and matched against the labels.
2. **Keyword fallback** when the LLM step is off, raises (`ChatUnavailable`, `ChatBusy`, `ChatQuota`,
   timeout) or returns an unknown label: `mappings/agent_keywords.csv` (columns `agent, language, keyword,
   note`; team-owned, all rows REVIEW; en / fr / Darija incl. Arabizi). Matching is case-insensitive
   substring on the normalised message; the agent with the most hits wins; ties and no hit → `stylist`.
3. Only the latest message is routed (history is not sent to the router).

Quota: one extra small call per message on Gemini. `ROUTER=keywords` in `backend/.env` skips it (for
demos on the 20-requests/day free key). Settings default: `ROUTER=llm`.

## Code layout

```
backend/app/agents/
    __init__.py      AGENTS = {"stylist": ..., "shopping": ..., "analyst": ...}; Agent dataclass (name, title, system, tools)
    common.py        shared prompt base, image attachments + capture wrapper (moved from chat.py)
    stylist.py       SYSTEM + tools(request, user)
    shopping.py      SYSTEM + tools(request, user)
    analyst.py       SYSTEM + tools(request, user)
    router.py        route(), keyword table loading
backend/app/chat_engine.py   + classify() on GeminiEngine and OllamaEngine
backend/app/routers/chat.py  /chat: route → agent → engine.reply; stores and returns `agent`
mappings/agent_keywords.csv  team-owned keyword table
```

`chat.tools_for` stays as a thin alias to the Stylist + `buy_advice_last_scan` tool set, because
`src/phase4/build_chat_dataset.py` and `evaluate_chat.py` import it: the fine-tuning data keeps its four
tools and is not changed by this work.

## Data flow (`POST /chat`)

1. Load the last 20 messages (unchanged).
2. `agent_name, how = route(engine, message)`.
3. `agent = AGENTS[agent_name]`; `engine.reply(agent.system(user), history, message, agent.tools(request, user, attachments))`.
4. Save the user message and the answer; the answer document gets `agent` and `routed_by`.
5. Response: `{"reply", "tools_used", "attachments", "agent", "agent_title"}`. `GET /chat/history`
   returns `agent` per message (empty for older messages).
6. `log_event(db, "chat", ..., tools=used, agent=agent_name)`.

Errors are unchanged (503 no key, 502 busy, 429 quota) and come only from the `reply` step; a router
failure never fails the request (it falls back to keywords).

## Frontend

`ChatPage.tsx`: a small badge above each assistant answer with the agent's title ("Stylist", "Shopping
advisor", "Wardrobe analyst"), translated like the rest of the page. No other UI change.

## Testing (`backend/tests/`, fakes, `dressme_test`)

- `FakeChatEngine` gets `classify()` (returns a label set by the test, or raises) and learns the new tool
  names.
- Router: LLM label used; LLM raises → keywords; unknown label → keywords; no keyword → `stylist`;
  `ROUTER=keywords` never calls `classify`; keyword CSV loads and every `agent` value is a known agent.
- Each new tool: happy path on a seeded wardrobe; another user's ids ignored; `search_listings` hides
  pending, gone and out-of-stock listings; `get_weather` with `FakeWeather` and with weather off;
  `find_similar` with no scan → error dict.
- `/chat`: response and history carry `agent`; the shopping agent's answer uses its tools; existing chat
  tests still pass.
- Regression: `GET /listings` and `/insights` answers unchanged after the helper extraction.

## Documentation

- `AGENTS.md` (project root): the three agents, their tools, the router flow (diagram) and the quota
  note — written for the Phase 4 report.
- `CLAUDE.md` Phase 4 backend section: one bullet pointing to `backend/app/agents/` and `AGENTS.md`.
- `LLM.md`: note that the fine-tuned model is trained for the Stylist's original tool set.

## Open points for the team

- `mappings/agent_keywords.csv` rows (especially Darija) are REVIEW, like the other team-owned tables.
- Extending the chat SFT dataset to the shopping and analyst tools is a possible follow-up, not part of
  this work.
