"""
Handoff (step 3e.6), with a scripted fake model on the golden wardrobe: the first agent hands a part of the message to
another agent, which answers ONCE with the same ledgers, cannot hand over again, and both agents are saved.
(`golden_chat` is in test_explainer_tools.py.)
"""

import json

from app.assistant.agents import load_agents
from app.assistant import default_registry
from app.assistant.handoff import INSTRUCTION_LINE, second_run_agent
from app.assistant.model import ModelReply, ToolCall
from app.config import ROOT
from tests.test_explainer_tools import ALL_REFS, golden_chat, ref, tool_call  # noqa: F401  (golden_chat is a fixture)

AGENTS = load_agents(ROOT / "mappings" / "agents.yaml", default_registry().names())
HANDOFF = {"agent": "explainer", "note": "why the outfit scores low"}


def listed(model):
    """The pieces list_wardrobe gave the model during this turn (the first tool message of that name)."""
    for call in model.received:
        for message in call["messages"]:
            if message["role"] == "tool" and message["name"] == "list_wardrobe":
                return json.loads(message["content"])["pieces"]


def score_the_listed_pink_top_and_black_skirt(model):
    """A reply for the second agent: score two pieces by the numbers the FIRST agent's list_wardrobe created."""
    pieces = listed(model)
    return tool_call("score_outfit", {"pieces": [ref(pieces, "top", "pink"), ref(pieces, "skirt", "black")]})


def chat(golden_chat, message="Why is my outfit low, and what else could I wear?", agent="stylist"):
    r = golden_chat.client.post("/chat", json={"message": message, "agent": agent}, headers=golden_chat.headers)
    assert r.status_code == 200, r.text
    return r.json()


def handed_over_script(second_agent_replies):
    """list_wardrobe, handoff, the first agent's own words, then what the second agent does."""
    return [tool_call("list_wardrobe", {"limit": 60}), tool_call("handoff", HANDOFF),
            ModelReply(text="First part: the outfit is fine."), *second_agent_replies]


def test_the_second_agent_answers_once_with_the_same_ledger(golden_chat):
    model = golden_chat.model
    model.script[:] = handed_over_script([score_the_listed_pink_top_and_black_skirt,
                                          ModelReply(text=f"Second part. {ALL_REFS}")])
    body = chat(golden_chat)
    assert body["agent"] == "explainer" and body["stop_reason"] == "answered"
    assert body["answer"].startswith("First part: the outfit is fine.\n\nSecond part.")
    assert len(model.received) == 5                       # list, handoff, first agent's words, score, second's words
    # the second agent used numbers only the first agent's tool created: the ledger is shared
    scored = [m for m in model.received[-1]["messages"] if m["role"] == "tool"]
    assert "score" in json.loads(scored[0]["content"])
    assert {p["colour"] for p in body["pieces"].values()} >= {"pink", "black"}


def test_the_trace_has_the_handoff_line_between_the_two_agents(golden_chat):
    golden_chat.model.script[:] = handed_over_script([ModelReply(text="Second part.")])
    trace = chat(golden_chat)["trace"]
    where = [i for i, line in enumerate(trace) if "handoff" in line]
    assert trace[0] == {"router": "stylist", "how": "button"} and len(where) == 1
    assert trace[where[0]]["handoff"] == {"from": "stylist", **{"to": "explainer", "note": HANDOFF["note"]}}
    assert [line["tool"] for line in trace[:where[0]] if "tool" in line] == ["list_wardrobe", "handoff"]
    assert [line for line in trace[where[0] + 1:] if "tool" in line] == []       # nothing of the first agent after it


def test_the_second_agent_has_no_handoff_tool_and_cannot_hand_over_again(golden_chat):
    model = golden_chat.model
    model.script[:] = handed_over_script([tool_call("handoff", {"agent": "seller", "note": "again"}),
                                          ModelReply(text="Second part.")])
    body = chat(golden_chat)
    names = lambda call: [t["function"]["name"] for t in call["tools"]]
    assert "handoff" in names(model.received[0]) and "handoff" not in names(model.received[3])
    assert INSTRUCTION_LINE in model.received[0]["messages"][0]["content"]
    assert INSTRUCTION_LINE not in model.received[3]["messages"][0]["content"]
    assert json.loads(model.received[4]["messages"][-1]["content"])["error"] == "unknown_tool"
    assert len([line for line in body["trace"] if "handoff" in line]) == 1 and body["agent"] == "explainer"


