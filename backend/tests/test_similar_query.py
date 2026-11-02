"""GET /similar answers `query`: the piece the look-alikes are compared with (shown at the top of the Similar page)."""

from bson import ObjectId

from tests.conftest import BLUE, RED, photo, sign_up, upload

QUERY_FIELDS = {"id", "kind", "image_url", "category", "sub_category", "colour"}


def test_query_for_a_wardrobe_item(client):
    headers = sign_up(client)
    item = upload(client, headers, RED)
    upload(client, headers, BLUE)
    body = client.get(f"/similar?item_id={item['id']}", headers=headers).json()
    assert body["query"] == {"id": item["id"], "kind": "item", "image_url": f"/items/{item['id']}/image",
                             "category": "top", "sub_category": "t-shirt", "colour": "red"}
    assert client.get(body["query"]["image_url"], headers=headers).status_code == 200
    assert {"wardrobe", "catalog", "shop", "listings"} <= set(body)          # the rows are unchanged


def test_query_for_a_scan(client):
    headers = sign_up(client)
    cand = client.post("/analyze", files={"photo": photo(BLUE)}, headers=headers).json()
    body = client.get(f"/similar?candidate_id={cand['id']}", headers=headers).json()
    assert set(body["query"]) == QUERY_FIELDS
    assert body["query"]["kind"] == "candidate" and body["query"]["image_url"] == f"/candidates/{cand['id']}/image"
    assert body["query"]["category"] == "bottom"
    assert "vector" not in body["query"] and "predicted" not in body["query"]


def test_missing_piece_is_404_as_before(client):
    headers = sign_up(client)
    cand = client.post("/analyze", files={"photo": photo(RED)}, headers=headers).json()
    client.app.state.db.candidates.delete_one({"_id": ObjectId(cand["id"])})     # an expired scan
    assert client.get(f"/similar?candidate_id={cand['id']}", headers=headers).status_code == 404
    assert client.get(f"/similar?item_id={ObjectId()}", headers=headers).status_code == 404
