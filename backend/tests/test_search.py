"""POST /search (routers/search.py): contract tests with the usual fakes, no real model.

The fake analyzer gives a fixed vector per text and, for a picture, the same vector it gives that picture when it is
added: so a photo search finds the piece of the same colour at similarity 1.0. The golden user's pieces have real
FashionCLIP vectors, so the text searches on them check the shape and the ownership, not the quality (the quality is
measured by src/phase4/calibrate_search.py)."""

import pytest

import search
from tests.conftest import BLUE, RED, photo, sign_up, upload
from tests.test_golden import golden  # noqa: F401  (fixture: the frozen wardrobe of the golden user)


@pytest.fixture
def rules(monkeypatch):
    """Change the team's numbers for one test: rules(text_cut=-1) makes every piece a close match."""
    def change(**overrides):
        monkeypatch.setattr(search, "load_rules", lambda: {**real, **overrides})
    real = search.load_rules()
    return change


def ask(client, headers, **form):
    return client.post("/search", data={k: str(v) for k, v in form.items()}, headers=headers)


def ids(response):
    return [r["item"]["id"] for r in response.json()["results"]]


def test_text_search_returns_only_the_users_own_pieces_in_the_documented_shape(golden, rules):  # noqa: F811
    rules(text_cut=-1)                                             # every piece counts as close
    mine = {str(d["_id"]) for d in golden.db.items.find({})}
    r = ask(golden.client, golden.headers, text="black jeans")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"mode", "results", "nothing_close", "skipped_no_vector"}
    assert body["mode"] == "text" and body["nothing_close"] is False and body["skipped_no_vector"] == 0
    assert len(body["results"]) == 8                               # default_limit
    first = body["results"][0]
    assert set(first) == {"item", "similarity", "close"} and first["close"] is True
    assert {"id", "category", "sub_category", "colour", "pattern", "image_url"} <= set(first["item"])
    assert "vector" not in first["item"]                           # item_out is a whitelist
    sims = [r["similarity"] for r in body["results"]]
    assert sims == sorted(sims, reverse=True)
    assert set(ids(r)) <= mine
    assert len(ids(ask(golden.client, golden.headers, text="black jeans", limit=3))) == 3


def test_nothing_close_is_said_and_the_nearest_few_still_come_back(golden, rules):  # noqa: F811
    rules(text_cut=2.0)                                            # no cosine reaches 2
    body = ask(golden.client, golden.headers, text="black jeans").json()
    assert body["nothing_close"] is True
    assert len(body["results"]) == 3 and not any(r["close"] for r in body["results"])    # closest_anyway


def test_another_users_pieces_never_appear(golden, rules):  # noqa: F811
    rules(text_cut=-1)
    other = sign_up(golden.client, "other@example.com", "Other")
    theirs = upload(golden.client, other, RED)["id"]
    r = ask(golden.client, golden.headers, text="red shirt", limit=20)
    assert len(ids(r)) == 17 and theirs not in ids(r)              # all 17 golden pieces, none of theirs
    r = ask(golden.client, other, text="red shirt", limit=20)
    assert ids(r) == [theirs]                                      # and the other way round


def test_text_and_photo_together_or_neither_is_a_400_with_a_code(client):
    headers = sign_up(client)
    both = client.post("/search", data={"text": "red"}, files={"photo": photo(RED)}, headers=headers)
    assert both.status_code == 400 and both.json()["detail"] == "search_text_and_photo"
    for form in ({}, {"text": "   "}):
        r = client.post("/search", data=form, headers=headers)
        assert r.status_code == 400 and r.json()["detail"] == "search_need_text_or_photo"
    assert ask(client, headers, text="x" * 121).json()["detail"] == "search_text_too_long"
    assert ask(client, headers, text=",,").json()["detail"] == "search_text_no_words"
    assert ask(client, headers, text="red", limit=0).status_code == 422
    assert ask(client, headers, text="red", limit=21).status_code == 422
    assert client.post("/search", data={"text": "red"}).status_code == 401           # no token


def test_a_photo_search_finds_the_matching_piece_and_saves_nothing(client, settings):
    headers = sign_up(client)
    red, blue = upload(client, headers, RED)["id"], upload(client, headers, BLUE)["id"]
    db = client.app.state.db
    files = lambda: sorted(str(p) for p in settings.storage_dir.rglob("*") if p.is_file())      # noqa: E731
    before = (db.items.count_documents({}), db.candidates.count_documents({}), files())

    r = client.post("/search", files={"photo": photo(RED)}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "photo" and body["nothing_close"] is False
    assert ids(r)[0] == red and body["results"][0]["close"] is True and body["results"][0]["similarity"] > 0.999
    assert set(ids(r)) == {red, blue}
    assert (db.items.count_documents({}), db.candidates.count_documents({}), files()) == before   # nothing saved

    assert client.post("/search", files={"photo": ("x.jpg", b"not a picture", "image/jpeg")},
                       headers=headers).status_code == 400


def test_the_log_keeps_the_numbers_but_never_the_words(client):
    headers = sign_up(client)
    upload(client, headers, RED)
    ask(client, headers, text="my secret words")
    event = client.app.state.db.events.find_one({"type": "search"})
    assert set(event) == {"_id", "type", "user_id", "at", "mode", "results", "nothing_close", "ms"}
    assert event["mode"] == "text" and event["results"] >= 1 and isinstance(event["ms"], int)
    assert "secret" not in str(event)
