"""
Compares chat models served by Ollama (the base qwen3:4b-instruct and our
fine-tuned dressme-chat) on the test conversations of src/build_chat_dataset.py.

Every assistant turn of a test conversation is one decision. The model gets
the conversation up to that point (system prompt, tools, earlier messages and
the real tool answers) and must either call the right tool or answer:
    tool decision   called a tool when it should, and answered when it should
    tool name       the right tool (among the turns that need one)
    arguments       the same arguments (item ids as a set; tools' defaults filled in)
    language        a final answer in the right language (en / fr / ar)
    seconds         time per decision on this machine
The test wardrobes were never seen in training, and about a third of the
questions use phrasings held out of the training split.

Usage (from the project root, Ollama running, ~2-5 s per decision):
    python src/evaluate_chat.py                                    # both models, 150 conversations
    python src/evaluate_chat.py --models qwen3:4b-instruct --limit 20
Output: reports/chat_evaluation.md + reports/chat_evaluation.json
"""

import argparse
import json
import re
import time
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "data" / "processed" / "chat_sft" / "test.jsonl"
REPORT = ROOT / "reports" / "chat_evaluation.md"
DEFAULTS = {"suggest_outfits": {"season": "", "occasion": "", "n": 1}, "list_wardrobe": {"category": ""}}

FR_WORDS = {"le", "la", "les", "tu", "ton", "ta", "tes", "et", "avec", "pour", "une", "un", "des",
            "de", "est", "pas", "je", "ça", "dans", "ce", "mais", "ou", "sur", "va", "aux", "du"}
EN_WORDS = {"the", "you", "your", "and", "with", "for", "a", "is", "not", "i", "it", "this", "in",
            "to", "of", "or", "but", "on", "go", "would", "have", "my"}


def language(text):
    letters = [c for c in text if c.isalpha()]
    if letters and sum("؀" <= c <= "ۿ" for c in letters) / len(letters) > 0.3:
        return "ar"
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", text.lower())
    fr, en = sum(w in FR_WORDS for w in words), sum(w in EN_WORDS for w in words)
    return "fr" if fr > en else "en"


def normalise(name, arguments):
    """Arguments with the tool's defaults filled in; item ids as a sorted list."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except ValueError:
            arguments = {}
    args = {**DEFAULTS.get(name, {}), **(arguments or {})}
    if "n" in args:
        try:
            args["n"] = int(args["n"])
        except (TypeError, ValueError):
            pass
    if isinstance(args.get("item_ids"), list):
        args["item_ids"] = sorted(map(str, args["item_ids"]))
    return args


def to_ollama(messages):
    """Our dataset messages in Ollama's format (tool answers carry tool_name)."""
    out = []
    for m in messages:
        if m["role"] == "tool":
            out.append({"role": "tool", "tool_name": m["name"], "content": m["content"]})
        elif m.get("tool_calls"):
            out.append({"role": "assistant", "content": m["content"],
                        "tool_calls": [{"function": c["function"]} for c in m["tool_calls"]]})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out


def ask(url, model, messages, tools):
    r = httpx.post(url + "/api/chat", timeout=300, json={
        "model": model, "messages": to_ollama(messages), "tools": tools, "stream": False,
        # num_predict: same answer limit as the backend (a model that repeats itself
        # forever would otherwise hit the timeout and stop the whole evaluation)
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 600}})
    r.raise_for_status()
    return r.json()["message"]


