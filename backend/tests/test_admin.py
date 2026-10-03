import shutil

import pytest
from pymongo import MongoClient

import compatibility
from app.config import ROOT
from tests.conftest import BLACK, BLUE, RED, TEST_DB, photo, sign_up, upload


def make_admin(settings, email):
    MongoClient(settings.mongo_url)[TEST_DB].users.update_one({"email": email}, {"$set": {"role": "admin"}})


@pytest.fixture
def admin(client, settings):
    headers = sign_up(client, "boss@example.com", "Boss")
    make_admin(settings, "boss@example.com")
    return headers


def test_only_admins_get_in(client, admin):
    user = sign_up(client)
    for url in ["/admin/stats", "/admin/model-quality", "/admin/users", "/admin/formula"]:
        assert client.get(url, headers=user).status_code == 403
        assert client.get(url).status_code == 401
        assert client.get(url, headers=admin).status_code == 200
    assert client.get("/me", headers=admin).json()["role"] == "admin"


def test_stats_count_what_users_do(client, admin):
    user = sign_up(client)
    upload(client, user, RED)
    upload(client, user, BLUE)
    cand = client.post("/analyze", files={"photo": photo(BLACK)}, headers=user).json()
    client.post("/buy-advice", json={"candidate_id": cand["id"]}, headers=user)
    client.post("/chat", json={"message": "hello"}, headers=user)
    s = client.get("/admin/stats?days=7", headers=admin).json()
    t = s["totals"]
    assert (t["users"], t["items"], t["upload"], t["scan"], t["verdict"], t["chat"]) == (2, 2, 2, 1, 1, 1)
    assert t["active_users"] == 1 and sum(s["verdicts"].values()) == 1
    assert len(s["per_day"]) == 1 and s["per_day"][0]["upload"] == 2


def test_model_quality_counts_real_corrections(client, admin):
    user = sign_up(client)
    a, b = upload(client, user, RED), upload(client, user, BLUE)
    client.patch(f"/items/{a['id']}", json={"colour": "navy"}, headers=user)       # model said red
    client.patch(f"/items/{b['id']}", json={"colour": "blue"}, headers=user)       # same as the model
    q = client.get("/admin/model-quality", headers=admin).json()
    colour = next(f for f in q["fields"] if f["field"] == "colour")
    assert colour["items"] == 2 and colour["corrected"] == 1 and colour["rate"] == 0.5
    assert colour["top_changes"] == [{"predicted": "red", "corrected": "navy", "n": 1}]
    category = next(f for f in q["fields"] if f["field"] == "category")
    assert category["corrected"] == 0
    stats = client.get("/admin/stats", headers=admin).json()
    assert stats["totals"]["correction"] == 2


def test_disable_and_delete_users(client, admin, settings):
    user = sign_up(client)
    upload(client, user, RED)
    users = client.get("/admin/users?q=amira", headers=admin).json()
    assert users["total"] == 1 and users["users"][0]["items"] == 1
    uid = users["users"][0]["id"]

    assert client.patch(f"/admin/users/{uid}", json={"disabled": True}, headers=admin).json()["disabled"]
    assert client.get("/items", headers=user).status_code == 403
    r = client.post("/auth/login", json={"email": "amira@example.com", "password": "secret-pass"})
    assert r.status_code == 403

    assert client.delete(f"/admin/users/{uid}", headers=admin).status_code == 204
    assert client.get("/admin/users?q=amira", headers=admin).json()["total"] == 0
    db = MongoClient(settings.mongo_url)[TEST_DB]
    assert db.items.count_documents({}) == 0 and db.events.count_documents({"user_id": {"$ne": None}}) == 0
    assert not list(settings.storage_dir.rglob("*.jpg"))
    # an admin cannot lock themselves out
    me = client.get("/me", headers=admin).json()["id"]
    assert client.patch(f"/admin/users/{me}", json={"disabled": True}, headers=admin).status_code == 400


@pytest.fixture
def temp_mappings(settings, tmp_path):
    """A copy of mappings/ so the real CSV files are never changed by the tests."""
    folder = tmp_path / "mappings"
    shutil.copytree(ROOT / "mappings", folder)
    settings.mappings_dir = folder
    yield folder
    compatibility.reload_rules()          # back to the real files


def test_formula_edit_writes_the_csv_and_reloads(client, admin, temp_mappings):
    f = client.get("/admin/formula", headers=admin).json()
    names = {s["name"]: s["value"] for s in f["settings"]}
    assert names["weight_style"] == 0.35 and f["colour_harmony"]
    r = client.put("/admin/formula", json={"values": {"weight_style": 0.6, "good_outfit": 65}}, headers=admin)
    assert r.status_code == 200 and "Commit" in r.json()["note"]
    text = (temp_mappings / "compatibility_weights.csv").read_text(encoding="utf-8")
    assert "weight_style,0.6," in text and "good_outfit,65," in text
    assert "REVIEW" in text                                  # notes are kept
    assert compatibility.RULES.weights["style"] == 0.6       # used at once

    bad = [{"weight_unknown": 1}, {"weight_style": -1},
           {"weight_style": 0, "weight_colour": 0, "weight_pattern": 0, "weight_structure": 0},
           {"style_low": 0.9}]
    for values in bad:
        assert client.put("/admin/formula", json={"values": values}, headers=admin).status_code == 422
    real = (ROOT / "mappings" / "compatibility_weights.csv").read_text(encoding="utf-8")
    assert "weight_style,0.35," in real                      # the real file was not touched
