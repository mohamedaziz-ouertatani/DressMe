"""
Golden output tests: the safety net of the upgrade (docs/superpowers/plans/2026-10-23-step-0-safety-net.md).

They seed a FROZEN wardrobe (tests/golden/wardrobe.json: 17 items, 3 scans, 1 shop listing, with
real FashionCLIP vectors) straight into the dressme_test database, call the real routes with the
usual fakes (no real model), and compare each answer with the one recorded in
tests/golden/expected/*.json. If a later change alters what the app answers today, one of these
tests fails and prints exactly what changed.

    docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_golden.py

GOLDEN_RECORD=1 REWRITES the expected files from the current answers instead of comparing:

    docker exec -e GOLDEN_RECORD=1 dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_golden.py

Only do that in a pull request that explains why EACH difference is intended
(tests/golden/README.md). The answers also depend on the team's rule files in mappings/*.csv
(weights, harmony, pairing...): changing one of them changes the goldens on purpose.

What is compared (see `differences`):
  exactly   verdict, good_outfits, item ids and their order, reasons, explanation codes, every
            string / integer / list length
  +-0.5     scores and points (0-100 scale)
  +-0.005   part values, similarities and other 0-1 values (the same 0.5 points)
  +-0.01    model confidences
Anything else that is a number must match exactly.

The two tests named test_known_issue_* document behaviour that is KNOWN and EXPECTED to change in
a later step. When that step changes it, those tests are updated in the same pull request.
"""

import base64
import json
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from bson import Binary, ObjectId
from pymongo import MongoClient

import compatibility
from tests.conftest import BLACK, RED, TEST_DB, photo, sign_up

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
EXPECTED_DIR = GOLDEN_DIR / "expected"
WARDROBE = json.loads((GOLDEN_DIR / "wardrobe.json").read_text(encoding="utf-8"))
RECORD = os.getenv("GOLDEN_RECORD") == "1"

TOL_SCORE = 0.5      # scores and points
TOL_UNIT = 0.005     # values from 0 to 1 (parts, similarity): the same 0.5 points
TOL_CONF = 0.01      # model confidences
SCORE_KEYS = {"score", "owned_score", "margin", "points", "max_points", "gain"}
UNIT_KEYS = {"similarity", "value"}
MAX_SHOWN = 40       # differences printed per answer


# ---------------------------------------------------------------- comparing
def tolerance(keys):
    """How far a number may move, from the names on its path (parts.style, contributions[0].points...)."""
    last = next((k for k in reversed(keys) if isinstance(k, str)), "")
    if "parts" in keys:
        return TOL_UNIT
    if last in SCORE_KEYS:
        return TOL_SCORE
    if last in UNIT_KEYS:
        return TOL_UNIT
    if last == "conf":
        return TOL_CONF
    return 1e-9


def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def where(keys):
    out = ""
    for k in keys:
        out += f"[{k}]" if isinstance(k, int) else f".{k}"
    return out.lstrip(".") or "(answer)"


