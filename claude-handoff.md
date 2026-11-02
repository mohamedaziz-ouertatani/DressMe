# Hand-off for the next steps of the chat assistant (3e onward)

Collected 2026-11-02 from the working tree on `main` (merge commit `ec1e430`). Nothing in the project was changed to
make this file. No secret is included: from `backend/.env` only `CHAT_MODEL` and `OLLAMA_URL` were looked for, and
**neither line is in that file**, so both take the code defaults (`qwen3.5:4b`, `http://host.docker.internal:11434`).

---

## 1. Environment

### Ollama

```
$ ollama --version
ollama version is 0.40.10

$ ollama list
NAME                      ID              SIZE      MODIFIED
qwen3.5:4b                d8b0f5e9760c    3.3 GB    7 days ago
dressme-chat-v4:latest    1b354eaf9bbd    2.5 GB    10 days ago
qwen2.5vl:7b              5ced39dfa4ba    6.0 GB    13 days ago
qwen2.5:7b-instruct       845dbda0ea48    4.7 GB    13 days ago
qwen3.5:cloud             a7bf6f7891c3    -         6 months ago
```

`ollama show qwen3.5:4b` (model, capabilities and parameters; the licence text is cut):

```
  Model
    architecture        qwen35
    parameters          4.2B
    context length      262144
    embedding length    2560
    quantization        Q4_K_M
    requires            0.30.0
    renderer            qwen3.5
    parser              qwen3.5
    template source     renderer_parser

  Capabilities
    completion
    vision
    tools
    thinking
        levels     false, true
        default    true

  Projector
    architecture        clip
    parameters          333.51M
    embedding length    1024
    dimensions          2560

  Parameters
    presence_penalty    1.5
    temperature         1
    top_k               20
    top_p               0.95
```

Note: the model's default is `thinking: true`; the app sends `think` from `mappings/agents.yaml` (`model.think: false`).

### Docker, git

```
$ docker compose ps
NAME                 IMAGE              SERVICE    CREATED          STATUS                    PORTS
dressme-backend-1    dressme-backend    backend    40 minutes ago   Up 40 minutes (healthy)   0.0.0.0:8000->8000/tcp
dressme-frontend-1   dressme-frontend   frontend   9 days ago       Up 6 days                 0.0.0.0:5173->5173/tcp
dressme-mongo-1      mongo:7.0.45       mongo      10 days ago      Up 6 days (healthy)       0.0.0.0:27017->27017/tcp

$ git branch --show-current
main

$ git log --oneline -15
ec1e430 Merge origin/main: price model, budget-aware Similar, listing price tag
353654f Ignore the Encoder Validation Lab exports (bench/exports/)
3b0840c CLAUDE.md: the search cuts come from the Encoder Validation Lab
20dfe2e Test the chat search tool's closest_anyway and guard the lab's cuts
d4b02a9 Protect the lab's search cuts: photo_target_precision, opt-in calibration write
5b7ecfd Apply Phase 6 search cuts (words 0.292, photo 0.792)
f7cccbc Price card: condition selector with measured factors (#71)
1fa3bca Pre-register FashionCLIP tuning rule
4d84265 Pre-register decision rule for the encoder lab
90b054a Price model: RBF-kernel SVR, chosen by benchmark (#70)
fbc575f Shops: switch on 'Above the usual price' (#69)
e7a050f Seller agent: price_hint uses the price model when it is loaded (#68)
62e5d47 Feat/listing price tag (#67)
5a61a67 Similar page: show the piece it compares with (#66)
17a9c93 Similar: shop listings respect the user's budget (#65)

$ git status --short
?? bench/phase3_questions.ipynb
?? bench/results/
```

The local `main` is 38 commits ahead of `origin/main` (not pushed). The merge dropped #68 (Seller agent `price_hint`
using the price model) on purpose, because the old chat was removed in step 3a.

### The backend test command

The backend packages are installed in the container, not on the host. PowerShell:

```
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q
```

In Git Bash put `MSYS_NO_PATHCONV=1` in front (it rewrites container paths otherwise). One file:
`docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_chat.py`.
Last full run (2026-11-02, after the merge): **392 passed, 3 skipped, 178 s**. The 3 skipped are the real-model tests
(`DRESSME_SLOW=1` un-skips them). Tests use the `dressme_test` MongoDB database, dropped before and after every test.
After any backend change: `docker compose up -d --build backend` and wait about a minute.

---

## 2. Source files

### `backend/app/assistant/model.py`

```python
"""
The language model, seen from the assistant (step 3c).

The loop only knows this small interface, so the model behind it can change: a scripted FakeModel in the tests
(step 3c), a real model served by Ollama (step 3d, ollama.py), our own fine-tune (step 3h).

    chat(messages, tools, max_tokens) -> ModelReply
        messages   the conversation so far, as a list of {"role": ..., "content": ...} dicts
        tools      the tools the model may ask for (the registry's schemas); [] = it must just answer
        ModelReply either some text (the answer) or tool calls (the model asks us to run tools)
"""

import copy
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class ModelReply:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking_stripped: bool = False      # a <think>...</think> block was removed from the text (step 3d)


class ModelUnavailable(Exception):
    """The model cannot be reached or is not set up. The route answers 503 assistant_unavailable."""


class ModelClient(Protocol):
    name: str          # saved with every chat turn, so we know which model said what

    def chat(self, messages: list[dict], tools: list[dict], max_tokens: int) -> ModelReply: ...

    def available(self) -> bool: ...   # GET /assistant/status (step 3d)


class FakeModel:
    """Returns the scripted replies in order and remembers everything it was asked (`received`)."""
    name = "fake"

    def __init__(self, script):
        self.script = list(script)
        self.received = []         # one {"messages", "tools", "max_tokens"} per call

    def chat(self, messages, tools, max_tokens):
        self.received.append({"messages": copy.deepcopy(messages), "tools": tools, "max_tokens": max_tokens})
        if not self.script:
            raise AssertionError("FakeModel: the script has no reply left for this call")
        return self.script.pop(0)

    def available(self):
        return True


class NoModel:
    """No model at all (the tests' default since step 3d plugged in Ollama): every call says it is unavailable."""
    name = "none"

    def chat(self, messages, tools, max_tokens):
        raise ModelUnavailable("no language model is set up")

    def available(self):
        return False
```

### `backend/app/assistant/agents.py`

