# Seller Assistant Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fourth chat agent, the Seller assistant, that picks pieces worth selling, suggests a friperie price, lists the user's own listings and prepares a ready-filled Sell form, without ever posting or changing data itself.

**Architecture:** A new agent file `backend/app/agents/seller.py` (same `Agent` record as the other three) with five tools. Prices come from a pure module `backend/app/resale.py`: FashionCLIP look-alikes from `ListingIndex.search`, friperie prices as they are, shop prices × a team-owned factor (`mappings/resale_pricing.csv`). `prepare_sell` returns a chat *action* (a `/sell?...` link) that `/chat` collects like pictures; the Chat page shows it as a button and the Sell page fills itself from the link.

**Tech Stack:** FastAPI, pymongo, numpy, pytest with fakes; React + TypeScript + react-router + Tailwind.

**Spec:** `docs/superpowers/specs/2026-10-08-seller-agent-design.md` (builds on `docs/superpowers/specs/2026-10-08-ai-agents-design.md`, `AGENTS.md`)

## Global Constraints

- The Seller assistant **never posts, edits or marks listings**; posting only happens when the user presses Send on the Sell page, and listings still wait for admin review.
- City and contact never appear in any tool result.
- Every read is filtered by `user["_id"]`; another user's ids are ignored (error dict), never revealed.
- Only actions with `kind == "sell"` and a `url` starting with `/sell?` reach the app.
- Team-owned rules in CSVs (`mappings/resale_pricing.csv`, `mappings/agent_keywords.csv`), every new row `REVIEW`; a loader fails with the line number on unknown values. Darija keyword rows and Arabic strings are a first draft for the native review.
- `chat.SYSTEM` / `chat.tools_for` stay unchanged (fine-tuning data).
- Code simple and commented, in the style of `backend/app/agents/*.py`.
- Commits: no `Co-Authored-By` trailer, no "Generated with Claude Code" footer (user rule).
- Backend tests: from `backend/`, `python -m pytest` (local MongoDB, database `dressme_test`). Frontend: from `frontend/`, `npm run build` and `npm run lint`.
- Work on branch `seller-agent` in `C:\dev\DressMe` (already created from `main`, spec committed).

---

## File map

| File | Responsibility |
|---|---|
| `mappings/resale_pricing.csv` (new) | team factors (second-hand share of a new price) + settings |
| `backend/app/resale.py` (new) | `load_rules`, `price_range` (pure) |
| `backend/app/listings.py` | `ListingIndex.search(..., exclude_seller=None)` |
| `backend/app/agents/common.py` | `with_attachments(..., actions=None)`, `sell_actions`, `Agent.bound_tools(..., actions=None)`, TEAM line |
| `backend/app/agents/seller.py` (new) | the agent and its 5 tools |
| `backend/app/agents/__init__.py` | register `seller` |
| `mappings/agent_keywords.csv` | seller keywords |
| `backend/app/routers/chat.py` | collect, return and store `actions` |
| `backend/tests/test_resale.py` (new), `backend/tests/test_seller_agent.py` (new), `backend/tests/test_agents.py`, `backend/tests/test_chat.py`, `backend/tests/conftest.py` | tests and fake branch |
| `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/pages/ChatPage.tsx`, `frontend/src/pages/SellPage.tsx`, `frontend/src/i18n/strings.ts` | action button, Sell prefill, strings |
| `AGENTS.md`, `CLAUDE.md`, `LISTINGS.md` | docs |

---

### Task 0: Plan commit and baseline

- [ ] **Step 1: Commit the plan**

```bash
git add docs/superpowers/plans/2026-10-08-seller-agent.md
git commit -m "Seller assistant: implementation plan"
```

- [ ] **Step 2: Baseline**

Run (from `backend/`): `python -m pytest -q`
Expected: 177 passed, 2 skipped. If not, stop and report (not caused by this work).

---

### Task 1: Price rules — `resale.py` and `mappings/resale_pricing.csv`

**Files:**
- Create: `mappings/resale_pricing.csv`, `backend/app/resale.py`, `backend/tests/test_resale.py`

**Interfaces:**
- Produces:
  - `resale.RULES_CSV: Path`
  - `resale.load_rules(path=RULES_CSV) -> {"factor": dict[str, float], "neighbours": int, "min_friperie": int}`
  - `resale.price_range(hits: list[dict], rules: dict) -> dict | None` with keys `low`, `high`, `median` (int TND), `based_on` (`"friperie" | "shops" | "both"`), `count` (int), `examples` (≤ 5 × `{title, source_id, price_tnd, resale_price, similarity, snapshot}`)

- [ ] **Step 1: Write the CSV** — `mappings/resale_pricing.csv`

```csv
kind,name,value,note
factor,*,0.3,REVIEW: placeholder; share of the new-shop price a second-hand piece sells for (team to set per category)
setting,neighbours,8,REVIEW: look-alike listings read for one price hint
setting,min_friperie,3,REVIEW: friperie look-alikes needed to ignore shop prices
```

- [ ] **Step 2: Write the failing tests** — `backend/tests/test_resale.py`