def differences(expected, actual, keys=()):
    """Readable list of what differs between a recorded answer and the current one."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        out = []
        for k in expected:
            if k not in actual:
                out.append(f"{where(keys + (k,))}: missing now (was {short(expected[k])})")
            else:
                out += differences(expected[k], actual[k], keys + (k,))
        out += [f"{where(keys + (k,))}: new field {short(actual[k])}" for k in actual if k not in expected]
        return out
    if isinstance(expected, list) and isinstance(actual, list):
        out = []
        if len(expected) != len(actual):
            out.append(f"{where(keys)}: {len(expected)} entries before, {len(actual)} now")
        for i, (e, a) in enumerate(zip(expected, actual)):
            out += differences(e, a, keys + (i,))
        return out
    if is_number(expected) and is_number(actual):
        tol = tolerance(keys)
        if abs(expected - actual) > tol + 1e-12:
            return [f"{where(keys)}: {expected} -> {actual} (moved {abs(expected - actual):.4g}, allowed {tol:g})"]
        return []
    if expected != actual:
        return [f"{where(keys)}: {short(expected)} -> {short(actual)}"]
    return []


def short(value):
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 80 else text[:77] + "..."


def scrub(obj, replacements):
    """Replace ids that change on every run (a candidate made from a listing) by fixed names."""
    text = json.dumps(obj)
    for real, name in replacements.items():
        text = text.replace(real, name)
    return json.loads(text)


def check(name, actual):
    """Compare `actual` with tests/golden/expected/<name>.json (GOLDEN_RECORD=1: write it)."""
    path = EXPECTED_DIR / f"{name}.json"
    actual = json.loads(json.dumps(actual))               # plain JSON types, like the file
    if RECORD:
        EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(actual, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    assert path.exists(), f"{path.name} is missing: record it with GOLDEN_RECORD=1 (see this file's top)"
    expected = json.loads(path.read_text(encoding="utf-8"))
    diffs = differences(expected, actual)
    if diffs:
        shown = diffs[:MAX_SHOWN] + ([f"... and {len(diffs) - MAX_SHOWN} more"] if len(diffs) > MAX_SHOWN else [])
        # pytrace=False: only the list of differences, not a page of traceback around it
        pytest.fail(f"\n{len(diffs)} difference(s) from tests/golden/expected/{path.name} (before -> now):\n  "
                    + "\n  ".join(shown) +
                    "\nIf this change is intended, re-record with GOLDEN_RECORD=1 in a pull request "
                    "that explains each difference.", pytrace=False)


# ---------------------------------------------------------------- the seeded app
def when(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def stored(doc, user_id):
    """A document of the golden wardrobe as the API stores it."""
    return {"_id": ObjectId(doc["id"]), "user_id": user_id, "category": doc["category"],
            "sub_category": doc["sub_category"], "pattern": doc["pattern"], "colour": doc["colour"],
            "coverage": doc["coverage"], "season": doc["season"], "usage": doc["usage"],
            "predicted": doc["predicted"], "corrected": doc["corrected"],
            "vector": Binary(base64.b64decode(doc["vector_b64"])), "created_at": when(doc["created_at"])}


@pytest.fixture(autouse=True)
def real_rules():
    """The answers depend on the team's real rule files: reload them, so a test that edited the
    formula before this one (and failed before restoring it) cannot leak into the goldens."""
    compatibility.reload_rules()
    yield


@pytest.fixture
def golden(make_client, settings):
    """A client logged in as the golden user, with the frozen wardrobe, scans and listing seeded."""
    client = make_client()
    user = WARDROBE["user"]
    headers = sign_up(client, user["email"], user["name"], user["gender"])
    assert client.put("/me", json={"min_coverage": user["min_coverage"]}, headers=headers).status_code == 200
    db = MongoClient(settings.mongo_url)[TEST_DB]
    user_id = db.users.find_one({"email": user["email"]})["_id"]
    db.items.insert_many([stored(d, user_id) for d in WARDROBE["items"]])         # in wardrobe order
    db.candidates.insert_many([stored(d, user_id) for d in WARDROBE["candidates"]])
    listing = WARDROBE["listing"]
    db.listings.insert_one({
        **{k: v for k, v in stored(listing, user_id).items() if k not in ("user_id", "coverage", "season", "usage")},
        "source_id": listing["shop_id"], "external_id": listing["dataset_id"], "title": listing["title"],
        "brand": listing["brand"], "shop_colour": listing["shop_colour"], "gender": listing["gender"],
        "url": "", "price_tnd": listing["price_tnd"], "sizes": listing["sizes"], "sizes_in_stock": listing["sizes"],
        "in_stock": True, "availability_level": "colour", "image_url": "", "checked_at": None, "snapshot": False,
        "price_original": None, "seen_at": when(listing["created_at"]), "status": "active"})
    ids = {d["key"]: d["id"] for d in WARDROBE["items"] + WARDROBE["candidates"]}
    return SimpleNamespace(client=client, headers=headers, ids=ids, listing_id=listing["id"], db=db)


def ids_of(golden, keys):
    return [golden.ids[k] for k in keys]


# ---------------------------------------------------------------- "should I buy this?"
@pytest.mark.parametrize("name", ["near_twin", "think", "buy"])
def test_buy_advice(golden, name):
    r = golden.client.post("/buy-advice", json={"candidate_id": golden.ids[name]}, headers=golden.headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # the verdict each frozen scan was chosen for (also checked when recording)
    assert body["verdict"] == WARDROBE["checked"]["candidates"][name]["verdict"]
    check(f"buy_advice_{name}", body)


def test_buy_advice_from_a_shop_listing(golden):
    """The Shops page: POST /listings/{id}/candidate, then the same /buy-advice."""
    r = golden.client.post(f"/listings/{golden.listing_id}/candidate", headers=golden.headers)
    assert r.status_code == 201, r.text
    candidate = r.json()
    r2 = golden.client.post("/buy-advice", json={"candidate_id": candidate["id"]}, headers=golden.headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["verdict"] == WARDROBE["checked"]["candidates"]["listing"]["verdict"]
    # the candidate gets a new id every run: replace it by a fixed name
    check("buy_advice_listing", {"candidate": scrub(candidate, {candidate["id"]: "<candidate>"}),
                                 "advice": scrub(r2.json(), {candidate["id"]: "<candidate>"})})


# ---------------------------------------------------------------- outfits
def test_outfits_suggest(golden):
    answers = {}
    for name, p in WARDROBE["scenarios"]["suggest"].items():
        params = {k: v for k, v in p.items()}
        r = golden.client.get("/outfits/suggest", params=params, headers=golden.headers)
        assert r.status_code == 200, r.text
        answers[name] = r.json()
    check("outfits_suggest", answers)


def test_outfits_score(golden):
    answers = {}
    for name, keys in WARDROBE["scenarios"]["score"].items():
        r = golden.client.post("/outfits/score", json={"item_ids": ids_of(golden, keys)}, headers=golden.headers)
        answers[name] = {"status": r.status_code, "body": r.json()}
    assert answers["clash_two_tops"]["status"] == 422          # the same category twice is refused
    check("outfits_score", answers)


def test_outfits_complete(golden):
    answers = {}
    for name, p in WARDROBE["scenarios"]["complete"].items():
        r = golden.client.post("/outfits/complete", json={"item_ids": ids_of(golden, p["item_ids"]), "k": p["k"]},
                               headers=golden.headers)
        assert r.status_code == 200, r.text
        answers[name] = r.json()
    check("outfits_complete", answers)


def test_insights(golden):
    r = golden.client.get("/insights", headers=golden.headers)
    assert r.status_code == 200, r.text
    check("insights", r.json())


# ---------------------------------------------------------------- KNOWN ISSUES (expected to change)
def test_known_issue_bought_it_reanalyses_the_photo(client):
    """KNOWN, EXPECTED TO CHANGE (step 1 of the upgrade replaced it: see below).

    "Bought it" on the Scan page (frontend ScanPage.addToWardrobe) did NOT turn the scan into a
    wardrobe item: it uploaded the original photo again with POST /items, which cleans and
    analyses it a second time. So the item got a new id, the scan stayed until it expired after
    24 h, and the log counted an extra `upload`.

    FIXED IN STEP 1: the Scan and Shop pages now call POST /decisions, which saves the scan with
    `promote` and no second analysis (tests/test_promote_decisions.py). This test is unchanged on
    purpose: it still documents what uploading the same photo again through POST /items does."""
    headers = sign_up(client)
    scan = client.post("/analyze", files={"photo": photo(RED)}, headers=headers)
    assert scan.status_code == 201
    scan_id = scan.json()["id"]

    analyzer = client.app.state.analyzer
    calls = []
    analyze = analyzer.analyze
    analyzer.analyze = lambda img: (calls.append(1), analyze(img))[1]      # count the model calls

    bought = client.post("/items", files={"photo": photo(RED)}, headers=headers)     # what "Bought it" sends
    assert bought.status_code == 201
    assert len(calls) == 1, "the photo is analysed again"
    assert bought.json()["id"] != scan_id, "a new item, not the scan promoted"
    assert client.get(f"/candidates/{scan_id}/image", headers=headers).status_code == 200, "the scan is still there"
    events = client.app.state.db.events
    assert events.count_documents({"type": "scan"}) == 1 and events.count_documents({"type": "upload"}) == 1


def test_known_issue_incomplete_outfit_scores_high(client):
    """KNOWN, EXPECTED TO CHANGE.

    POST /outfits/score gives a top + shoes outfit (no bottom) a score ABOVE the good-outfit line:
    a part that cannot be computed is left out and the other weights are rescaled, so the missing
    bottom only costs the structure part. suggest and buy-advice never build such outfits."""
    headers = sign_up(client)
    top = client.post("/items", files={"photo": photo(RED)}, headers=headers).json()
    shoes = client.post("/items", files={"photo": photo(BLACK)}, headers=headers).json()
    r = client.post("/outfits/score", json={"item_ids": [top["id"], shoes["id"]]}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score"] == pytest.approx(86.0, abs=0.5)
    assert "missing a top or a bottom" in body["reasons"]
    assert body["score"] >= compatibility.rules_for("women").settings["good_outfit"], \
        "an outfit with no bottom is rated as a good one"
