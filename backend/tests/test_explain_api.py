"""GET /items/{id}/explain and /candidates/{id}/explain (fake analyzer)."""

from bson import ObjectId

from tests.conftest import BLUE, RED, photo, sign_up, upload

FIELDS = {"category", "sub_category", "pattern", "colour"}


def test_explain_an_item(client):
    headers = sign_up(client)
    item = upload(client, headers, RED)
    r = client.get(f"/items/{item['id']}/explain", headers=headers)
    assert r.status_code == 200
    fields = r.json()["fields"]
    assert set(fields) == FIELDS
    cat = fields["category"]
    assert (cat["value"], cat["conf"], cat["shown"]) == ("top", 0.95, "top")
    assert cat["heatmap"].startswith("data:image/jpeg;base64,")
    assert cat["alternatives"][0]["value"] == "top"          # old-style item: computed from the photo
    assert cat["unsure"] is False and cat["corrected"] is False
    colour = fields["colour"]
    assert colour["pixels"].startswith("data:image/jpeg;base64,") and colour["reliable"] is True


def test_explain_one_alternative(client):
    headers = sign_up(client)
    item = upload(client, headers, BLUE)
    r = client.get(f"/items/{item['id']}/explain?head=pattern&value=striped", headers=headers)
    assert r.status_code == 200
    fields = r.json()["fields"]
    assert list(fields) == ["pattern"] and fields["pattern"]["shown"] == "striped"
    assert fields["pattern"]["value"] == "solid"              # the stored answer is unchanged


def test_explain_bad_requests(client):
    headers = sign_up(client)
    item = upload(client, headers, RED)
    base = f"/items/{item['id']}/explain"
    assert client.get(base + "?head=brand", headers=headers).status_code == 422
    assert client.get(base + "?head=pattern&value=nonsense", headers=headers).status_code == 422
    assert client.get(base + "?value=striped", headers=headers).status_code == 422


def test_explain_is_private(client):
    owner = sign_up(client)
    item = upload(client, owner, RED)
    other = sign_up(client, email="sami@example.com", name="Sami")
    assert client.get(f"/items/{item['id']}/explain", headers=other).status_code == 404


def test_explain_marks_corrected_fields(client):
    headers = sign_up(client)
    item = upload(client, headers, RED)
    client.patch(f"/items/{item['id']}", json={"colour": "navy"}, headers=headers)
    fields = client.get(f"/items/{item['id']}/explain", headers=headers).json()["fields"]
    assert fields["colour"]["corrected"] is True and fields["colour"]["value"] == "red"


def test_explain_a_scan(client):
    headers = sign_up(client)
    cand = client.post("/analyze", files={"photo": photo(RED)}, headers=headers).json()
    r = client.get(f"/candidates/{cand['id']}/explain?head=category", headers=headers)
    assert r.status_code == 200 and list(r.json()["fields"]) == ["category"]


def test_stored_alternatives_are_used(client):
    """An item analysed by the real Analyzer keeps its alternatives; explain uses those."""
    headers = sign_up(client)
    item = upload(client, headers, RED)
    stored = [{"value": "top", "conf": 0.55}, {"value": "dress", "conf": 0.45}]
    client.app.state.db.items.update_one({"_id": ObjectId(item["id"])},
                                         {"$set": {"predicted.category.alternatives": stored}})
    cat = client.get(f"/items/{item['id']}/explain?head=category", headers=headers).json()["fields"]["category"]
    assert cat["alternatives"] == stored and cat["unsure"] is True     # 0.55 < 0.6 and a 0.10 lead