```python
"""
The agents, read from mappings/agents.yaml and checked at start-up (step 3c).

An agent is a job, its instructions, the tools it may use, keywords that will route a message to it (step 3e) and
its own limits. The team edits the file; this module refuses to start the API with a clear message when something
is wrong, so a typo is found at start-up and not in the middle of a user's chat:

    - a field is missing or has the wrong type (the message names the agent and the field)
    - an agent lists a tool that is not registered
    - an agent has more tools than limits.max_tools (small models choose badly among many tools)
    - an agent's max_rounds or max_tokens is above the global limit
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class AgentsConfigError(Exception):
    """agents.yaml cannot be used. The text says where."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")      # an unknown field is a typo: refuse it


class Limits(Strict):
    max_tools: int = Field(gt=0)
    max_rounds: int = Field(gt=0)
    max_tokens: int = Field(gt=0)


class ModelSettings(Strict):
    """How the model is asked (step 3d): the sampling knobs, the context window, how long it stays loaded."""
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    top_k: int = Field(ge=1)
    presence_penalty: float = Field(ge=-2, le=2)
    num_ctx: int = Field(ge=512, le=262144)           # the context window, in tokens (more = more GPU memory)
    keep_alive: str = Field(pattern=r"^(-1|0|\d+[smh])$")   # e.g. "10m"; -1 = keep it loaded, 0 = unload at once
    timeout_s: float = Field(gt=0, le=600)
    think: bool


class Agent(Strict):
    job: str
    instructions: str
    tools: list[str]
    keywords: dict[str, list[str]]                 # language -> words (en / fr / ar)
    max_rounds: int = Field(gt=0)
    max_tokens: int = Field(gt=0)


class AgentsFile(Strict):
    limits: Limits
    model: ModelSettings
    shared_rules: str
    agents: dict[str, Agent]


def where(loc):
    """('agents', 'stylist', 'job') -> "agent 'stylist', field 'job'"."""
    if len(loc) >= 3 and loc[0] == "agents":
        return f"agent '{loc[1]}', field '{'.'.join(map(str, loc[2:]))}'"
    return "field '" + ".".join(map(str, loc)) + "'"


def load_agents(path, tool_names):
    """The validated agents file. `tool_names` = the names in the tool registry."""
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        config = AgentsFile.model_validate(raw)
    except OSError as error:
        raise AgentsConfigError(f"{path.name}: cannot be read ({error})") from error
    except yaml.YAMLError as error:
        raise AgentsConfigError(f"{path.name}: is not valid YAML ({error})") from error
    except ValidationError as error:
        lines = [f"{where(e['loc'])}: {e['msg']}" for e in error.errors()]
        raise AgentsConfigError(f"{path.name}: " + "; ".join(lines)) from error

    problems = []
    for name, agent in config.agents.items():
        for tool in agent.tools:
            if tool not in tool_names:
                problems.append(f"agent '{name}', field 'tools': tool '{tool}' is not registered "
                                f"(known tools: {', '.join(sorted(tool_names))})")
        if len(agent.tools) > config.limits.max_tools:
            problems.append(f"agent '{name}', field 'tools': {len(agent.tools)} tools, "
                            f"but limits.max_tools is {config.limits.max_tools}")
        for field in ("max_rounds", "max_tokens"):
            if getattr(agent, field) > getattr(config.limits, field):
                problems.append(f"agent '{name}', field '{field}': {getattr(agent, field)} is above "
                                f"limits.{field} ({getattr(config.limits, field)})")
    if not config.agents:
        problems.append("field 'agents': there is no agent")
    if problems:
        raise AgentsConfigError(f"{path.name}: " + "; ".join(problems))
    return config
```

### `backend/app/assistant/placeholders.py`

```python
"""
The {n} rule: the model names pieces as {1}, {2}... and only numbers shown this turn are real (step 3c).

A known {n} stays in the text (the app will turn it into the piece's photo and name). An invented one is removed
from the text, so no ghost piece is ever shown, and is returned so the turn can log it.
"""

import re

PLACEHOLDER = re.compile(r"\{(\d+)\}")


def resolve(text, ledger):
    """(clean text, refs used, unknown refs); both lists are in order of first appearance, without repeats."""
    used, unknown = [], []

    def keep_or_drop(match):
        ref = int(match.group(1))
        if ledger.item_id(ref) is not None:
            if ref not in used:
                used.append(ref)
            return match.group(0)
        if ref not in unknown:
            unknown.append(ref)
        return ""

    clean = PLACEHOLDER.sub(keep_or_drop, text)
    if unknown:                                           # tidy the gaps the removal left
        clean = re.sub(r"[ \t]{2,}", " ", clean)
        clean = re.sub(r"\s+([.,;:!?])", r"\1", clean).strip()
    return clean, used, unknown
```

### `backend/app/assistant/tools_wardrobe.py`

```python
"""
The wardrobe tools: list_wardrobe (step 3c) and search_wardrobe (step 3d, the Wardrobe page's search).

A tool only shows the model CODED fields (category, type, colour, pattern, season): no database id, no free text,
no photo. The model names a piece by the small number the ledger gives it.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .. import ml  # noqa: F401  (puts src/ on the import path)
import search

from ..routers.search import find_owned
from ..vocab import CATEGORIES
from .tools import Tool, ToolError

Category = Literal[tuple(CATEGORIES)]       # the app's categories, as a fixed list the model must choose from


class ListWardrobeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Optional[Category] = None
    colour: Optional[str] = None
    limit: int = Field(default=30, ge=1, le=60)


def list_wardrobe(ctx, args):
    """Only ctx.user_id's pieces: the user filter is in the query itself, and the id is not an argument."""
    query = {"user_id": ctx.user_id}
    if args.category:
        query["category"] = args.category
    if args.colour:
        query["colour"] = args.colour.strip().lower()
    docs = list(ctx.db.items.find(query).sort("created_at", 1))
    pieces = []
    for doc in docs[:args.limit]:
        pieces.append({"ref": ctx.ledger.add(doc["_id"]), "category": doc["category"],
                       "type": doc["sub_category"], "colour": doc["colour"], "pattern": doc["pattern"],
                       "season": doc.get("season", [])})
    return {"pieces": pieces, "total": len(docs)}


LIST_WARDROBE = Tool(
    name="list_wardrobe",
    description=("List the pieces in the user's wardrobe, optionally only one category or one colour. "
                 "Example: list_wardrobe(category='bottom', colour='black') for the black bottoms. "
                 "Do not use it to find a piece by a description, and do not use it for shop items."),
    args_model=ListWardrobeArgs,
    fn=list_wardrobe,
)


class SearchWardrobeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=80)
    category: Optional[Category] = None


def search_wardrobe(ctx, args):
    """The Wardrobe page's word search (step 3b): the words in English, FashionCLIP's text vector, the words cut,
    the same `find_owned` as POST /search. Only ctx.user_id's pieces."""
    rules = search.load_rules()
    query = search.normalise_query(args.query, search.load_terms())
    if not query:
        raise ToolError("no_words", "The query has no words to search for. Use the names of clothes or colours.")
    vector = ctx.request.app.state.analyzer.embed_text(query)
    ranked = find_owned(ctx.db, ctx.user_id, vector, rules["text_cut"], int(rules["default_limit"]), rules,
                        category=args.category)
    pieces = [{"ref": ctx.ledger.add(r["item"]["_id"]), "category": r["item"]["category"],
               "type": r["item"]["sub_category"], "colour": r["item"]["colour"], "close": r["close"]}
              for r in ranked["results"]]
    return {"pieces": pieces, "nothing_close": ranked["nothing_close"]}


SEARCH_WARDROBE = Tool(
    name="search_wardrobe",
    description=("Find the user's own pieces that look like a short description, best match first; close = a sure "
                 "match. Example: search_wardrobe(query='white shirt') to check whether the user owns one. "
                 "Do not use it to list everything (use list_wardrobe) or to find shop items."),
    args_model=SearchWardrobeArgs,
    fn=search_wardrobe,
)
```

### `backend/app/assistant/tools_stylist.py`