```python
"""The Seller assistant's price rule (app/resale.py): pure functions, no database."""

import pytest

from app.resale import load_rules, price_range

RULES = {"factor": {"*": 0.3, "shoes": 0.5}, "neighbours": 8, "min_friperie": 3}


def hit(price, source="exist_tn", category="top", score=0.9, title="Shirt", snapshot=False):
    return {"price_tnd": price, "source_id": source, "category": category, "score": score,
            "title": title, "snapshot": snapshot}


def test_team_table_loads():
    rules = load_rules()
    assert rules["factor"]["*"] > 0
    assert rules["neighbours"] >= 1 and rules["min_friperie"] >= 1


def test_shop_prices_use_the_category_factor_or_the_default():
    r = price_range([hit(100), hit(100, category="shoes")], RULES)
    assert r["based_on"] == "shops" and r["count"] == 2
    assert sorted(e["resale_price"] for e in r["examples"]) == [30, 50]
    assert r["low"] <= r["median"] <= r["high"]


def test_enough_friperie_prices_replace_shop_prices():
    hits = [hit(10, "sellers"), hit(14, "sellers"), hit(20, "sellers"), hit(300)]
    r = price_range(hits, RULES)
    assert r["based_on"] == "friperie" and r["count"] == 3
    assert r["median"] == 14 and 10 <= r["low"] <= r["high"] <= 20


def test_few_friperie_prices_are_mixed_with_shops():
    r = price_range([hit(12, "sellers"), hit(50)], RULES)
    assert r["based_on"] == "both" and r["count"] == 2      # 12 and 50 x 0.3 = 15


def test_rows_without_price_are_dropped_and_examples_capped():
    hits = [hit(None), hit(0)] + [hit(100 + i) for i in range(7)]
    r = price_range(hits, RULES)
    assert r["count"] == 7 and len(r["examples"]) == 5


def test_nothing_priced_gives_none():
    assert price_range([], RULES) is None
    assert price_range([hit(None)], RULES) is None


@pytest.mark.parametrize("rows, message", [
    ("factor,*,0.3,\nsetting,neighbours,8,\nsetting,min_friperie,3,\nmood,x,1,\n", "unknown kind"),
    ("factor,*,0.3,\nfactor,hats,0.5,\nsetting,neighbours,8,\nsetting,min_friperie,3,\n", "unknown category"),
    ("factor,top,0.3,\nsetting,neighbours,8,\nsetting,min_friperie,3,\n", r"\*"),
    ("factor,*,0.3,\nsetting,neighbours,8,\n", "min_friperie"),
])
def test_broken_tables_stop_with_a_clear_error(tmp_path, rows, message):
    path = tmp_path / "resale_pricing.csv"
    path.write_text("kind,name,value,note\n" + rows, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_rules(path)
```

- [ ] **Step 3: Run them to see them fail**

Run: `python -m pytest tests/test_resale.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.resale'`.

- [ ] **Step 4: Write `backend/app/resale.py`**

```python
"""
A friperie price for something the user wants to sell (the Seller assistant, AGENTS.md).

Look-alike listings (FashionCLIP, same category) give the prices:
  - friperie sellers' listings count as they are;
  - shop listings are new clothes, so their price is multiplied by the team's
    second-hand factor for that category (mappings/resale_pricing.csv, REVIEW);
  - once there are enough friperie look-alikes (min_friperie), shop prices are left out.
The answer is a range (25th-75th percentile) and the median, rounded to 1 TND, with
the listings it came from so the user can see why.
"""

import csv

import numpy as np

from .config import ROOT
from .listings import SELLERS
from .vocab import CATEGORIES

RULES_CSV = ROOT / "mappings" / "resale_pricing.csv"
SETTINGS = ("neighbours", "min_friperie")
EXAMPLES = 5


def load_rules(path=RULES_CSV):
    """The team's factors and settings. Anything unknown or missing stops with an error."""
    factor, settings = {}, {}
    with open(path, encoding="utf-8", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            kind, name, value = row["kind"].strip(), row["name"].strip(), row["value"].strip()
            if kind == "factor":
                if name != "*" and name not in CATEGORIES:
                    raise ValueError(f"{path.name} line {line}: unknown category {name!r}")
                factor[name] = float(value)
            elif kind == "setting":
                if name not in SETTINGS:
                    raise ValueError(f"{path.name} line {line}: unknown setting {name!r}")
                settings[name] = int(value)
            else:
                raise ValueError(f"{path.name} line {line}: unknown kind {kind!r}")
    if "*" not in factor:
        raise ValueError(f"{path.name}: needs a default factor row (name = *)")
    for name in SETTINGS:
        if name not in settings:
            raise ValueError(f"{path.name}: missing setting {name}")
    return {"factor": factor, **settings}


def price_range(hits, rules):
    """The price range from look-alike listings (rows of ListingIndex.search), or None."""
    priced = [h for h in hits if h.get("price_tnd") and h["price_tnd"] > 0]
    friperie = [h for h in priced if h["source_id"] == SELLERS]
    shops = [h for h in priced if h["source_id"] != SELLERS]
    used = friperie if len(friperie) >= rules["min_friperie"] else friperie + shops
    if not used:
        return None
    factor = rules["factor"]

    def resale(h):
        if h["source_id"] == SELLERS:
            return float(h["price_tnd"])
        return h["price_tnd"] * factor.get(h["category"], factor["*"])

    prices = np.array([resale(h) for h in used])
    low, median, high = (int(round(float(np.percentile(prices, q)))) for q in (25, 50, 75))
    shop_used = any(h["source_id"] != SELLERS for h in used)
    based_on = ("both" if friperie and shop_used else "shops" if shop_used else "friperie")
    return {"low": low, "high": high, "median": median, "based_on": based_on, "count": len(used),
            "examples": [{"title": h.get("title", ""), "source_id": h["source_id"],
                          "price_tnd": h["price_tnd"], "resale_price": int(round(resale(h))),
                          "similarity": h.get("score"), "snapshot": bool(h.get("snapshot"))}
                         for h in used[:EXAMPLES]]}
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_resale.py -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add mappings/resale_pricing.csv backend/app/resale.py backend/tests/test_resale.py
git commit -m "Resale price rule: look-alike listings, shop prices x team factor"
```

