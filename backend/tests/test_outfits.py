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


def test_sub_category_pairing_lowers_structure():
    """mappings/sub_category_pairing.csv: a blazer with track pants scores lower than
    with trousers, and the reason names the pair."""
    import compatibility
    shoes = {"id": "f", "category": "shoes", "sub_category": "sneakers"}
    blazer = {"id": "b", "category": "outerwear", "sub_category": "blazer"}
    shirt = {"id": "s", "category": "top", "sub_category": "shirt"}
    good = compatibility.score_outfit([shirt, blazer, shoes, {"id": "t", "category": "bottom", "sub_category": "trousers"}])
    bad = compatibility.score_outfit([shirt, blazer, shoes, {"id": "p", "category": "bottom", "sub_category": "track-pants"}])
    assert good["parts"]["structure"] == 1.0 and good["reasons"] == []
    assert bad["parts"]["structure"] < 0.5 and bad["score"] < good["score"]
    assert "blazer and track-pants don't go together" in bad["reasons"]
    # suggestions prefer the pair that goes together
    tee = {"id": "e", "category": "top", "sub_category": "t-shirt"}
    trousers = {"id": "t", "category": "bottom", "sub_category": "trousers"}
    pants = {"id": "p", "category": "bottom", "sub_category": "track-pants"}
    best = compatibility.suggest_outfits([shirt, tee, trousers, pants, shoes, blazer], n=1)[0]
    assert "track-pants" not in {i["sub_category"] for i in best["items"]} or "blazer" not in {i["sub_category"] for i in best["items"]}


def test_beach_outfits_use_swimwear_only():
    """Swimwear is left out of everyday suggestions; beach=True builds outfits around it."""
    import compatibility
    wardrobe = [{"id": "w", "category": "swimwear", "sub_category": "swimsuit"},
                {"id": "t", "category": "top", "sub_category": "t-shirt"},
                {"id": "b", "category": "bottom", "sub_category": "shorts"},
                {"id": "f", "category": "shoes", "sub_category": "flip-flops"},
                {"id": "h", "category": "shoes", "sub_category": "formal-shoes"}]
    everyday = compatibility.suggest_outfits(wardrobe, {}, n=5)
    assert everyday and all("w" not in {i["id"] for i in o["items"]} for o in everyday)
    beach = compatibility.suggest_outfits(wardrobe, {"beach": True, "season": "summer"}, n=5)
    assert beach and all(o["items"][0]["id"] == "w" for o in beach)
    assert all(i["category"] != "shoes" for o in beach for i in o["items"])   # no shoes
    assert beach[0]["parts"]["structure"] == 1.0 and "no shoes" not in beach[0]["reasons"]
    # in winter the swimsuit is filtered out, so there is no beach outfit
    assert compatibility.suggest_outfits(wardrobe, {"beach": True, "season": "winter"}, n=5) == []


def test_suggest_beach_endpoint(client):
    headers = sign_up(client)
    wardrobe(client, headers)                       # no swimwear: no beach outfit
    assert client.get("/outfits/suggest?beach=true", headers=headers).json() == []


def test_outfit_answers_explain_the_score(client):
    headers = sign_up(client)
    w = wardrobe(client, headers)
    body = client.post("/outfits/score", json={"item_ids": [w["top"]["id"], w["jeans"]["id"],
                                                            w["shoes"]["id"]]}, headers=headers).json()
    assert round(sum(c["points"] for c in body["contributions"]), 1) == body["score"]
    assert {c["part"] for c in body["contributions"]} == {"style", "colour", "pattern", "structure"}
    assert ("+", "structure_complete") in [(e["sign"], e["code"]) for e in body["explanations"]]
    for o in client.get("/outfits/suggest?n=3", headers=headers).json():
        assert "contributions" in o and "explanations" in o


def test_outfit_explain_endpoint(client):
    headers = sign_up(client)
    w = wardrobe(client, headers)
    ids = [w["top"]["id"], w["jeans"]["id"], w["shoes"]["id"]]
    r = client.post("/outfits/explain", json={"item_ids": ids}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert [s["item_id"] for s in body["swaps"]] == ids
    assert len(body["pair_map"]) == 3
    assert body["weakest"] in ids + [None]
    other = sign_up(client, "other@example.com", "Other")
    assert client.post("/outfits/explain", json={"item_ids": ids}, headers=other).status_code == 404
    two_jeans = upload(client, headers, BLUE)
    clash = client.post("/outfits/explain", json={"item_ids": [w["jeans"]["id"], two_jeans["id"]]}, headers=headers)
    assert clash.status_code == 422


def test_buy_advice_explains_the_verdict(client):
    headers = sign_up(client)
    wardrobe(client, headers)
    cand = client.post("/analyze", files={"photo": photo(RED)}, headers=headers).json()
    advice = client.post("/buy-advice", json={"candidate_id": cand["id"]}, headers=headers).json()
    why = advice["explanation"]
    assert why["path"]["verdict"] == advice["verdict"] and why["path"]["good"] == advice["good_outfits"]
    for b in why["beats"]:
        assert b["owned"] is None or b["owned"]["image_url"].startswith("/items/")
    for t in why["twins"]:
        assert t["item"]["id"] and 0 <= t["similarity"] <= 1.0001
    assert all("contributions" in o for o in advice["best"])


def test_chat_tools_keep_the_short_outfit_form():
    from app.wardrobe import outfit_out
    result = {"score": 50.0, "parts": {"style": 0.5, "colour": None, "pattern": None, "structure": 0.5},
              "reasons": [], "problems": [], "items": []}
    assert "contributions" not in outfit_out(result, {})
    assert "contributions" in outfit_out(result, {}, explain=True)


def test_similar_explains_each_look_alike(client):
    headers = sign_up(client)
    first = upload(client, headers, RED)
    upload(client, headers, RED)                                       # a second red t-shirt
    sim = client.get(f"/similar?item_id={first['id']}&k=3", headers=headers).json()
    twin = sim["wardrobe"][0]["why"]
    assert {"field": "sub_category", "value": "t-shirt"} in twin["shared"]
    assert {"field": "colour", "value": "red"} in twin["shared"]
    assert set(twin) == {"shared", "differs", "both", "contrast"}
    for group in ("catalog", "shop"):
        assert all("why" in hit for hit in sim[group])
    assert all(isinstance(c, str) for c in twin["both"])
