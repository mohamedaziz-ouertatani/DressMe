"""
The router's own test (step 3e): which agent does the router choose for a message?

The trap set (eval_traps.py) tests whole answers, which takes minutes. The router is ONE short model call, so it can be
tested alone, in seconds, on many messages. That makes the agents' descriptions and examples quick to tune, and keeps
the trap set for what it is good at: answers.

Run it in the backend container (Ollama must have the model):

    docker exec dressme-backend-1 python -m app.eval_router                      # the dev cases, 5 runs each
    docker exec dressme-backend-1 python -m app.eval_router --split test         # the held-out cases (rarely!)
    docker exec dressme-backend-1 python -m app.eval_router --split all --repeat 10

bench/assistant/router_cases.yaml holds the labelled messages. Each has a split:
    dev    used while tuning the agents' descriptions and examples
    test   held back: run it once per decision and never tune on it, so its number stays honest
A case is scored only when its expected agent exists in mappings/agents.yaml; the others are listed, not scored (they
start counting the day that agent is built). `acceptable_agents` lists other agents that do no harm for an overlapping
question (the stylist and the wardrobe analyst can both search the wardrobe, for example).

Writes bench/results/assistant/router-<model>-<time>.jsonl and .md.
"""

import argparse
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml


def load_cases(path, split):
    cases = yaml.safe_load(Path(path).read_text(encoding="utf-8"))["cases"]
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        sys.exit("router_cases.yaml: two cases have the same id")
    return [c for c in cases if split == "all" or c.get("split", "dev") == split]


def right_agents(case):
    return {case["expected"], *case.get("acceptable_agents", [])}


def run(cases, agents, model, repeat, choose):
    """One row per (case, run). `choose(message, agents, model)` -> (agent name, how); `agents.agents` = the agents."""
    existing = set(agents.agents)
    rows = []
    for run_number in range(1, repeat + 1):
        for case in cases:
            started = time.perf_counter()
            chosen, how = choose(case["message"], agents, model)
            seconds = round(time.perf_counter() - started, 2)
            scored = case["expected"] in existing
            rows.append({"id": case["id"], "run": run_number, "split": case.get("split", "dev"),
                         "message": case["message"], "expected": case["expected"],
                         "acceptable": case.get("acceptable_agents", []), "chosen": chosen, "how": how,
                         "scored": scored, "ok": scored and chosen in right_agents(case), "seconds": seconds})
    return rows


def cell(text, limit=None):
    text = " ".join(str(text).split()).replace("|", "\\|")
    return text if limit is None or len(text) <= limit else text[:limit - 1] + "…"


