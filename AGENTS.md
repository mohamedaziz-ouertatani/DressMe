# DressMe AI agents

DressMe's chat is four AI agents. Each is a language model (Gemini, or our local
Qwen3-4B through Ollama, see LLM.md) with its own instructions and its own tools:
Python functions on the user's real data that the model decides to call.
Code: `backend/app/agents/`.

| Agent | Answers | Tools |
|---|---|---|
| Stylist | what to wear today / for an occasion | `list_wardrobe`, `suggest_outfits`, `score_outfit`, `complete_outfit`, `get_weather` |
| Shopping advisor | should I buy this, where to find one, prices | `list_wardrobe`, `buy_advice_last_scan`, `search_listings`, `find_similar` |
| Wardrobe analyst | what is missing, unused pieces, near-duplicates | `list_wardrobe`, `wardrobe_insights`, `wardrobe_stats`, `find_near_twins` |
| Seller assistant | what to sell, at what price, the listing | `list_wardrobe`, `pieces_to_sell`, `price_hint`, `my_listings`, `prepare_sell` |

## How a message is answered

    user message
        │
        ▼
    router (agents/router.py)
        1. the model answers one word: stylist / shopping / analyst / seller   (skipped with ROUTER=keywords)
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

Every tool reads only the logged-in user's data; another user's ids are ignored.

## Chat actions

A tool can return `{"action": {"kind": "sell", "url": "/sell?..."}}`. `/chat` collects these like
pictures (`actions` in the answer and the history) and the Chat page shows a button. Only `sell`
actions pointing to `/sell?` are kept, so a model cannot put any other link in front of the user.

## Keyword table

`mappings/agent_keywords.csv` (`agent, language, keyword, note`): a keyword matches at the
start of a word, ignoring case and accents (`achet` matches "acheter" and "achète"); the
agent with the most matches wins, ties go to the Stylist. An unknown agent name stops the
backend with the line number. All rows are REVIEW; the Darija rows (Arabizi and Arabic
script) are a first draft for the native-speaker review.

## Cost

With `ROUTER=llm` each message costs one short extra model call (the router). The free
Gemini key allows ~20 requests a day: set `ROUTER=keywords` in `backend/.env` for demos.

## Local model

The fine-tuned model (LLM.md) was trained on the original four tools (`chat.tools_for`):
`list_wardrobe`, `suggest_outfits`, `score_outfit`, `buy_advice_last_scan`. The other tools
work with the base model; adding them to the training data is a follow-up.

## Tests

`backend/tests/test_agents.py` (each agent's tools, privacy, the router and its fallbacks)
and `backend/tests/test_chat.py` (`/chat` returns and stores the agent).
