"""
Step 1: saving a scan into the wardrobe (`promote`, app/wardrobe_store.py) and the decision log
(`POST /decisions`, `GET /decisions`, app/routers/decisions.py).

Promote has two ways in: an upload (POST /items, unchanged) and a scan ("Bought it": the cleaned
photo, the labels, the guesses and the vector are reused, no second analysis).
"""

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.wardrobe_store import promote
from tests.conftest import BLACK, BLUE, RED, photo, sign_up, upload


def scan(client, headers, rgb=RED):
    r = client.post("/analyze", files={"photo": photo(rgb)}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def shown(client, headers, rgb=RED, **more):
    """A scan whose verdict was shown (what the Scan page does before Bought it / Left it)."""
    cand = scan(client, headers, rgb)
    assert client.post("/buy-advice", json={"candidate_id": cand["id"], **more}, headers=headers).status_code == 200
    return cand


def decide(client, headers, candidate_id, answer, **more):
    return client.post("/decisions", json={"candidate_id": candidate_id, "answer": answer, **more}, headers=headers)


def count_analyses(client):
    calls = []
    analyze = client.app.state.analyzer.analyze
    client.app.state.analyzer.analyze = lambda img: (calls.append(1), analyze(img))[1]
    return calls


def candidate_doc(client, candidate_id):
    return client.app.state.db.candidates.find_one({"_id": ObjectId(candidate_id)})


# ================================================================ promote: from an upload
def test_an_upload_is_promoted_as_before_with_two_new_empty_fields(client):
    headers = sign_up(client)
    r = client.post("/items", files={"photo": photo(RED)}, headers=headers)
    assert r.status_code == 201
    item = r.json()
    assert set(item) == {"id", "category", "sub_category", "pattern", "colour", "coverage", "season", "usage",
                         "predicted", "corrected", "image_url"}              # the answer did not change
    db = client.app.state.db
    doc = db.items.find_one({"_id": ObjectId(item["id"])})
    assert doc["promoted_from"] is None                                      # an upload has no source scan
    assert doc["analysed_by"]["models"] is None and doc["analysed_by"]["at"] is not None     # a fake knows no models
    storage = client.app.state.settings.storage_dir
    assert (storage / str(doc["user_id"]) / f"{item['id']}.jpg").exists()
    assert db.events.count_documents({"type": "upload"}) == 1


def test_the_models_of_a_real_analyzer_are_kept_on_the_item(client):
    headers = sign_up(client)
    client.app.state.analyzer.versions = {"classifier": "classifier_best.pt 2026-10-10", "embedding": "fashion-clip"}
    item = upload(client, headers, RED)
    doc = client.app.state.db.items.find_one({"_id": ObjectId(item["id"])})
    assert doc["analysed_by"]["models"] == {"classifier": "classifier_best.pt 2026-10-10", "embedding": "fashion-clip"}


def test_many_uploads_do_not_clash_on_the_unique_index(client):
    headers = sign_up(client)
    for rgb in (RED, BLUE, BLACK, RED):
        upload(client, headers, rgb)
    assert len(client.get("/items", headers=headers).json()) == 4


def test_the_index_only_covers_items_that_came_from_a_scan(client):
    info = client.app.state.db.items.index_information()["promoted_from.id_1"]
    assert info["unique"] and info["partialFilterExpression"] == {"promoted_from.id": {"$exists": True}}


def test_items_from_before_the_step_keep_working(client):
    headers = sign_up(client)
    item = upload(client, headers, RED)
    db = client.app.state.db
    db.items.update_one({"_id": ObjectId(item["id"])}, {"$unset": {"promoted_from": "", "analysed_by": ""}})
    assert client.get(f"/items/{item['id']}", headers=headers).status_code == 200
    assert client.patch(f"/items/{item['id']}", json={"colour": "pink"}, headers=headers).status_code == 200


# ================================================================ promote: from a scan
def test_bought_it_reuses_the_scan_and_never_analyses_again(client):
    headers = sign_up(client)
    client.app.state.analyzer.versions = {"classifier": "classifier_best.pt"}
    cand = shown(client, headers, RED, corrections={"colour": "pink"})        # the user corrected the colour
    calls = count_analyses(client)
    r = decide(client, headers, cand["id"], "bought")
    assert r.status_code == 201, r.text
    assert calls == [], "no second analysis"

    db = client.app.state.db
    item = db.items.find_one({"_id": ObjectId(r.json()["item_id"])})
    scan_doc = candidate_doc(client, cand["id"])
    assert item["promoted_from"] == {"kind": "candidate", "id": cand["id"]}
    assert item["colour"] == "pink" and "colour" in item["corrected"]          # the user's correction came along
    for field in ("category", "sub_category", "pattern", "predicted", "corrected", "coverage", "season", "usage"):
        assert item[field] == scan_doc[field], field
    assert bytes(item["vector"]) == bytes(scan_doc["vector"])
    assert item["analysed_by"] == scan_doc["analysed_by"] and item["analysed_by"]["models"] == {"classifier": "classifier_best.pt"}
    # the cleaned photo of the scan is now the item's photo file
    path = client.app.state.settings.storage_dir / str(item["user_id"]) / f"{item['_id']}.jpg"
    assert path.read_bytes() == bytes(scan_doc["photo"])
    assert client.get(f"/items/{item['_id']}/image", headers=headers).status_code == 200
    # one `upload` event, marked as coming from a scan
    event = db.events.find_one({"type": "upload", "source": "candidate"})
    assert event["category"] == item["category"]


def test_promoting_the_same_scan_twice_gives_the_same_item(client):
    headers = sign_up(client)
    cand = shown(client, headers)
    db = client.app.state.db
    user = db.users.find_one({})
    doc = candidate_doc(client, cand["id"])
    storage = client.app.state.settings.storage_dir
    first, created = promote(db, storage, user["_id"], candidate=doc, photo=bytes(doc["photo"]))
    second, created_again = promote(db, storage, user["_id"], candidate=doc, photo=bytes(doc["photo"]))
    assert created and not created_again and first["_id"] == second["_id"]
    assert db.items.count_documents({}) == 1
    assert len(list((storage / str(user["_id"])).glob("*.jpg"))) == 1          # and one photo file


def test_two_requests_at_once_still_make_one_item(client):
    """The check-then-insert can be beaten by a second request: the unique index says no, and the
    loser gets the item the winner made, with no stray photo file."""
    headers = sign_up(client)
    cand = shown(client, headers)
    db = client.app.state.db
    user = db.users.find_one({})
    doc = candidate_doc(client, cand["id"])
    storage = client.app.state.settings.storage_dir
    winner, _ = promote(db, storage, user["_id"], candidate=doc, photo=bytes(doc["photo"]))

    class BlindOnce:                                  # the loser's first look finds nothing (the winner is not in yet)
        def __init__(self, items):
            self.items, self.looked = items, False

        def find_one(self, query, *a, **k):
            if not self.looked and "promoted_from.id" in query:
                self.looked = True
                return None
            return self.items.find_one(query, *a, **k)

        def __getattr__(self, name):
            return getattr(self.items, name)

    class Db:
        def __init__(self, real):
            self.real, self.items = real, BlindOnce(real.items)

        def __getattr__(self, name):
            return getattr(self.real, name)

    loser, created = promote(Db(db), storage, user["_id"], candidate=doc, photo=bytes(doc["photo"]))
    assert not created and loser["_id"] == winner["_id"]
    assert db.items.count_documents({}) == 1
    assert len(list((storage / str(user["_id"])).glob("*.jpg"))) == 1


def test_the_unique_index_refuses_a_second_item_for_one_scan(client):
    headers = sign_up(client)
    cand = shown(client, headers)
    db = client.app.state.db
    user = db.users.find_one({})
    doc = candidate_doc(client, cand["id"])
    promote(db, client.app.state.settings.storage_dir, user["_id"], candidate=doc, photo=b"x")
    with pytest.raises(DuplicateKeyError):
        db.items.insert_one({"user_id": user["_id"], "category": "top", "promoted_from": {"kind": "candidate", "id": cand["id"]}})


def test_promote_needs_exactly_one_source(client):
    with pytest.raises(ValueError):
        promote(client.app.state.db, client.app.state.settings.storage_dir, ObjectId())


def test_a_listing_scan_is_bought_with_the_picture_the_listing_gave_it(client):
    db = client.app.state.db
    seller = sign_up(client)
    buyer = sign_up(client, "buyer@example.com", "Buyer")
    sold = client.post("/listings/sell", files={"photo": photo(RED)},
                       data={"price_tnd": "25", "size": "M", "city": "Tunis", "contact": "@s"}, headers=seller).json()
    db.listings.update_one({"_id": ObjectId(sold["id"])}, {"$set": {"status": "active"}})
    cand = client.post(f"/listings/{sold['id']}/candidate", headers=buyer).json()
    assert client.post("/buy-advice", json={"candidate_id": cand["id"]}, headers=buyer).status_code == 200
    r = decide(client, buyer, cand["id"], "bought")
    assert r.status_code == 201, r.text
    assert r.json()["listing_id"] == sold["id"] and r.json()["price_tnd"] == 25
    item = db.items.find_one({"_id": ObjectId(r.json()["item_id"])})
    assert (client.app.state.settings.storage_dir / str(item["user_id"]) / f"{item['_id']}.jpg").exists()
    assert item["analysed_by"] is None                      # a listing's analysis time is unknown: never guessed


# ================================================================ decisions
def test_bought_it_logs_the_decision_and_makes_the_item(client):
    headers = sign_up(client)
    cand = shown(client, headers, RED, price_tnd=30)
    r = decide(client, headers, cand["id"], "bought", price_paid=25)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["answer"] == "bought" and body["candidate_id"] == cand["id"] and body["listing_id"] is None
    assert body["price_tnd"] == 30 and body["price_paid"] == 25 and body["item_id"]
    assert (body["category"], body["colour"]) == (cand["category"], cand["colour"])
    advice = candidate_doc(client, cand["id"])["last_advice"]
    assert body["last_advice"]["verdict"] == advice["verdict"] and body["last_advice"]["codes"] == advice["codes"]
    assert [i["id"] for i in client.get("/items", headers=headers).json()] == [body["item_id"]]
    event = client.app.state.db.events.find_one({"type": "decision"})
    assert event["answer"] == "bought" and event["verdict"] == advice["verdict"]


def test_never_the_photo_in_a_decision(client):
    headers = sign_up(client)
    cand = shown(client, headers)
    decide(client, headers, cand["id"], "bought")
    doc = client.app.state.db.decisions.find_one({})
    assert "photo" not in doc and "vector" not in doc
    assert "photo" not in decide(client, headers, cand["id"], "bought").json()


def test_left_it_makes_no_item(client):
    headers = sign_up(client)
    cand = shown(client, headers)
    r = decide(client, headers, cand["id"], "left")
    assert r.status_code == 201 and r.json()["answer"] == "left" and r.json()["item_id"] is None
    assert client.get("/items", headers=headers).json() == []


@pytest.mark.parametrize("answer", ["bought", "left"])
def test_the_same_answer_twice_returns_the_first_decision(client, answer):
    headers = sign_up(client)
    cand = shown(client, headers)
    first = decide(client, headers, cand["id"], answer)
    again = decide(client, headers, cand["id"], answer)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json() == first.json()
    db = client.app.state.db
    assert db.decisions.count_documents({}) == 1 and db.events.count_documents({"type": "decision"}) == 1
    assert db.items.count_documents({}) == (1 if answer == "bought" else 0)


@pytest.mark.parametrize("first, second", [("bought", "left"), ("left", "bought")])
def test_a_different_answer_is_refused(client, first, second):
    headers = sign_up(client)
    cand = shown(client, headers)
    decide(client, headers, cand["id"], first)
    r = decide(client, headers, cand["id"], second)
    assert r.status_code == 409 and first in r.json()["detail"]
    assert client.app.state.db.items.count_documents({}) == (1 if first == "bought" else 0)


def test_no_verdict_shown_yet_is_a_409(client):
    headers = sign_up(client)
    cand = scan(client, headers)
    assert decide(client, headers, cand["id"], "bought").status_code == 409
    assert client.app.state.db.decisions.count_documents({}) == 0 and client.app.state.db.items.count_documents({}) == 0


def test_someone_elses_or_an_unknown_or_an_expired_scan_is_a_404(client):
    amira = sign_up(client)
    other = sign_up(client, "other@example.com", "Other")
    cand = shown(client, amira)
    assert decide(client, other, cand["id"], "bought").status_code == 404
    assert decide(client, amira, "0" * 24, "bought").status_code == 404
    assert decide(client, amira, "not-an-id", "bought").status_code == 404
    client.app.state.db.candidates.delete_one({"_id": ObjectId(cand["id"])})        # the 24 h expiry
    assert decide(client, amira, cand["id"], "bought").status_code == 404


def test_bad_requests_are_422_and_anonymous_is_refused(client):
    headers = sign_up(client)
    cand = shown(client, headers)
    assert decide(client, headers, cand["id"], "maybe").status_code == 422
    assert decide(client, headers, cand["id"], "bought", price_paid=0).status_code == 422
    assert client.post("/decisions", json={"candidate_id": cand["id"], "answer": "left"}).status_code in (401, 403)
    assert client.get("/decisions").status_code in (401, 403)


def test_the_list_is_newest_first_and_private(client):
    amira = sign_up(client)
    other = sign_up(client, "other@example.com", "Other")
    first, second = shown(client, amira, RED), shown(client, amira, BLUE)
    decide(client, amira, first["id"], "left")
    decide(client, amira, second["id"], "bought")
    mine = client.get("/decisions", headers=amira).json()
    assert [d["candidate_id"] for d in mine] == [second["id"], first["id"]]
    assert client.get("/decisions", headers=other).json() == []


def test_the_decision_event_is_counted_by_the_admin_stats(client):
    boss = sign_up(client, "boss@example.com", "Boss")
    client.app.state.db.users.update_one({"email": "boss@example.com"}, {"$set": {"role": "admin"}})
    headers = sign_up(client)
    decide(client, headers, shown(client, headers)["id"], "left")
    stats = client.get("/admin/stats", headers=boss).json()
    assert stats["totals"]["decision"] == 1 and stats["per_day"][0]["decision"] == 1
    assert {"upload", "scan", "verdict", "correction", "chat", "tryon"} <= set(stats["totals"])    # nothing removed


def test_deleting_the_account_deletes_its_decisions(client):
    boss = sign_up(client, "boss@example.com", "Boss")
    db = client.app.state.db
    db.users.update_one({"email": "boss@example.com"}, {"$set": {"role": "admin"}})
    headers = sign_up(client)
    decide(client, headers, shown(client, headers)["id"], "bought")
    uid = db.users.find_one({"email": "amira@example.com"})["_id"]
    assert db.decisions.count_documents({"user_id": uid}) == 1
    assert client.delete(f"/admin/users/{uid}", headers=boss).status_code == 204
    assert db.decisions.count_documents({"user_id": uid}) == 0