---

### Task 2: Plumbing — `exclude_seller` and chat actions

**Files:**
- Modify: `backend/app/listings.py` (`ListingIndex.search`)
- Modify: `backend/app/agents/common.py` (`with_attachments`, `sell_actions`, `Agent.bound_tools`)
- Create: `backend/tests/test_seller_agent.py`

**Interfaces:**
- Produces:
  - `ListingIndex.search(db, vector, k=6, category=None, exclude_seller=None) -> list[dict]`
  - `common.sell_actions(value) -> Iterator[dict]` — every `{"kind": "sell", "url": "/sell?..."}` found under an `"action"` key
  - `common.with_attachments(functions, attachments, actions=None)` — also appends actions (dedup by `url`) when `actions` is a list
  - `Agent.bound_tools(request, user, attachments=None, actions=None)`

- [ ] **Step 1: Write the failing tests** — create `backend/tests/test_seller_agent.py`

```python
"""The Seller assistant (AGENTS.md): its tools, chat actions, and the plumbing they use."""

from app.agents.common import with_attachments
from app.db import vector_to_bson
from tests.conftest import RED, fake_vector, sign_up, upload
from tests.test_agents import add_listing, user_doc


def test_actions_keep_only_sell_form_links():
    def tool():
        return {"a": {"action": {"kind": "sell", "url": "/sell?item=1&price=12"}},
                "b": {"action": {"kind": "sell", "url": "https://example.com/phish"}},
                "c": {"action": {"kind": "pay", "url": "/sell?item=2"}},
                "d": [{"action": {"kind": "sell", "url": "/sell?item=1&price=12"}}]}   # duplicate
    attachments, actions = [], []
    with_attachments({"tool": tool}, attachments, actions)["tool"]()
    assert actions == [{"kind": "sell", "url": "/sell?item=1&price=12"}]


def test_listing_search_can_leave_out_one_seller(client):
    sign_up(client)
    me = user_doc(client)["_id"]
    mine = add_listing(client, source_id="sellers", seller_id=me, price_tnd=10.0)
    other = add_listing(client, price_tnd=40.0)
    index, db = client.app.state.listing_index, client.app.state.db
    ids = [h["id"] for h in index.search(db, fake_vector(1), k=5, category="top")]
    assert set(ids) == {mine, other}
    ids = [h["id"] for h in index.search(db, fake_vector(1), k=5, category="top", exclude_seller=me)]
    assert ids == [other]
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_seller_agent.py -q`
Expected: FAIL — `TypeError: with_attachments() takes 2 positional arguments but 3 were given` and `TypeError: ... unexpected keyword argument 'exclude_seller'`.

- [ ] **Step 3: `exclude_seller` in `backend/app/listings.py`**

Change `ListingIndex.search`:

```python
    def search(self, db, vector, k=6, category=None, exclude_seller=None):
        """The k nearest listings. exclude_seller: leave out that seller's own listings
        (the Seller assistant's price hint must not quote the user's own prices)."""
        self._refresh(db)
        if not self._docs:
            return []
        scores = self._vectors @ np.asarray(vector, np.float32)
        hits = []
        for i in np.argsort(-scores):
            doc = self._docs[i]
            if category and doc.get("category") != category:
                continue
            if exclude_seller is not None and doc.get("seller_id") == exclude_seller:
                continue
            hits.append({**listing_out(doc), "score": round(float(scores[i]), 3)})
            if len(hits) == k:
                break
        return hits
```

- [ ] **Step 4: Actions in `backend/app/agents/common.py`**

Add after `image_attachments`:

```python
def sell_actions(value):
    """The chat actions in a tool result: only links to the app's own Sell form
    (a model must not be able to put any other link in front of the user)."""
    if isinstance(value, dict):
        action = value.get("action")
        if (isinstance(action, dict) and action.get("kind") == "sell"
                and isinstance(action.get("url"), str) and action["url"].startswith("/sell?")):
            yield {"kind": "sell", "url": action["url"]}
        for child in value.values():
            yield from sell_actions(child)
    elif isinstance(value, list):
        for child in value:
            yield from sell_actions(child)
```

Replace `with_attachments` with:

```python
def with_attachments(functions, attachments, actions=None):
    """The tools as {name: function}. With an `attachments` list, every item picture a
    tool returns is also added to it (once), so the app can show it under the answer;
    with an `actions` list, every Sell-form link too (once)."""
    if attachments is None and actions is None:
        return dict(functions)

    def capture(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            result = fn(*args, **kwargs)
            if attachments is not None:
                seen = {item["id"] for item in attachments}
                for item in image_attachments(result):
                    if item["id"] not in seen:
                        attachments.append(item)
                        seen.add(item["id"])
            if actions is not None:
                for action in sell_actions(result):
                    if action not in actions:
                        actions.append(action)
            return result
        return wrapped

    return {name: capture(fn) for name, fn in functions.items()}
```

