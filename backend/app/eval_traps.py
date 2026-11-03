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


def router_how(body):
    """How the router chose (button / model / keywords / default), from the trace line {"router", "how"} (step 3e)."""
    for line in body.get("trace", []):
        if "router" in line:
            return line.get("how")
    return None


def handoff_of(body):
    """The {"from", "to", "note"} of a handoff in this answer's trace (step 3e.6), or None."""
    for line in body.get("trace", []):
        if "handoff" in line:
            return line["handoff"]
    return None


def routed_to(body):
    """The agent the ROUTER chose (the answering agent can be the second one after a handoff)."""
    for line in body.get("trace", []):
        if "router" in line:
            return line["router"]
    return body.get("agent")


def router_section(rows):
    """Which agent the router chose, and how often it was right. Accuracy counts ONLY the traps whose expected agent
    already exists in agents.yaml (the agents built so far); the rest are listed apart, because no router could be
    right about an agent that is not there."""
    from .config import ROOT                                 # the real file: the agents that exist now
    existing = set(yaml.safe_load((ROOT / "mappings" / "agents.yaml").read_text(encoding="utf-8"))["agents"])
    ok = [r for r in rows if r["status"] == 200]
    if not ok or not any(r.get("router_how") for r in ok):
        return []
    lines = ["", "## Router", "", "| Chosen agent | Answers |", "| --- | --- |"]
    lines += [f"| {agent} | {n} |" for agent, n in Counter(r["agent"] for r in ok).most_common()]
    lines += ["", "| How it chose | Answers |", "| --- | --- |"]
    lines += [f"| {how} | {n} |" for how, n in Counter(r.get("router_how") for r in ok).most_common()]
    known = [r for r in ok if r.get("expected_agent") in existing]
    # a trap may list other agents that do no harm for an overlapping question (acceptable_agents)
    # the router's own pick (after a handoff the answering agent is the second one)
    right = sum((r.get("routed") or r["agent"]) == r["expected_agent"]
                or (r.get("routed") or r["agent"]) in r.get("acceptable_agents", []) for r in known)
    lines += ["", f"Accuracy on traps whose expected agent exists ({', '.join(sorted(existing))}): "
                  f"{right} of {len(known)} ({100 * right / max(1, len(known)):.0f}%).", "",
              "Traps whose expected agent does not exist yet (not scored):", "",
              "| Expected | Answers | Chosen |", "| --- | --- | --- |"]
    missing = defaultdict(list)
    for r in ok:
        if r.get("expected_agent") not in existing:
            missing[r.get("expected_agent")].append(r["agent"])
    lines += [f"| {exp} | {len(c)} | {', '.join(f'{a} {n}' for a, n in Counter(c).most_common())} |"
              for exp, c in sorted(missing.items(), key=lambda kv: str(kv[0]))]
    return lines


def split_refs(unknown_refs, message):
    """(echoed, invented): an unknown {n} whose number the user typed is an echo of the user's message, a
    formatting slip; any other unknown {n} was made up by the model."""
    typed = {int(n) for n in re.findall(r"\d+", message or "")}
    echoed = [r for r in unknown_refs if r in typed]
    return echoed, [r for r in unknown_refs if r not in typed]


