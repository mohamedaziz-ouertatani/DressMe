"""The synthetic fine-tuning conversations (src/build_chat_dataset.py) use the
real tools correctly: no Mongo, no model needed."""

import json
import sys

from app.config import ROOT

sys.path.insert(0, str(ROOT / "src"))
import build_chat_dataset as B  # noqa: E402
from app.chat_engine import tool_schema  # noqa: E402
from app.routers.chat import tools_for  # noqa: E402


def test_conversations_are_well_formed():
    schemas = [tool_schema(f) for f in tools_for(None, None).values()]
    names = {s["function"]["name"] for s in schemas}
    rows = B.build_split("val", 60, schemas)
    assert {r["scenario"] for r in rows} >= {"list", "suggest", "score", "buy"}
    for r in rows:
        msgs = r["messages"]
        assert msgs[0]["role"] == "system" and msgs[1]["role"] == "user"
        assert msgs[-1]["role"] == "assistant" and msgs[-1]["content"]     # ends with an answer
        for k, m in enumerate(msgs):
            if m.get("tool_calls"):
                call = m["tool_calls"][0]["function"]
                assert call["name"] in names
                assert msgs[k + 1]["role"] == "tool" and msgs[k + 1]["name"] == call["name"]
                json.loads(msgs[k + 1]["content"])
        if r["language"] == "ar":
            assert any("؀" <= c <= "ۿ" for c in msgs[-1]["content"])
        # one language per plain answer (what evaluate_chat.py checks each answer against)
        answers = [m for m in msgs if m["role"] == "assistant" and not m.get("tool_calls")]
        assert len(r["answer_languages"]) == len(answers)
        assert r["answer_languages"][-1] == r["language"]
        for m, lang in zip(answers, r["answer_languages"]):
            assert any("؀" <= c <= "ۿ" for c in m["content"]) == (lang == "ar")


def test_score_uses_the_ids_from_list_wardrobe():
    schemas = [tool_schema(f) for f in tools_for(None, None).values()]
    for r in B.build_split("test", 80, schemas):
        if r["scenario"] != "score":
            continue
        listed = {i["id"] for m in r["messages"] if m.get("name") == "list_wardrobe"
                  for i in json.loads(m["content"])}
        for m in r["messages"]:
            for c in m.get("tool_calls", []):
                if c["function"]["name"] == "score_outfit":
                    assert set(c["function"]["arguments"]["item_ids"]) <= listed


def test_train_split_holds_out_phrasings():
    import random
    conv = B.Conversation(random.Random(0), B.WardrobeMaker(random.Random(0)), "train")
    assert {conv.pick(["a", "b", "c"]) for _ in range(50)} == {"a", "b"}
