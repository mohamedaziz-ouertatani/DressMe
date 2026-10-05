"""Shop listings: saving a collector run, the /listings API, buy advice on a
listing, the admin sources page, and the Inditex connector (no real site)."""

import csv
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from app.listings import RawListing, SourceBlocked, sync_listings, usable
from connectors import inditex
from tests.conftest import BLACK, BLUE, RED, fake_vector, sign_up, upload

FIELDS = {RED: ("top", "t-shirt", "red"), BLUE: ("bottom", "jeans", "blue"),
          BLACK: ("shoes", "sneakers", "black")}


def raw(ext_id, rgb=RED, price=59.9, in_stock=True, image=None):
    """A listing whose 'picture URL' says which colour the fake labeller sees."""
    return RawListing(external_id=ext_id, url=f"https://shop.example/{ext_id}",
                      title=f"Product {ext_id}", image_url=image or f"rgb:{rgb}", brand="zara",
                      shop_colour="ECRU", price_tnd=price, sizes=["S", "M", "L"],
                      sizes_in_stock=["M"], in_stock=in_stock, availability_level="colour")


class FakeLabeller:
    """Stands in for download + background removal + models."""

    def __init__(self, fail=(), block=False):
        self.calls, self.fail, self.block = [], set(fail), block

    def __call__(self, r):
        self.calls.append(r.external_id)
        if self.block:
            raise SourceBlocked("HTTP 403 on pictures")
        if r.external_id in self.fail:
            return None
        rgb = next(k for k in FIELDS if r.image_url == f"rgb:{k}")
        category, sub, colour = FIELDS[rgb]
        conf = {"value": category, "conf": 0.9}
        return {"fields": {"category": category, "sub_category": sub, "pattern": "solid", "colour": colour},
                "predicted": {"category": conf}, "vector": fake_vector(sum(rgb)),
                "thumbnail": Image.new("RGB", (32, 40), rgb)}


@pytest.fixture
def db(client):
    return client.app.state.db


def sync(client, raws, labeller=None, when=None, **kw):
    return sync_listings(client.app.state.db, "zara_tn", raws, labeller or FakeLabeller(),
                         client.app.state.settings.storage_dir, now=when, **kw)


# ------------------------------------------------------------------ saving a run
def test_sync_adds_updates_and_marks_gone(client, db):
    t0 = datetime.now(timezone.utc)
    labeller = FakeLabeller()
    counts = sync(client, [raw("a"), raw("b", BLUE)], labeller, when=t0)
    assert counts["added"] == 2 and labeller.calls == ["a", "b"]
    a = db.listings.find_one({"external_id": "a"})
    assert a["category"] == "top" and a["status"] == "active" and a["vector"]
    assert (client.app.state.settings.storage_dir / "listings" / f"{a['_id']}.jpg").exists()

    # next run: same picture -> no new analysis; price changes; "b" is gone
    labeller = FakeLabeller()
    counts = sync(client, [raw("a", price=39.9)], labeller, when=t0 + timedelta(days=1))
    assert labeller.calls == [] and counts["updated"] == 1 and counts["gone"] == 1
    assert db.listings.find_one({"external_id": "a"})["price_tnd"] == 39.9
    assert db.listings.find_one({"external_id": "b"})["status"] == "gone"

    # a new picture is analysed again, and the same document is kept
    labeller = FakeLabeller()
    counts = sync(client, [raw("a", BLACK)], labeller, when=t0 + timedelta(days=2))
    again = db.listings.find_one({"external_id": "a"})
    assert labeller.calls == ["a"] and counts["relabelled"] == 1
    assert again["_id"] == a["_id"] and again["category"] == "shoes"


def test_sync_never_lists_an_item_it_could_not_see(client, db):
    counts = sync(client, [raw("a"), raw("b")], FakeLabeller(fail={"b"}))
    assert counts == {**counts, "added": 1, "no_picture": 1}
    assert db.listings.count_documents({}) == 1


def test_blocked_or_limited_runs_mark_nothing_gone(client, db):
    t0 = datetime.now(timezone.utc)
    sync(client, [raw("a"), raw("b")], when=t0)
    with pytest.raises(SourceBlocked):
        sync(client, [raw("c")], FakeLabeller(block=True), when=t0 + timedelta(days=1))
    counts = sync(client, [raw("a")], when=t0 + timedelta(days=2), mark_gone=False)  # --limit run
    assert counts["gone"] == 0
    assert db.listings.count_documents({"status": "active"}) == 2


def test_usable_needs_enabled_known_kind_and_team_approval():
    ok = {"kind": "inditex", "enabled": "yes", "approved_on": "2026-10-04"}
    assert usable(ok) == ""
    assert usable({**ok, "enabled": "no"}) == "not enabled"
    assert "approval" in usable({**ok, "approved_on": ""})
    assert "no connector" in usable({**ok, "kind": "facebook"})


