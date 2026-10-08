# Seller assistant agent — design

Date: 2026-10-08 · Status: approved in chat, awaiting spec review
Builds on: `docs/superpowers/specs/2026-10-08-ai-agents-design.md` (the three agents, the router; see `AGENTS.md`)

## Goal

Add a fourth chat agent, the **Seller assistant**, for users who want to sell clothes as friperie
sellers (any user can: `POST /listings/sell`). It helps them choose what to sell, price it, write
the listing, and follow their listings. It **advises and prepares** but never changes data: posting
always goes through the Sell page, where the user adds their city and contact and presses Send, and
the listing then waits for admin review as today.

Non-goals: posting, editing or marking listings sold from the chat; photos in the chat; condition
or brand in the price; retraining the local chat model.

## Why it fits

- The chat cannot receive a photo, so the agent works from things that already have one: a piece in
  the user's wardrobe, or their last scan (`candidates`, kept 24 h).
- The Wardrobe analyst already finds pieces that go with nothing and near twins: "sell what you never
  wear" is the natural next step.
- Second-hand prices are scarce (2026-10-08, local DB: 3 seller listings, median 15 TND) while shop
  listings have prices for new clothes (Exist median 120, Hamadi Abid 60, Inditex snapshot 179 TND),
  so the price hint must use shop prices with a second-hand factor until enough friperie prices exist.

## The agent

`backend/app/agents/seller.py`, `AGENT = Agent(name="seller", title="Seller assistant", ...)`,
registered in `AGENTS` after `analyst`. Its job text: help the user sell pieces they do not wear, at a
fair friperie price; suggest a price with `price_hint`, write a short honest title (category, colour,
size if known; never invent brand or condition), and end with `prepare_sell` so the user gets a
ready-filled Sell form; say that a listing is checked by an admin before others see it.

### Tools

All bound to `(request, user)`, every read filtered by `user["_id"]`; another user's ids are ignored.

| Tool | Returns |
|---|---|
| `list_wardrobe(category="")` | shared tool (`common.list_wardrobe_tool`) |
| `pieces_to_sell()` | `{"unmatched": [piece...], "twins": [{"keep": piece, "sell": piece, "similarity"}...]}` — main pieces in no good outfit (`compatibility.wardrobe_insights(...)["unmatched"]`) and, for each near-twin pair, the second piece as the one to sell; at most 5 of each; `piece` = `describe(...)` (id, category, sub_category, colour, image_url) |
| `price_hint(item_id="")` | the price range below, for a wardrobe item, or for the last scan when `item_id` is empty; `{"error": ...}` when the item is unknown / has no vector, or no priced look-alike exists |
| `my_listings()` | the user's seller listings (`source_id = sellers`, `seller_id = user`), newest first, max 10: id, title, price_tnd, category, sub_category, colour, status (`pending` / `active` / `rejected` / `gone` = sold or removed), review_note, image_url; **never** city or contact |
| `prepare_sell(price_tnd, item_id="", title="", size="")` | posts nothing; returns `{"action": {"kind": "sell", "url": "/sell?..."}, "item": piece}`. The URL carries `item=<id>` (or `candidate=<id>` for the last scan when `item_id` is empty), `price`, and `title` / `size` when given, URL-encoded. Unknown item / no scan / price ≤ 0 → `{"error": ...}` |

### Price hint (`backend/app/resale.py`)

Pure functions, so they test without a database:

- `load_rules(path=mappings/resale_pricing.csv) -> {"factor": {category: float}, "neighbours": int, "min_friperie": int}`.
  CSV columns `kind, name, value, note` (team-owned, every row `REVIEW`):
  - `factor` rows: `name` = a category from `vocab.CATEGORIES` or `*` (default); `value` = the share of
    the new-shop price a second-hand piece sells for. Placeholder **0.3** on `*` only, until the team
    sets per-category values.
  - `setting` rows: `neighbours` = **8** (look-alikes read), `min_friperie` = **3** (friperie look-alikes
    needed to ignore shop prices).
  - Unknown `kind`, unknown category, missing `*` or a missing setting → `ValueError` with the line
    number (same rule as the other mapping loaders).
- `price_range(hits, rules) -> dict | None`. `hits` = `ListingIndex.search(...)` rows (each has
  `price_tnd`, `source_id`, `category`, `score`, `title`, `snapshot`). Rows without a positive price are
  dropped. Friperie rows (`source_id == SELLERS`) keep their price; shop rows are multiplied by
  `factor[category]` (else `*`). If at least `min_friperie` friperie rows exist, only they are used.
  Result: `{"low", "high", "median"}` (25th / 75th percentile and median of the used prices, rounded to
  1 TND, `low ≤ median ≤ high`), `"based_on": "friperie" | "shops" | "both"`, `"count"`, and
  `"examples"`: up to 5 used rows `{title, source_id, price_tnd, resale_price, similarity, snapshot}`.
  No usable row → `None`.