```python
"""
The Stylist's outfit and weather tools (step 3d). Each one calls the SAME function a screen calls (one function, two
callers), so the chat and the app never disagree:

    get_weather      the Dress page's weather engine (30-minute cache), at the default city
    suggest_outfits  GET  /outfits/today   (routers/dress.py `today`: same seed, so the same three outfits today)
    build_outfit     POST /outfits/build   (routers/dress.py `build`)
    score_outfit     POST /outfits/score   (routers/outfits.py `score` -> compatibility.score_outfit)

The route functions are plain Python functions: the tool gives them the /chat request and the logged-in user. Their
answers hold item ids, so each tool translates them before the model sees anything: pieces become ledger refs, scores
whole numbers 0-100, reasons the explanation codes with their sign ("+colour_pair"). No id, no free text.
"""

from typing import Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .. import ml  # noqa: F401  (puts src/ on the import path)
import dress

from ..routers import dress as dress_routes
from ..routers import outfits as outfit_routes
from ..schemas import BuildIn, ItemIds
from ..security import user_gender
from ..weather import WeatherUnavailable
from .tools import Tool, ToolError

Occasion = Literal[tuple(c["chip"] for c in dress.load_occasions())]     # everyday, work, ... (dress_occasions.csv)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def screen(ctx, route, *args, clash_code="refused", **kwargs):
    """Call a screen's route function as the logged-in user; its HTTP refusals become tool errors."""
    if user_gender(ctx.user) is None:                     # the screens answer 409 until the app has asked it
        raise ToolError("gender_required", "The user has not said men or women yet; outfits need it.")
    try:
        return route(*args, request=ctx.request, user=ctx.user, **kwargs)
    except HTTPException as error:
        raise ToolError(clash_code if error.status_code == 422 else "refused", str(error.detail)) from error


def reasons(outfit):
    return [e["sign"] + e["code"] for e in outfit.get("explanations", [])]


def outfit_for_model(outfit, ledger):
    return {"pieces": [ledger.add(i["id"]) for i in outfit["items"]], "label": outfit.get("label"),
            "score": round(outfit["score"]), "complete": outfit.get("complete"), "missing": outfit.get("missing"),
            "reasons": reasons(outfit)}


# ---------------------------------------------------------------- get_weather
class WeatherArgs(Strict):
    pass                                                  # no arguments


def get_weather(ctx, args):
    state = ctx.request.app.state
    if state.weather is None:
        raise ToolError("weather_unavailable", "The weather is switched off.")
    try:                                                  # the server stores no position: the default city
        today = state.weather.today(state.settings.weather_lat, state.settings.weather_lon)
    except WeatherUnavailable as error:
        raise ToolError("weather_unavailable", "The weather service cannot be reached.") from error
    return {"location": "default city", "temp_c": round(today["temperature"]), "condition": today["condition"],
            "rain": bool(today["rain_likely"]), "season": today["season"]}


# ---------------------------------------------------------------- suggest_outfits
class SuggestArgs(Strict):
    occasion: Optional[Occasion] = None


def suggest_outfits(ctx, args):
    page = screen(ctx, dress_routes.today, occasion=args.occasion or "everyday", shuffle=0, lat=None, lon=None)
    return {"occasion": page["occasion"], "season": page["season"],
            "outfits": [outfit_for_model(o, ctx.ledger) for o in page["outfits"]], "missing": page["missing"]}


# ---------------------------------------------------------------- build_outfit
class BuildArgs(Strict):
    pieces: list[int] = Field(min_length=1, max_length=3)
    occasion: Optional[Occasion] = None


def build_outfit(ctx, args):
    page = screen(ctx, dress_routes.build, BuildIn(item_ids=args.pieces, occasion=args.occasion))
    return {"outfits": [outfit_for_model(o, ctx.ledger) for o in page["outfits"]],
            "notes": [n["code"] for n in page["notes"]]}


# ---------------------------------------------------------------- score_outfit
class ScoreArgs(Strict):
    pieces: list[int] = Field(min_length=2, max_length=6)


def score_outfit(ctx, args):
    result = screen(ctx, outfit_routes.score, ItemIds(item_ids=args.pieces), clash_code="pieces_clash")
    return {"score": round(result["score"]),
            "parts": {k: (None if v is None else round(v * 100)) for k, v in result["parts"].items()},
            "complete": result["complete"], "missing": result["missing"], "reasons": reasons(result)}


GET_WEATHER = Tool("get_weather", (
    "Today's weather at the user's city: temperature, condition, rain, and the season to dress for. "
    "Example: get_weather() before advising a jacket. Do not use it for other days or other cities."),
    WeatherArgs, get_weather)
SUGGEST_OUTFITS = Tool("suggest_outfits", (
    "Today's three outfits from the user's wardrobe, the same ones the Dress page shows, for an occasion. "
    "Example: suggest_outfits(occasion='work') for 'what should I wear to work?'. "
    "Do not use it to build around a piece the user names (use build_outfit)."),
    SuggestArgs, suggest_outfits)
BUILD_OUTFIT = Tool("build_outfit", (
    "Up to three outfits built around 1 to 3 of the user's pieces, given by their numbers from this turn. "
    "Example: build_outfit(pieces=[2]) for 'what goes with my black jeans?' after finding them as {2}. "
    "Do not use it with numbers you were not given in this turn."),
    BuildArgs, build_outfit, piece_args=("pieces",))
SCORE_OUTFIT = Tool("score_outfit", (
    "Score 0-100 for 2 to 6 of the user's pieces worn together, with the part scores and the reasons. "
    "Example: score_outfit(pieces=[1, 3]) for 'do these go together?'. "
    "Do not use it to find new outfits (use suggest_outfits or build_outfit)."),
    ScoreArgs, score_outfit, piece_args=("pieces",))
```

### `backend/app/main.py` (the whole file; `create_app` loads the agents, builds the registry and the model client)

The three assistant lines are `registry = default_registry()`, `agents = load_agents(settings.mappings_dir / "agents.yaml", registry.names())`
(both run at app creation, so a broken `agents.yaml` stops start-up) and, inside `lifespan`, `app.state.chat_model = chat_model or make_ollama(settings, agents.model)`.

```python
"""
The DressMe API (FastAPI).

Run from the backend/ folder (models load in ~1 min, then the API is ready):
    uvicorn app.main:create_app --factory --port 8000
Interactive documentation: http://localhost:8000/docs

`create_app` takes optional replacements for the models, the background remover,
the try-on engine, the weather, the chat model and the price model, so the tests run in seconds with small fakes (see tests/conftest.py).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .assistant import default_registry
from .assistant.agents import load_agents
from .assistant.ollama import make_ollama
from .background import load_remover
from .config import Settings
from .db import connect
from .jobs import JobRunner
from .listings import ListingIndex, backfill_gender
from .routers import (admin, admin_xai, auth, chat, decisions, dress, explain, insights, items, listings, outfits, search,
                      tryon, vocab, wear, weather)
from .routers import price as price_routes
from .tryon import make_tryon
from .weather import make_weather


def create_app(settings=None, analyzer=None, catalog=None, remover=None,
               tryon_engine=None, weather_engine=None, chat_model=None, price=None):
    settings = settings or Settings()
    settings.check()
    # the assistant: its tools and agents are checked NOW, so a broken mappings/agents.yaml stops the start-up
    registry = default_registry()
    agents = load_agents(settings.mappings_dir / "agents.yaml", registry.names())

    @asynccontextmanager
    async def lifespan(app):
        app.state.settings = settings
        app.state.registry, app.state.agents = registry, agents
        app.state.chat_model = chat_model or make_ollama(settings, agents.model)   # Ollama (step 3d)
        app.state.db = connect(settings)
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        if analyzer is None or catalog is None:
            from .ml import Analyzer, Catalog      # the real models (slow to load)
        app.state.analyzer = analyzer or Analyzer()
        app.state.catalog = catalog or Catalog()
        classifier = getattr(app.state.analyzer, "classify_for_mask", None)
        app.state.remover = remover or load_remover(settings, classifier)   # None = keep backgrounds
        app.state.tryon = tryon_engine or make_tryon(settings)   # None = switched off
        app.state.weather = weather_engine or make_weather(settings)   # None = switched off
        if price is None:
            from price import make_price_model      # src/phase4/price.py (on the path through ml)
        app.state.price = price or make_price_model(settings)   # None = no model file yet
        app.state.listing_index = ListingIndex()
        backfill_gender(app.state.db)      # older listings get men / women / unisex
        app.state.jobs = JobRunner(app.state.db, settings.storage_dir)   # collector runs (admin)
        yield

    app = FastAPI(title="DressMe API", version="0.1", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["*"], allow_headers=["*"])
    for r in (auth.router, chat.router, items.router, explain.router, outfits.router, dress.router, decisions.router, insights.router, search.router,
              listings.router, tryon.router, weather.router, vocab.router, wear.router, admin.router, admin_xai.router,
              price_routes.router):
        app.include_router(r)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
```

(`default_registry()` is in `backend/app/assistant/__init__.py`; the registered tools today are `list_wardrobe`,
`search_wardrobe`, `get_weather`, `suggest_outfits`, `build_outfit`, `score_outfit`. The Ollama client is
`backend/app/assistant/ollama.py`, the loop `loop.py`, the registry/`Tool`/`ToolError`/`ToolContext` `tools.py`, the
ref ledger `ledger.py`, the route `backend/app/routers/chat.py`; none of them was asked for, so their text is not pasted.)

### Settings: `backend/app/config.py` (defines `CHAT_MODEL` and `OLLAMA_URL`)

