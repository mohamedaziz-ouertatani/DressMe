"""Admin > Explainability (routers/admin_xai.py): evaluation numbers, the 'not sure'
flag on real uploads, chat trace statistics, and editing mappings/xai_settings.csv."""

import csv
from datetime import datetime, timezone

from bson import ObjectId

from tests.conftest import BLUE, RED, sign_up, upload
from tests.test_admin import admin, temp_mappings  # noqa: F401  (fixtures)


def test_only_admins(client):
    user = sign_up(client, "someone@example.com", "Someone")
    assert client.get("/admin/xai", headers=user).status_code == 403
    assert client.put("/admin/xai/settings", json={"values": {"margin": 0.2}}, headers=user).status_code == 403


def test_evaluations_settings_and_concepts(client, admin, temp_mappings):  # noqa: F811
    body = client.get("/admin/xai", headers=admin).json()
    assert body["evaluations"]["concepts"]["mean_auc"] > 0.5
    names = {s["name"] for s in body["settings"]}
    assert {"min_conf_category", "margin", "near_miss", "min_swap_gain"} <= names
    assert all(s["note"] for s in body["settings"])
    assert any(c["concept"] == "denim" for c in body["concepts"])


def test_real_use_calibration(client, admin, temp_mappings):  # noqa: F811
    user = sign_up(client, "amira@example.com", "Amira")
    sure = upload(client, user, RED)
    unsure = upload(client, user, BLUE)
    upload(client, user, RED)                                           # no stored alternatives
    db = client.app.state.db
    db.items.update_one({"_id": ObjectId(sure["id"])}, {"$set": {
        "predicted.category.alternatives": [{"value": "top", "conf": 0.95}, {"value": "dress", "conf": 0.03}]}})
    db.items.update_one({"_id": ObjectId(unsure["id"])}, {"$set": {
        "predicted.category.alternatives": [{"value": "bottom", "conf": 0.5}, {"value": "dress", "conf": 0.4}],
        "category": "dress", "corrected": ["category"]}})
    cat = next(r for r in client.get("/admin/xai", headers=admin).json()["real_use"]["fields"]
               if r["field"] == "category")
    assert (cat["items"], cat["unsure"], cat["unsure_corrected"], cat["sure_corrected"]) == (2, 1, 1, 0)
    assert client.get("/admin/xai", headers=admin).json()["real_use"]["before_xai"] == 1


def test_trace_stats(client, admin, temp_mappings):  # noqa: F811
    user = sign_up(client, "amira@example.com", "Amira")
    uid = client.app.state.db.users.find_one({"email": "amira@example.com"})["_id"]
    now = datetime.now(timezone.utc)
    client.app.state.db.chats.insert_many([
        {"user_id": uid, "role": "model", "text": "a", "agent": "explainer", "created_at": now, "trace": [
            {"tool": "explain_outfit", "args": {}, "result": "score 70.1"},
            {"tool": "explain_similarity", "args": {}, "result": "error: unknown piece"}]},
        {"user_id": uid, "role": "model", "text": "b", "agent": "explainer", "created_at": now, "trace": []},
        {"user_id": uid, "role": "model", "text": "c", "agent": "stylist", "created_at": now, "trace": [
            {"tool": "list_wardrobe", "args": {}, "result": "failed: ValueError"}]},
    ])
    t = client.get("/admin/xai", headers=admin).json()["traces"]
    tools = {r["tool"]: r for r in t["tools"]}
    assert tools["explain_similarity"]["errors"] == 1 and tools["explain_outfit"]["errors"] == 0
    assert tools["list_wardrobe"]["errors"] == 1 and tools["list_wardrobe"]["agents"] == ["stylist"]
    assert t["answers"] == 3 and t["explainer_answers"] == 2 and t["explainer_without_tools"] == 1
    assert user


def test_edit_settings(client, admin, temp_mappings):  # noqa: F811
    r = client.put("/admin/xai/settings", json={"values": {"margin": 0.2, "near_miss": 8}}, headers=admin)
    assert r.status_code == 200
    rows = {row["setting"]: row for row in csv.DictReader(open(temp_mappings / "xai_settings.csv", encoding="utf-8"))}
    assert rows["margin"]["value"] == "0.2" and rows["near_miss"]["value"] == "8"
    assert rows["margin"]["note"].startswith("REVIEW")                         # notes kept
    for bad in ({"margin": 1.5}, {"near_miss": -1}, {"brand_new": 1}):
        assert client.put("/admin/xai/settings", json={"values": bad}, headers=admin).status_code == 422