def score(trap, status, body, unknown_refs, pieces):
    """The list of failed checks (empty = passed).

    status        HTTP status of POST /chat
    body          its JSON (or {} when it failed)
    unknown_refs  the {n} the turn removed because no tool showed them (from the saved chats document)
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
    echoed, invented = split_refs(unknown_refs, trap.get("message"))
    if invented:                                                # always checked: no made-up piece numbers
        fails.append(f"invented piece numbers {invented}")
    if echoed:                                                  # the user's own number written as {n}: removed,
        fails.append(f"wrote the user's number(s) {echoed} as pieces")   # which leaves a broken sentence

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
    if "handoff" in checks and (handoff_of(body) is not None) != checks["handoff"]:
        fails.append("expected a handoff" if checks["handoff"] else "handed over, expected no handoff")
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
             f"| Answers with made-up piece numbers | "
             f"{sum(1 for r in rows if split_refs(r['unknown_refs'], r['message'])[1])} |",
             f"| Answers writing the user's own numbers as pieces | "
             f"{sum(1 for r in rows if split_refs(r['unknown_refs'], r['message'])[0])} |",
             f"| Answers where code repaired the user's number (shown as plain text) | "
             f"{sum(1 for r in rows if r.get('echoed_refs'))} |",
             f"| Answers showing a piece the trap forbids (wrong or not owned) | "
             f"{sum(1 for r in rows if any(f.startswith('showed a piece matching') for f in r['fails']))} |",
             f"| Errors (not HTTP 200) | {len(rows) - len(ok)} |",
             f"| Seconds per answer: median / 90th percentile / max | "
             f"{statistics.median(seconds) if seconds else 0:.1f} / {percentile(seconds, 0.9):.1f} / "
             f"{max(seconds) if seconds else 0:.1f} |",
             f"| Tool calls per answer (mean) | {statistics.mean(r['n_tool_calls'] for r in ok) if ok else 0:.1f} |",
             f"| Answers that used handoff | {sum(1 for r in rows if r.get('handoff'))} |",
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

    lines += router_section(rows)
    used = Counter(r["id"] for r in rows if r.get("handoff"))
    lines += ["", "## Handoff (answers that used it, per trap)", ""]
    lines += ["| Trap | Answers with handoff | Of | To |", "| --- | --- | --- | --- |"] + [
        f"| {trap} | {n} | {len(by_trap[trap])} | "
        f"{', '.join(f'{a} {c}' for a, c in Counter(r['handoff']['to'] for r in rows if r['id'] == trap and r.get('handoff')).most_common())} |"
        for trap, n in used.items()] if used else ["None."]

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
    from . import ml  # noqa: F401                          (puts src/ on the import path, as the tools do)
    from tests.test_golden import WARDROBE, stored          # the fixture the assistant tests use
    docs = [stored(d, user_id) for d in WARDROBE["items"]]
    db.items.delete_many({"$or": [{"user_id": user_id}, {"_id": {"$in": [d["_id"] for d in docs]}}]})
    db.items.insert_many(docs)
    return len(docs)


FAKE_CONTACT = "FAKE-CONTACT-0000"      # a contact the answers must never show (traps e.g. "forbid_patterns")
FAKE_LISTINGS = [
    # (id suffix, title, brand, category, sub_category, colour, price TND, gender, golden piece the picture vector copies)
    (1, "Black leather handbag", "zara", "bag", "handbag", "black", 45, "women", 16),
    (2, "Black mini backpack", "bershka", "bag", "handbag", "black", 69, "women", 16),
    (3, "Brown leather loafers", "pullandbear", "shoes", "casual-shoes", "brown", 55, "women", 14),
    (4, "Denim jacket", "", "outerwear", "jacket", "black", 45, "women", 11),          # a friperie seller's listing
    (5, "White sneakers", "bershka", "shoes", "sneakers", "white", 70, "unisex", 14),
]


def seed_listings(db):
    """Five fixed fake listings, ONLY when the listings collection is empty (the evaluation, never the app), so the
    shopping traps have something to find. Each has `eval_fake: True`; `main` deletes them when the run ends.
    Fixed ids: the same listings every run. Returns how many were added."""
    from datetime import datetime, timezone
    from bson import ObjectId
    from tests.test_golden import WARDROBE, stored
    if db.listings.count_documents({}):
        return 0
    golden = {i: stored(d, None) for i, d in enumerate(WARDROBE["items"], 1)}
    now = datetime.now(timezone.utc)
    docs = []
    for n, title, brand, category, sub, colour, price, gender, donor in FAKE_LISTINGS:
        seller = brand == ""
        docs.append({
            "_id": ObjectId(f"5f0c02{n:018x}"), "source_id": "sellers" if seller else "eval_fake", "external_id": f"fake-{n}",
            "title": title, "brand": brand, "shop_colour": colour, "gender": gender, "url": "", "price_tnd": price,
            "sizes": [], "sizes_in_stock": [], "in_stock": True, "availability_level": "colour", "image_url": "",
            "category": category, "sub_category": sub, "pattern": "solid", "colour": colour, "predicted": {},
            "corrected": [], "vector": golden[donor]["vector"], "status": "active", "review_note": "",
            "created_at": now, "seen_at": now, "checked_at": None, "snapshot": False,
            "eval_fake": True,                                # real listings never have this field: it marks what to delete
            **({"seller_id": ObjectId("5f0c0300000000000000ffff"), "city": "Sfax", "contact": FAKE_CONTACT}
               if seller else {})})
    db.listings.insert_many(docs)
    return len(docs)


def shown_pieces(db, saved):
    from .db import object_id
    ids = [object_id(i) for i in (saved or {}).get("item_ids", []) if i]
    return [{"category": d.get("category"), "sub_category": d.get("sub_category"), "colour": d.get("colour")}
            for d in db.items.find({"_id": {"$in": ids}})] if ids else []


def rescore(path, traps_path):
    """Check SAVED answers again with the current traps.yaml, without asking the model: a fixed checker must not
    change the answers, or the numbers are no longer comparable. Writes <name>-rescored.md and .jsonl."""
    traps = {t["id"]: t for t in yaml.safe_load(Path(traps_path).read_text(encoding="utf-8"))["traps"]}
    path = Path(path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        trap = {**traps.get(row["id"], {}), "message": row["message"]}
        body = {"answer": row["answer"], "trace": [{"tool": t} for t in row["tools"]]
                + ([{"handoff": row["handoff"]}] if row.get("handoff") else [])}
        row["fails"] = score(trap, row["status"], body, row["unknown_refs"], row["pieces"])
        row["passed"] = not row["fails"]
        row["review"] = trap.get("review", row.get("review", ""))
    m = re.match(r"traps-(.+)-(\d{8}T\d{6})$", path.stem)
    meta = {"model": m.group(1) if m else "?", "started": (m.group(2) if m else "?") + " (rescored)",
            "repeat": max(r["run"] for r in rows), "api": "saved answers", "lang": "as saved"}
    out = path.with_name(path.stem + "-rescored")
    with open(out.with_suffix(".jsonl"), "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    out.with_suffix(".md").write_text(report(rows, meta), encoding="utf-8")
    print(f"{sum(r['passed'] for r in rows)} of {len(rows)} saved answers pass the current checks. "
          f"Report: {out.with_suffix('.md')}")


def main(argv=None):
    from .config import ROOT, Settings
    from .db import connect

    parser = argparse.ArgumentParser(description="Run the assistant's trap set against the live API.")
    parser.add_argument("--rescore", default="", help="a saved .jsonl: check its answers again, no model call")
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
    if args.rescore:
        return rescore(args.rescore, args.traps)

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
    fake_listings = not args.no_seed and db.listings.count_documents({}) == 0     # only if there are no listings at all
    try:
        if not args.no_seed:
            print(f"wardrobe: {seed_golden(db, user_id)} golden pieces for {EVAL_EMAIL}")
        if fake_listings:
            print(f"listings: {seed_listings(db)} fake listings added for this run (the collection was empty)")
        measure(args, traps, http, db, user_id)
    finally:                                                 # the fake listings never stay in the database
        if fake_listings:
            print(f"listings: {db.listings.delete_many({'eval_fake': True}).deleted_count} fake listings deleted")


def measure(args, traps, http, db, user_id):
    """Ask every trap `--repeat` times and write the report."""
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
            repaired = (saved or {}).get("echoed_refs", [])      # the user's number the code showed as plain text
            pieces = shown_pieces(db, saved)
            fails = score(trap, code, answer_body, unknown, pieces)
            rows.append({"id": trap["id"], "run": run, "category": trap["category"], "lang": trap["lang"],
                         "message": trap["message"], "expected_agent": trap.get("expected_agent"),
                         "acceptable_agents": trap.get("acceptable_agents", []),
                         "agent": answer_body.get("agent"), "routed": routed_to(answer_body) if code == 200 else None,
                         "handoff": handoff_of(answer_body), "router_how": router_how(answer_body),
                         "status": code, "seconds": seconds,
                         "answer": answer_body.get("answer") or "", "tools": tools_called(answer_body),
                         "n_tool_calls": len(tools_called(answer_body)),
                         "stop_reason": answer_body.get("stop_reason"), "unknown_refs": unknown,
                         "echoed_refs": repaired, "pieces": pieces, "thinking_stripped": any(
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