```python
"""
Settings, read from environment variables (or backend/.env, never committed).

    MONGO_URL        default mongodb://localhost:27017
    MONGO_DB         default dressme
    JWT_SECRET       REQUIRED in real use: a long random string
    JWT_HOURS        how long a log-in lasts (default 72)
    STORAGE_DIR      where uploaded photos go (default backend/storage)
    REMOVE_BACKGROUND  1 (default) = put uploaded photos on white before analysing them, 0 = off
    BACKGROUND_MODEL   rembg model for that (default u2net)
    CLOTH_MODEL        rembg model that keeps only the garment when it is worn
                       (default u2net_cloth_seg; empty = keep the whole person)
    TRYON_ENGINE     space (default: a Hugging Face Space, see tryon.py) or off
    TRYON_SPACES     Hugging Face Spaces tried in order (see tryon.py), comma-separated
    TRYON_STEPS      diffusion steps per garment (default 30: fewer = faster, rougher)
    HF_TOKEN         optional Hugging Face token: a bigger free GPU quota on the Space
    WEATHER_ENGINE   open-meteo (default, free, no key; see weather.py) or off
    WEATHER_LAT / WEATHER_LON / WEATHER_PLACE   place used when the app sends no position
                     (default Tunis: 36.81, 10.18)
    CORS_ORIGINS     comma-separated, default http://localhost:5173 (React dev server)
    CHAT_MODEL       the assistant's model in Ollama (default qwen3.5:4b; teammates may use dressme-chat-v4,
                     which is not evaluated: docs/superpowers/handoff/assistant-model.md)
    OLLAMA_URL       where Ollama answers (default http://host.docker.internal:11434 = the PC, seen from Docker)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
# the project code the API reuses (classifier, compatibility, connectors, ...)
SRC_DIRS = [ROOT / "src" / folder for folder in ("common", "phase3", "phase4")]
load_dotenv(BACKEND_DIR / ".env")


@dataclass
class Settings:
    mongo_url: str = field(default_factory=lambda: os.getenv("MONGO_URL", "mongodb://localhost:27017"))
    mongo_db: str = field(default_factory=lambda: os.getenv("MONGO_DB", "dressme"))
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    jwt_hours: int = field(default_factory=lambda: int(os.getenv("JWT_HOURS", "72")))
    storage_dir: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_DIR", BACKEND_DIR / "storage")))
    tryon_engine: str = field(default_factory=lambda: os.getenv("TRYON_ENGINE", "space").lower())
    tryon_spaces: str = field(default_factory=lambda: os.getenv(
        "TRYON_SPACES",
        "zhengchong/CatVTON, Kwai-Kolors/Kolors-Virtual-Try-On, yisol/IDM-VTON, levihsu/OOTDiffusion"))
    tryon_steps: int = field(default_factory=lambda: int(os.getenv("TRYON_STEPS", "30")))
    tryon_timeout: float = 180.0       # seconds per garment (a sleeping Space wakes up first)
    tryon_max_garments: int = 3        # chained garments per try-on (each costs GPU quota)
    hf_token: str = field(default_factory=lambda: os.getenv("HF_TOKEN", ""))
    weather_engine: str = field(default_factory=lambda: os.getenv("WEATHER_ENGINE", "open-meteo").lower())
    weather_lat: float = field(default_factory=lambda: float(os.getenv("WEATHER_LAT", "36.81")))
    weather_lon: float = field(default_factory=lambda: float(os.getenv("WEATHER_LON", "10.18")))
    weather_place: str = field(default_factory=lambda: os.getenv("WEATHER_PLACE", "Tunis"))
    cors_origins: list = field(default_factory=lambda: os.getenv(
        "CORS_ORIGINS", "http://localhost:5173").split(","))
    chat_model: str = field(default_factory=lambda: os.getenv("CHAT_MODEL", "qwen3.5:4b"))
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://host.docker.internal:11434"))
    mappings_dir: Path =field(default_factory=lambda: ROOT / "mappings")   # formula CSVs
    max_upload_mb: int = 10
    max_image_side: int = 1024     # uploads are shrunk to save disk
    remove_background: bool = field(default_factory=lambda: os.getenv("REMOVE_BACKGROUND", "1") != "0")
    background_model: str = field(default_factory=lambda: os.getenv("BACKGROUND_MODEL", "u2net"))
    cloth_model: str = field(default_factory=lambda: os.getenv("CLOTH_MODEL", "u2net_cloth_seg"))

    def check(self):
        if len(self.jwt_secret) < 32:
            raise RuntimeError("Set JWT_SECRET (at least 32 characters) in backend/.env")
```

Values in force on this PC: `CHAT_MODEL` and `OLLAMA_URL` are **not set in `backend/.env`**, so `qwen3.5:4b` at
`http://host.docker.internal:11434`.

### `backend/app/routers/search.py`: `find_owned` (the function the `search_wardrobe` tool shares with `POST /search`)

```python
def find_owned(db, user_id, vector, cut, limit, rules, category=None):
    """The user's own pieces nearest to `vector` (search.rank_owned). When none is close, only the nearest
    `closest_anyway` are kept. Only this user's pieces are ever loaded: the user filter is in the query itself."""
    query = {"user_id": user_id, **({"category": category} if category else {})}
    pieces = [{**d, "vector": vector_from_bson(d.get("vector"))} for d in db.items.find(query)]
    ranked = search.rank_owned(vector, pieces, cut, limit)
    if ranked["nothing_close"]:                          # say so, and still show the nearest few
        ranked["results"] = ranked["results"][:int(rules["closest_anyway"])]
    return ranked
```

It returns `{"results": [{"item": <db doc>, "similarity": float, "close": bool}], "nothing_close": bool, "skipped_no_vector": int}`.
(The rest of that file is `POST /search`: multipart `text` or `photo`, optional `limit`; 400 codes
`search_text_and_photo`, `search_need_text_or_photo`, `search_text_too_long`, `search_text_no_words`.)

### `backend/app/routers/auth.py`: the login endpoint only

```python
@router.post("/auth/login")
def login(body: Login, request: Request):
    db, settings = request.app.state.db, request.app.state.settings
    user = db.users.find_one({"email": body.email.lower()})
    # same message for unknown email and wrong password (do not reveal which)
    if not user or not check_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Wrong email or password")
    if user.get("disabled"):
        raise HTTPException(403, "This account is disabled")
    return {"token": make_token(user["_id"], settings), "user": profile_out(user)}
```

Request body `{"email", "password"}`; answer `{"token": <JWT>, "user": {id, email, role, demo, name, gender, min_coverage,
language, budget_tnd, consent_at, needs_gender}}`. Send the token as `Authorization: Bearer <token>`.

---

## 3. Tests

Fixtures live in `backend/tests/conftest.py` (there is no top-level `tests/`). Run them in the container (section 1).

### `backend/tests/conftest.py`

