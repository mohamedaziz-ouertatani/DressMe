"""Gender in the routes: the user's rules and a {gender, unisex} filter on everything
from outside the wardrobe; the wardrobe itself is never filtered."""

import sys

from app.config import SRC_DIRS
from tests.conftest import BLACK, BLUE, GREEN, RED, sign_up, upload

sys.path[:0] = [str(d) for d in SRC_DIRS]
import compatibility as C  # noqa: E402


def test_similar_filters_the_catalogue_unless_all(client):
    headers = sign_up(client, gender="men")
    item = upload(client, headers, RED)
    assert client.get(f"/similar?item_id={item['id']}", headers=headers).status_code == 200
    assert client.app.state.catalog.last_genders == {"men", "unisex"}
    client.get(f"/similar?item_id={item['id']}&gender=all", headers=headers)
    assert client.app.state.catalog.last_genders is None


def test_wardrobe_is_never_filtered(client):
    headers = sign_up(client, gender="men")
    dress = upload(client, headers, GREEN)                 # a "women's" piece in a man's wardrobe
    assert dress["sub_category"] == "dress"
    assert len(client.get("/items", headers=headers).json()) == 1
    for rgb in (RED, BLUE, BLACK):
        upload(client, headers, rgb)
    r = client.get("/outfits/suggest", headers=headers)
    assert r.status_code == 200
    scored = client.post("/outfits/score", json={"item_ids": [dress["id"]]}, headers=headers)
    assert scored.status_code == 200                       # a man's dress still counts as his
    assert dress["id"] in {i["id"] for i in scored.json()["items"]}


def test_outfit_routes_use_the_users_rules(client, monkeypatch):
    seen = []
    real = C.score_outfit
    monkeypatch.setattr(C, "score_outfit",
                        lambda items, rules=C.RULES, **kw: seen.append(rules.gender) or real(items, rules, **kw))
    headers = sign_up(client, gender="men")
    ids = [upload(client, headers, rgb)["id"] for rgb in (RED, BLUE, BLACK)]
    assert client.post("/outfits/score", json={"item_ids": ids}, headers=headers).status_code == 200
    assert seen and set(seen) == {"men"}


def test_limits_follow_the_gender(client):
    headers = sign_up(client, gender="women")
    limits = client.get("/outfits/limits", headers=headers).json()["max_items"]
    assert limits == {c: int(n) for c, n in C.rules_for("women").max_items.items()}