def evaluate(url, model, rows):
    per = defaultdict(lambda: defaultdict(list))          # scenario -> metric -> [0/1]
    examples = []
    for row in rows:
        msgs = row["messages"]
        # The language can change from one question to the next, so each answer is
        # checked against its own turn's language (older files: the last turn's only)
        answer_languages = iter(row.get("answer_languages", []))
        for k, gold in enumerate(msgs):
            if gold["role"] != "assistant" or k == 0:
                continue
            if not gold.get("tool_calls"):
                expected_language = next(answer_languages, row["language"])
            if not any(m["role"] == "user" for m in msgs[:k]):
                continue
            started = time.time()
            pred = ask(url, model, msgs[:k], row["tools"])
            seconds = time.time() - started
            calls = pred.get("tool_calls") or []
            m = per[row["scenario"]]
            m["seconds"].append(seconds)
            if gold.get("tool_calls"):
                g = gold["tool_calls"][0]["function"]
                m["tool_decision"].append(int(bool(calls)))
                name_ok = bool(calls) and calls[0]["function"]["name"] == g["name"]
                m["tool_name"].append(int(name_ok))
                m["arguments"].append(int(name_ok and normalise(g["name"], calls[0]["function"].get("arguments"))
                                          == normalise(g["name"], g["arguments"])))
            else:
                m["tool_decision"].append(int(not calls))
                if not calls:
                    m["language"].append(int(language(pred.get("content", "")) == expected_language))
                    if len(examples) < 6 and k == len(msgs) - 1:
                        examples.append({"question": next(x["content"] for x in reversed(msgs[:k])
                                                          if x["role"] == "user"),
                                         "gold": gold["content"], "answer": pred.get("content", "")})
        print(f"  {model}: {row['id']} done", end="\r")
    print()
    return per, examples


def mean(values):
    return round(100 * sum(values) / len(values), 1) if values else None


def summary(per):
    metrics = ["tool_decision", "tool_name", "arguments", "language"]
    total = {k: [v for s in per.values() for v in s[k]] for k in metrics + ["seconds"]}
    out = {k: mean(total[k]) for k in metrics}
    out["seconds"] = round(sum(total["seconds"]) / max(len(total["seconds"]), 1), 2)
    out["decisions"] = len(total["seconds"])
    out["by_scenario"] = {s: {k: mean(per[s][k]) for k in metrics} for s in sorted(per)}
    return out


def write_report(results, n_conv):
    lines = ["# Chat model evaluation", "",
             f"{n_conv} test conversations of `src/build_chat_dataset.py` (wardrobes never seen in "
             "training, ~1/3 of the questions phrased differently from the training split). Each "
             "assistant turn is one decision; the model sees the real conversation up to that point.", "",
             "| Model | Tool decision | Tool name | Arguments | Language | s / decision |",
             "|---|---|---|---|---|---|"]
    for model, r in results.items():
        s = r["summary"]
        lines.append(f"| {model} | {s['tool_decision']}% | {s['tool_name']}% | {s['arguments']}% | "
                     f"{s['language']}% | {s['seconds']} |")
    for model, r in results.items():
        lines += ["", f"## {model} by scenario", "",
                  "| Scenario | Tool decision | Tool name | Arguments | Language |", "|---|---|---|---|---|"]
        for scen, s in r["summary"]["by_scenario"].items():
            lines.append(f"| {scen} | " + " | ".join(
                "-" if s[k] is None else f"{s[k]}%" for k in ("tool_decision", "tool_name", "arguments", "language"))
                + " |")
        lines += ["", "Examples (expected / model):", ""]
        for e in r["examples"]:
            lines += [f"- **Q:** {e['question']}", f"  - expected: {e['gold']}", f"  - model: {e['answer']}"]
    lines += ["", "Synthetic data measures tool use and language, not how natural the answers sound: "
              "also try a few real questions in the app (CHAT_ENGINE=ollama)."]
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--models", nargs="+", default=["qwen3:4b-instruct", "dressme-chat"])
    ap.add_argument("--limit", type=int, default=150, help="test conversations to use")
    ap.add_argument("--url", default="http://localhost:11434")
    args = ap.parse_args()
    with open(TEST, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f][:args.limit]
    results = {}
    for model in args.models:
        print(f"evaluating {model} on {len(rows)} conversations...")
        per, examples = evaluate(args.url, model, rows)
        results[model] = {"summary": summary(per), "examples": examples}
        print(json.dumps(results[model]["summary"], indent=1))
    write_report(results, len(rows))
    REPORT.with_suffix(".json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"-> {REPORT}")


if __name__ == "__main__":
    main()