```python
"""
Test setup: the real FastAPI app with small FAKE models, try-on and weather, on a
separate MongoDB database (dressme_test, emptied before and after each test).

The fake analyzer reads the photo's colour, so a test chooses what is
"recognised" by the colour of the picture it uploads:
    red -> top, blue -> bottom (jeans), black -> shoes, green -> dress, white -> bag
"""

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pymongo import MongoClient

from app.assistant.model import NoModel
from app.config import Settings
from app.main import create_app
from app.weather import OpenMeteo

TEST_DB = "dressme_test"
FAKE = {  # rgb -> what the fake "model" answers
    (200, 30, 30): ("top", "t-shirt", "red"),
    (30, 60, 200): ("bottom", "jeans", "blue"),
    (10, 10, 10): ("shoes", "sneakers", "black"),
    (40, 160, 80): ("dress", "dress", "green"),
    (250, 250, 250): ("bag", "handbag", "white"),
}


def fake_vector(seed):
    v = np.random.default_rng(seed).normal(size=512) + 3.0   # all fairly similar
    return (v / np.linalg.norm(v)).astype(np.float32)


class FakeAnalyzer:
    def analyze(self, img):
        rgb = tuple(int(c) for c in np.asarray(img).reshape(-1, 3).mean(0).round())
        category, sub, colour = FAKE[min(FAKE, key=lambda k: sum(abs(a - b) for a, b in zip(k, rgb)))]
        return {"category": {"value": category, "conf": 0.95},
                "sub_category": {"value": sub, "conf": 0.9},
                "pattern": {"value": "solid", "conf": 0.8},
                "colour": {"value": colour, "conf": 0.9},
                "vector": fake_vector(sum(rgb))}

    def embed_image(self, img):
        """The vector analyze() gives the same picture, so a photo search finds the piece of the same colour."""
        return fake_vector(sum(int(c) for c in np.asarray(img).reshape(-1, 3).mean(0).round()))

    def embed_text(self, text):
        """A fixed fake vector per text."""
        return fake_vector(sum(map(ord, text)))

    def concept_vectors(self, gender=None):
        """{concept: vector} for the team's concepts (fixed fakes, like the real text vectors)."""
        import explain_similarity
        return {r["concept"]: fake_vector(1000 + i)
                for i, r in enumerate(explain_similarity.load_concepts(gender=gender))}

    def explain(self, img, head=None, value=None):
        """Like the real one: fixed small pictures, alternatives from analyze()."""
        fields = ["category", "sub_category", "pattern", "colour"]
        if head is not None and head not in fields:
            raise ValueError(f"unknown field {head!r}")
        if value == "nonsense":
            raise ValueError(f"unknown {head} {value!r}")
        analysis = self.analyze(img)
        out = {}
        for f in [head] if head else fields:
            best = analysis[f]
            entry = {"shown": value or best["value"],
                     "alternatives": [{"value": best["value"], "conf": best["conf"]},
                                      {"value": "other", "conf": round(1 - best["conf"], 3)}]}
            picture = Image.new("RGB", (8, 8), (255, 0, 0))
            if f == "colour":
                entry.update(pixels=picture, share=0.5, reliable=True)
            else:
                entry["heatmap"] = picture
            out[f] = entry
        return out


class FakeCatalog:
    last_genders = "not called"     # what the last search asked for (tests check the filter)

    def search(self, vector, k=6, category=None, genders=None):
        self.last_genders = genders
        return [{"id": f"pv_{i}", "category": category or "top", "sub_category": "",
                 "colour": "black", "score": 0.9 - i / 100} for i in range(k)]

    def search_shop(self, vector, k=6, category=None, genders=None):
        self.last_genders = genders
        return [{"id": f"hm_{i}", "name": f"Product {i}", "shop": "H&M", "department": "Menswear",
                 "category": category or "top", "sub_category": "", "colour": "navy",
                 "score": 0.8 - i / 100} for i in range(k)]

    def image(self, item_id):
        known = item_id.startswith(("pv_", "hm_"))
        return Image.new("RGB", (20, 20), (128, 128, 128)) if known else None

    def vector(self, item_id):
        """The stored picture vector of a dataset / H&M item (a fixed fake)."""
        return fake_vector(sum(map(ord, item_id)))

    def mean_vector(self):
        """The "average picture" for the concept baseline (a fixed fake)."""
        return fake_vector(7)


class FakeTryOn:
    """Records each call and returns the person photo with a band of the
    garment's colour, so a test can see what was "put on" and in what order."""

    def __init__(self, fail_after=None, fail_kinds=()):
        self.calls, self.descriptions = [], []
        self.fail_after = fail_after     # raise TryOnBusy from this call number on
        self.fail_kinds = fail_kinds     # raise TryOnBusy for these kinds (e.g. "lower")

    def dress(self, person, garment, kind, description=""):
        from app.tryon import TryOnBusy
        if kind in self.fail_kinds or (self.fail_after is not None and len(self.calls) >= self.fail_after):
            raise TryOnBusy("Space asleep")
        self.calls.append(kind)
        self.descriptions.append(description)
        out = person.copy()
        out.paste(garment.resize((out.width, 8)), (0, 0))
        return out


class FakeWeather(OpenMeteo):
    """The real engine (cache, simplify) with a canned Open-Meteo answer: no network.
    `raw` can be changed by a test; `calls` lists the places asked for."""

    def __init__(self, raw=None):
        super().__init__(settings=None)
        self.raw = raw or open_meteo_answer()
        self.calls = []

    def fetch(self, lat, lon):
        self.calls.append((lat, lon))
        return self.raw


class FakePriceModel:
    """Like src/phase4/price.PriceModel.estimate, without the trained file: a fixed
    band for the friperie / classified channels, None for any other (as the real one).
    `calls` lists (category, channel) and the vector length, so tests see what was read."""

    def __init__(self):
        self.calls = []

    def estimate(self, vector, category=None, channel="friperie", rules=None):
        self.calls.append((len(vector), category, channel))
        if channel not in ("friperie", "classified"):
            return None
        return {"low": 20, "median": 25, "high": 32, "channel": channel, "based_on": "category",
                "count": 53, "percentile": 0.42, "typical_error_factor": 1.53,
                "note": "Estimated against friperie and Instagram resale prices."}


def open_meteo_answer(feels=(20, 28), rain=10, code=2, now=26):
    return {"current": {"temperature_2m": now, "apparent_temperature": now + 0.4, "weather_code": code},
            "daily": {"temperature_2m_min": [feels[0] - 1], "temperature_2m_max": [feels[1] - 1],
                      "apparent_temperature_min": [feels[0]], "apparent_temperature_max": [feels[1]],
                      "precipitation_probability_max": [rain], "weather_code": [code]}}


def photo(rgb, size=(64, 80)):
    buf = io.BytesIO()
    Image.new("RGB", size, rgb).save(buf, format="PNG")
    return ("photo.png", buf.getvalue(), "image/png")


RED, BLUE, BLACK, GREEN, WHITE = FAKE


@pytest.fixture
def settings(tmp_path):
    # remove_background=False: no rembg in the tests unless a fake remover is passed
    return Settings(mongo_db=TEST_DB, jwt_secret="test-secret-" + "x" * 40,
                    storage_dir=tmp_path / "storage", remove_background=False)


@pytest.fixture
def make_client(settings):
    MongoClient(settings.mongo_url).drop_database(TEST_DB)
    clients = []

    def make(remover=None, tryon=None, weather=None, chat_model=None, price=None):
        app = create_app(settings, analyzer=FakeAnalyzer(), catalog=FakeCatalog(),
                         remover=remover, tryon_engine=tryon or FakeTryOn(), weather_engine=weather or FakeWeather(),
                         chat_model=chat_model or NoModel(),      # never the real Ollama: the assistant answers 503
                         price=price or FakePriceModel())
        c = TestClient(app)
        c.__enter__()            # runs the start-up (database connection)
        clients.append(c)
        return c

    yield make
    for c in clients:
        c.__exit__(None, None, None)
    MongoClient(settings.mongo_url).drop_database(TEST_DB)


@pytest.fixture
def client(make_client):
    return make_client()


def sign_up(client, email="amira@example.com", name="Amira", gender="women"):
    r = client.post("/auth/register", json={"email": email, "password": "secret-pass", "name": name,
                                            "gender": gender})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def upload(client, headers, rgb):
    r = client.post("/items", files={"photo": photo(rgb)}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()
```

### `backend/tests/test_chat.py`

