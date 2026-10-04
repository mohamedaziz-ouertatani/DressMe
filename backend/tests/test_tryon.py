import base64
import io

from PIL import Image

from tests.conftest import BLACK, BLUE, GREEN, RED, FakeTryOn, photo, sign_up, upload

PERSON = (180, 150, 120)


def try_on(client, headers, item_ids=(), candidate_id=None):
    data = {"item_ids": list(item_ids)}
    if candidate_id:
        data["candidate_id"] = candidate_id
    return client.post("/tryon", files={"photo": photo(PERSON, size=(60, 100))}, data=data, headers=headers)


def decode(data_url):
    head, b64 = data_url.split(",", 1)
    assert head == "data:image/jpeg;base64"
    return Image.open(io.BytesIO(base64.b64decode(b64)))


def test_outfit_is_chained_bottom_first_and_shoes_skipped(make_client, settings):
    engine = FakeTryOn()
    client = make_client(tryon=engine)
    headers = sign_up(client)
    top, jeans, shoes = (upload(client, headers, c)["id"] for c in (RED, BLUE, BLACK))
    stored = len(list(settings.storage_dir.rglob("*.jpg")))
    r = try_on(client, headers, [top, shoes, jeans])
    assert r.status_code == 200, r.text
    body = r.json()
    assert engine.calls == ["lower", "upper"]              # trousers before the top
    assert body["applied"] == [jeans, top] and body["failed"] == []
    assert body["skipped"] == [{"id": shoes, "reason": "unsupported"}]
    assert decode(body["image"]).size == (60, 100)          # the person photo, dressed
    assert len(list(settings.storage_dir.rglob("*.jpg"))) == stored   # nothing saved
    assert client.app.state.db.events.count_documents({"type": "tryon"}) == 1


def test_scanned_candidate_can_be_tried_on(make_client):
    engine = FakeTryOn()
    client = make_client(tryon=engine)
    headers = sign_up(client)
    cand = client.post("/analyze", files={"photo": photo(GREEN)}, headers=headers).json()
    r = try_on(client, headers, candidate_id=cand["id"])
    assert r.status_code == 200, r.text
    assert engine.calls == ["overall"] and r.json()["applied"] == [cand["id"]]
    img = client.get(f"/candidates/{cand['id']}/image", headers=headers)   # kept in the document
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"


def test_refusals(client):
    headers = sign_up(client)
    shoes = upload(client, headers, BLACK)["id"]
    top = upload(client, headers, RED)["id"]
    assert try_on(client, headers).status_code == 422                     # nothing picked
    assert try_on(client, headers, [shoes]).status_code == 422            # no garment
    other = sign_up(client, email="sami@example.com", name="Sami")
    assert try_on(client, other, [top]).status_code == 404                # not their item
    second_top = upload(client, headers, RED)["id"]
    r = try_on(client, headers, [top, second_top])                        # two t-shirts
    assert r.status_code == 422 and "can't be worn together" in r.json()["detail"]


def test_space_failure(make_client):
    client = make_client(tryon=FakeTryOn(fail_after=0))
    headers = sign_up(client)
    top = upload(client, headers, RED)["id"]
    assert try_on(client, headers, [top]).status_code == 502              # app shows the overlay


def test_failure_mid_chain_keeps_the_first_garment(make_client):
    client = make_client(tryon=FakeTryOn(fail_after=1))
    headers = sign_up(client)
    top, jeans = upload(client, headers, RED)["id"], upload(client, headers, BLUE)["id"]
    r = try_on(client, headers, [top, jeans])
    assert r.status_code == 200
    assert r.json()["applied"] == [jeans] and r.json()["failed"] == [top]


def test_switched_off(client):
    headers = sign_up(client)
    top = upload(client, headers, RED)["id"]
    client.app.state.tryon = None                                         # TRYON_ENGINE=off
    assert try_on(client, headers, [top]).status_code == 503


def test_corrected_scan_is_dressed_as_corrected(make_client):
    engine = FakeTryOn()
    client = make_client(tryon=engine)
    headers = sign_up(client)
    cand = client.post("/analyze", files={"photo": photo(RED)}, headers=headers).json()   # read as a top
    r = client.post("/buy-advice", json={"candidate_id": cand["id"], "corrections": {"category": "dress"}},
                    headers=headers)
    assert r.status_code == 200
    assert try_on(client, headers, candidate_id=cand["id"]).status_code == 200
    assert engine.calls == ["overall"]


def test_shop_listing_can_be_tried_on(make_client):
    from tests.test_listings import raw, sync
    engine = FakeTryOn()
    client = make_client(tryon=engine)
    headers = sign_up(client)
    sync(client, [raw("a")])
    listing = client.get("/listings", headers=headers).json()["items"][0]
    cand = client.post(f"/listings/{listing['id']}/candidate", headers=headers).json()
    r = try_on(client, headers, candidate_id=cand["id"])            # picture copied as a file
    assert r.status_code == 200, r.text
    assert engine.calls == ["upper"]