And in `Agent`:

```python
    def bound_tools(self, request, user, attachments=None, actions=None):
        return with_attachments(self.tools(request, user), attachments, actions)
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_seller_agent.py tests/test_agents.py tests/test_chat.py tests/test_listings.py -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/listings.py backend/app/agents/common.py backend/tests/test_seller_agent.py
git commit -m "Chat actions (Sell-form links only) and listing search without one seller"
```

---

### Task 3: The Seller assistant agent

**Files:**
- Create: `backend/app/agents/seller.py`
- Modify: `backend/app/agents/__init__.py`, `backend/app/agents/common.py` (TEAM), `mappings/agent_keywords.csv`
- Modify: `backend/tests/test_agents.py` (`test_three_agents_each_with_tools`)
- Test: `backend/tests/test_seller_agent.py`

**Interfaces:**
- Consumes: `resale.load_rules`, `resale.price_range` (Task 1); `ListingIndex.search(..., exclude_seller=)`, `sell_actions` (Task 2); `Agent`, `list_wardrobe_tool`, `describe`, `compatibility.wardrobe_insights`, `compatibility.near_twins`
- Produces: `seller.AGENT` (name `"seller"`, title `"Seller assistant"`), tools `list_wardrobe`, `pieces_to_sell`, `price_hint`, `my_listings`, `prepare_sell`; `AGENTS` = stylist, shopping, analyst, seller

- [ ] **Step 1: Write the failing tests** — append to `backend/tests/test_seller_agent.py`

Add to the imports at the top:

```python
from urllib.parse import parse_qs, urlparse

from app.agents import AGENTS, seller
from app.agents.router import by_keywords, load_keywords
from tests.conftest import BLUE, photo
from tests.test_agents import as_request
```

(merge with the existing `from tests.conftest import ...` line: `from tests.conftest import BLUE, RED, fake_vector, photo, sign_up, upload`, and `from tests.test_agents import add_listing, as_request, user_doc`).

Append:

```python
def seller_tools(client, email="amira@example.com"):
    return seller.AGENT.bound_tools(as_request(client), user_doc(client, email))


def test_seller_has_its_tools_and_is_registered():
    assert set(seller.tools(None, None)) == {
        "list_wardrobe", "pieces_to_sell", "price_hint", "my_listings", "prepare_sell"}
    assert list(AGENTS) == ["stylist", "shopping", "analyst", "seller"]


def test_pieces_to_sell_unmatched_and_twins(client):
    headers = sign_up(client)
    a = upload(client, headers, RED)
    b = upload(client, headers, RED)          # same photo: b is the twin to sell
    result = seller_tools(client)["pieces_to_sell"]()
    assert {p["id"] for p in result["unmatched"]} == {a["id"], b["id"]}    # tops with no bottom
    assert result["twins"][0]["keep"]["id"] == a["id"]
    assert result["twins"][0]["sell"]["id"] == b["id"]


def test_price_hint_from_an_item_and_from_the_last_scan(client):
    headers = sign_up(client)
    top = upload(client, headers, RED)
    add_listing(client, price_tnd=50.0)                       # a shop shirt: 50 x 0.3 = 15
    tools = seller_tools(client)
    hint = tools["price_hint"](item_id=top["id"])
    assert hint["based_on"] == "shops" and hint["median"] == 15
    assert "contact" not in hint["examples"][0] and "city" not in hint["examples"][0]
    assert "error" in tools["price_hint"]()                   # no scan yet
    client.post("/analyze", files={"photo": photo(RED)}, headers=headers)
    assert tools["price_hint"]()["median"] == 15


def test_price_hint_skips_own_listings_and_other_users_items(client):
    amira = sign_up(client)
    sign_up(client, "youssef@example.com", "Youssef")
    top = upload(client, amira, RED)
    add_listing(client, source_id="sellers", seller_id=user_doc(client)["_id"], price_tnd=10.0)
    assert seller_tools(client)["price_hint"](item_id=top["id"]) == {
        "error": "no similar listings with a price yet"}
    assert "error" in seller_tools(client, "youssef@example.com")["price_hint"](item_id=top["id"])


def test_my_listings_are_private_and_never_show_contact(client):
    headers = sign_up(client)
    sign_up(client, "youssef@example.com", "Youssef")
    r = client.post("/listings/sell", files={"photo": photo(BLUE)}, headers=headers,
                    data={"price_tnd": "20", "city": "Sousse", "contact": "+216 00 000 000", "title": "Jeans"})
    assert r.status_code == 201, r.text
    mine = seller_tools(client)["my_listings"]()["listings"]
    assert [(m["title"], m["status"]) for m in mine] == [("Jeans", "pending")]
    assert "contact" not in mine[0] and "city" not in mine[0]
    assert seller_tools(client, "youssef@example.com")["my_listings"]()["listings"] == []


def test_prepare_sell_builds_a_sell_form_link(client):
    headers = sign_up(client)
    top = upload(client, headers, RED)
    tools = seller_tools(client)
    result = tools["prepare_sell"](price_tnd=15, item_id=top["id"], title="Red T-shirt & co", size="M")
    url = urlparse(result["action"]["url"])
    assert result["action"]["kind"] == "sell" and url.path == "/sell"
    assert parse_qs(url.query) == {"item": [top["id"]], "price": ["15"], "title": ["Red T-shirt & co"],
                                   "size": ["M"]}
    assert "error" in tools["prepare_sell"](price_tnd=15)               # no scan yet
    assert "error" in tools["prepare_sell"](price_tnd=0, item_id=top["id"])
    cand = client.post("/analyze", files={"photo": photo(RED)}, headers=headers).json()
    url = tools["prepare_sell"](price_tnd=12.5)["action"]["url"]
    assert parse_qs(urlparse(url).query) == {"candidate": [cand["id"]], "price": ["12.5"]}


def test_prepare_sell_ignores_other_users_items(client):
    amira = sign_up(client)
    sign_up(client, "youssef@example.com", "Youssef")
    top = upload(client, amira, RED)
    assert "error" in seller_tools(client, "youssef@example.com")["prepare_sell"](
        price_tnd=10, item_id=top["id"])


def test_sell_keywords_route_to_the_seller():
    keywords = load_keywords()
    assert by_keywords("I want to sell my jacket", keywords) == "seller"
    assert by_keywords("je veux vendre ce jean", keywords) == "seller"
```