# ------------------------------------------------------------------ API
def test_browse_filters_and_images(client):
    headers = sign_up(client)
    sync(client, [raw("a", price=80), raw("b", BLUE, price=40), raw("c", in_stock=False)])
    all_ = client.get("/listings", headers=headers).json()
    assert all_["total"] == 2                      # out of stock hidden by default
    assert client.get("/listings?in_stock=false", headers=headers).json()["total"] == 3
    tops = client.get("/listings?category=top", headers=headers).json()["items"]
    assert [x["title"] for x in tops] == ["Product a"]
    cheap = client.get("/listings?max_price=50&sort=price", headers=headers).json()["items"]
    assert [x["title"] for x in cheap] == ["Product b"] and "vector" not in cheap[0]
    item = cheap[0]
    assert item["url"] == "https://shop.example/b" and item["sizes_in_stock"] == ["M"]
    assert client.get(item["image_url"], headers=headers).status_code == 200
    assert client.get("/listings/nope", headers=headers).status_code == 404
    assert client.get("/listings", headers={}).status_code == 401
    assert client.get("/listings/sources", headers=headers).json() == [
        {"source_id": "zara_tn", "brands": ["zara"], "count": 2}]


def test_buy_advice_and_similar_on_a_listing(client):
    headers = sign_up(client)
    for rgb in (RED, BLUE, BLACK):
        upload(client, headers, rgb)
    sync(client, [raw("a"), raw("b"), raw("j", BLUE)])
    listing = client.get("/listings?category=top", headers=headers).json()["items"][0]

    r = client.post(f"/listings/{listing['id']}/candidate", headers=headers)
    assert r.status_code == 201
    cand = r.json()
    assert cand["category"] == "top" and cand["image_url"].startswith("/candidates/")
    assert client.get(cand["image_url"], headers=headers).status_code == 200
    advice = client.post("/buy-advice", json={"candidate_id": cand["id"]}, headers=headers)
    assert advice.status_code == 200 and advice.json()["verdict"] in ("buy", "think", "skip")

    similar = client.get(f"/similar?candidate_id={cand['id']}", headers=headers).json()
    ids = [x["id"] for x in similar["listings"]]
    assert listing["id"] not in ids and ids                   # other tops, never itself
    assert all(x["category"] == "top" for x in similar["listings"])

    # the candidate is private, like a scan
    other = sign_up(client, "other@example.com", "Other")
    assert client.post("/buy-advice", json={"candidate_id": cand["id"]}, headers=other).status_code == 404


def test_gone_listing_cannot_become_a_candidate(client, db):
    headers = sign_up(client)
    t0 = datetime.now(timezone.utc)
    sync(client, [raw("a")], when=t0)
    sync(client, [], when=t0 + timedelta(days=1))
    lid = str(db.listings.find_one()["_id"])
    assert client.post(f"/listings/{lid}/candidate", headers=headers).status_code == 404
    assert client.get(f"/listings/{lid}", headers=headers).json()["status"] == "gone"


def test_admin_sources(client, db):
    from app.listings import record_run

    headers = sign_up(client)
    assert client.get("/admin/sources", headers=headers).status_code == 403
    db.users.update_one({}, {"$set": {"role": "admin"}})
    record_run(db, "zara_tn", datetime.now(timezone.utc), "blocked", "Access Denied")
    rows = {s["source_id"]: s for s in client.get("/admin/sources", headers=headers).json()["sources"]}
    # blocked on 2026-10-04 and again on 2026-10-05: switched off, the block stays in its history
    assert rows["zara_tn"]["refused"] == "not enabled" and rows["zara_tn"]["last_run"]["result"] == "blocked"
    assert "kind not set" in rows["zen_tn"]["refused"]
    assert rows["zara_tn"]["last_ok"] is None
    assert rows["inditex_snapshot"]["refused"] == ""
    assert "check_shop_source" in rows["exist_tn"]["refused"]           # kind not set until checked


# ------------------------------------------------------------------ Inditex connector
SOURCE = {"source_id": "zara_tn", "kind": "inditex", "brand": "zara", "country": "tn",
          "delay_s": "5", "catalogue_days": "7"}


