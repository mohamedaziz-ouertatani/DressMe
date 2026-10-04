"""Friperie sellers' listings: post -> pending -> admin review -> listed, the
seller's own edits, privacy, and cleanup when an account is deleted."""

from tests.conftest import BLACK, BLUE, GREEN, RED, photo, sign_up, upload


def sell(client, headers, rgb=RED, **form):
    data = {"price_tnd": "25", "size": "M", "city": "Tunis", "contact": "@amira.friperie", **form}
    return client.post("/listings/sell", files={"photo": photo(rgb)}, data=data, headers=headers)


def admin(client, db):
    headers = sign_up(client, "admin@example.com", "Admin")
    db.users.update_one({"email": "admin@example.com"}, {"$set": {"role": "admin"}})
    return headers


def test_sell_review_then_listed(client):
    db = client.app.state.db
    seller = sign_up(client)
    buyer = sign_up(client, "buyer@example.com", "Buyer")
    boss = admin(client, db)

    r = sell(client, seller, title="Veste en jean vintage")
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["status"] == "pending" and item["category"] == "top" and item["price_tnd"] == 25
    assert item["seller"] == {"city": "Tunis", "contact": "@amira.friperie", "review_note": ""}
    assert item["sizes_in_stock"] == ["M"] and item["url"] == ""

    # not shown to others until reviewed, but the seller sees it
    assert client.get("/listings", headers=buyer).json()["total"] == 0
    assert client.get(f"/listings/{item['id']}", headers=buyer).status_code == 404
    assert client.get(f"/listings/{item['id']}/image", headers=buyer).status_code == 404
    assert client.get(f"/listings/{item['id']}", headers=seller).status_code == 200
    assert [x["id"] for x in client.get("/listings/mine", headers=seller).json()] == [item["id"]]

    # the review queue is for admins only
    assert client.get("/admin/listings", headers=seller).status_code == 403
    queue = client.get("/admin/listings", headers=boss).json()
    assert queue["total"] == 1 and queue["listings"][0]["seller_email"] == "amira@example.com"
    r = client.patch(f"/admin/listings/{item['id']}", json={"status": "active"}, headers=boss)
    assert r.status_code == 200 and r.json()["status"] == "active"

    listed = client.get("/listings", headers=buyer).json()["items"]
    assert [x["id"] for x in listed] == [item["id"]]
    assert client.get(f"/listings/{item['id']}/image", headers=buyer).status_code == 200
    sources = client.get("/listings/sources", headers=buyer).json()
    assert sources == [{"source_id": "sellers", "brands": [], "count": 1}]

    # "Should I buy this?" works on it, and Similar finds it for a look-alike
    upload(client, buyer, BLUE)
    upload(client, buyer, BLACK)
    cand = client.post(f"/listings/{item['id']}/candidate", headers=buyer).json()
    assert client.post("/buy-advice", json={"candidate_id": cand["id"]}, headers=buyer).status_code == 200
    mine = upload(client, buyer, RED)
    similar = client.get(f"/similar?item_id={mine['id']}", headers=buyer).json()
    assert [x["id"] for x in similar["listings"]] == [item["id"]]


def test_reject_with_a_note(client):
    db = client.app.state.db
    seller = sign_up(client)
    boss = admin(client, db)
    lid = sell(client, seller).json()["id"]
    client.patch(f"/admin/listings/{lid}", json={"status": "rejected", "note": "Photo too dark"}, headers=boss)
    mine = client.get("/listings/mine", headers=seller).json()[0]
    assert mine["status"] == "rejected" and mine["seller"]["review_note"] == "Photo too dark"
    assert client.get("/listings?in_stock=false", headers=boss).json()["total"] == 0


def test_seller_edits_sold_and_delete(client):
    db = client.app.state.db
    seller = sign_up(client)
    other = sign_up(client, "other@example.com", "Other")
    boss = admin(client, db)
    lid = sell(client, seller).json()["id"]
    client.patch(f"/admin/listings/{lid}", json={"status": "active"}, headers=boss)

    # price, size and labels: stays listed
    r = client.patch(f"/listings/{lid}", json={"price_tnd": 20, "size": "L", "colour": "white"}, headers=seller)
    assert r.status_code == 200
    body = r.json()
    assert (body["status"], body["price_tnd"], body["sizes"], body["colour"]) == ("active", 20, ["L"], "white")
    assert db.listings.find_one({"source_id": "sellers"})["corrected"] == ["colour"]
    # a wrong sub_category for the category is refused, like on wardrobe items
    assert client.patch(f"/listings/{lid}", json={"sub_category": "jeans"}, headers=seller).status_code == 422
    # new free text (contact): back to review
    r = client.patch(f"/listings/{lid}", json={"contact": "+216 20 000 000"}, headers=seller)
    assert r.json()["status"] == "pending"

    # nobody else can change or delete it, and they cannot tell it exists
    assert client.patch(f"/listings/{lid}", json={"sold": True}, headers=other).status_code == 404
    assert client.delete(f"/listings/{lid}", headers=other).status_code == 404
    assert client.patch(f"/listings/{lid}", json={"sold": True}, headers=boss).status_code == 404

    r = client.patch(f"/listings/{lid}", json={"sold": True}, headers=seller)
    assert r.json()["status"] == "gone" and r.json()["in_stock"] is False
    assert client.patch(f"/admin/listings/{lid}", json={"status": "active"}, headers=boss).status_code == 409
    assert client.delete(f"/listings/{lid}", headers=seller).status_code == 204
    assert client.get("/listings/mine", headers=seller).json() == []


def test_shop_listings_cannot_be_changed_by_users(client):
    from datetime import datetime, timezone
    from bson import ObjectId
    db = client.app.state.db
    headers = sign_up(client)
    lid = ObjectId()
    db.listings.insert_one({"_id": lid, "source_id": "inditex_snapshot", "external_id": "zr_1", "status": "active",
                            "seen_at": datetime.now(timezone.utc), "category": "top"})
    assert client.patch(f"/listings/{lid}", json={"sold": True}, headers=headers).status_code == 404
    assert client.delete(f"/listings/{lid}", headers=headers).status_code == 404


def test_validation_and_pending_limit(client, monkeypatch):
    from app.routers import listings as router
    seller = sign_up(client)
    assert sell(client, seller, contact="").status_code == 422
    assert sell(client, seller, contact="x" * 61).status_code == 422
    assert sell(client, seller, price_tnd="0").status_code == 422
    monkeypatch.setattr(router, "MAX_PENDING", 2)
    assert sell(client, seller).status_code == 201
    assert sell(client, seller, GREEN).status_code == 201
    assert sell(client, seller, BLUE).status_code == 429


def test_deleting_the_account_removes_its_listings(client):
    db = client.app.state.db
    seller = sign_up(client)
    boss = admin(client, db)
    lid = sell(client, seller).json()["id"]
    picture = client.app.state.settings.storage_dir / "listings" / f"{lid}.jpg"
    assert picture.exists()
    user_id = str(db.users.find_one({"email": "amira@example.com"})["_id"])
    assert client.delete(f"/admin/users/{user_id}", headers=boss).status_code == 204
    assert db.listings.count_documents({}) == 0 and not picture.exists()