```python
"""
POST /chat (step 3c): the whole path with a scripted fake model and the real list_wardrobe tool on the golden wardrobe.
"""

import json

from pymongo import MongoClient

from app.assistant.model import FakeModel, ModelReply, ToolCall
from tests.conftest import RED, TEST_DB, photo, sign_up
from tests.test_golden import WARDROBE, stored


def wardrobe_then(answer):
    return FakeModel([ModelReply(tool_calls=[ToolCall("list_wardrobe", {"limit": 5})]), ModelReply(text=answer)])


def test_a_turn_with_the_golden_wardrobe(make_client, settings):
    model = wardrobe_then("Try {2} with {1}. {99}")
    # the golden fixture builds its own client, so the golden user is seeded here, on a client with the fake model
    client = make_client(chat_model=model)
    user = WARDROBE["user"]
    headers = sign_up(client, user["email"], user["name"], user["gender"])
    db = MongoClient(settings.mongo_url)[TEST_DB]
    user_id = db.users.find_one({"email": user["email"]})["_id"]
    db.items.insert_many([stored(d, user_id) for d in WARDROBE["items"]])
    owned = {d["id"] for d in WARDROBE["items"]}

    r = client.post("/chat", json={"message": "What can I wear with my black jeans?"}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"] == "Try {2} with {1}."                     # {99} was invented: removed
    assert body["stop_reason"] == "answered" and body["agent"] == "stylist" and body["model"] == "fake"
    assert sorted(body["pieces"]) == ["1", "2"]
    assert {p["id"] for p in body["pieces"].values()} <= owned       # the user's own items
    assert [(t["tool"], t["ok"], t["n_pieces"]) for t in body["trace"]] == [("list_wardrobe", True, 5)]

    # the model saw coded pieces only: refs, never an id or a photo
    tool_message = json.loads(model.received[1]["messages"][-1]["content"])
    assert tool_message["total"] == len(WARDROBE["items"]) and len(tool_message["pieces"]) == 5
    assert set(tool_message["pieces"][0]) == {"ref", "category", "type", "colour", "pattern", "season"}
    assert not any(item_id in json.dumps(tool_message) for item_id in owned)      # no database id reached the model

    saved = db.chats.find_one({"user_id": user_id})
    assert saved["message"] == "What can I wear with my black jeans?" and saved["answer"] == "Try {2} with {1}."
    assert saved["chat_id"] == body["chat_id"] and saved["unknown_refs"] == [99] and len(saved["item_ids"]) == 2
    event = db.events.find_one({"type": "assistant"})
    assert (event["agent"], event["n_tool_calls"], event["n_unknown_refs"]) == ("stylist", 1, 1)
    assert "message" not in event and "What can I wear" not in json.dumps(event, default=str)


def test_another_user_never_sees_the_first_users_items(make_client):
    model = FakeModel([ModelReply(tool_calls=[ToolCall("list_wardrobe", {})]), ModelReply(text="Nothing to wear: {1}.")])
    client = make_client(chat_model=model)
    first = sign_up(client, "first@example.com", "First")
    client.post("/items", files={"photo": photo(RED)}, headers=first)
    second = sign_up(client, "second@example.com", "Second")

    r = client.post("/chat", json={"message": "What do I own?"}, headers=second)
    assert r.status_code == 200
    tool_message = json.loads(model.received[1]["messages"][-1]["content"])
    assert tool_message == {"pieces": [], "total": 0}                # the first user's red top is not there
    assert r.json()["pieces"] == {} and r.json()["answer"] == "Nothing to wear:."   # {1} was never shown: removed


def test_no_model_answers_503_assistant_unavailable(client):
    headers = sign_up(client)
    r = client.post("/chat", json={"message": "Hello"}, headers=headers)
    assert r.status_code == 503 and r.json()["detail"] == "assistant_unavailable"
    assert client.app.state.db.chats.count_documents({}) == 0       # a failed turn saves nothing


def test_the_request_is_checked(make_client):
    client = make_client(chat_model=FakeModel([ModelReply(text="Hi")]))
    headers = sign_up(client)
    assert client.post("/chat", json={"message": ""}, headers=headers).status_code == 422
    assert client.post("/chat", json={"message": "x" * 1001}, headers=headers).status_code == 422
    unknown = client.post("/chat", json={"message": "Hi", "agent": "wizard"}, headers=headers)
    assert unknown.status_code == 422 and unknown.json()["detail"] == "unknown_agent"
    assert client.post("/chat", json={"message": "Hi"}).status_code in (401, 403)       # a login is needed
    ok = client.post("/chat", json={"message": "Hi", "chat_id": "abc-1"}, headers=headers)
    assert ok.status_code == 200 and ok.json()["chat_id"] == "abc-1"
```

### Summary of `backend/tests/test_assistant_engine.py` (12 tests, no database, no real model)

- Tests the engine alone (`loop.run_turn`, `Registry`, `PieceLedger`, `resolve`) with a scripted `FakeModel` and a tiny
  fake registry of two tools: `echo` (puts two item ids "id-a"/"id-b" in the ledger) and `wear` (takes a piece ref, records
  the item id it receives after the translation). `ToolContext(user_id="u1", db=None, ledger=PieceLedger())`.
- `make_agent()` builds an `Agent(job, instructions, tools=["echo","wear"], keywords={}, max_rounds, max_tokens=100)`
  directly; helpers `say(text)` and `call(name, **args)` make `ModelReply` objects.
- Covers: an answer without tools returns at once; invalid arguments go back to the model as a tool message
  (`invalid_arguments`) and it corrects them; the same call twice stops with `repeat` and a final no-tools call;
  `max_rounds` forces a final answer; a tool the agent was not given is refused (`unknown_tool`); a stripped `<think>`
  block is noted in the trace; known `{n}` stay and invented ones are removed and reported; the same item keeps its ref;
  an unknown piece ref in the arguments is rejected and the tool does not run; an unknown or crashing tool is an error
  result, not an exception; schemas use the tools format.
- No fake users or items are needed: pieces are just strings in the ledger.

### Summary of `backend/tests/test_stylist_tools.py` (9 tests, MongoDB `dressme_test`, fake model, fake analyzer)

- One fixture, `golden_chat`: `make_client(chat_model=FakeModel([]))`, `sign_up` as the golden user, then
  `db.items.insert_many([stored(d, user_id) for d in WARDROBE["items"]])` using `WARDROBE` and `stored` imported from
  `tests/test_golden.py` (the frozen 17-item women's wardrobe in `tests/golden/wardrobe.json`, real FashionCLIP vectors,
  no photos).
- `ask(*calls)` appends one scripted tool-call reply per `(tool, arguments)`, then a final text naming every ref
  (`{1} ... {39}`), POSTs `/chat`, and returns `(what the model read from the LAST tool message, {ref: item id})`. It
  also asserts that no 24-hex database id appears in any tool message and that every ref maps to an owned item.
- Each test compares a tool with the screen it wraps: `search_wardrobe` vs `POST /search` (same order, same
  `nothing_close`; the `closest_anyway` cut is checked by monkeypatching `search.load_rules` with `text_cut` 2.0; the
  `no_words` error for ",,"); `get_weather` (the fake weather gives `{"location": "default city", "temp_c": 26,
  "condition": "cloudy", "rain": False, "season": "summer"}`); `suggest_outfits` vs the Dress page; `build_outfit` vs the
  Build page; `score_outfit` vs `/outfits/score`; refs live for one turn only; clashing pieces give a readable
  `pieces_clash` error.
- Other test files that matter for the next steps: `test_ollama_client.py` (the Ollama translator, with an
  `httpx.MockTransport`, so no Ollama is needed; also `GET /assistant/status`), `test_agents_yaml.py` (start-up validation), `test_golden*.py` (frozen answers; `GOLDEN_RECORD=1` rewrites
  them, only in a reviewed PR), `test_deletion_complete.py` (every per-user collection must be emptied; a new one goes in
  `db.USER_COLLECTIONS`).

---

## 4. Demo wardrobe

### How it is created

```
cd backend
python -m app.seed_demo                       # the API must be running (it uploads through the API)
python -m app.seed_demo --api http://localhost:8000
```

File: `backend/app/seed_demo.py`. It registers `demo@example.com` (name "Amira", gender **women**) and
`admin@example.com` (role admin) with generated passwords that it appends to `backend/.env` as `DEMO_PASSWORD` /
`DEMO_ADMIN_PASSWORD` (not read for this file). It then uploads **17 PolyVore test-split photos** through `POST /items`, so each
one is really analysed, with `random_state=11`: top 5, bottom 3, dress 2, outerwear 2, shoes 3, bag 2. It reads
`data/processed/dressme.csv`. Re-running only adds missing pieces. The accounts get `demo: true`.

### Important: the demo account does NOT exist on this PC right now