def write_products(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["id", "brand", "name", "colour_name", "url", "image_url", "price", "gender", "sizes",
            "sku_sizes", "availability", "availability_from", "sizes_in_stock"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows([{c: r.get(c, "") for c in cols} for r in rows])


def test_inditex_rows_and_stock_levels(tmp_path):
    path = tmp_path / "zara_tn" / "products.csv"
    write_products(path, [
        {"id": "zr_1_2", "brand": "zara", "name": "SHIRT", "url": "u1", "image_url": "i1", "price": "89.9",
         "sizes": "S|M", "sku_sizes": "11:S|12:M", "availability": "low_on_stock",
         "availability_from": "stock_api", "sizes_in_stock": "M"},
        {"id": "zr_3_4", "url": "u2", "image_url": "i2", "availability": "in_stock",
         "availability_from": "stock_api", "sizes_in_stock": "998|999"},      # SKUs of mixed colours
        {"id": "zr_5_6", "url": "u3", "image_url": "i3", "availability": "out_of_stock",
         "availability_from": "catalogue"},
        {"id": "zr_7_8", "url": "", "image_url": "i4"},                         # no link: skipped
    ])
    rows = inditex.read_rows(path)
    assert [r.external_id for r in rows] == ["zr_1_2", "zr_3_4", "zr_5_6"]
    a, b, c = rows
    assert (a.in_stock, a.availability_level, a.sizes_in_stock, a.price_tnd) == (True, "colour", ["M"], 89.9)
    assert (b.availability_level, b.sizes_in_stock) == ("product", [])
    assert (c.in_stock, c.availability_level, c.price_tnd) == (False, "catalogue", None)


def test_inditex_mode_and_block_detection(tmp_path, monkeypatch):
    path = tmp_path / "zara_tn" / "products.csv"
    assert inditex.catalogue_due(path, 7)                        # never read: full catalogue
    write_products(path, [{"id": "zr_1_2", "url": "u", "image_url": "i", "availability": "in_stock"}])
    assert not inditex.catalogue_due(path, 7)
    old = time.time() - 8 * 86400
    os.utime(path, (old, old))
    assert inditex.catalogue_due(path, 7)

    assert "--stock-only" in inditex.command(SOURCE, catalogue=False)
    assert "--stock-only" not in inditex.command(SOURCE, catalogue=True)
    assert inditex.outcome(0, "wrote products.csv")[0] == "ok"
    assert inditex.outcome(1, "ERROR: zara refused the automated browser")[0] == "blocked"
    assert inditex.outcome(1, "ERROR: zara keeps refusing our requests (HTTP 403")[0] == "blocked"
    assert inditex.outcome(1, "ModuleNotFoundError: playwright")[0] == "error"

    # a blocked scraper run returns no listings at all
    monkeypatch.setattr(inditex, "SHOPS_DIR", tmp_path)
    args = type("Args", (), {"catalogue": False, "limit": 0})()
    blocked = inditex.fetch(SOURCE, args, runner=lambda cmd: (1, "zara refused the automated browser"))
    assert blocked.status == "blocked" and blocked.listings == []
    ok = inditex.fetch(SOURCE, args, runner=lambda cmd: (0, "done"))
    assert ok.status == "ok" and [r.external_id for r in ok.listings] == ["zr_1_2"]


# ------------------------------------------------------------------ the collector job
def test_collector_saves_ok_runs_and_reports_blocks(client, db, monkeypatch):
    import collect_listings
    from connectors import FetchResult

    settings = client.app.state.settings
    args = type("Args", (), {"limit": 0, "catalogue": False})()
    source = {**SOURCE, "refresh_days": "2"}
    now = datetime.now(timezone.utc)
    assert collect_listings.due(db, source, now) == ""          # never ran

    fake = type("Connector", (), {})()
    fake.fetch = lambda s, a: FetchResult("blocked", "Access Denied", mode="stock")
    monkeypatch.setitem(collect_listings.CONNECTORS, "inditex", fake)
    assert collect_listings.collect(db, settings, source, args, lambda s: FakeLabeller()) == "blocked"
    assert db.listings.count_documents({}) == 0
    assert collect_listings.due(db, source, now) == ""          # a blocked run is not a good run

    fake.fetch = lambda s, a: FetchResult("ok", "done", [raw("a"), raw("b", BLUE)], "catalogue")
    assert collect_listings.collect(db, settings, source, args, lambda s: FakeLabeller()) == "ok"
    run = db.listing_runs.find_one({"result": "ok"})
    assert run["counts"]["added"] == 2 and run["mode"] == "catalogue"
    assert "refresh every 2" in collect_listings.due(db, source, datetime.now(timezone.utc))
    assert collect_listings.due(db, source, datetime.now(timezone.utc) + timedelta(days=3)) == ""

    # pictures refused while saving: reported as blocked
    fake.fetch = lambda s, a: FetchResult("ok", "done", [raw("c")], "stock")
    result = collect_listings.collect(db, settings, source, args, lambda s: FakeLabeller(block=True))
    assert result == "blocked" and db.listings.count_documents({"status": "active"}) == 2


def test_snapshot_listing_keeps_its_own_check_date(client):
    headers = sign_up(client)
    old = raw("s1")
    old.checked_at, old.snapshot = "2026-10-03T10:00:00Z", True
    sync(client, [old, raw("live")])
    by_title = {x["title"]: x for x in client.get("/listings", headers=headers).json()["items"]}
    snap, live = by_title["Product s1"], by_title["Product live"]
    assert snap["snapshot"] is True and snap["checked_at"] == "2026-10-03T10:00:00Z"
    assert live["snapshot"] is False and live["checked_at"] == live["seen_at"]
    assert snap["seller"] is None