Check `/analyze`'s answer has `id` (the candidate id) before relying on it: `grep -n '"/analyze"' -A25 backend/app/routers/items.py` — it returns `item_out(cand, kind="candidates")`, which has `id`.

- [ ] **Step 2: Update the registry test** — in `backend/tests/test_agents.py`, rename `test_three_agents_each_with_tools` to `test_every_agent_has_tools` and change its first assertion to:

```python
    assert list(AGENTS) == ["stylist", "shopping", "analyst", "seller"]
```

- [ ] **Step 3: Run them to see them fail**

Run: `python -m pytest tests/test_seller_agent.py tests/test_agents.py -q`
Expected: FAIL — `ImportError: cannot import name 'seller' from 'app.agents'`.

- [ ] **Step 4: Write `backend/app/agents/seller.py`**

```python
"""
The Seller assistant agent: "what should I sell, and for how much?". It advises and
prepares, never acts: prepare_sell only builds a link to the Sell page, where the user
adds their city and contact and presses Send (then an admin reviews the listing).
"""

from urllib.parse import urlencode

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..db import object_id, vector_from_bson
from ..listings import SELLERS
from ..resale import load_rules, price_range
from ..routers.outfits import user_profile, wardrobe
from ..wardrobe import describe, to_compat
from .common import Agent, list_wardrobe_tool

TOP = 5                # pieces listed per answer: keeps the prompt small
MAX_LISTINGS = 10
MAX_PRICE = 100000     # same limit as POST /listings/sell


def tools(request, user):
    """The Seller assistant's tools, bound to this user."""
    def own_piece(item_id):
        """The user's wardrobe item, or (no id) their last scan, as (document, kind), or (None, '')."""
        db = request.app.state.db
        if item_id:
            oid = object_id(item_id)
            doc = oid and db.items.find_one({"_id": oid, "user_id": user["_id"]})
            return (doc, "item") if doc else (None, "")
        doc = db.candidates.find_one({"user_id": user["_id"]}, sort=[("created_at", -1)])
        return (doc, "candidate") if doc else (None, "")

    def pieces_to_sell() -> dict:
        """Pieces worth selling: main pieces that go with nothing in the wardrobe, and for each
        pair of near-identical pieces, the second one."""
        docs, by_id = wardrobe(request, user)
        items = [to_compat(d) for d in docs]
        facts = compatibility.wardrobe_insights(items, user_profile(user, docs, request))
        return {"unmatched": [describe(i, by_id) for i in facts["unmatched"][:TOP]],
                "twins": [{"keep": describe(a, by_id), "sell": describe(b, by_id), "similarity": round(s, 3)}
                          for a, b, s in compatibility.near_twins(items)[:TOP]]}

    def price_hint(item_id: str = "") -> dict:
        """A fair friperie price range (TND) for one of the user's items (id from list_wardrobe)
        or, with no id, for the last photo they analysed, from similar listings."""
        doc, _ = own_piece(item_id)
        if not doc or not doc.get("vector"):
            return {"error": "no such item or analysed photo"}
        rules = load_rules()
        hits = request.app.state.listing_index.search(
            request.app.state.db, vector_from_bson(doc["vector"]), k=rules["neighbours"],
            category=doc["category"], exclude_seller=user["_id"])
        return price_range(hits, rules) or {"error": "no similar listings with a price yet"}

    def my_listings() -> dict:
        """The user's own friperie listings, newest first: price and status (pending = waiting
        for an admin, active = visible, rejected = see review_note, gone = sold or removed)."""
        docs = (request.app.state.db.listings
                .find({"source_id": SELLERS, "seller_id": user["_id"]}, {"vector": 0})
                .sort([("created_at", -1), ("_id", -1)]).limit(MAX_LISTINGS))
        return {"listings": [{"id": str(d["_id"]), "title": d.get("title", ""),
                              "price_tnd": d.get("price_tnd"), "category": d.get("category", ""),
                              "sub_category": d.get("sub_category", ""), "colour": d.get("colour", ""),
                              "status": d.get("status", ""), "review_note": d.get("review_note", ""),
                              "image_url": f"/listings/{d['_id']}/image"}
                             for d in docs]}

    def prepare_sell(price_tnd: float, item_id: str = "", title: str = "", size: str = "") -> dict:
        """Prepare the Sell form for one of the user's items (id from list_wardrobe) or, with
        no id, their last analysed photo: the app shows a button that opens it already filled.
        Nothing is posted: the user adds their city and contact and sends it."""
        doc, kind = own_piece(item_id)
        if not doc:
            return {"error": "no such item or analysed photo"}
        price = float(price_tnd)
        if not 0 < price <= MAX_PRICE:
            return {"error": "the price must be more than 0 TND"}
        query = {kind: str(doc["_id"]), "price": f"{price:g}"}
        if title.strip():
            query["title"] = title.strip()[:80]
        if size.strip():
            query["size"] = size.strip()[:20]
        folder = "items" if kind == "item" else "candidates"
        return {"action": {"kind": "sell", "url": "/sell?" + urlencode(query)},
                "item": {"id": str(doc["_id"]), "category": doc["category"],
                         "sub_category": doc.get("sub_category", ""), "colour": doc.get("colour", ""),
                         "image_url": f"/{folder}/{doc['_id']}/image"}}

    functions = (list_wardrobe_tool(request, user), pieces_to_sell, price_hint, my_listings, prepare_sell)
    return {f.__name__: f for f in functions}


AGENT = Agent(
    name="seller", title="Seller assistant",
    description="selling clothes the user owns: what to sell, at what price, writing the listing, their listings",
    job=("help the user sell pieces they do not wear, at a fair friperie price. Use pieces_to_sell to "
         "find candidates, price_hint for a price (say it is a range from similar listings), write a "
         "short honest title (category, colour, size if known; never invent a brand or the condition), "
         "and finish with prepare_sell so the user gets a ready-filled Sell form. Tell them an admin "
         "checks each listing before others see it. my_listings shows their listings and status."),
    tools=tools)
```

