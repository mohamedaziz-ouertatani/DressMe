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


# ------------------------------------------------------------------ the Space chain (no network)
class FakeJob:
    def __init__(self, answer):
        self.answer = answer

    def result(self, timeout=None):
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


class FakeSpace:
    """A gradio Client stand-in: records the call, answers `answer`."""

    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def submit(self, *args, api_name=None):
        self.calls.append(api_name)
        return FakeJob(self.answer)


def space_engine(settings, tmp_path, spaces, behaviour):
    """SpaceTryOn over fake Spaces. behaviour[space] = "broken" (can't connect),
    "busy" (the job fails), "empty" (no picture) or "ok"."""
    from app.tryon import SpaceTryOn
    picture = tmp_path / "made.png"
    Image.new("RGB", (30, 50), (0, 200, 0)).save(picture)
    settings.tryon_spaces = spaces
    made = {}

    def connect(space):
        if behaviour[space] == "broken":
            raise ValueError("The current space is in the invalid state: RUNTIME_ERROR.")
        answer = {"busy": RuntimeError("quota"), "empty": (None, 42, "Too many users"),
                  "ok": (str(picture), 42, "")}[behaviour[space]]
        made[space] = FakeSpace(answer)
        return made[space]

    return SpaceTryOn(settings, make_client=connect), made


def person_and_garment():
    return Image.new("RGB", (30, 50), PERSON), Image.new("RGB", (20, 20), RED)


def test_next_space_is_tried_when_one_is_broken(settings, tmp_path):
    engine, made = space_engine(
        settings, tmp_path, "zhengchong/CatVTON, Kwai-Kolors/Kolors-Virtual-Try-On, yisol/IDM-VTON",
        {"zhengchong/CatVTON": "broken", "Kwai-Kolors/Kolors-Virtual-Try-On": "empty",
         "yisol/IDM-VTON": "ok"})
    img = engine.dress(*person_and_garment(), "upper")
    assert img.getpixel((0, 0)) == (0, 200, 0)                   # the picture the Space made
    assert engine.last_space == "yisol/IDM-VTON"
    assert made["yisol/IDM-VTON"].calls == ["/tryon"]


def test_spaces_that_cant_dress_the_kind_are_skipped(settings, tmp_path):
    from app.tryon import TryOnBusy
    engine, made = space_engine(settings, tmp_path, "yisol/IDM-VTON, someone/copy=catvton",
                                {"yisol/IDM-VTON": "ok", "someone/copy": "busy"})
    try:
        engine.dress(*person_and_garment(), "lower")
        raise AssertionError("should fail")
    except TryOnBusy as e:
        assert "yisol/IDM-VTON: can't dress 'lower'" in str(e) and "someone/copy: quota" in str(e)
    assert "yisol/IDM-VTON" not in made                            # never called for trousers
    assert made["someone/copy"].calls == ["/submit_function"]      # the CatVTON adapter


def test_unknown_space_needs_an_adapter():
    import pytest
    from app.tryon import parse_spaces
    assert parse_spaces("a/My-CatVTON, b/x=kolors") == [("a/My-CatVTON", "catvton"), ("b/x", "kolors")]
    with pytest.raises(ValueError, match="no adapter"):
        parse_spaces("someone/try-on")
