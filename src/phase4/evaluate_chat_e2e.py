"""
End-to-end check of the local chat models: whole chats through the app's real engine
(backend/app/chat_engine.py, OllamaEngine) and the agents' real tools, with NO help.

evaluate_chat.py scores each decision with the correct conversation in front of the
model (the right list_wardrobe answer is already there), which is lenient: v2 scored
100% on look-alike explanations that way, but made up reasons in a real chat. Here
the model must get every step right by itself, like in the app.

For each scenario, src/phase4/build_chat_dataset.py makes a test conversation (a
random wardrobe in a scratch MongoDB database, a question, the reference tool calls).
The model gets the agent's prompt, its tools and the question. A chat is right when
it calls exactly the reference tools, in order, no tool answers an error and the
final answer is not empty. Models run at the app's temperature (0.3), so two runs
can differ by a chat or two.

Usage (from the project root, Ollama + local MongoDB running, ~20 s per chat):
    python src/phase4/evaluate_chat_e2e.py --models dressme-chat-v2 dressme-chat-v3 --per 8
Output: reports/phase4/chat_e2e_evaluation.md
"""

import argparse
import random
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import build_chat_dataset as B          # also puts backend/ and src/ on the import path
from app.agents import AGENTS
from app.chat_engine import OllamaEngine

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "phase4" / "chat_e2e_evaluation.md"
SCRATCH_DB = "dressme_e2e_eval"
# scenario -> agent that gets it (None: one of build_chat_dataset.SCENARIO_AGENTS)
SCENARIOS = {"why_similar": "explainer", "similar": "shopping", "search": "shopping", "buy": "shopping",
             "not_owned": "stylist", "not_owned_other": None, "handoff": "shopping", "chit_chat": "stylist",
             "score": "stylist", "today": "stylist"}
ALLOWED_ERRORS = {"weather unavailable"}     # the data switches the weather off on purpose


def watch(fn, errors):
    """The tool, noting every error it answers."""
    def run(*args, **kwargs):
        out = fn(*args, **kwargs)
        if isinstance(out, dict) and "error" in out and out["error"] not in ALLOWED_ERRORS:
            errors.append(out["error"])
        return out
    run.__name__, run.__doc__, run.__wrapped__ = fn.__name__, fn.__doc__, fn
    return run


def evaluate(model, db, per, failures):
    settings = SimpleNamespace(ollama_url="http://localhost:11434", ollama_timeout=300, ollama_model=model,
                               ollama_temperature=0.3, ollama_num_ctx=8192, ollama_max_tokens=600)
    engine = OllamaEngine(settings)
    rng = random.Random(7)                   # the same chats for every model
    world = B.World(db, rng)
    right, crashes = defaultdict(list), 0
    for scenario, agent in SCENARIOS.items():
        for _ in range(per):
            name = agent or rng.choice(B.SCENARIO_AGENTS.get(scenario, list(AGENTS)))
            conv = B.Conversation(rng, world, "test", name)
            conv.build(scenario)
            if conv.kind != scenario:       # the wardrobe could not make this scenario
                continue
            gold = [c["function"]["name"] for m in conv.messages for c in m.get("tool_calls", [])]
            # the real question (a chat may open with a greeting exchange)
            question = [m["content"] for m in conv.messages if m["role"] == "user"][-1]
            errors = []
            tools = {n: watch(f, errors) for n, f in AGENTS[name].tools(conv.request, conv.user).items()}
            started = time.time()
            try:
                answer, used = engine.reply(AGENTS[name].prompt(conv.user), [], question, tools)
            except Exception as e:           # e.g. Ollama 500 on malformed tool-call JSON
                answer, used, crashes = "", [f"crash: {str(e)[:80]}"], crashes + 1
            ok = used == gold and not errors and bool(answer.strip())
            right[scenario].append(ok)
            if not ok:
                failures.append(f"- **{model}**, {scenario}: {question}  \n  expected {gold}, used {used}"
                                f"{', error: ' + errors[0] if errors else ''} ({time.time() - started:.0f} s)  \n"
                                f"  answer: {answer[:160]}")
        print(f"  {model} {scenario}: {sum(right[scenario])} / {len(right[scenario])}", flush=True)
    return right, crashes


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--models", nargs="+", default=["dressme-chat-v2", "dressme-chat-v3"])
    ap.add_argument("--per", type=int, default=8, help="chats per scenario")
    ap.add_argument("--mongo", default="mongodb://localhost:27017")
    args = ap.parse_args()
    from pymongo import MongoClient
    client = MongoClient(args.mongo)
    results, failures = {}, []
    try:
        for model in args.models:
            print(f"evaluating {model}...")
            results[model] = evaluate(model, client[SCRATCH_DB], args.per, failures)
    finally:
        client.drop_database(SCRATCH_DB)
    lines = ["# Chat models end to end", "",
             "Whole chats through the app's engine and the agents' real tools, with no help (see "
             "`src/phase4/evaluate_chat_e2e.py`). A chat is right when the model calls exactly the "
             f"reference tools in order, no tool answers an error and the answer is not empty. {args.per} "
             "chats per scenario (fewer when a wardrobe cannot make it), the same chats for every model, "
             "temperature 0.3 (a rerun can differ by a chat or two).", "",
             "| Scenario | " + " | ".join(args.models) + " |", "|---|" + "---|" * len(args.models)]
    for scenario in SCENARIOS:
        lines.append(f"| {scenario} | " + " | ".join(
            f"{sum(results[m][0][scenario])} / {len(results[m][0][scenario])}" for m in args.models) + " |")
    totals = {m: [x for v in results[m][0].values() for x in v] for m in args.models}
    lines.append("| **all** | " + " | ".join(
        f"**{sum(t)} / {len(t)} ({100 * sum(t) / max(len(t), 1):.1f}%)**" for t in totals.values()) + " |")
    lines.append("| crashes (Ollama could not read a tool call) | " + " | ".join(
        str(results[m][1]) for m in args.models) + " |")
    lines += ["", "## Failures", ""] + failures
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[6:6 + len(SCENARIOS) + 3]))
    print(f"-> {REPORT}")


if __name__ == "__main__":
    main()
