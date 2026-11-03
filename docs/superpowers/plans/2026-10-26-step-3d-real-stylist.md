# Step 3d: the first real agent (Ollama + the Stylist's tools)

Branch `upgrade/step-3d-real-stylist`, from local `main` (`2cbcc34`). Local only, nothing pushed.
Baseline: 333 collected, 330 passed, 3 skipped.

**Goal:** plug a real model (Ollama, `qwen3.5:4b`, the name a setting) into the 3c engine behind the same `ModelClient`
interface, and give the Stylist five real tools that call the functions the screens already use ("one function, two
callers"). The Stylist then answers real questions on the golden wardrobe.

## Part 0: read-only checks (done before any code)

| # | Question | Finding |
|---|---|---|
| 1 | Ollama, the model, one raw call | Ollama **0.40.10** on the host. `ollama show qwen3.5:4b`: 4.2 B parameters, Q4_K_M, context length 262144, capabilities **completion, vision, tools, thinking** (levels false / true, default true); default parameters top_k 20, top_p 0.95, presence_penalty 1.5, temperature 1. Raw `POST /api/chat` from the backend container (stream false, think false, one tool `get_time`, "What time is it?"): **a structured `message.tool_calls`** (`[{"id": "call_...", "function": {"index": 0, "name": "get_time", "arguments": {}}}]`), `content` empty, **no `<think>` text**. Arguments come as a dict. |
| 2 | Container -> host | `host.docker.internal` resolves (192.168.65.254) and Ollama answers **without** `extra_hosts` on this PC (Docker Desktop). `extra_hosts: host-gateway` is added anyway, for Linux machines. |
| 3 | The functions behind | See the table below. |
| 4 | Occasions, outfit fields | `dress_occasions.csv` chips: everyday, work, university, outing, eid, wedding, beach. An app outfit (`outfit_out(explain=True)`) has `score` (0-100, one decimal), `parts` (0-1), `items` (ids), `label` (safe / bolder / experimental / null), `confidence`, `complete`, `missing` (bottom / top / core / null), `explanations` (`{code, part, sign, params}`; params can hold ids, e.g. `swap`). |
| 5 | GPU | After the first call, `ollama ps`: `qwen3.5:4b  3.4 GB  100% GPU  8192  llamacpp  9 minutes from now`. |

**Timing (finding, not a contradiction):** the very first load after a reboot took **170 s** (118 s reading the file
from disk, 44 s for the first prompt). A second cold load (file in the OS cache) took **13 s** (12 s load), and a warm call
**0.5 s** of model time. With `timeout_s` 90, the first chat after a reboot can answer 503 once; the next one works.

**The functions behind (3):**

| Tool | Reuses | File, function | Inputs | Output | MongoDB |
|---|---|---|---|---|---|
| `search_wardrobe` | 3b text search | `src/phase4/search.py` `normalise_query`, `rank_owned`; `Analyzer.embed_text` | words, terms table, vectors, cut | `{results: [{item, similarity, close}], nothing_close}` | the route reads `items` |
| `get_weather` | Dress's weather | `routers/dress.py` `weather_today(request, lat, lon)` -> `app.state.weather.today` (30-min cache) | lat / lon or the settings' default | `{temp_c, condition, season}` (+ `rain_likely` in the engine's answer) | no |
| `suggest_outfits` | `GET /outfits/today` | `routers/dress.py` `today(request, occasion, shuffle, lat, lon, user)` | request (only `.app.state`), user document | the route's JSON | reads `items`, `outfit_feedback`, `wear_log` |
| `build_outfit` | `POST /outfits/build` | `routers/dress.py` `build(BuildIn, request, user)` | ids, occasion | the route's JSON | reads |
| `score_outfit` | `POST /outfits/score` | `routers/outfits.py` `score(ItemIds, request, user)` -> `compatibility.score_outfit` | ids | `outfit_out(explain=True)` | reads |

`today` and `build` keep their logic inside the route functions (no separate helper), so the tools call **the route
functions themselves** (plain Python functions; FastAPI's decorators return them unchanged) with the `/chat` request and the
user document. That is the strictest "same function": same seed, same weather, same labels. It needs two new optional fields on
`ToolContext`: `user` (the logged-in user's document) and `request`. The user still never comes from the model.

**Location (3):** Dress uses the browser's rounded position when the user pressed "Use my location" (kept in that browser
only), else the settings' default place (`WEATHER_LAT` / `WEATHER_LON`, Tunis). The server never stores a position, so the
tools use the default place and say `"location": "default city"`. Chat and Dress therefore agree when Dress has no position.

## Design (as decided), with the choices made inside the brief

- `config.py`: `CHAT_MODEL` (default `qwen3.5:4b`), `OLLAMA_URL` (default `http://host.docker.internal:11434`); both in
  `.env.example`. `docker-compose.yml`: `extra_hosts: ["host.docker.internal:host-gateway"]` on the backend.
- `mappings/agents.yaml` `model:` section (REVIEW), validated with ranges: temperature 0-2, top_p (0, 1], top_k >= 1,
  presence_penalty -2..2, num_ctx 512-262144, keep_alive like `10m` / `-1`, timeout_s 1-600, think bool.
- `assistant/ollama.py` `OllamaClient(url, model, options, transport=None)`: the translator. Sends our messages with
  `tool_name` for tool results, tools only when there are some, options with `num_predict` = the agent's `max_tokens`.
  Errors (connection, timeout, HTTP error, model not found, a broken answer) -> `ModelUnavailable`. `available()` asks
  `/api/show` with a 3 s timeout, cached 60 s. TODO(step 3e): retries and a second provider.
- `ModelReply` gains `thinking_stripped` (default false). **The loop needs one small change:** when a reply had a `<think>`
  block removed, it adds a trace line `{round, note: "thinking_stripped"}`. Only the loop sees each reply, so only the loop
  can write it into the turn's trace. Nothing else in the loop changes.
- `tools.py` gains `ToolError(code, message)`: a tool raises it for an expected refusal (pieces that clash, no words, weather
  off) and the registry turns it into an error result with that code, like the others.
- `GET /assistant/status` -> `{available, model}`.
- Tools in `assistant/tools_stylist.py` (+ `search_wardrobe` next to `list_wardrobe`). Output rules: pieces only as refs,
  whole numbers 0-100, no ids, no free text. Reasons are the explanation codes with their sign (`"+colour_pair"`,
  `"-pattern_clash"`), without params (params can hold ids). `get_weather` also returns `season` (what Dress dresses for).
  The search keeps 3b's rule: when nothing is close, only the nearest `closest_anyway` come back; to share it, the route's
  "load the pieces, rank, trim" part becomes `routers/search.py` `rank_text_or_photo` (same answers).
- Tools that read gender rules answer the error `gender_required` for an account without a gender (the screens answer 409).
- Stylist instructions rewritten for the six tools; `shared_rules` unchanged.
- Tests keep `NoModel` by default (`make_client`), so no test calls Ollama.

## Commits (small, in this order)

1. plan (this file)
2. settings, `.env.example`, compose `extra_hosts`, the `model:` section of agents.yaml + its validation
3. `OllamaClient`, `thinking_stripped` in the loop, `GET /assistant/status`, `create_app` builds the client, start-up line, tests
4. `ToolError`, `ToolContext.user/request`, the five tools, the Stylist in agents.yaml, contract tests
5. frontend types
6. live check (8 questions) and docs: manual check, hand-off, learning note, step-3a note fix, CLAUDE.md

## Verification

Suite in the container after `docker compose up -d --build backend`; `npm run build`, `npm run lint`; `git diff main` on the
goldens and `compatibility.py` empty; the live check on a throwaway golden user (deleted after); Ollama stopped -> 503 and
`available: false`, the app keeps running; fast-forward into local `main`.

## As built

Suite: 355 collected, 352 passed, 3 skipped (+22: 10 Ollama client and status, 8 Stylist tools, 2 engine, 2 agents.yaml). Goldens and `compatibility.py` unchanged. `npm run build` and `oxlint` pass.

The loop changed in two small places, both explained in its comments: a `thinking_stripped` trace note (only the loop sees
every reply) and the refusal of a tool the agent was not given (3c ran any registered tool; with five agents in 3e that
would let one agent use another's tools).

Live check (golden wardrobe, throwaway user deleted after; first question cold): 25.0 s, then 3.1 to 10.0 s.
7 of 8 answered with the right tools or rightly without; the French interview question called no tool and invented pieces
(4 invented refs removed by the `{n}` rule, the invented words stayed). Not tuned (3g measures it). Ollama stopped:
`/assistant/status` false, `/chat` 503, `/health` ok.
