# DressMe AI agents

DressMe's chat is five AI agents. Each is a language model (Gemini, or our local
Qwen3-4B through Ollama, see LLM.md) with its own instructions and its own tools:
Python functions on the user's real data that the model decides to call.
Code: `backend/app/agents/`.

| Agent | Answers | Tools |
|---|---|---|
| Stylist | what to wear today / for an occasion | `list_wardrobe`, `suggest_outfits`, `score_outfit`, `complete_outfit`, `get_weather` |
| Shopping advisor | should I buy this, where to find one, prices | `list_wardrobe`, `buy_advice_last_scan`, `search_listings`, `find_similar` |
| Wardrobe analyst | what is missing, unused pieces, near-duplicates | `list_wardrobe`, `wardrobe_insights`, `wardrobe_stats`, `find_near_twins` |
| Seller assistant | what to sell, at what price, the listing | `list_wardrobe`, `pieces_to_sell`, `price_hint`, `my_listings`, `prepare_sell` |
| Explainer | why an outfit has its score, what would change it, why a piece got its labels, why two pieces look alike, why a buy verdict, how scoring works | `list_wardrobe`, `explain_outfit`, `what_if`, `explain_labels`, `explain_similarity`, `explain_verdict`, `how_scoring_works` |

## How a message is answered

    user message
        │
        ▼
    router (agents/router.py)
        1. the model answers one word: stylist / shopping / analyst / seller / explainer   (skipped with ROUTER=keywords)
        2. failed or unclear → keyword table mappings/agent_keywords.csv (team-owned, REVIEW)
        3. no keyword → stylist
        │
        ▼
    chosen agent: its prompt + its tools + the last 20 messages
        │  the model calls tools (max 6 rounds), reads their answers
        ▼
    answer + tools used + item pictures + the agent's name (badge in the app)

Each agent's prompt = the shared rules (language, modesty level, never invent items,
budget) + its own job + one line on what the other two do, so it can send the user to
the right one.

## Tools

