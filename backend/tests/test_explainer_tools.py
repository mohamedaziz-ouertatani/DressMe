"""
The explainer's tools (step 3e.3), called by a scripted fake model through POST /chat on the golden wardrobe: they
answer with refs and never a database id, their lists are short, and the numbers match the routes the app uses.

`golden_chat` is shared with test_seller_tools.py: the model first lists the wardrobe (so refs exist), then makes the
calls a test gives it. A call may be a function of the listed pieces, to find a ref by what the piece is.
"""

import json
import re

import pytest
from pymongo import MongoClient

import compatibility
from app.assistant.model import FakeModel, ModelReply, ToolCall
from tests.conftest import TEST_DB, sign_up
from tests.test_golden import WARDROBE, stored

OWNED = {d["id"] for d in WARDROBE["items"]}
OBJECT_ID = re.compile(r"\b[0-9a-f]{24}\b")
ALL_REFS = " ".join(f"{{{n}}}" for n in range(1, 40))      # the closing text names every piece, so /chat returns them
MAX_CHARS = 2500                     # about 800 tokens: a tool result must stay small next to num_ctx 8192


class Scripted(FakeModel):
    """A FakeModel whose script may hold functions(model) -> ModelReply, to decide a reply from what it has read."""

    def chat(self, messages, tools, max_tokens, temperature=None):
        reply = super().chat(messages, tools, max_tokens, temperature)
        return reply(self) if callable(reply) else reply


def tool_call(name, args):
    return ModelReply(tool_calls=[ToolCall(name, args)])


def ref(pieces, sub_category=None, colour=None, category=None):
    """The ref of the first listed piece that is this type / colour / category."""
    for p in pieces:
        if (sub_category in (None, p["type"]) and colour in (None, p["colour"])
                and category in (None, p["category"])):
            return p["ref"]
    raise AssertionError(f"no {colour} {sub_category} {category} in the listed wardrobe")


@pytest.fixture
def golden_chat(make_client, settings):
    """run(agent, *calls) = one turn of `agent`: list_wardrobe first, then each call (name, args) or
    function(listed pieces) -> (name, args), then a closing sentence. Returns (the /chat answer, what each tool
    result said, as read by the model, in order, the list_wardrobe one first)."""
    model = Scripted([])
    client = make_client(chat_model=model)
    user = WARDROBE["user"]
    headers = sign_up(client, user["email"], user["name"], user["gender"])
    db = MongoClient(settings.mongo_url)[TEST_DB]
    user_id = db.users.find_one({"email": user["email"]})["_id"]
    db.items.insert_many([stored(d, user_id) for d in WARDROBE["items"]])

    def reads_of(received):
        return [json.loads(m["content"]) for m in received["messages"] if m["role"] == "tool"]

    def later(call):
        def reply(m):
            run.reads = reads_of(m.received[-1])             # everything the model has read so far (a call may use it)
            pieces = run.reads[0]["pieces"]
            name, args = call(pieces) if callable(call) else call
            return tool_call(name, args)
        return reply

    def run(agent, *calls):
        model.received.clear()
        model.script[:] = [tool_call("list_wardrobe", {"limit": 60}), *[later(c) for c in calls],
                           ModelReply(text=ALL_REFS)]
        r = client.post("/chat", json={"message": "help", "agent": agent}, headers=headers)
        assert r.status_code == 200, r.text
        reads = reads_of(model.received[-1])
        assert not any(OBJECT_ID.search(json.dumps(x)) for x in reads), "a database id reached the model"
        assert all(len(json.dumps(x)) <= MAX_CHARS for x in reads)
        return r.json(), reads

    run.client, run.headers, run.db = client, headers, db
    run.reads = []
    return run


def pink_top_and_black_skirt(pieces):
    return [ref(pieces, "top", "pink"), ref(pieces, "skirt", "black")]


# ---------------------------------------------------------------- explain_outfit
def test_explain_outfit_names_the_weakest_piece_and_at_most_three_swaps(golden_chat):
    answer, reads = golden_chat("explainer",
                                lambda p: ("explain_outfit", {"pieces": pink_top_and_black_skirt(p)}))
    seen = reads[1]
    refs = {int(n): p["id"] for n, p in answer["pieces"].items()}
    ours = pink_top_and_black_skirt(reads[0]["pieces"])
    assert len(seen["swaps"]) <= 3 and set(refs.values()) <= OWNED
    assert seen["weakest"] is None or seen["weakest"] in ours
    for swap in seen["swaps"]:
        assert swap["piece"] in ours and swap["gain"] >= 0 and swap["piece"] in refs
        assert swap["better"] is None or (set(swap["better"]) == {"ref", "type", "colour"} and swap["better"]["ref"] in refs)
    # the same numbers as the route the Dress page uses
    route = golden_chat.client.post("/outfits/explain", json={"item_ids": [refs[r] for r in ours]},
                                    headers=golden_chat.headers).json()
    assert (refs[seen["weakest"]] if seen["weakest"] else None) == route["weakest"]
    best = sorted(route["swaps"], key=lambda s: s["gain"], reverse=True)[:3]
    assert [s["gain"] for s in seen["swaps"]] == [round(s["gain"], 1) for s in best]


def test_pieces_that_clash_come_back_as_an_error_not_a_crash(golden_chat):
    two_tops = lambda p: ("explain_outfit", {"pieces": [ref(p, "top", "pink"), ref(p, "top", "white")]})
    _, reads = golden_chat("explainer", two_tops)
    assert reads[1]["error"] == "pieces_clash"


def test_a_number_that_was_never_shown_is_refused(golden_chat):
    _, reads = golden_chat("explainer", ("explain_outfit", {"pieces": [98, 99]}))
    assert reads[1]["error"] == "unknown_piece"


# ---------------------------------------------------------------- how_scoring_works
def test_how_scoring_works_gives_the_teams_weights_as_shares(golden_chat):
    _, reads = golden_chat("explainer", ("how_scoring_works", {}))
    seen = reads[1]
    rules = compatibility.rules_for("women")
    assert [p["part"] for p in seen["parts"]] == list(rules.weights)
    assert abs(sum(p["share_percent"] for p in seen["parts"]) - 100) <= 1          # rounding only
    best = max(seen["parts"], key=lambda p: p["share_percent"])
    assert best["part"] == max(rules.weights, key=rules.weights.get)
    assert seen["good_from"] == int(rules.settings["good_outfit"])
    assert all(p["looks_at"] for p in seen["parts"])


# ---------------------------------------------------------------- who may use what
def test_score_outfit_works_for_the_explainer_and_the_tools_stay_apart(golden_chat):
    _, reads = golden_chat(
        "explainer",
        lambda p: ("score_outfit", {"pieces": pink_top_and_black_skirt(p)}),
        ("build_outfit", {"pieces": [1]}),)                 # the explainer was not given build_outfit
    assert 0 <= reads[1]["score"] <= 100 and set(reads[1]["parts"]) == {"style", "colour", "pattern", "structure"}
    assert reads[2]["error"] == "unknown_tool"


def test_the_stylist_cannot_use_the_explainers_tools(golden_chat):
    _, reads = golden_chat("stylist", ("explain_outfit", {"pieces": [1, 2]}), ("how_scoring_works", {}))
    assert [r["error"] for r in reads[1:]] == ["unknown_tool", "unknown_tool"]