I queried MongoDB (`dressme` database): 2 users, **0 demo accounts**, 10 items. Both users are real people
(`profile.gender` = `men` for both), so there is **no demo wardrobe to tabulate** and I did not run the seed (it would
change the database and write to `.env`). The per-item labels of a seeded demo wardrobe are model predictions on random
PolyVore photos, so they would differ from machine to machine anyway.

### Use this instead: the golden wardrobe (the fixture all assistant tests use)

`backend/tests/golden/wardrobe.json`, user `golden@example.com`, name "Golden", **gender women**, `min_coverage` 2.
17 items (colour empty = unknown, as the app stores it):

| # | category | sub_category | colour | pattern |
|---|---|---|---|---|
| 1 | top | t-shirt | pink | printed |
| 2 | top | top | pink | solid |
| 3 | top | top | white | printed |
| 4 | top | top | white | printed |
| 5 | top | top | (empty) | solid |
| 6 | bottom | skirt | black | solid |
| 7 | bottom | leggings | green | floral |
| 8 | bottom | shorts | grey | checked |
| 9 | dress | dress | (empty) | floral |
| 10 | dress | dress | grey | printed |
| 11 | outerwear | jacket | pink | solid |
| 12 | accessory | scarf | burgundy | printed |
| 13 | shoes | heels | pink | printed |
| 14 | shoes | casual-shoes | brown | printed |
| 15 | shoes | heels | (empty) | printed |
| 16 | bag | laptop-bag | black | solid |
| 17 | bag | handbag | pink | solid |

(Row order is the file's order; the file also holds `candidates` (3 scans), one shop `listing` and `scenarios`.) There is
also a second frozen wardrobe for a man, `wardrobe_men.json`, built by `make_wardrobe.py`.

---

## 5. Functions the next agents will wrap as tools

**Status in the current tree (after step 3a removed the old chat):** none of the old agent tools exist as such. They were
closures inside `backend/app/agents/*.py`, which were deleted. They are readable only through the git tag
`pre-chat-removal` (`git show pre-chat-removal:backend/app/agents/analyst.py`, etc.). The table says what is "found" now
and where the real logic lives; the "example" shapes below are **derived from reading the code, not from a live run**.

| name asked | current status | where the logic is now |
|---|---|---|
| buy_advice | found (logic) | `src/phase4/compatibility.py:447`, route `POST /buy-advice` `routers/outfits.py:193` |
| search_listings | **not found** | old tool in `pre-chat-removal:backend/app/agents/shopping.py:72`; the logic is `listing_query(...)` + `db.listings.find`, as in route `GET /listings` `routers/listings.py:80` |
| find_similar | **not found** | old tool `shopping.py:86`; the logic is route `GET /similar` `routers/outfits.py:237` and `ListingIndex.search` (`backend/app/listings.py:294`) |
| find_near_twins | **not found** under that name | `compatibility.near_twins(items, rules)` `src/phase4/compatibility.py:507` |
| wardrobe_insights | found | `compatibility.wardrobe_insights` `src/phase4/compatibility.py:522`, route `GET /insights` `routers/insights.py:49` |
| wardrobe_stats | **not found** under that name | `wardrobe_counts(docs)` `backend/app/routers/insights.py:25` |
| pieces_to_sell | **not found** | old tool `seller.py:37`; it was `wardrobe_insights()["unmatched"]` + `near_twins` |
| price_hint | **not found** | old tool `seller.py:47` (and `resale.py`, both deleted). Closest now: `PriceModel.estimate(vector, category, channel)` `src/phase4/price.py`, route `GET /price-estimate` `routers/price.py` |
| my_listings | **not found as a tool**; a route function with that name exists | `my_listings(request, user)` `backend/app/routers/listings.py:115` (`GET /listings/mine`) |
| prepare_sell | **not found** | old tool `seller.py:72` (built a link `/sell?item=..&price=..`; posted nothing) |
| complete_outfit | found (logic) | `compatibility.complete_outfit` `src/phase4/compatibility.py:490`, route `POST /outfits/complete` `routers/outfits.py:178` |
| what_if | **not found** | old tool `explainer.py:161` (scored an outfit before and after removing/adding a piece) |
| how_scoring_works | **not found** | old tool `explainer.py:282` (read weights and cuts from `rules`) |
| explain_* | **not found** as functions with that name, except `explain_pair`; see below | |

### Signatures and example returns

**buy_advice** — `src/phase4/compatibility.py:447`

```python
def buy_advice(candidate, wardrobe, profile=None, rules=RULES):
```
Inputs are "compat" dicts (`backend/app/wardrobe.py` `to_compat(doc)`). Returns:
```python
{"verdict": "buy" | "think" | "skip", "good_outfits": 3,
 "reasons": ["you already own 1 very similar top item(s)"],                 # empty or one line
 "best": [{"score": 78.4, "parts": {...}, "reasons": [...], "items": [<compat item>, ...]}],   # up to 3
 "detail": {"outfits": [{"item_ids": [...], "score": 74.1, "owned_id": "..", "owned_score": 61.0}],
            "twins": [{"id": "..", "similarity": 0.931}]}}
```
The route adds `confidence` (high/medium/low), `codes`, `candidate`, and `explanation` (from
`explain_outfit.buy_explanation`: `path`, `to_next_verdict`, `beats`, `lost_to`, `near_misses`, `twins`).

**search_listings** — not found. Old signature (tag `pre-chat-removal`, `shopping.py:72`):
`search_listings(category="", sub_category="", colour="", max_price=0, n=5) -> {"total": int, "listings": [short_listing, ...]}`.
Today's equivalent is the route `list_listings(request, category, sub_category, colour, size, source, max_price, in_stock,
sort, gender, page, per_page, user)` returning `{"total", "page", "per_page", "items": [listing_out(d), ...]}`.

**find_similar** — not found. Old: `find_similar(item_id="", n=5) -> {"shop": [...], "listings": [...]}`. Today:
`similar(request, item_id, candidate_id, k=6, gender="mine", all_prices=False, user)` returns
`{"wardrobe": [item + similarity + why], "catalog": [...], "shop": [...], "listings": [...], "budget_cap": float|None, "query": {...}}`.
`ListingIndex.search(self, db, vector, k=6, category=None, exclude_seller=None, genders=None, max_price=None)`.

**find_near_twins** — not found under that name; `compatibility.near_twins(items, rules=RULES)` returns
`[(item_a, item_b, similarity), ...]` sorted by similarity, same category, similarity >= `similar_item` cut. Old tool shape:
`{"twins": [{"items": [piece, piece], "similarity": 0.94}]}`.

**wardrobe_insights** — `src/phase4/compatibility.py:522`

```python
def wardrobe_insights(wardrobe, profile=None, rules=RULES):
```
```python
{"good_outfits": 12, "complete": True, "outfit_use": {"<item id>": 4, ...},
 "versatile": [<compat item>, ...], "unmatched": [<compat item>, ...], "filtered": ["<id>", ...],
 "new_pairs": {"top": 3, "bottom": 5}, "missing": ["shoes"],          # also "top" | "bottom" | "main"
 "twins": [(item, item, 0.93)]}
