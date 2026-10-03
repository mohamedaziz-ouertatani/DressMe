from tests.conftest import BLUE, RED, photo, sign_up, upload


def test_upload_is_analysed_and_listed(client, settings):
    headers = sign_up(client)
    item = upload(client, headers, RED)
    assert (item["category"], item["sub_category"], item["colour"]) == ("top", "t-shirt", "red")
    assert item["predicted"]["category"] == {"value": "top", "conf": 0.95}
    assert item["corrected"] == [] and "vector" not in item
    upload(client, headers, BLUE)
    assert [i["category"] for i in client.get("/items", headers=headers).json()] == ["top", "bottom"]
    assert len(client.get("/items?category=bottom", headers=headers).json()) == 1
    stored = list((settings.storage_dir).rglob("*.jpg"))
    assert len(stored) == 2


def test_not_a_picture(client):
    headers = sign_up(client)
    r = client.post("/items", files={"photo": ("x.jpg", b"not an image", "image/jpeg")}, headers=headers)
    assert r.status_code == 400


def test_user_corrections(client):
    headers = sign_up(client)
    item = upload(client, headers, RED)
    r = client.patch(f"/items/{item['id']}", json={"colour": "navy", "coverage": 4,
                                                   "season": ["summer"]}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["colour"] == "navy" and body["coverage"] == 4
    assert body["corrected"] == ["colour", "coverage", "season"]
    assert body["predicted"]["colour"]["value"] == "red"          # the model's guess is kept

    # changing the category clears a sub_category that no longer fits
    body = client.patch(f"/items/{item['id']}", json={"category": "outerwear"}, headers=headers).json()
    assert body["category"] == "outerwear" and body["sub_category"] == ""
    # a sub_category of another category is refused
    r = client.patch(f"/items/{item['id']}", json={"sub_category": "jeans"}, headers=headers)
    assert r.status_code == 422
    # values outside the schema are refused
    assert client.patch(f"/items/{item['id']}", json={"colour": "rainbow"}, headers=headers).status_code == 422
    assert client.patch(f"/items/{item['id']}", json={"season": ["spring"]}, headers=headers).status_code == 422


def test_image_and_delete(client, settings):
    headers = sign_up(client)
    item = upload(client, headers, RED)
    token = headers["Authorization"].split()[1]
    r = client.get(item["image_url"], headers=headers)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    # a token in the URL is never accepted (it would leak into logs and history)
    assert client.get(f"{item['image_url']}?token={token}").status_code == 401
    assert client.delete(f"/items/{item['id']}", headers=headers).status_code == 204
    assert client.get(f"/items/{item['id']}", headers=headers).status_code == 404
    assert not list(settings.storage_dir.rglob("*.jpg"))


def test_users_cannot_see_each_other(client):
    amira = sign_up(client)
    youssef = sign_up(client, "youssef@example.com", "Youssef")
    item = upload(client, amira, RED)
    assert client.get("/items", headers=youssef).json() == []
    for method, url in [("get", f"/items/{item['id']}"), ("delete", f"/items/{item['id']}"),
                        ("get", f"/items/{item['id']}/image")]:
        assert getattr(client, method)(url, headers=youssef).status_code == 404
    assert client.patch(f"/items/{item['id']}", json={"colour": "black"}, headers=youssef).status_code == 404
    assert client.get("/items/not-an-id", headers=amira).status_code == 404


def test_analyze_does_not_add_to_wardrobe(client):
    headers = sign_up(client)
    r = client.post("/analyze", files={"photo": photo(BLUE)}, headers=headers)
    assert r.status_code == 201 and r.json()["category"] == "bottom" and "image_url" not in r.json()
    assert client.get("/items", headers=headers).json() == []
