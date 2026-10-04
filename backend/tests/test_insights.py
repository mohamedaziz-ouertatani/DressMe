from tests.conftest import BLACK, BLUE, GREEN, RED, sign_up, upload


def test_insights_empty_wardrobe(client):
    headers = sign_up(client)
    body = client.get("/insights", headers=headers).json()
    assert body["total"] == 0 and body["outfits"]["good"] == 0
    assert body["missing"] == ["main", "shoes"]
    assert body["twins"] == [] and body["unmatched"] == []


def test_insights_counts_gaps_and_twins(client):
    headers = sign_up(client)
    top = upload(client, headers, RED)
    twin = upload(client, headers, RED)          # same photo again: a near twin
    upload(client, headers, BLUE)
    body = client.get("/insights", headers=headers).json()

    assert body["total"] == 3
    assert body["categories"] == [{"category": "top", "count": 2}, {"category": "bottom", "count": 1}]
    assert {"colour": "red", "count": 2, "neutral": False} in body["colours"]
    assert body["to_confirm"] == {"colour": 0, "coverage": 3, "season": 3, "usage": 3}
    assert body["missing"] == ["shoes"]
    # one more bottom pairs with both tops; one more top with the single bottom
    assert body["new_pairs"] == {"top": 1, "bottom": 2}
    assert len(body["twins"]) == 1
    assert {i["id"] for i in body["twins"][0]["items"]} == {top["id"], twin["id"]}


def test_insights_unmatched_and_modesty(client):
    headers = sign_up(client)
    for rgb in (RED, BLUE, BLACK):
        upload(client, headers, rgb)
    dress = upload(client, headers, GREEN)
    body = client.get("/insights", headers=headers).json()
    assert body["outfits"]["good"] >= 0 and body["outfits"]["complete"] is True
    used = {i["id"] for i in body["versatile"]} | {i["id"] for i in body["unmatched"]}
    assert used, "every main piece is either versatile or unmatched"

    # under the modesty level: left out of the outfits, counted as filtered
    client.patch(f"/items/{dress['id']}", json={"coverage": 2}, headers=headers)
    client.put("/me", json={"min_coverage": 4}, headers=headers)
    body = client.get("/insights", headers=headers).json()
    assert body["filtered"] == 1
    assert dress["id"] not in {i["id"] for i in body["unmatched"] + body["versatile"]}


def test_insights_is_private(client):
    headers = sign_up(client)
    upload(client, headers, RED)
    other = sign_up(client, "other@example.com", "Other")
    assert client.get("/insights", headers=other).json()["total"] == 0
    assert client.get("/insights").status_code == 401