def test_the_second_agent_is_told_which_part_is_its_own(golden_chat):
    model = golden_chat.model
    model.script[:] = handed_over_script([ModelReply(text="Second part.")])
    chat(golden_chat, message="Why is my outfit low, and what else could I wear?")
    asked = model.received[3]["messages"][1]["content"]
    assert asked.startswith("Why is my outfit low, and what else could I wear?") and HANDOFF["note"] in asked
    menu = model.received[0]["messages"][0]["content"]
    assert "Agents you can hand over to" in menu and "- explainer:" in menu and "- stylist:" not in menu.split("Agents you can")[1]


def test_a_bad_target_is_refused_and_the_turn_goes_on(golden_chat):
    model = golden_chat.model
    model.script[:] = [tool_call("handoff", {"agent": "stylist", "note": "myself"}),
                       tool_call("handoff", {"agent": "nobody", "note": "x"}),
                       tool_call("handoff", {"agent": "seller", "note": "x" * 101}),
                       ModelReply(text="I will answer it myself.")]
    body = chat(golden_chat)
    errors = [json.loads(m["content"])["error"] for m in model.received[-1]["messages"] if m["role"] == "tool"]
    assert errors == ["invalid_target", "unknown_agent", "invalid_arguments"]
    assert body["agent"] == "stylist" and body["stop_reason"] == "answered"
    assert not [line for line in body["trace"] if "handoff" in line]              # no handoff happened


def test_one_handoff_per_turn(golden_chat):
    model = golden_chat.model
    model.script[:] = [ModelReply(tool_calls=[ToolCall("handoff", HANDOFF), ToolCall("handoff", {"agent": "seller", "note": "x"})]),
                       ModelReply(text="First."), ModelReply(text="Second.")]
    body = chat(golden_chat)
    results = [json.loads(m["content"]) for m in model.received[1]["messages"] if m["role"] == "tool"]   # the first agent's last call
    assert "error" not in results[0] and results[1]["error"] == "already_handed_over"
    assert body["agent"] == "explainer" and len([line for line in body["trace"] if "handoff" in line]) == 1


def test_both_agents_are_saved_with_the_handoff(golden_chat):
    golden_chat.model.script[:] = handed_over_script([ModelReply(text="Second part.")])
    body = chat(golden_chat)
    saved = golden_chat.db.chats.find_one({"chat_id": body["chat_id"]})
    assert saved["agent"] == "explainer" and saved["agents"] == ["stylist", "explainer"]
    assert saved["handoff"] == {"from": "stylist", "to": "explainer", "note": HANDOFF["note"]}
    event = golden_chat.db.events.find_one({"type": "assistant"})
    assert event["agent"] == "explainer" and event["handed_from"] == "stylist" and "message" not in event


def test_a_turn_without_handoff_is_saved_as_before(golden_chat):
    golden_chat.model.script[:] = [ModelReply(text="Just me.")]
    body = chat(golden_chat)
    saved = golden_chat.db.chats.find_one({"chat_id": body["chat_id"]})
    assert saved["agents"] == ["stylist"] and saved["handoff"] is None
    assert not [line for line in body["trace"] if "handoff" in line]


def test_general_has_no_handoff_tool(golden_chat):
    golden_chat.model.script[:] = [tool_call("handoff", HANDOFF), ModelReply(text="Hi.")]
    body = chat(golden_chat, agent="general")
    assert json.loads(golden_chat.model.received[-1]["messages"][-1]["content"])["error"] == "unknown_tool"
    assert body["agent"] == "general"


# ---------------------------------------------------------------- agents.yaml
def test_every_agent_with_tools_has_the_handoff_tool_and_the_line_and_general_has_neither():
    for name, agent in AGENTS.agents.items():
        has_tools = bool(agent.tools)
        assert ("handoff" in agent.tools) == has_tools, name
        lines = [line for line in agent.instructions.splitlines() if line.startswith(INSTRUCTION_LINE)]
        assert len(lines) == (1 if has_tools else 0), name
        assert len(agent.tools) <= AGENTS.limits.max_tools


def test_the_second_run_agent_loses_exactly_the_tool_and_the_line():
    agent = AGENTS.agents["explainer"]                    # its line has an example after the shared sentence
    second = second_run_agent(agent)
    assert second.tools == [t for t in agent.tools if t != "handoff"] and "handoff" not in second.tools
    assert INSTRUCTION_LINE not in second.instructions and second.instructions.startswith(agent.instructions[:200])
    assert "handoff" in agent.tools and INSTRUCTION_LINE in agent.instructions          # the original is untouched
