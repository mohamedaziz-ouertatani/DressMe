"""
The assistant's trap set, run against the LIVE API with the real model (step 2 of the chat plan; "3g" in the report).

Run it in the backend container (the API must be up, Ollama must have the model):

    docker exec dressme-backend-1 python -m app.eval_traps                  # every ENGLISH trap once
    docker exec dressme-backend-1 python -m app.eval_traps --repeat 3       # the official baseline: 3 runs each
    docker exec dressme-backend-1 python -m app.eval_traps --only g01,n01   # just these traps
    docker exec dressme-backend-1 python -m app.eval_traps --lang ar,arabizi   # later: Arabic, then --lang fr

Languages: English is measured first; Arabic (ar, arabizi) and then French (fr) are added once everything works
in English. Their traps stay in traps.yaml and are skipped until --lang asks for them.
    docker exec dressme-backend-1 python -m app.eval_traps --lang en        # English only (quick checks while building)

What it does:
  1. Logs in as the eval user traps@example.com (creates it the first time, gender women).
  2. Gives that user the GOLDEN wardrobe (backend/tests/golden/wardrobe.json, 17 pieces), replacing what it had,
     so every run asks the same questions about the same wardrobe.
  3. Sends one warm-up message (not scored), then every trap in bench/assistant/traps.yaml to POST /chat.
  4. Scores each answer with the trap's automatic checks, reading the saved `chats` document for unknown_refs and
     the pieces shown.
  5. Writes bench/results/assistant/traps-<model>-<time>.jsonl (every answer) and .md (the report, with a sheet
     for the checks a human must make by reading).

The eval user is a normal account in the dev database. Its chats are tagged by chat_id "trap-...".
Temperature is 0.7, so answers vary: use --repeat 3 for numbers you report.
"""

import argparse
import json
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

EVAL_EMAIL = "traps@example.com"
EVAL_NAME = "Trap set"
EVAL_GENDER = "women"                      # the golden wardrobe is a women's wardrobe
CHAT_TIMEOUT_S = 900                       # up to 7 model calls of 90 s each, plus the tools

# ---------------------------------------------------------------- language of an answer (rough, on purpose)
ARABIC = re.compile(r"[؀-ۿ]")
FRENCH_ACCENTS = re.compile(r"[àâçéèêëîïôûùüœ]")
FR_WORDS = {"le", "la", "les", "un", "une", "des", "et", "est", "tu", "ton", "ta", "tes", "avec", "pour", "pas",
            "que", "qui", "je", "de", "du", "dans", "sur", "ce", "cette", "vous", "votre", "mais", "ou", "aussi",
            "bien", "très", "tenue", "porter", "jupe", "robe", "veste", "chaussures", "aujourd'hui", "avec"}
EN_WORDS = {"the", "a", "an", "and", "is", "you", "your", "with", "for", "not", "that", "it", "to", "of", "in",
            "on", "this", "are", "can", "what", "today", "wear", "skirt", "dress", "jacket", "shoes", "would"}