- [ ] **Step 5: Register it** — `backend/app/agents/__init__.py`

```python
from . import analyst, seller, shopping, stylist

# name -> agent, in the order the router prompt and AGENTS.md list them
AGENTS = {a.name: a for a in (stylist.AGENT, shopping.AGENT, analyst.AGENT, seller.AGENT)}
```

- [ ] **Step 6: TEAM line** — in `backend/app/agents/common.py`, change `TEAM` to:

```python
TEAM = """DressMe has four assistants and each message goes to one of them:
- the Stylist: what to wear today or for an occasion, outfits from the wardrobe, the weather;
- the Shopping advisor: should I buy this, where to find a piece, prices in shops and friperie;
- the Wardrobe analyst: what the wardrobe lacks, its most and least useful pieces, near-duplicates;
- the Seller assistant: what to sell, at what price, writing the listing, the user's listings.
If the question is for another assistant, say so in one sentence and invite the user to ask it."""
```

- [ ] **Step 7: Keywords** — append to `mappings/agent_keywords.csv`:

```csv
seller,en,sell,REVIEW
seller,fr,vend,REVIEW
seller,fr,revend,REVIEW
seller,darija,nbi3,REVIEW: native check
seller,ar,نبيع,REVIEW: native check
```

- [ ] **Step 8: Run the tests**

Run: `python -m pytest tests/test_seller_agent.py tests/test_agents.py tests/test_resale.py -q`
Expected: all PASS. If `test_pieces_to_sell_unmatched_and_twins` fails on `unmatched` because the fake wardrobe's tops get filtered by default seasons, print `compatibility.wardrobe_insights(...)` for that wardrobe and adjust the assertion to what the formula says (do not change the formula).

- [ ] **Step 9: Commit**

```bash
git add backend/app/agents mappings/agent_keywords.csv backend/tests/test_seller_agent.py backend/tests/test_agents.py
git commit -m "Agents: Seller assistant (pieces to sell, price hint, my listings, Sell form)"
```

---

### Task 4: `/chat` returns and stores actions

**Files:**
- Modify: `backend/app/routers/chat.py`, `backend/tests/conftest.py`, `backend/tests/test_chat.py`

**Interfaces:**
- Consumes: `Agent.bound_tools(request, user, attachments, actions)` (Task 2), `seller.AGENT` (Task 3)
- Produces: `POST /chat` → adds `"actions": [{"kind": "sell", "url": ...}]` when not empty; model message documents store `actions`; `GET /chat/history` items gain `"actions"` (`[]` for older ones)

- [ ] **Step 1: Fake engine branch** — in `FakeChatEngine.reply` (`backend/tests/conftest.py`), before the `if "missing" in message ...` branch:

```python
        if "sell" in message and "prepare_sell" in tools:
            items = tools["list_wardrobe"]()
            if not items:
                return "Nothing to sell yet.", ["list_wardrobe"]
            tools["prepare_sell"](price_tnd=12, item_id=items[0]["id"], title="Red T-shirt")
            return "Here is your Sell form.", ["list_wardrobe", "prepare_sell"]
```

- [ ] **Step 2: Write the failing test** — append to `backend/tests/test_chat.py` (before the `import copy  # noqa: E402` line, next to the other agent tests)