```
The route `GET /insights` shapes it for the app: `{total, categories, colours, patterns, to_confirm, outfits: {good, complete,
good_score}, versatile, unmatched, filtered, new_pairs, missing, twins}`.

**wardrobe_stats** — not found under that name: `wardrobe_counts(docs)` (`routers/insights.py:25`) returns
`{"total": 17, "categories": [{"category": "top", "count": 5}], "colours": [{"colour": "pink", "count": 5, "neutral": False}],
"patterns": [{"pattern": "solid", "count": 7}], "to_confirm": {"colour": 2, "coverage": 17, "season": 17, "usage": 17}}`.

**pieces_to_sell** — not found. Old shape: `{"unmatched": [piece, ...], "twins": [{"keep": piece, "sell": piece, "similarity": 0.94}]}`
built from `wardrobe_insights()["unmatched"]` and `near_twins`.

**price_hint** — not found. Old shape: `{"low": 20, "high": 32, "median": 25, "based_on": "shops"|"friperie", "count": n, "examples": [...]}`
or `{"error": "no similar listings with a price yet"}`. Upstream's #68 variant (not merged here) returned
`{low, high, median, based_on, count, "source": "price_model"}`. Today's building block:
`PriceModel.estimate(vector, category=None, channel="friperie", rules=None)` in `src/phase4/price.py`, returning a band dict
`{"low": 20, "median": 25, "high": 32, "channel": "friperie", "based_on": "category", "count": 53, "percentile": 0.42,
"typical_error_factor": 1.53, "note": "..."}` or `None` when it cannot price (`app.state.price` is `None` without the model file).

**my_listings** — `backend/app/routers/listings.py:115`

```python
def my_listings(request: Request, user=Depends(current_user)):
```
Returns a list of `listing_out(d)` for the user's seller listings, newest first (status pending/active/rejected/gone,
`review_note`, price in TND). The old tool returned `{"listings": [{id, title, price_tnd, category, sub_category, colour, status, review_note, image_url}]}`
(max 10) and never city or contact.

**prepare_sell** — not found. Old: `prepare_sell(price_tnd, item_id="", title="", size="") -> {"action": {"kind": "sell", "url": "/sell?item=<id>&price=25&title=..&size=.."}, "item": {...}}`.
Posted nothing; the user adds city + contact on the Sell page.

**complete_outfit** — `src/phase4/compatibility.py:490`

```python
def complete_outfit(items, candidates, profile=None, k=5, rules=RULES):
```
Returns up to `k` `score_outfit` results sorted best first, each `{**score_outfit(items + [c]), "item": c}`, never a clash.
Route `POST /outfits/complete` (`Complete` body: `item_ids`, `k`) adds labels and the `item` for the app.

**what_if** — not found. Old: `what_if(item_ids, remove_id="", add_id="") -> {"before": {score, points, works, problems}, "after": {...}, "change": -4.2, "removed": piece, "added": piece}`.

**how_scoring_works** — not found. Old: `{"parts": {...}, "weights": {...}, "weights_note": ..., "good_outfit": 70, "verdict": {buy, think, skip},
"near_twin_similarity": ..., "label_unsure": {...}, "set_by": "the DressMe team, ..."}`, read from `rules.weights`, `rules.settings`, `explain.load_settings()`.

**explain_\* functions** — nothing named `explain_*` exists as a callable the next agents could wrap, except:

- `explain_similarity.explain_pair(a, b, va, vb, concept_vectors, k=3, baseline=None)` (`src/phase4/explain_similarity.py:86`),
  returns `{"shared": [...], "differs": [...], "both": [...], "contrast": [...]}`.
- Route functions: `explain_item(item_id, request, head=None, value=None, ...)` and `explain_candidate(candidate_id, ...)`
  (`backend/app/routers/explain.py:50/56`, Grad-CAM + alternatives for the labels), `explain_outfit_route(body, request, user)`
  (`routers/outfits.py:105`, `POST /outfits/explain`: `{swaps, weakest, pair_map}`).
- Building blocks in `src/phase4/explain_outfit.py`: `contributions(result, weights)`, `strengths(items, parts, rules, settings)`,
  `swaps(items, wardrobe, rules, style_profile)`, `weakest(swap_list, positive_only, min_gain)`, `pair_map(items, rules)`,
  `buy_explanation(advice, rules, settings)`; `src/phase4/explain.py` (`is_unsure`, Grad-CAM, `load_settings`).
- Old tools (tag `pre-chat-removal`, `explainer.py`): `explain_outfit`, `what_if`, `explain_labels`, `explain_verdict`,
  `explain_similarity`, `how_scoring_works`.

How the existing step 3d tools call screens (the pattern to copy): `tools_stylist.screen(ctx, route_fn, ...)` calls the
route function with `request=ctx.request, user=ctx.user`, turns an `HTTPException` into a `ToolError`, and the tool then
translates ids to ledger refs and reasons to signed codes. Rules per user come from `routers.outfits.rules_of(user)`,
the wardrobe from `routers.outfits.wardrobe(request, user)`, and compat dicts from `wardrobe.to_compat(doc)`.

---

## 6. Docs

### Files that mention step 3

`docs/superpowers/plans/`
- `2026-10-25-step-3a-remove-old-chat.md`
- `2026-10-25-step-3b-search.md`
- `2026-10-26-step-3c-assistant-skeleton.md`
- `2026-10-26-step-3d-real-stylist.md`

`docs/learn/`
- `step-3a.md`, `step-3b.md`, `step-3c.md`, `step-3d.md`

`docs/superpowers/manual-checks/` (the `manual-checks/` folder is under `docs/superpowers/`)
- `step-3a.md`, `step-3b.md`, `step-3c.md`, `step-3d.md`

Also relevant: `docs/superpowers/handoff/assistant-model.md` (below), and the discovery notes
`docs/superpowers/discovery/2026-10-25-step3-facts.md`. Team numbers for agents are in `mappings/agents.yaml`
(REVIEW), search in `mappings/search_rules.csv` / `search_terms.csv`.

### `docs/superpowers/handoff/assistant-model.md` (full)

````markdown
# Hand-off: the assistant's model (step 3d)

The assistant's answers come from a language model that runs in **Ollama on your own PC**, not in Docker. The backend
container reaches it at `http://host.docker.internal:11434`. Which model is a setting.

## 1. Pick the model

| `CHAT_MODEL` | Size | Who | Evaluated? |
|---|---|---|---|
| `qwen3.5:4b` (default) | 3.3 GB on disk, ~3.4 GB of GPU memory | everyone who can | **yes**: the only model the reports measure |
| `dressme-chat-v4` | 2.5 GB | a teammate short of disk space who already has it | **no** |

Why only one model is evaluated: the project's results (the live checks of 3d, the traps of 3g, the fine-tune of 3h)
must all describe the same model, or the numbers cannot be compared. `qwen3.5:4b` is the base that 3h fine-tunes.
`dressme-chat-v4` is the old chat's fine-tune (removed in step 3a): it is there only so the app runs on a smaller disk.
Its answers may be worse and nobody measures them, so never report a result made with it.

## 2. Set it up

1. Install Ollama (https://ollama.com) and start it (the tray icon, or `ollama serve`).
2. Pull the model: `ollama pull qwen3.5:4b` (or check that `ollama list` already shows `dressme-chat-v4`).
3. In `backend/.env` (never committed) add:
   ```
   CHAT_MODEL=qwen3.5:4b
   OLLAMA_URL=http://host.docker.internal:11434
   ```
   (Both are the defaults, so with the default model you may leave them out. Without Docker, use
   `OLLAMA_URL=http://localhost:11434`.)
4. Restart the backend: `docker compose up -d --build backend`, wait about a minute. Its log says
   `assistant: model qwen3.5:4b at http://host.docker.internal:11434; Ollama answered /api/show: yes`.
   `NO` means Ollama is off or does not have the model: the app still runs and the assistant answers 503.

## 3. Check it

- `GET /assistant/status` (logged in, e.g. from http://localhost:8000/docs) -> `{"available": true, "model": "qwen3.5:4b"}`.
- Ask one question (`POST /chat`), then `ollama ps` on the PC. OK:
  `qwen3.5:4b  ...  3.4 GB  100% GPU  8192  ...  9 minutes from now`.
  **PROCESSOR must say 100% GPU.** If it says e.g. `25%/75% CPU/GPU`, the GPU is too small or busy (another model is
  loaded: `ollama stop <name>`), and answers get several times slower.
- The first question after a reboot can take minutes (the model is read from disk) and may answer 503 once; after
  that a cold load is ~13 s and a loaded model answers in a few seconds. Ollama keeps the model loaded 10 minutes after
  the last question (`keep_alive` in `mappings/agents.yaml`).

## 4. What the team may tune

`mappings/agents.yaml`, section `model:` (REVIEW): temperature, top_p, top_k, presence_penalty, num_ctx (context window:
more = more GPU memory), keep_alive, timeout_s, think. The API refuses to start with a clear message if a value is out of
range.
````