def detect_lang(text):
    """'ar', 'fr', 'en' or 'unknown'. Enough to catch an answer in the wrong language, not a real detector."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "unknown"
    if sum(1 for c in letters if ARABIC.match(c)) / len(letters) > 0.3:
        return "ar"
    lowered = text.lower()
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", lowered)
    fr = sum(w in FR_WORDS for w in words) + 2 * len(FRENCH_ACCENTS.findall(lowered))
    en = sum(w in EN_WORDS for w in words)
    if fr == en == 0:
        return "unknown"
    return "fr" if fr > en else "en"


# ---------------------------------------------------------------- the automatic checks
def tools_called(body):
    return [line["tool"] for line in body.get("trace", []) if "tool" in line]


def score(trap, status, body, unknown_refs, pieces):
    """The list of failed checks (empty = passed).

    status        HTTP status of POST /chat
    body          its JSON (or {} when it failed)
    unknown_refs  the invented {n} the turn removed (from the saved chats document)
    pieces        the pieces shown in the answer, as dicts with category / sub_category / colour
    """
    if status != 200:
        return [f"http {status}"]
    checks = trap.get("checks") or {}
    answer = body.get("answer") or ""
    tools = tools_called(body)
    fails = []

    if not answer.strip():
        fails.append("empty answer")
    if unknown_refs:                                            # always checked: no invented piece numbers
        fails.append(f"invented piece numbers {unknown_refs}")

    if "tools_any" in checks and not set(tools) & set(checks["tools_any"]):
        fails.append(f"expected one of {checks['tools_any']}, called {tools or 'no tool'}")
    if checks.get("no_tools") and tools:
        fails.append(f"expected no tool, called {tools}")
    for tool in checks.get("forbid_tools", []):
        if tool in tools:
            fails.append(f"called forbidden tool {tool}")

    if "min_pieces" in checks and len(pieces) < checks["min_pieces"]:
        fails.append(f"showed {len(pieces)} pieces, expected at least {checks['min_pieces']}")
    if "max_pieces" in checks and len(pieces) > checks["max_pieces"]:
        fails.append(f"showed {len(pieces)} pieces, expected at most {checks['max_pieces']}")
    for rule in checks.get("forbid_pieces", []):
        for piece in pieces:
            if all(str(piece.get(k, "")).lower() == str(v).lower() for k, v in rule.items()):
                fails.append(f"showed a piece matching {rule}")
                break

    if "reply_lang" in checks:
        lang = detect_lang(answer)
        if lang != checks["reply_lang"]:
            fails.append(f"answered in {lang}, expected {checks['reply_lang']}")
    for pattern in checks.get("forbid_patterns", []):
        if re.search(pattern, answer, re.IGNORECASE | re.DOTALL):
            fails.append(f"answer matches forbidden pattern {pattern!r}")
    if "max_questions" in checks:
        questions = answer.count("?") + answer.count("؟")
        if questions > checks["max_questions"]:
            fails.append(f"{questions} question marks, at most {checks['max_questions']}")
    return fails


# ---------------------------------------------------------------- the report
def cell(text, limit=None):
    text = " ".join(str(text).split()).replace("|", "\\|")
    return text if limit is None or len(text) <= limit else text[:limit - 1] + "…"


def percentile(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))] if values else 0


def report(rows, meta):
    """The markdown report: totals, per category, timing, failures, and the human review sheet."""
    ok = [r for r in rows if r["status"] == 200]
    passed = [r for r in rows if r["passed"]]
    seconds = [r["seconds"] for r in ok]
    by_trap = defaultdict(list)
    for r in rows:
        by_trap[r["id"]].append(r["passed"])
    every_run = sum(all(v) for v in by_trap.values())

    lines = [f"# Trap set report: {meta['model']}", "",
             f"Run {meta['started']} · {meta['repeat']} run(s) of {len(by_trap)} traps · {len(rows)} answers · "
             f"languages: {meta.get('lang', 'all')} · API {meta['api']}", "",
             "## Totals", "",
             "| Measure | Value |", "| --- | --- |",
             f"| Answers passing every automatic check | {len(passed)} of {len(rows)} "
             f"({100 * len(passed) / max(1, len(rows)):.0f}%) |",
             f"| Traps passing in every run | {every_run} of {len(by_trap)} |",
             f"| Answers with invented piece numbers | {sum(1 for r in rows if r['unknown_refs'])} |",
             f"| Errors (not HTTP 200) | {len(rows) - len(ok)} |",
             f"| Seconds per answer: median / 90th percentile / max | "
             f"{statistics.median(seconds) if seconds else 0:.1f} / {percentile(seconds, 0.9):.1f} / "
             f"{max(seconds) if seconds else 0:.1f} |",
             f"| Tool calls per answer (mean) | {statistics.mean(r['n_tool_calls'] for r in ok) if ok else 0:.1f} |",
             f"| Stop reasons | {', '.join(f'{k} {v}' for k, v in Counter(r['stop_reason'] for r in ok).items())} |",
             f"| `<think>` blocks stripped | {sum(r['thinking_stripped'] for r in ok)} |", "",
             "Automatic checks catch tool use, invented numbers, pieces that do not exist, language and some "
             "forbidden phrases. They cannot judge tone or truth: fill the review sheet below as well.", "",
             "## By category", "",
             "| Category | Answers | Passed | Rate | Median seconds |", "| --- | --- | --- | --- | --- |"]
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    for cat, items in by_cat.items():
        good = sum(r["passed"] for r in items)
        secs = [r["seconds"] for r in items if r["status"] == 200]
        lines.append(f"| {cat} | {len(items)} | {good} | {100 * good / len(items):.0f}% | "
                     f"{statistics.median(secs) if secs else 0:.1f} |")

    lines += ["", "## By language", "", "| Language | Answers | Passed | Rate |", "| --- | --- | --- | --- |"]
    by_lang = defaultdict(list)
    for r in rows:
        by_lang[r["lang"]].append(r["passed"])
    for lang, results in by_lang.items():
        lines.append(f"| {lang} | {len(results)} | {sum(results)} | {100 * sum(results) / len(results):.0f}% |")

    failures = [r for r in rows if not r["passed"]]
    lines += ["", f"## Failed checks ({len(failures)})", ""]
    if failures:
        lines += ["| Trap | Run | What failed | Answer |", "| --- | --- | --- | --- |"]
        lines += [f"| {r['id']} | {r['run']} | {cell('; '.join(r['fails']))} | {cell(r['answer'], 160)} |"
                  for r in failures]
    else:
        lines.append("None.")

    lines += ["", "## Review sheet (read each answer, mark OK or not)", "",
              "| Trap | Lang | Message | Answer (run 1) | Check by reading | OK? |",
              "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if r["run"] == 1:
            lines.append(f"| {r['id']} | {r['lang']} | {cell(r['message'])} | {cell(r['answer'], 300)} | "
                         f"{cell(r['review'])} |  |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- the run (needs the app and the database)
def log_in(http, password):
    """The eval user's token: created the first time, then just logged in."""
    created = http.post("/auth/register", json={"email": EVAL_EMAIL, "password": password, "name": EVAL_NAME,
                                                "gender": EVAL_GENDER})
    if created.status_code == 201:
        return created.json()["token"]
    r = http.post("/auth/login", json={"email": EVAL_EMAIL, "password": password})
    if r.status_code != 200:
        sys.exit(f"Cannot log in as {EVAL_EMAIL} ({r.status_code} {r.text}). If the account exists with another "
                 f"password, set EVAL_PASSWORD or delete that user.")
    return r.json()["token"]


