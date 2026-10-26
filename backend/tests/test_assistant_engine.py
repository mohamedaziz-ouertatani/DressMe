"""
The assistant's engine (step 3c): the loop, the registry, the piece ledger and the {n} rule, tested with a
scripted FAKE model and a tiny fake registry. No database, no real model.
"""

from pydantic import BaseModel

from app.assistant.agents import Agent
from app.assistant.ledger import PieceLedger
from app.assistant.loop import run_turn
from app.assistant.model import FakeModel, ModelReply, ToolCall
from app.assistant.placeholders import resolve
from app.assistant.tools import Registry, Tool, ToolContext


class EchoArgs(BaseModel, extra="forbid"):
    word: str


class WearArgs(BaseModel, extra="forbid"):
    piece: int


def say(text):
    return ModelReply(text=text)


def call(name, **arguments):
    return ModelReply(tool_calls=[ToolCall(name=name, arguments=arguments)])


def make_registry(seen=None):
    """Two tiny tools: `echo` lists two pieces (so the ledger fills), `wear` takes a piece by its ref."""
    seen = seen if seen is not None else []

    def echo(ctx, args):
        return {"pieces": [{"ref": ctx.ledger.add("id-a"), "colour": args.word},
                           {"ref": ctx.ledger.add("id-b"), "colour": "blue"}]}

    def wear(ctx, args):
        seen.append(args.piece)           # after the translation this is the item id, not the ref
        return {"worn": args.piece}

    registry = Registry()
    registry.register(Tool("echo", "Echo a word. Example: echo(word='red'). Do not use for anything else.",
                           EchoArgs, echo))
    registry.register(Tool("wear", "Wear a piece. Example: wear(piece=1). Do not use for unknown pieces.",
                           WearArgs, wear, piece_args=("piece",)))
    return registry


def make_agent(max_rounds=6):
    return Agent(job="test", instructions="Be brief.", tools=["echo", "wear"], keywords={},
                 max_rounds=max_rounds, max_tokens=100)


def turn(script, max_rounds=6):
    model = FakeModel(script)
    ctx = ToolContext(user_id="u1", db=None, ledger=PieceLedger())
    result = run_turn(make_agent(max_rounds), "hello", model, make_registry(), ctx, shared_rules="Rule one.")
    return result, model


# ---------------------------------------------------------------- the loop
def test_an_answer_without_tools_returns_at_once():
    result, model = turn([say("Hi!")])
    assert (result.answer, result.stop_reason, result.rounds, result.trace) == ("Hi!", "answered", 1, [])
    system, user = model.received[0]["messages"]
    assert "Be brief." in system["content"] and "Rule one." in system["content"]
    assert user == {"role": "user", "content": "hello"}


def test_invalid_arguments_go_back_to_the_model_which_corrects_them():
    result, model = turn([call("echo"), call("echo", word="red"), say("Done.")])
    assert result.stop_reason == "answered" and result.rounds == 3
    assert [(t["ok"], t["error_code"]) for t in result.trace] == [(False, "invalid_arguments"), (True, None)]
    second_round = model.received[1]["messages"]
    assert second_round[-1]["role"] == "tool" and "invalid_arguments" in second_round[-1]["content"]


def test_the_same_call_twice_stops_with_repeat_and_a_final_answer_without_tools():
    result, model = turn([call("echo", word="red"), call("echo", word="red"), say("Here you go.")])
    assert result.stop_reason == "repeat" and result.answer == "Here you go."
    assert len(result.trace) == 1                       # the repeat was not run
    assert model.received[-1]["tools"] == []            # the last call gives the model no tool to ask for


def test_max_rounds_forces_a_final_answer_without_tools():
    result, model = turn([call("echo", word="a"), call("echo", word="b"), say("Enough.")], max_rounds=2)
    assert result.stop_reason == "max_rounds" and result.rounds == 2 and result.answer == "Enough."
    assert model.received[-1]["tools"] == []
    assert len(model.received) == 3


# ---------------------------------------------------------------- the {n} rule
def test_known_placeholders_stay_and_unknown_ones_are_removed_and_reported():
    ledger = PieceLedger()
    ledger.add("id-a"), ledger.add("id-b")
    assert resolve("Try {2} with {1}. {99}", ledger) == ("Try {2} with {1}.", [2, 1], [99])
    assert resolve("Nothing here.", ledger) == ("Nothing here.", [], [])


def test_an_invented_placeholder_in_the_answer_is_removed_by_the_loop():
    result, _ = turn([call("echo", word="black"), say("Try {2} with {1}. {99}")])
    assert result.answer == "Try {2} with {1}."
    assert (result.refs, result.unknown_refs) == ([2, 1], [99])


def test_the_same_item_keeps_its_ref():
    ledger = PieceLedger()
    assert [ledger.add("x"), ledger.add("y"), ledger.add("x")] == [1, 2, 1]
    assert ledger.item_id(2) == "y" and ledger.item_id(9) is None and ledger.refs() == {1: "x", 2: "y"}


# ---------------------------------------------------------------- the registry
def test_an_unknown_piece_ref_in_the_arguments_is_rejected_and_the_tool_does_not_run():
    seen = []
    registry = make_registry(seen)
    ctx = ToolContext(user_id="u1", db=None, ledger=PieceLedger())
    bad = registry.run(ToolCall(name="wear", arguments={"piece": 5}), ctx)
    assert (bad.ok, bad.error_code) == (False, "unknown_piece") and seen == []
    ctx.ledger.add("id-a")
    good = registry.run(ToolCall(name="wear", arguments={"piece": 1}), ctx)
    assert good.ok and seen == ["id-a"]                 # the tool got the id the ref stands for


def test_an_unknown_tool_and_a_crashing_tool_are_error_results_not_exceptions():
    def boom(ctx, args):
        raise RuntimeError("database down")

    registry = make_registry()
    registry.register(Tool("boom", "Crash. Example: boom(word='x'). Do not use.", EchoArgs, boom))
    ctx = ToolContext(user_id="u1", db=None, ledger=PieceLedger())
    assert registry.run(ToolCall(name="nope", arguments={}), ctx).error_code == "unknown_tool"
    assert registry.run(ToolCall(name="boom", arguments={"word": "x"}), ctx).error_code == "tool_failed"
    extra = registry.run(ToolCall(name="echo", arguments={"word": "x", "user_id": "someone else"}), ctx)
    assert extra.error_code == "invalid_arguments"      # the user id can never be an argument


def test_schemas_use_the_tools_format():
    schema = make_registry().schemas(["echo"])[0]
    assert schema["type"] == "function" and schema["function"]["name"] == "echo"
    assert schema["function"]["parameters"]["properties"]["word"]["type"] == "string"
