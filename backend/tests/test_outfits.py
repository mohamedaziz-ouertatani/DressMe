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
    assert client.get("/similar", headers=headers).status_code == 422


def test_candidates_are_private(client):
    amira = sign_up(client)
    youssef = sign_up(client, "youssef@example.com", "Youssef")
    cand = client.post("/analyze", files={"photo": photo(RED)}, headers=amira).json()
    r = client.post("/buy-advice", json={"candidate_id": cand["id"]}, headers=youssef)
    assert r.status_code == 404
    assert client.get(f"/similar?candidate_id={cand['id']}", headers=youssef).status_code == 404
