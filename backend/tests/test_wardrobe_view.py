"""
Step 5: the Wardrobe view's API. One contract test each: POST /me/consent, PUT /me (the budget),
GET /wear/summary and DELETE /me (the full "leaves nothing behind" check is in test_deletion_complete.py).
"""

from datetime import datetime, timedelta, timezone

from bson import ObjectId

from tests.conftest import BLACK, BLUE, RED, sign_up, upload


def test_consent_is_stamped_once(client):
    # sign-up with the checkbox stamps the date; without it the date stays empty
    r = client.post("/auth/register", json={"email": "yes@example.com", "password": "secret-pass", "name": "Yes",
                                            "gender": "women", "consent": True})
    assert r.status_code == 201 and r.json()["user"]["consent_at"] is not None
    old = sign_up(client, "old@example.com", "Old")                       # an account without the checkbox
    assert client.get("/me", headers=old).json()["consent_at"] is None

    first = client.post("/me/consent", headers=old)
    assert first.status_code == 200 and first.json()["consent_at"] is not None
    assert client.post("/me/consent", headers=old).json()["consent_at"] == first.json()["consent_at"]   # idempotent
    assert client.get("/me", headers=old).json()["consent_at"] == first.json()["consent_at"]

    # it only touches the caller: another user's date is still empty
    other = sign_up(client, "other@example.com", "Other")
    assert client.get("/me", headers=other).json()["consent_at"] is None
    assert client.post("/me/consent").status_code == 401


def test_budget_is_saved_through_the_profile_update(client):
    mine, other = sign_up(client), sign_up(client, "karim@example.com", "Karim")
    assert client.get("/me", headers=mine).json()["budget_tnd"] is None
    r = client.put("/me", json={"budget_tnd": 120.5}, headers=mine)
    assert r.status_code == 200 and r.json()["budget_tnd"] == 120.5
    assert client.get("/me", headers=mine).json()["budget_tnd"] == 120.5
    assert client.get("/me", headers=other).json()["budget_tnd"] is None              # not shared
    assert client.put("/me", json={"budget_tnd": -5}, headers=mine).status_code == 422
    assert client.get("/me", headers=mine).json()["budget_tnd"] == 120.5              # a refused value changes nothing
    assert client.put("/me", json={"name": "Amira B"}, headers=mine).json()["budget_tnd"] == 120.5   # left alone
    assert client.put("/me", json={"budget_tnd": None}, headers=mine).json()["budget_tnd"] is None   # null clears it


def test_wear_summary_lists_worn_lately_and_never_worn(client):
    mine, other = sign_up(client), sign_up(client, "karim@example.com", "Karim")
    worn, rested, old_unworn, new_unworn = (upload(client, mine, c) for c in (RED, BLUE, BLACK, (200, 120, 40)))
    theirs = upload(client, other, RED)
    db = client.app.state.db
    long_ago = datetime.now(timezone.utc) - timedelta(days=60)
    for item in (worn, rested, old_unworn):                      # owned for two months; new_unworn was added just now
        db.items.update_one({"_id": ObjectId(item["id"])}, {"$set": {"created_at": long_ago}})

    assert client.post("/wear", json={"item_ids": [worn["id"]], "source": "card"}, headers=mine).status_code == 201
    old_day = (datetime.now(timezone.utc) - timedelta(days=40)).date().isoformat()
    db.wear_log.insert_one({"user_id": db.users.find_one({"email": "amira@example.com"})["_id"],
                            "item_ids": [rested["id"]], "worn_on": old_day, "source": "build", "created_at": long_ago})

    body = client.get("/wear/summary", headers=mine).json()
    assert set(body) == {"worn_lately", "never_worn", "window_days", "grace_days"}
    assert body["window_days"] == 14 and body["grace_days"] == 14                    # mappings/wardrobe_view.csv
    assert [w["item_id"] for w in body["worn_lately"]] == [worn["id"]]
    assert body["worn_lately"][0]["last_worn_on"] == client.get("/wear", headers=mine).json()[0]["worn_on"]
    # worn long ago is in neither list; a piece added just now is not neglected yet (grace period)
    assert body["never_worn"] == [old_unworn["id"]] and new_unworn["id"] not in body["never_worn"]

    # nobody else's pieces or entries show up, and the other user sees only their own
    assert theirs["id"] not in body["never_worn"] + [w["item_id"] for w in body["worn_lately"]]
    assert client.get("/wear/summary", headers=other).json()["never_worn"] == []
    assert client.get("/wear/summary").status_code == 401


def test_delete_my_account(client):
    mine, other = sign_up(client), sign_up(client, "karim@example.com", "Karim")
    mine_item, other_item = upload(client, mine, RED), upload(client, other, BLUE)
    db = client.app.state.db

    # a wrong password: 403, and nothing is deleted
    assert client.request("DELETE", "/me", json={"password": "not-my-password"}, headers=mine).status_code == 403
    assert client.get(f"/items/{mine_item['id']}", headers=mine).status_code == 200

    # the demo account cannot be deleted from the app
    db.users.update_one({"email": "karim@example.com"}, {"$set": {"demo": True}})
    assert client.request("DELETE", "/me", json={"password": "secret-pass"}, headers=other).status_code == 403
    db.users.update_one({"email": "karim@example.com"}, {"$set": {"demo": False}})

    # the right password: 204, the account and its pieces are gone, the other user is untouched
    assert client.request("DELETE", "/me", json={"password": "secret-pass"}, headers=mine).status_code == 204
    assert client.get("/me", headers=mine).status_code == 401
    assert client.post("/auth/login", json={"email": "amira@example.com", "password": "secret-pass"}).status_code == 401
    assert db.items.count_documents({}) == 1 and db.users.count_documents({}) == 1
    assert client.get(f"/items/{other_item['id']}", headers=other).status_code == 200
    assert client.request("DELETE", "/me", headers=other).status_code == 422          # the password is required