```python
def test_seller_answer_carries_a_sell_form_action(client):
    headers = sign_up(client)
    top = upload(client, headers, RED)
    r = client.post("/chat", json={"message": "I want to sell my top"}, headers=headers)
    assert r.json()["agent"] == "seller"
    assert r.json()["actions"] == [{"kind": "sell", "url": f"/sell?item={top['id']}&price=12&title=Red+T-shirt"}]
    history = client.get("/chat/history", headers=headers).json()
    assert history[-1]["actions"] == r.json()["actions"]
    assert history[0]["actions"] == []
    r = client.post("/chat", json={"message": "suggest an outfit"}, headers=headers)
    assert "actions" not in r.json()
```

- [ ] **Step 3: Run it to see it fail**

Run: `python -m pytest tests/test_chat.py -q -k sell_form`
Expected: FAIL — `KeyError: 'actions'`.

- [ ] **Step 4: Collect actions in `backend/app/routers/chat.py`**

In `chat()`:
- after `attachments = []` add `actions = []`;
- pass them: `agent.bound_tools(request, user, attachments, actions)`;
- in the model message document add `"actions": actions,` next to `"attachments": attachments,`;
- after `if attachments: result["attachments"] = attachments` add:

```python
    if actions:                        # e.g. the Seller assistant's ready-filled Sell form
        result["actions"] = actions
```

In `chat_history`, add `"actions": d.get("actions", [])` to each returned dict.

- [ ] **Step 5: Run the whole backend suite**

