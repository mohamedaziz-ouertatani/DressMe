"""
Step 2: the wear log (POST / GET / DELETE /wear, app/routers/wear.py). One contract test: the answers the
app relies on, from the first POST to the undo, and the refusals.
"""

from datetime import datetime, timedelta, timezone

from bson import ObjectId

from tests.conftest import BLACK, BLUE, RED, sign_up, upload


def test_wear_contract(client):
    headers = sign_up(client)
    top, bottom, shoes = (upload(client, headers, rgb) for rgb in (RED, BLUE, BLACK))
    ids = [top["id"], bottom["id"]]

    # POST: the entry, dated in Tunis by the server, with what the app showed
    r = client.post("/wear", json={"item_ids": ids, "occasion": "casual", "score_shown": 81.5,
                                   "label_shown": "safe", "source": "card"}, headers=headers)
    assert r.status_code == 201, r.text
    entry = r.json()
    assert set(entry) == {"id", "item_ids", "worn_on", "occasion", "event_name", "score_shown", "label_shown",
                          "source", "created_at"}
    assert entry["item_ids"] == ids and entry["occasion"] == "casual" and entry["event_name"] is None
    assert entry["score_shown"] == 81.5 and entry["label_shown"] == "safe" and entry["source"] == "card"
    assert client.app.state.db.events.count_documents({"type": "wear"}) == 1

    # the same pieces on the same day are the same entry (a double tap or a reload does not double the log)
    again = client.post("/wear", json={"item_ids": ids[::-1], "source": "build"}, headers=headers)
    assert again.status_code == 200 and again.json()["id"] == entry["id"]

    # GET: newest first, optional dates
    client.post("/wear", json={"item_ids": [shoes["id"]], "source": "build"}, headers=headers)
    listed = client.get("/wear", headers=headers).json()
    assert len(listed) == 2 and listed[0]["item_ids"] == [shoes["id"]]
    day = entry["worn_on"]
    assert len(client.get("/wear", params={"from": day, "to": day}, headers=headers).json()) == 2
    assert client.get("/wear", params={"to": "2000-01-01"}, headers=headers).json() == []

    # the pieces must be the user's own (404, nothing is written)
    other = sign_up(client, "karim@example.com", "Karim")
    theirs = upload(client, other, RED)
    r = client.post("/wear", json={"item_ids": [top["id"], theirs["id"]], "source": "card"}, headers=headers)
    assert r.status_code == 404
    assert client.get("/wear", headers=other).json() == []
    assert client.delete(f"/wear/{entry['id']}", headers=other).status_code == 404       # another user's entry

    # DELETE: today's entry goes; an older one answers 409
    old = client.app.state.db.wear_log.insert_one({
        "user_id": client.app.state.db.users.find_one({"email": "amira@example.com"})["_id"], "item_ids": ids,
        "worn_on": (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat(), "source": "card",
        "created_at": datetime.now(timezone.utc)}).inserted_id
    assert client.delete(f"/wear/{old}", headers=headers).status_code == 409
    assert client.delete(f"/wear/{entry['id']}", headers=headers).status_code == 204
    assert entry["id"] not in [e["id"] for e in client.get("/wear", headers=headers).json()]
    assert client.delete(f"/wear/{entry['id']}", headers=headers).status_code == 404
    assert client.delete(f"/wear/{ObjectId()}", headers=headers).status_code == 404
