"""
Deleting an account must leave nothing of the user behind.

The delete code (routers/admin.py `delete_user`) lists the collections it cleans BY NAME. This
test does not trust that list: it makes a user write to every place the API allows (with the usual
fakes), deletes the account as an admin, then looks through EVERY collection of the database
(`list_collection_names()`, so one added later is found too) for any document that still holds the
user's id, anywhere inside it, and checks that the user's photo folder and the seller-listing
pictures are gone. It fails with the name of each collection that still holds the user's data.

When a later step adds a new way for a user to write data, add that write to `leave_data_everywhere`
so this test keeps covering "every place the API allows".
"""

from bson import ObjectId

from tests.conftest import BLACK, BLUE, GREEN, RED, photo, sign_up

# the places that must really hold the user's data before the deletion, or the test proves nothing
MUST_HOLD_DATA = {"users", "items", "candidates", "chats", "events", "outfit_feedback", "listings", "decisions",
                  "wear_log"}


def mentions(value, user_id):
    """True if the user's id is anywhere in a document (as an ObjectId or as text)."""
    if isinstance(value, ObjectId):
        return value == user_id
    if isinstance(value, str):
        return value == str(user_id)
    if isinstance(value, dict):
        return any(mentions(v, user_id) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(mentions(v, user_id) for v in value)
    return False


def collections_holding(db, user_id):
    """{collection: number of documents that mention the user}, for every collection that has any."""
    found = {}
    for name in db.list_collection_names():
        n = sum(1 for doc in db[name].find({}) if mentions(doc, user_id))
        if n:
            found[name] = n
    return found


def make_admin(db, email):
    db.users.update_one({"email": email}, {"$set": {"role": "admin"}})


def leave_data_everywhere(client, headers):
    """Use every feature that stores something for the user. Returns the ids the test needs."""
    top = client.post("/items", files={"photo": photo(RED)}, headers=headers).json()
    bottom = client.post("/items", files={"photo": photo(BLUE)}, headers=headers).json()
    client.post("/items", files={"photo": photo(BLACK)}, headers=headers).json()
    assert client.patch(f"/items/{top['id']}", json={"colour": "pink"}, headers=headers).status_code == 200

    scan = client.post("/analyze", files={"photo": photo(GREEN)}, headers=headers).json()
    assert client.post("/buy-advice", json={"candidate_id": scan["id"], "corrections": {"colour": "green"}},
                       headers=headers).status_code == 200
    # step 1: the decision log. "Bought it" also saves the scan into the wardrobe; "Left it" leaves a
    # second scan alone
    assert client.post("/decisions", json={"candidate_id": scan["id"], "answer": "bought"},
                       headers=headers).status_code == 201
    left = client.post("/analyze", files={"photo": photo(RED)}, headers=headers).json()
    assert client.post("/buy-advice", json={"candidate_id": left["id"], "price_tnd": 40},
                       headers=headers).status_code == 200
    assert client.post("/decisions", json={"candidate_id": left["id"], "answer": "left"},
                       headers=headers).status_code == 201

    # step 2: the wear log
    assert client.post("/wear", json={"item_ids": [top["id"], bottom["id"]], "source": "card"},
                       headers=headers).status_code == 201
    assert client.post("/outfits/feedback", json={"item_ids": [top["id"], bottom["id"]], "rating": 1},
                       headers=headers).status_code == 200
    assert client.post("/chat", json={"message": "how many items are in my wardrobe?"},
                       headers=headers).status_code == 200
    r = client.post("/tryon", files={"photo": photo(BLACK, size=(60, 100))},
                    data={"item_ids": [top["id"], bottom["id"]]}, headers=headers)
    assert r.status_code == 200, r.text

    sold = client.post("/listings/sell", files={"photo": photo(RED)},
                       data={"price_tnd": "25", "size": "M", "city": "Tunis", "contact": "@leaver"},
                       headers=headers)
    assert sold.status_code == 201, sold.text
    return {"listing_id": sold.json()["id"]}


def test_deleting_an_account_leaves_nothing_behind(make_client, settings):
    client = make_client()
    db = client.app.state.db
    leaver = sign_up(client, "leaver@example.com", "Leaver")
    stayer = sign_up(client, "stayer@example.com", "Stayer")
    boss = sign_up(client, "boss@example.com", "Boss")
    make_admin(db, "boss@example.com")

    stayer_item = client.post("/items", files={"photo": photo(RED)}, headers=stayer).json()
    made = leave_data_everywhere(client, leaver)
    # the admin approves the seller listing; the seller then scans their own listing
    # (this copies the listing picture into the user's photo folder)
    assert client.patch(f"/admin/listings/{made['listing_id']}", json={"status": "active"},
                        headers=boss).status_code == 200
    assert client.post(f"/listings/{made['listing_id']}/candidate", headers=leaver).status_code == 201

    user_id = db.users.find_one({"email": "leaver@example.com"})["_id"]
    folder = settings.storage_dir / str(user_id)
    listing_picture = settings.storage_dir / "listings" / f"{made['listing_id']}.jpg"
    before = collections_holding(db, user_id)
    assert MUST_HOLD_DATA <= set(before), f"the test no longer writes to: {sorted(MUST_HOLD_DATA - set(before))}"
    assert folder.exists() and listing_picture.exists()

    assert client.delete(f"/admin/users/{user_id}", headers=boss).status_code == 204

    left = collections_holding(db, user_id)
    assert not left, f"user data left in these collections after the account was deleted: {left} (before: {before})"
    assert not folder.exists(), "the user's photo folder is still there"
    assert not listing_picture.exists(), "the seller listing's picture is still there"
    # and nobody else lost anything
    assert client.get(f"/items/{stayer_item['id']}", headers=stayer).status_code == 200
    assert db.users.count_documents({}) == 2

    # step 5: the user's own DELETE /me (the password is asked) leaves nothing behind either: same check
    quitter = sign_up(client, "quitter@example.com", "Quitter")
    made = leave_data_everywhere(client, quitter)
    quitter_id = db.users.find_one({"email": "quitter@example.com"})["_id"]
    quitter_folder = settings.storage_dir / str(quitter_id)
    quitter_picture = settings.storage_dir / "listings" / f"{made['listing_id']}.jpg"
    assert MUST_HOLD_DATA <= set(collections_holding(db, quitter_id))
    assert quitter_folder.exists() and quitter_picture.exists()
    assert client.request("DELETE", "/me", json={"password": "secret-pass"}, headers=quitter).status_code == 204
    assert not collections_holding(db, quitter_id), "DELETE /me left user data behind"
    assert not quitter_folder.exists() and not quitter_picture.exists()
    assert client.get(f"/items/{stayer_item['id']}", headers=stayer).status_code == 200
    assert db.users.count_documents({}) == 2