def report(rows, meta):
    scored = [r for r in rows if r["scored"]]
    right = sum(r["ok"] for r in scored)
    how = Counter(r["how"] for r in rows)
    seconds = [r["seconds"] for r in rows]
    lines = [f"# Router test: {meta['model']}", "",
             f"Run {meta['started']} · split: {meta['split']} · {meta['repeat']} run(s) of {meta['n_cases']} cases · "
             f"{len(rows)} answers · agents in the file: {', '.join(meta['agents'])}", "",
             "## Totals", "", "| Measure | Value |", "| --- | --- |",
             f"| Router accuracy (cases whose expected agent exists) | {right} of {len(scored)} "
             f"({100 * right / max(1, len(scored)):.0f}%) |",
             f"| Chosen by the model | {how['model']} of {len(rows)} |",
             f"| Fell back to the keywords | {how['keywords']} |",
             f"| Fell back to the default agent | {how['default']} |",
             f"| Seconds per router call: median / max | "
             f"{statistics.median(seconds) if seconds else 0:.2f} / {max(seconds) if seconds else 0:.2f} |", "",
             "If the model was not chosen for most answers, the router did not really run: check Ollama.", "",
             "## By expected agent", "", "| Expected | Cases | Answers | Right | Rate |", "| --- | --- | --- | --- | --- |"]
    by_agent = defaultdict(list)
    for r in scored:
        by_agent[r["expected"]].append(r)
    for name, items in by_agent.items():
        good = sum(r["ok"] for r in items)
        lines.append(f"| {name} | {len({r['id'] for r in items})} | {len(items)} | {good} | "
                     f"{100 * good / len(items):.0f}% |")

    wrong = Counter((r["expected"], r["chosen"]) for r in scored if not r["ok"])
    lines += ["", "## Mix-ups (expected to chosen)", ""]
    if wrong:
        lines += ["| Expected | Chosen | Answers |", "| --- | --- | --- |"]
        lines += [f"| {e} | {c} | {n} |" for (e, c), n in wrong.most_common(12)]
    else:
        lines.append("None.")

    by_case = defaultdict(list)
    for r in scored:
        by_case[r["id"]].append(r)
    unsure = {k: v for k, v in by_case.items() if not all(r["ok"] for r in v)}
    lines += ["", f"## Cases that were not always right ({len(unsure)})", ""]
    if unsure:
        lines += ["| Case | Message | Expected | Right | Chosen |", "| --- | --- | --- | --- | --- |"]
        for key, items in unsure.items():
            chosen = ", ".join(f"{a} {n}" for a, n in Counter(r["chosen"] for r in items).most_common())
            lines.append(f"| {key} | {cell(items[0]['message'], 70)} | {items[0]['expected']} | "
                         f"{sum(r['ok'] for r in items)} of {len(items)} | {chosen} |")
    else:
        lines.append("None.")

    skipped = [r for r in rows if not r["scored"]]
    lines += ["", "## Not scored yet (the expected agent is not built)", ""]
    if skipped:
        lines += ["| Expected | Answers | Chosen |", "| --- | --- | --- |"]
        for name in sorted({r["expected"] for r in skipped}):
            chosen = ", ".join(f"{a} {n}" for a, n in Counter(r["chosen"] for r in skipped
                                                             if r["expected"] == name).most_common())
            lines.append(f"| {name} | {sum(1 for r in skipped if r['expected'] == name)} | {chosen} |")
    else:
        lines.append("None: every expected agent exists.")
    lines += ["", "Tune the descriptions and examples on the dev split only. Run the test split once per decision."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    from .assistant import default_registry
    from .assistant.agents import load_agents
    from .assistant.ollama import OllamaClient
    from .assistant.routing import choose_agent
    from .config import ROOT, Settings

    parser = argparse.ArgumentParser(description="Test the router alone on labelled messages.")
    parser.add_argument("--cases", default=str(ROOT / "bench" / "assistant" / "router_cases.yaml"))
    parser.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--out", default=str(ROOT / "bench" / "results" / "assistant"))
    args = parser.parse_args(argv)

    settings = Settings()
    agents = load_agents(ROOT / "mappings" / "agents.yaml", default_registry().names())
    model = OllamaClient(settings.ollama_url, settings.chat_model, agents.model)
    if not model.available():
        sys.exit(f"Ollama has no model {settings.chat_model} at {settings.ollama_url}.")
    cases = load_cases(args.cases, args.split)
    choose_agent("Hi!", agents, model)                     # warm-up: the first call may load the model, not scored
    print(f"model: {model.name}; split {args.split}: {len(cases)} cases x {args.repeat}; agents: {list(agents.agents)}")

    rows = run(cases, agents, model, args.repeat, choose_agent)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    name = f"router-{re.sub(r'[^A-Za-z0-9.-]+', '_', model.name)}-{stamp}"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{name}.jsonl", "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    meta = {"model": model.name, "started": stamp, "split": args.split, "repeat": args.repeat,
            "n_cases": len(cases), "agents": list(agents.agents)}
    text = report(rows, meta)
    (out / f"{name}.md").write_text(text, encoding="utf-8")
    scored = [r for r in rows if r["scored"]]
    print(f"{sum(r['ok'] for r in scored)} of {len(scored)} scored answers right. Report: {out / (name + '.md')}")


if __name__ == "__main__":
    main()