Run: `python -m pytest -q`
Expected: all PASS (177 + the new tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/chat.py backend/tests/conftest.py backend/tests/test_chat.py
git commit -m "Chat: return and keep the agents' Sell-form actions"
```

---

### Task 5: Frontend — action button and Sell prefill

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/pages/ChatPage.tsx`, `frontend/src/pages/SellPage.tsx`, `frontend/src/i18n/strings.ts`

**Interfaces:**
- Consumes: `/chat` and `/chat/history` `actions` (Task 4); `/sell?item=|candidate=&price=&title=&size=` links (Task 3); `loadImage(path) -> Promise<objectUrl>` (existing, `api/client.ts`)

- [ ] **Step 1: Types and client**

`frontend/src/api/types.ts`, next to `ChatAttachment`:

```ts
/** Something the assistant prepared for the user to open (never done for them). */
export interface ChatAction {
  kind: 'sell'
  url: string               // /sell?item=...&price=...: the Sell form, already filled
}
```

In `ChatTurn` add `actions?: ChatAction[]`.

`frontend/src/api/client.ts`: import `ChatAction` with the other types and change the `chat` response type to

```ts
    request<{ reply: string; tools_used: string[]; agent: string; agent_title: string;
              attachments: ChatAttachment[]; actions?: ChatAction[] }>('/chat', json('POST', { message })),
```

- [ ] **Step 2: Chat page button** — `frontend/src/pages/ChatPage.tsx`

- import `Link` from `react-router-dom`;
- in the `setTurns` after `api.chat`, add `actions: r.actions` to the new turn;
- just before the `{m.tools_used.length > 0 && (` block:

```tsx
                {m.actions && m.actions.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {m.actions.map((a) => (
                      <Link key={a.url} to={a.url}
                        className="inline-flex min-h-11 items-center bg-ink px-4 text-[15px] font-medium text-paper">
                        {t('chatOpenSell')}
                      </Link>
                    ))}
                  </div>
                )}
```

- [ ] **Step 3: Sell page prefill** — `frontend/src/pages/SellPage.tsx`

- imports: `import { Link, useSearchParams } from 'react-router-dom'` and `import { api, loadImage } from '../api/client'`;
- at the top of `SellPage()`, before the `useState` calls: `const [params] = useSearchParams()`;
- start the form from the link (initial state, so no setState inside an effect):

```tsx
  const [form, setForm] = useState<SellForm>(() => ({
    ...EMPTY, title: params.get('title') ?? '', size: params.get('size') ?? '',
  }))
  const [priceText, setPriceText] = useState(() => params.get('price') ?? '')
  const [prefillFailed, setPrefillFailed] = useState(false)
```

(replacing the existing `form` and `priceText` lines);
- after `pick` is defined, load the photo of the item / scan named in the link:

```tsx
  // From the assistant's "Open the Sell form": use the photo the app already has
  const prefillPath = params.get('item') ? `/items/${encodeURIComponent(params.get('item')!)}/image`
    : params.get('candidate') ? `/candidates/${encodeURIComponent(params.get('candidate')!)}/image` : ''
  useEffect(() => {
    if (!prefillPath) return
    let cancelled = false
    loadImage(prefillPath)
      .then((url) => fetch(url).then((r) => r.blob()))
      .then((blob) => { if (!cancelled) pick(new File([blob], 'photo.jpg', { type: blob.type || 'image/jpeg' })) })
      .catch(() => { if (!cancelled) setPrefillFailed(true) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefillPath])
```

- under `<PhotoPicker onPick={pick} />`:

```tsx
            {prefillFailed && !file ? (
              <p role="status" className="text-[13px] text-stamp-deep">{t('sellPrefillFailed')}</p>
            ) : null}
```

`reset()` keeps working as before (it empties the form for "sell another").

- [ ] **Step 4: Strings** — `frontend/src/i18n/strings.ts`, after `tool_find_near_twins` in each language.

en:

```ts
  agent_seller: 'Seller assistant',
  tool_pieces_to_sell: 'looked for pieces to sell',
  tool_price_hint: 'estimated a price',
  tool_my_listings: 'checked your listings',
  tool_prepare_sell: 'prepared a Sell form',
  chatOpenSell: 'Open the Sell form',
  sellPrefillFailed: "Couldn't load the photo. Pick it again.",
```

fr:

```ts
  agent_seller: 'Assistant vente',
  tool_pieces_to_sell: 'a cherché des pièces à vendre',
  tool_price_hint: 'a estimé un prix',
  tool_my_listings: 'a regardé tes annonces',
  tool_prepare_sell: 'a préparé une annonce',
  chatOpenSell: 'Ouvrir le formulaire de vente',
  sellPrefillFailed: 'Impossible de charger la photo. Choisis-la à nouveau.',
```

ar (first draft, REVIEW in the PR):

```ts
  agent_seller: 'مساعد البيع',
  tool_pieces_to_sell: 'لوّج على حوايج للبيع',
  tool_price_hint: 'قدّر سوم',
  tool_my_listings: 'شاف إعلاناتك',
  tool_prepare_sell: 'حضّر إعلان',
  chatOpenSell: 'افتح استمارة البيع',
  sellPrefillFailed: 'ما تحمّلتش الصورة. اختارها من جديد.',
```

- [ ] **Step 5: Build and lint**

Run (from `frontend/`): `npm run build` then `npm run lint`
Expected: build OK; lint shows no error and no new warning (the existing `BuildPage.tsx` warning stays). If oxlint flags the `eslint-disable` comment as unknown, remove the comment line.

- [ ] **Step 6: Preview check**

Run the backend with the test fakes on a throwaway database (as done for the first agents: a scratchpad script calling `create_app(Settings(mongo_db="dressme_seller_preview", router="keywords", ...), analyzer=FakeAnalyzer(), ...)` on port 8010, and the frontend with a throwaway Vite config proxying `/api` to 8010 on port 5183 — never touch the user's servers on 8000 / 5173 or the `dressme` database). Sign up a throwaway account (`@example.com`), upload a red photo in Wardrobe, then in the Assistant send "I want to sell my top". Expected: "SELLER ASSISTANT" badge and an "Open the Sell form" button; clicking it opens Sell with the photo shown, price 12 and title "Red T-shirt" filled, city and contact empty. Screenshot, then stop the servers, delete the throwaway config / launch entries and drop `dressme_seller_preview`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/pages/ChatPage.tsx frontend/src/pages/SellPage.tsx frontend/src/i18n/strings.ts
git commit -m "Chat: Open the Sell form button; Sell page fills itself from the assistant's link"
```

---

### Task 6: Documentation

**Files:**
- Modify: `AGENTS.md`, `CLAUDE.md`, `LISTINGS.md`

- [ ] **Step 1: `AGENTS.md`**

- first sentence: "three AI agents" → "four AI agents";
- add a table row:

```markdown
| Seller assistant | what to sell, at what price, the listing | `list_wardrobe`, `pieces_to_sell`, `price_hint`, `my_listings`, `prepare_sell` |
```

- in the flow diagram, step 1: `stylist / shopping / analyst / seller`;
- in "Tools", add:

```markdown
- `pieces_to_sell`: the Insights facts again (pieces in no good outfit, the second of each near-twin pair).
- `price_hint`: look-alike listings (same category) → a friperie price range: friperie prices as they are,
  shop prices × the team's second-hand factor (`mappings/resale_pricing.csv`, REVIEW); the user's own
  listings are left out. `backend/app/resale.py`.
- `my_listings`: the user's own seller listings and their status (never city or contact).
- `prepare_sell`: posts nothing. It returns a chat action, a link to the Sell page already filled
  (photo, price, title, size); the user adds city and contact and presses Send, then an admin reviews it.
```

- add a section:

```markdown
## Chat actions

A tool can return `{"action": {"kind": "sell", "url": "/sell?..."}}`. `/chat` collects these like
pictures (`actions` in the answer and the history) and the Chat page shows a button. Only `sell`
actions pointing to `/sell?` are kept, so a model cannot put any other link in front of the user.
```

- [ ] **Step 2: `CLAUDE.md`** — in the Phase 4 → Backend → Endpoints `/chat` bullet, change "three AI agents" to "four AI agents", add after the Wardrobe analyst's tools: `, Seller assistant (`list_wardrobe`, `pieces_to_sell`, `price_hint`, `my_listings`, `prepare_sell`; advises and prepares a filled Sell form as a chat `action`, never posts; prices = look-alike listings, shop prices × `mappings/resale_pricing.csv` factor, REVIEW)`, and after "Answers and history carry `agent`" add "and `actions`".

- [ ] **Step 3: `LISTINGS.md`** — add at the end:

```markdown
## Seller assistant

In the chat, the Seller assistant (AGENTS.md) helps friperie sellers: which pieces to sell, a price
range from look-alike listings (friperie prices as they are, shop prices × the team's second-hand
factor in `mappings/resale_pricing.csv`, REVIEW), and a link that opens the Sell page already filled.
It never posts: the seller sends the form, and the listing waits for an admin as usual.
```

- [ ] **Step 4: Final check**

Run (from `backend/`): `python -m pytest -q` — Expected: all PASS.
Run (from `frontend/`): `npm run build` — Expected: success.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md CLAUDE.md LISTINGS.md
git commit -m "Docs: the Seller assistant"
```
