"""The synthetic fine-tuning conversations (src/phase4/build_chat_dataset.py) use the
real agents' prompts and tools correctly (scratch MongoDB database, no model needed)."""

import json
import random
import sys

import pytest
from pymongo import MongoClient

from app.config import SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]
import build_chat_dataset as B  # noqa: E402
from app.agents import AGENTS  # noqa: E402
from app.agents.router import router_prompt  # noqa: E402

ARABIC = range(0x0600, 0x0700)


def has_arabic(text):
    return any(ord(c) in ARABIC for c in text)


@pytest.fixture(scope="module")
def rows():
    client = MongoClient()
    try:
        yield B.build_split("val", 250, client["dressme_test_chatsft"])
    finally:
        client.drop_database("dressme_test_chatsft")


def test_every_agent_and_scenario_appears(rows):
    assert {r["agent"] for r in rows} == set(AGENTS) | {"router"}
    assert {r["scenario"] for r in rows} >= {"suggest", "today", "complete", "buy", "search", "insights",
                                            "what_sell", "sell", "why_score", "labels", "chit_chat",
                                            "handoff", "route", "why_similar", "not_owned_other"}


def test_conversations_use_their_agent_prompt_and_tools(rows):
    for r in rows:
        msgs = r["messages"]
        if r["scenario"] == "route":
            assert msgs[0]["content"] == router_prompt() and r["tools"] == []
            assert msgs[-1]["content"] in AGENTS
            continue
        names = {t["function"]["name"] for t in r["tools"]}
        assert names == set(AGENTS[r["agent"]].tools(None, {"_id": None, "profile": {}}))
        assert msgs[0]["role"] == "system" and AGENTS[r["agent"]].job in msgs[0]["content"]
        assert msgs[1]["role"] == "user"
        assert msgs[-1]["role"] == "assistant" and msgs[-1]["content"]     # ends with an answer
        for k, m in enumerate(msgs):
            if m.get("tool_calls"):
                call = m["tool_calls"][0]["function"]
                assert call["name"] in names
                assert msgs[k + 1]["role"] == "tool" and msgs[k + 1]["name"] == call["name"]
                json.loads(msgs[k + 1]["content"])


def test_answers_are_in_their_language(rows):
    for r in rows:
        if r["scenario"] == "route":
            continue
        answers = [m for m in r["messages"] if m["role"] == "assistant" and not m.get("tool_calls")]
        assert len(r["answer_languages"]) == len(answers)
        assert r["answer_languages"][-1] == r["language"]
        for m, lang in zip(answers, r["answer_languages"]):
            assert has_arabic(m["content"]) == (lang == "ar"), m["content"]


def test_ids_always_come_from_list_wardrobe(rows):
    """Every id the assistant sends was in an earlier list_wardrobe answer (or a tool's own answer)."""
    for r in rows:
        seen = set()
        for m in r["messages"]:
            if m["role"] == "tool" and m["name"] == "list_wardrobe":
                seen |= {i["id"] for i in json.loads(m["content"])}
            for c in m.get("tool_calls", []):
                args = c["function"]["arguments"]
                ids = list(args.get("item_ids", [])) + [args[k] for k in ("item_id", "other_id", "remove_id",
                                                                          "add_id")
                                                        if args.get(k) and args[k] != "last_scan"]
                assert set(ids) <= seen, (r["id"], c)


def test_today_checks_the_weather_first(rows):
    for r in rows:
        if r["scenario"] == "today":
            calls = [c["function"]["name"] for m in r["messages"] for c in m.get("tool_calls", [])]
            assert calls[:2] == ["get_weather", "suggest_outfits"]


def test_chit_chat_and_handoffs_call_no_tool(rows):
    for r in rows:
        if r["scenario"] in ("chit_chat", "handoff"):
            assert not any(m.get("tool_calls") for m in r["messages"])


def test_train_split_holds_out_phrasings():
    conv = B.Conversation.__new__(B.Conversation)
    conv.rng, conv.split = random.Random(0), "train"
    assert {conv.pick(["a", "b", "c"]) for _ in range(50)} == {"a", "b"}


def test_training_text_has_no_empty_think_block():
    """The hybrid Qwen3 template Unsloth ships writes an empty <think></think> before the
    last answer; Ollama's template never does, so it must not be learned."""
    import finetune_chat as F

    class Tokenizer:     # renders like the hybrid template: empty think before the last answer
        def apply_chat_template(self, messages, tools, tokenize):
            *rest, last = messages
            return "".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in rest) \
                + f"<|im_start|>assistant\n<think>\n\n</think>\n\n{last['content']}<|im_end|>\n"

        def __call__(self, text, add_special_tokens):
            return {"input_ids": text.split()}

    rows = [{"tools": [], "messages": [{"role": "user", "content": "hi"},
                                       {"role": "assistant", "content": "Hello!"}]}]
    texts, too_long = F.to_texts(rows, Tokenizer(), max_seq=100)
    assert texts == ["<|im_start|>user\nhi<|im_end|>\n<|im_start|>assistant\nHello!<|im_end|>\n"]


def test_a_piece_the_user_does_not_own_is_never_given_an_id(rows):
    """'What goes with / something like / how much for my X?' without an X: list the wardrobe and
    say so, never pass another piece's id (v2 did)."""
    for r in rows:
        if r["scenario"] in ("not_owned", "not_owned_other"):
            calls = [c["function"]["name"] for m in r["messages"] for c in m.get("tool_calls", [])]
            assert calls == ["list_wardrobe"], (r["id"], calls)