`price_hint` reads the item (or last scan) vector, calls
`listing_index.search(db, vector, k=rules["neighbours"], category=doc["category"])`, drops listings
posted by this same user (`seller_id`, needs the index to keep it: see below), and returns
`price_range(...)` or `{"error": "no similar listings with a price yet"}`.

`ListingIndex.search` rows come from `listing_out`, which has no `seller_id`; `search` gains an
optional `exclude_seller=None` argument that skips docs whose `seller_id` equals it. `/similar` is
unchanged (it does not pass it).

## Chat actions

A tool may return `{"action": {"kind": ..., "url": ...}}`. `common.with_attachments` gains an optional
`actions` list and collects every `action` dict found in tool results (deduplicated by `url`), like it
collects pictures. Only `kind == "sell"` with a URL starting with `/sell?` is kept (the model cannot
inject other links).

`POST /chat` returns `actions` (only when not empty, like `attachments`) and saves them on the model
message; `GET /chat/history` returns `actions` (`[]` for older messages).

## Frontend

- `ChatPage.tsx`: under an answer, each action renders a button-styled `Link` ("Open the Sell form",
  translated) to its `url`.
- `SellPage.tsx`: on load, reads `item` or `candidate`, `price`, `title`, `size` from the address
  (`useSearchParams`). With `item` / `candidate`, it fetches `/items/{id}/image` or
  `/candidates/{id}/image` through the existing authenticated `loadImage`, turns it into a `File`
  (`fetch(objectUrl).blob()`), and uses it as the picked photo (preview shown); it fills price, title
  and size. City and contact stay empty and required. A failed image load shows the normal photo picker
  and a short note ("pick the photo again"); nothing is sent. The backend is unchanged: the photo is
  uploaded and analysed exactly as when the user picks it.
- Strings (en / fr / ar): `agent_seller`, `tool_pieces_to_sell`, `tool_price_hint`, `tool_my_listings`,
  `tool_prepare_sell`, `chatOpenSell`, `sellPrefillFailed`. Arabic: first draft, REVIEW.

## Router

- `AGENTS` order: stylist, shopping, analyst, seller. The router prompt lists it automatically.
- `mappings/agent_keywords.csv` gains (REVIEW): en `sell`, `selling`; fr `vend` (vendre, vends),
  `revend`; Darija `nbi3`, ar `نبيع` (native check).
- Known limit, unchanged rule: a keyword tie goes to the Stylist, e.g. "what price should I sell at?"
  (`sell` + `price`); the LLM step handles it, keywords-only mode does not.
- `common.TEAM` adds: "the Seller assistant: what to sell, at what price, writing the listing, the
  user's listings".

## Privacy

- City and contact are never in any tool result: `my_listings` leaves them out, and `price_hint`
  examples carry only title, source, prices, similarity and snapshot.
- `prepare_sell` only builds a link to the user's own item or scan; the Sell page's image requests go
  through `/items/{id}/image` and `/candidates/{id}/image`, which answer 404 for another user's id.
- Nothing is posted without the user pressing Send on the Sell page; listings still need admin approval.

## Testing

- `tests/test_resale.py` (pure): friperie only (≥ `min_friperie`); shop × factor (category factor and
  `*` fallback); mixed below `min_friperie` → `"both"`; rows without price dropped; empty → `None`;
  `low ≤ median ≤ high`; examples capped at 5; loader errors (unknown kind, unknown category, no `*`,
  missing setting).
- `tests/test_agents.py`: seller has its 5 tools; `pieces_to_sell` lists an unmatched piece and the
  second of two twins; `price_hint` from an item and from the last scan, ignores another user's item,
  skips the user's own listings, error with no priced look-alike; `my_listings` shows own listings with
  status and no city / contact, not other users'; `prepare_sell` URL for item and candidate, encoding,
  error for unknown item and price ≤ 0; router keywords (`"I want to sell my jacket"` → seller,
  `"je veux vendre ce jean"` → seller); `AGENTS` has 4 agents.
- `tests/test_chat.py`: `/chat` returns and stores `actions` for the seller; a non-`/sell?` action from
  a tool is dropped.
- Frontend: `npm run build` + lint; preview check (fake backend) that the chat button opens a filled
  Sell form with the photo.

## Documentation

- `AGENTS.md`: four agents, the Seller assistant's tools, chat actions, the price rule.
- `CLAUDE.md` Phase 4: the `/chat` bullet gains the Seller assistant; the Listings item mentions
  seller help and `mappings/resale_pricing.csv` (REVIEW).
- `LISTINGS.md`: one paragraph on the Seller assistant (prices from look-alikes × team factor).

## Open points for the team

- `mappings/resale_pricing.csv`: the factor (0.3 placeholder) and per-category values; when friperie
  prices may take over (`min_friperie`).
- New keyword rows (Darija native check) and Arabic strings.
- The fine-tuned local model does not know these tools (as for the other new agents).
