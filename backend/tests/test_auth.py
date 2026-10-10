from tests.conftest import sign_up


def test_register_login_and_profile(client):
    headers = sign_up(client)
    me = client.get("/me", headers=headers).json()
    assert me["email"] == "amira@example.com" and me["name"] == "Amira"
    assert me["min_coverage"] is None and me["language"] == "en" and me["role"] == "user"

    r = client.post("/auth/login", json={"email": "AMIRA@example.com", "password": "secret-pass"})
    assert r.status_code == 200 and r.json()["token"]

    r = client.put("/me", json={"min_coverage": 4, "language": "ar"}, headers=headers)
    assert r.json()["min_coverage"] == 4 and r.json()["language"] == "ar"


def test_duplicate_email_and_wrong_password(client):
    sign_up(client)
    r = client.post("/auth/register", json={"email": "amira@example.com", "password": "another-pw",
                                            "name": "X", "gender": "women"})
    assert r.status_code == 409
    wrong_pw = client.post("/auth/login", json={"email": "amira@example.com", "password": "nope-nope"})
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": "nope-nope"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()          # does not reveal which emails exist


def test_protected_endpoints_need_a_valid_token(client):
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    assert client.get("/items").status_code == 401


def test_validation(client):
    r = client.post("/auth/register", json={"email": "bad", "password": "short", "name": "",
                                            "gender": "women"})
    assert r.status_code == 422
    headers = sign_up(client)
    assert client.put("/me", json={"language": "de"}, headers=headers).status_code == 422
    assert client.put("/me", json={"min_coverage": 9}, headers=headers).status_code == 422


def test_gender_is_required_and_editable(client):
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "secret-pass",
                                            "name": "X"})
    assert r.status_code == 422                                   # no gender
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "secret-pass",
                                            "name": "X", "gender": "other"})
    assert r.status_code == 422
    headers = sign_up(client, gender="men")
    me = client.get("/me", headers=headers).json()
    assert me["gender"] == "men" and me["needs_gender"] is False
    assert client.put("/me", json={"gender": "women"}, headers=headers).json()["gender"] == "women"
    assert client.put("/me", json={"gender": "x"}, headers=headers).status_code == 422


def test_old_accounts_are_asked_once(client):
    headers = sign_up(client)
    client.app.state.db.users.update_many({}, {"$unset": {"profile.gender": ""}})   # an account from before
    me = client.get("/me", headers=headers).json()
    assert me["gender"] is None and me["needs_gender"] is True
    r = client.get("/outfits/suggest", headers=headers)
    assert r.status_code == 409 and r.json()["detail"] == "gender_required"
    client.put("/me", json={"gender": "women"}, headers=headers)
    assert client.get("/outfits/suggest", headers=headers).status_code == 200


def test_sub_category_gender_table_is_public(client):
    table = client.get("/vocab/sub-category-gender").json()
    assert table["skirt"] == "women" and table["tie"] == "men" and table["jeans"] == "unisex"
