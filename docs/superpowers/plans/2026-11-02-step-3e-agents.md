# Step 3e: the other agents and the router

## Design

- Agents: stylist (existing 6 tools), general (tools: []), wardrobe_analyst, explainer, seller, shopping.
- Tools (each wraps existing code):
  - wardrobe_analyst: list_wardrobe, search_wardrobe, wardrobe_insights (routers/insights.py insights),
    near_twins (compatibility.near_twins)
  - explainer: list_wardrobe, score_outfit, explain_outfit (POST /outfits/explain), similar_pieces (with why)
  - seller: list_wardrobe, search_wardrobe, price_estimate (routers/price.py, takes item_id), near_twins
  - shopping: search_listings, buy_advice, price_estimate (listing_id), similar_pieces
- POST /buy-advice accepts candidate_id ONLY. The shopping tool must first call listing_candidate
  (routers/listings.py) to get a candidate, reuse an existing one if there is one, then buy_advice.
- Shop listings get their own numbers, never {n}.
- Router: skip it if body.agent is set. Otherwise one model call, no tools, temperature 0, few tokens,
  given each agent's name and one-line description, answering with one word. Invalid answer: keywords from
  agents.yaml, then stylist. ModelUnavailable during routing: same fallback. Trace: {"router": name, "how": "button|model|keywords|default"}.
- Build order: router + general, wardrobe_analyst, explainer, seller, shopping, handoff.
  Measure with the traps after each step.

## Corrections after reading the code

1. **Registry.** Tools are registered by hand in `backend/app/assistant/__init__.py` `default_registry()` (a fixed tuple
   of `Tool` objects imported from `tools_wardrobe.py` and `tools_stylist.py`). `main.py` passes `registry.names()` to
   `load_agents`, so a new tool file must be imported and added to that tuple, or `agents.yaml` is refused at start-up.
2. **A second kind of ref does not fit `piece_args`.** `Registry._translate_refs` turns the names in `piece_args` into
   item ids through `ctx.ledger` (a `PieceLedger` of the user's items, ids from `items`). Listing numbers need their own
   ledger (`ctx.listing_ledger`) and their own list of argument names (e.g. `listing_args`), translated the same way,
   and `placeholders.resolve` (the `{n}` rule) must leave the listing notation alone while still removing an invented
   `{n}`. Reusing `piece_args` with one ledger would let the model pass a listing number as a piece.
   The notation for listings still has to be chosen (not `{n}`).
3. **Empty tools list works.** `agents.py` accepts `tools: []` (the field has no minimum). `loop.py` calls
   `registry.schemas([])` -> `[]`, `model.chat(messages, [], max_tokens)`; `OllamaClient.chat` adds the `tools` key only
   `if tools`, so Ollama gets none. If the model still asks for a tool, the loop refuses it (`unknown_tool`, step 3d).
   Nothing to change for the general agent.
4. **The router needs a model call with its own temperature.** `ModelClient.chat(messages, tools, max_tokens)` has no
   temperature argument: the sampling knobs come from `agents.yaml` `model:` for every call. Temperature 0 needs an
   optional `temperature=None` argument on `chat` (`ModelClient`, `FakeModel`, `NoModel`, `OllamaClient`).
5. **Agents already have a one-line `job`.** The router needs a description written for a model that has to choose
   (what it handles, what it does not). Added as a separate `description` field; `job` stays the human summary.
6. **Existing tests assume the first model call is the agent's.** Without `agent` in the body, the router now makes
   a call first, so tests of `POST /chat` that script one reply need `"agent": "stylist"` or a routing reply first.
7. **The traps.** `traps.yaml` holds **43** traps: 24 English, 12 French, 5 Arabic, 2 Arabizi. `eval_traps.py` runs
   `--lang en` by default, so one repeat is 24 answers and `--repeat 10` is 240 = 24 x 10. (An earlier count of 44 was
   wrong.) Expected agents of the 24 English traps: stylist 16, shopping 3, none 3, seller 1, explainer 1.
   `wardrobe_analyst` appears only in an Arabic/French/other-language trap, not in the English run.
   `eval_traps` sends `agent` only with `--agent`, so the router is exercised by default.
8. **`n_tool_calls` and the eval's `tools_called`** count trace lines that have a `tool` key; a router line
   (`{"router": ..., "how": ...}`) has none, so neither count changes.
9. **q01 ("Help me.") now expects `general`.** `expected_agent` is one name, compared with `==` (a list would break the
   report), so a list of acceptable agents is not supported. "Help me" has no topic: `general` asks one question,
   which is what the trap checks (`max_questions: 1`). Whether the stylist could also answer is not scored.
10. **Router descriptions (3e.1b).** The 3e.1 `general` description said "general fashion advice ... vague requests",
    so a01 ("which colours go well with burgundy") and q01 went to `general` in 5 of 5 raw replies. Both descriptions
    were sharpened: stylist = ANY question about clothes, colours, outfits...; general = ONLY greetings, thanks,
    goodbyes and requests with nothing to do with clothes.

## Router examples

The router reads each agent's `description` and its `examples` (a list in `mappings/agents.yaml`,
printed after the description as `Examples: "a" ; "b" ; "c"`). The stylist, wardrobe_analyst and general examples
are already in the file. Copy the ones below into `agents.yaml` when each agent is built. None of them is a case of
`bench/assistant/router_cases.yaml`, so the router test stays honest.

- **explainer:** "Why does this outfit score so low?" ; "Which piece is dragging my outfit down?" ; "How are the points calculated?"
- **seller:** "What could I sell my old sandals for?" ; "Which clothes should I put up for sale?" ; "Is 40 dinars too much for my leather bag second-hand?"
- **shopping:** "Is this 70 dinar sweater a good buy for me?" ; "Find cheap white trainers in the shops." ; "Would another black skirt be a waste of money?"