What each tool wraps (no new fashion logic: the team's formula in `src/phase4/compatibility.py`):

- `list_wardrobe`: the user's items (every agent has it, to know item ids).
- `suggest_outfits`, `score_outfit`, `complete_outfit`: the compatibility formula.
- `get_weather`: Open-Meteo for the default city (WEATHER_LAT / WEATHER_LON); no user position reaches the model.
- `buy_advice_last_scan`: `buy_advice` on the last photo analysed in the app.
- `search_listings`: the same filter as the Shops page (active, in stock, approved sellers only); a seller's contact is never sent to the model.
- `find_similar`: FashionCLIP neighbours of an item or of the last scan, in the H&M catalogue and in the listings.
- `wardrobe_insights`, `wardrobe_stats`: the Insights page's facts and counts.
- `find_near_twins`: pairs of items above the team's `similar_item` similarity.
- `pieces_to_sell`: the Insights facts again (pieces in no good outfit, the second of each near-twin pair).
- `price_hint`: look-alike listings (same category) → a friperie price range: friperie prices as they are,
  shop prices × the team's second-hand factor (`mappings/resale_pricing.csv`, REVIEW); the user's own
  listings are left out. `backend/app/resale.py`.
- `my_listings`: the user's own seller listings and their status (never city or contact).
- `prepare_sell`: posts nothing. It returns a chat action, a link to the Sell page already filled
  (photo, price, title, size); the user adds city and contact and presses Send, then an admin reviews it.

- `explain_outfit`: why an outfit scores what it does (XAI, `src/phase4/explain_outfit.py`): points per
  part, what works and what does not (as short English facts, from the same codes as the app's lines),
  the weakest piece and its best swap (only above the team's `min_swap_gain`), the least alike pair.
- `what_if`: score and points before / after taking a piece out and / or putting another in.
- `explain_labels`: the stored model guesses of a piece or of `last_scan` (value, confidence, top 3,
  unsure flag with the team's cuts, corrected or not) + an `explain` action opening the item's
  "Why these labels?" panel (heatmaps). Nothing is recomputed.
- `explain_verdict`: the last scan's verdict made visible (`buy_explanation`: thresholds, what it beats,
  owned pieces that do as well, near misses, near twins).
- `explain_similarity`: why two pieces look alike: picture similarity (+ near twin at the team's
  `similar_item`), shared / different labels, and the concepts both pictures read as
  (`src/phase4/explain_similarity.py`, team list `mappings/style_concepts.csv`, above the average
  picture). "My two pink jackets" (the same description for both, matching exactly two pieces) compares
  those two; numbers and ordinals in a description are ignored. `dressme-chat-v3` is trained on it
  (2026-10-10; end to end it answers 8 / 8 look-alike questions with this tool). v2 predates it: on
  2026-10-09 it did not call it in a live chat and made up a reason.
- `how_scoring_works`: the team's current weights and thresholds, read from `mappings/`.

The Explainer's outfit tools take ids or short descriptions ("pink top"): a description is used only
when exactly one of the user's pieces matches it; otherwise the tool returns the candidates and the
agent asks which one is meant (by description, never by id). Its prompt: only give reasons found in a
tool result, never invent a rule, a number or a cause; labels are guesses with a confidence.

Every tool reads only the logged-in user's data; another user's ids are ignored.

## "How I answered" (trace)

Every tool call of an answer is recorded by the tool wrapper (`common.with_attachments`, `trace`):
`{"tool", "args", "result"}`, arguments shortened (texts to 60 characters, lists to 6 entries), the
result as one line (`score 55.4`, `verdict buy`, `error: …`, `18 items`, `failed: ValueError`). It is
saved with the answer next to `routed_by` (model or keywords) and returned by `/chat` and the history;
the Chat page shows it under the tool names ("how I answered"). Nothing new is sent to the model.

## Chat actions

A tool can return `{"action": {"kind": "sell", "url": "/sell?..."}}` or
`{"action": {"kind": "explain", "url": "/wardrobe/<id>?why=1"}}`. `/chat` collects these like
pictures (`actions` in the answer and the history) and the Chat page shows a button ("Open the
Sell form" / "Open the explanation"). Only these two shapes are kept (`common.ACTION_URLS`: `/sell?...`
and `/wardrobe/<24 hex>?why=1`), so a model cannot put any other link in front of the user.

## Keyword table

`mappings/agent_keywords.csv` (`agent, language, keyword, note`): a keyword matches at the
start of a word, ignoring case and accents (`achet` matches "acheter" and "achète"); the
agent with the most matches wins; a tie goes to the agent whose keyword comes first in the
message ("Why is my outfit…" is a why question); no match: the Stylist. An unknown agent name stops the
backend with the line number. All rows are REVIEW; the Darija rows (Arabizi and Arabic
script) are a first draft for the native-speaker review.

## Cost

With `ROUTER=llm` each message costs one short extra model call (the router). The free
Gemini key allows ~20 requests a day: set `ROUTER=keywords` in `backend/.env` for demos.

## Local model

The fine-tuned model (LLM.md) was trained on the original four tools (`chat.tools_for`):
`list_wardrobe`, `suggest_outfits`, `score_outfit`, `buy_advice_last_scan`. The other tools
work with the base model; adding them to the training data is a follow-up.
Explainer, tried live on 2026-10-08 on the demo wardrobe ("why is the outfit with my skirt, my pink
t-shirt and my brown casual shoes scored like that?"): `qwen3:4b-instruct` called `explain_outfit` once
with descriptions and gave a correct, grounded answer (points per part, what works); when a description
matched two pieces it asked which one. The fine-tuned `dressme-chat` (never trained on these tools)
wandered between tools and ran out of rounds. Use the base model or Gemini for the Explainer until
Explainer conversations are in the training data (Darija wording needs the native review first).

## Tests

`backend/tests/test_agents.py` (each agent's tools, privacy, the router and its fallbacks)
and `backend/tests/test_chat.py` (`/chat` returns and stores the agent).
