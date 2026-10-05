from tests.conftest import BLACK, BLUE, GREEN, RED, WHITE, photo, sign_up, upload


def wardrobe(client, headers):
    return {name: upload(client, headers, rgb) for name, rgb in
            [("top", RED), ("jeans", BLUE), ("shoes", BLACK), ("dress", GREEN), ("bag", WHITE)]}


def test_score_outfit(client):
    headers = sign_up(client)
    w = wardrobe(client, headers)
    r = client.post("/outfits/score", json={"item_ids": [w["top"]["id"], w["jeans"]["id"],
                                                         w["shoes"]["id"]]}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["score"] <= 100 and body["parts"]["structure"] == 1.0
    assert [i["category"] for i in body["items"]] == ["top", "bottom", "shoes"]
    # a top alone is not a wearable outfit
    alone = client.post("/outfits/score", json={"item_ids": [w["top"]["id"]]}, headers=headers).json()
    assert "missing a top or a bottom" in alone["reasons"]


def test_outfit_feedback_is_private_and_replaceable(client):
    headers = sign_up(client)
    w = wardrobe(client, headers)
    item_ids = [w["top"]["id"], w["jeans"]["id"], w["shoes"]["id"]]
    r = client.post("/outfits/feedback",
                    json={"item_ids": item_ids, "rating": 1}, headers=headers)
    assert r.status_code == 200
    assert r.json() == {"item_ids": sorted(item_ids), "rating": 1}
    r = client.post("/outfits/feedback",
                    json={"item_ids": list(reversed(item_ids)), "rating": -1}, headers=headers)
    assert r.status_code == 200
    suggested = client.get("/outfits/suggest?n=5", headers=headers)
    assert suggested.status_code == 200
    assert all(sorted(i["id"] for i in outfit["items"]) != sorted(item_ids)
               for outfit in suggested.json())

    other = sign_up(client, "other@example.com", "Other")
    r = client.post("/outfits/feedback",
                    json={"item_ids": item_ids, "rating": 1}, headers=other)
    assert r.status_code == 404


def test_suggest_respects_modesty(client):
    headers = sign_up(client)
    w = wardrobe(client, headers)
    outfits = client.get("/outfits/suggest?n=5", headers=headers).json()
    used = {i["id"] for o in outfits for i in o["items"]}
    assert w["dress"]["id"] in used and w["top"]["id"] in used

    client.patch(f"/items/{w['dress']['id']}", json={"coverage": 2}, headers=headers)
    client.put("/me", json={"min_coverage": 4}, headers=headers)
    outfits = client.get("/outfits/suggest?n=5", headers=headers).json()
    assert w["dress"]["id"] not in {i["id"] for o in outfits for i in o["items"]}
    assert client.get("/outfits/suggest?season=spring", headers=headers).status_code == 422


def test_complete_outfit(client):
    headers = sign_up(client)
    w = wardrobe(client, headers)
    r = client.post("/outfits/complete", json={"item_ids": [w["top"]["id"], w["jeans"]["id"]]},
                    headers=headers)
    ranked = r.json()
    assert ranked[0]["item"]["category"] == "shoes"       # shoes make it wearable
    assert all(x["item"]["id"] not in (w["top"]["id"], w["jeans"]["id"]) for x in ranked)


def test_buy_advice_and_similar(client):
    headers = sign_up(client)
    w = wardrobe(client, headers)
    cand = client.post("/analyze", files={"photo": photo(BLUE)}, headers=headers).json()
    r = client.post("/buy-advice", json={"candidate_id": cand["id"]}, headers=headers)
    assert r.status_code == 200
    advice = r.json()
    assert advice["verdict"] in ("buy", "think", "skip")
    # the same jeans twice: flagged as a near-twin of what you own
    assert any("very similar" in reason for reason in advice["reasons"])
    # corrections are applied before advising
    r = client.post("/buy-advice", json={"candidate_id": cand["id"],
                                         "corrections": {"colour": "black"}}, headers=headers)
    assert r.json()["candidate"]["colour"] == "black"

    sim = client.get(f"/similar?candidate_id={cand['id']}&k=3", headers=headers).json()
    assert sim["wardrobe"][0]["id"] == w["jeans"]["id"]
    assert len(sim["catalog"]) == 3 and sim["catalog"][0]["image_url"].startswith("/catalog/")
    assert client.get(sim["catalog"][0]["image_url"], headers=headers).status_code == 200
    assert client.get("/catalog/fp_unknown/image", headers=headers).status_code == 404
    # H&M products to buy, same category, with a picture
    assert len(sim["shop"]) == 3 and sim["shop"][0]["category"] == cand["category"]
    assert sim["shop"][0]["name"] and sim["shop"][0]["shop"] == "H&M"
    assert client.get(sim["shop"][0]["image_url"], headers=headers).status_code == 200
    assert client.get("/similar", headers=headers).status_code == 422


def test_candidates_are_private(client):
    amira = sign_up(client)
    youssef = sign_up(client, "youssef@example.com", "Youssef")
    cand = client.post("/analyze", files={"photo": photo(RED)}, headers=amira).json()
    r = client.post("/buy-advice", json={"candidate_id": cand["id"]}, headers=youssef)
    assert r.status_code == 404
    assert client.get(f"/similar?candidate_id={cand['id']}", headers=youssef).status_code == 404


def test_same_piece_twice_is_refused(client):
    headers = sign_up(client)
    w = wardrobe(client, headers)
    jeans2 = upload(client, headers, BLUE)              # a second pair of jeans
    pair = [w["jeans"]["id"], jeans2["id"]]
    for path in ("/outfits/score", "/outfits/complete"):
        r = client.post(path, json={"item_ids": [w["top"]["id"], *pair]}, headers=headers)
        assert r.status_code == 422 and "jeans" in r.json()["detail"]
    # a dress with a top is still allowed (different categories)
    r = client.post("/outfits/score", json={"item_ids": [w["top"]["id"], w["dress"]["id"]]},
                    headers=headers)
    assert r.status_code == 200
    # completing top + jeans never proposes the other jeans
    ranked = client.post("/outfits/complete", json={"item_ids": [w["top"]["id"], w["jeans"]["id"]]},
                         headers=headers).json()
    assert jeans2["id"] not in {x["item"]["id"] for x in ranked}
    limits = client.get("/outfits/limits", headers=headers).json()
    assert limits["max_items"]["top"] == 1 and limits["max_items"]["accessory"] == 4


def test_season_defaults_from_the_team_rules():
    """mappings/item_seasons.csv: shorts in summer, long pants and jackets not in summer.
    An item's own season always wins; a main piece is kept when it is the only choice."""
    import compatibility
    shorts = {"id": "s", "category": "bottom", "sub_category": "shorts"}
    jeans = {"id": "j", "category": "bottom", "sub_category": "jeans"}
    jacket = {"id": "k", "category": "outerwear", "sub_category": "jacket"}
    tee = {"id": "t", "category": "top", "sub_category": "t-shirt"}
    ids = lambda kept: {i["id"] for i in kept}

    kept, removed = compatibility.filter_items([shorts, jeans, jacket, tee], {"season": "summer"})
    assert ids(kept) == {"s", "t"} and set(removed) == {"j", "k"}
    kept, _ = compatibility.filter_items([shorts, jeans, jacket, tee], {"season": "winter"})
    assert ids(kept) == {"j", "k", "t"}
    # only jeans in summer: kept (better than no outfit); a lone jacket is not
    kept, _ = compatibility.filter_items([jeans, jacket, tee], {"season": "summer"})
    assert ids(kept) == {"j", "t"}
    # the user's own season beats the default
    kept, _ = compatibility.filter_items([dict(jeans, season={"summer"}), shorts], {"season": "summer"})
    assert ids(kept) == {"j", "s"}
    # no season chosen: nothing removed
    assert len(compatibility.filter_items([shorts, jeans, jacket], {})[0]) == 3
    # a swimsuit is never suggested outside summer, even as the only full piece
    swimsuit = {"id": "w", "category": "swimwear", "sub_category": "swimsuit"}
    assert compatibility.filter_items([swimsuit], {"season": "winter"})[0] == []