def seed_golden(db, user_id):
    """Replace the eval user's wardrobe with the golden one (same pieces, same ids, every run)."""
    from . import ml  # noqa: F401  (puts src/ on the import path, as the tools do)
    from tests.test_golden import WARDROBE, stored          # the fixture the assistant tests use
    docs = [stored(d, user_id) for d in WARDROBE["items"]]
    db.items.delete_many({"$or": [{"user_id": user_id}, {"_id": {"$in": [d["_id"] for d in docs]}}]})
    db.items.insert_many(docs)
    return len(docs)


def shown_pieces(db, saved):
    from .db import object_id
    ids = [object_id(i) for i in (saved or {}).get("item_ids", []) if i]
    return [{"category": d.get("category"), "sub_category": d.get("sub_category"), "colour": d.get("colour")}
            for d in db.items.find({"_id": {"$in": ids}})] if ids else []


def main(argv=None):
    from .config import ROOT, Settings
    from .db import connect

    parser = argparse.ArgumentParser(description="Run the assistant's trap set against the live API.")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--traps", default=str(ROOT / "bench" / "assistant" / "traps.yaml"))
    parser.add_argument("--out", default=str(ROOT / "bench" / "results" / "assistant"))
    parser.add_argument("--repeat", type=int, default=1, help="runs per trap (use 3 for reported numbers)")
    parser.add_argument("--only", default="", help="comma-separated trap ids")
    parser.add_argument("--lang", default="en",
                        help="comma-separated languages to run: en, ar, arabizi, fr, or all (default: en; "
                             "Arabic and French are measured after English, in that order)")
    parser.add_argument("--agent", default="", help="send this agent name with every message (default: none)")
    parser.add_argument("--no-seed", action="store_true", help="keep the eval user's current wardrobe")
    args = parser.parse_args(argv)

    traps = yaml.safe_load(Path(args.traps).read_text(encoding="utf-8"))["traps"]
    if args.lang != "all":
        langs = {lang.strip() for lang in args.lang.split(",")}
        traps = [t for t in traps if t["lang"] in langs]
    if args.only:
        wanted = {t.strip() for t in args.only.split(",")}
        traps = [t for t in traps if t["id"] in wanted]
    if not traps:
        sys.exit("No trap to run.")

    db = connect(Settings())
    http = httpx.Client(base_url=args.api, timeout=CHAT_TIMEOUT_S)
    token = log_in(http, os.getenv("EVAL_PASSWORD", "trap-set-local-only-password"))
    http.headers["Authorization"] = f"Bearer {token}"
    user_id = db.users.find_one({"email": EVAL_EMAIL})["_id"]
    if not args.no_seed:
        print(f"wardrobe: {seed_golden(db, user_id)} golden pieces for {EVAL_EMAIL}")

    status = http.get("/assistant/status").json()
    if not status.get("available"):
        sys.exit(f"The assistant is not available ({status}). Is Ollama running with the model?")
    model = status["model"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    print(f"model: {model}; {len(traps)} traps x {args.repeat} run(s)")

    t0 = time.perf_counter()                                 # the first call may load the model: not scored
    warm = http.post("/chat", json={"message": "Hi", "chat_id": f"trap-{stamp}-warmup"})
    print(f"warm-up: HTTP {warm.status_code} in {time.perf_counter() - t0:.1f} s")

    rows = []
    for run in range(1, args.repeat + 1):
        for trap in traps:
            chat_id = f"trap-{stamp}-{trap['id']}-{run}"
            body = {"message": trap["message"], "chat_id": chat_id, **({"agent": args.agent} if args.agent else {})}
            t0 = time.perf_counter()
            try:
                r = http.post("/chat", json=body)
                code, answer_body = r.status_code, (r.json() if r.status_code == 200 else {})
            except httpx.HTTPError as error:
                code, answer_body = 0, {}
                print(f"  {trap['id']}: {type(error).__name__}: {error}")
            seconds = round(time.perf_counter() - t0, 1)
            saved = db.chats.find_one({"chat_id": chat_id, "user_id": user_id}) if code == 200 else None
            unknown = (saved or {}).get("unknown_refs", [])
            pieces = shown_pieces(db, saved)
            fails = score(trap, code, answer_body, unknown, pieces)
            rows.append({"id": trap["id"], "run": run, "category": trap["category"], "lang": trap["lang"],
                         "message": trap["message"], "expected_agent": trap.get("expected_agent"),
                         "agent": answer_body.get("agent"), "status": code, "seconds": seconds,
                         "answer": answer_body.get("answer") or "", "tools": tools_called(answer_body),
                         "n_tool_calls": len(tools_called(answer_body)),
                         "stop_reason": answer_body.get("stop_reason"), "unknown_refs": unknown,
                         "pieces": pieces, "thinking_stripped": any(
                             line.get("note") == "thinking_stripped" for line in answer_body.get("trace", [])),
                         "model": answer_body.get("model", model), "fails": fails, "passed": not fails,
                         "review": trap.get("review", "")})
            mark = "ok  " if not fails else "FAIL"
            print(f"  [{run}] {trap['id']} {mark} {seconds:5.1f}s {', '.join(fails)}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = f"traps-{re.sub(r'[^A-Za-z0-9.-]+', '_', model)}-{stamp}"
    with open(out / f"{name}.jsonl", "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    meta = {"model": model, "started": stamp, "repeat": args.repeat, "api": args.api, "lang": args.lang}
    (out / f"{name}.md").write_text(report(rows, meta), encoding="utf-8")
    passed = sum(r["passed"] for r in rows)
    print(f"\n{passed} of {len(rows)} answers passed the automatic checks. Report: {out / (name + '.md')}")


if __name__ == "__main__":
    main()
