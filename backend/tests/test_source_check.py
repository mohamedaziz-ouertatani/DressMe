"""The shop check from Admin > Listings (POST /admin/sources/{id}/check): the same
read-only check as src/check_shop_source.py, with a fake instead of the network."""

import shutil

import pytest

import check_shop_source
from app.config import ROOT
from app.listings import load_sources, usable
from tests.conftest import sign_up


@pytest.fixture
def admin_client(client, settings, tmp_path, monkeypatch):
    folder = tmp_path / "mappings"
    shutil.copytree(ROOT / "mappings", folder)      # the real CSV is never changed
    settings.mappings_dir = folder
    found = {"https://www2.hm.com/fr_fr/": "sitemap", "https://zen.com.tn/fr/": ""}
    asked = []

    def fake_check(url, client=None, pattern=""):
        asked.append((url, pattern))
        kind = found.get(url, "")
        return [f"  shopify      no", f"  sitemap      {'YES' if kind else 'no'}"], kind

    monkeypatch.setattr(check_shop_source, "check", fake_check)
    headers = sign_up(client, "admin@example.com", "Admin")
    client.app.state.db.users.update_one({}, {"$set": {"role": "admin"}})
    client.headers.update(headers)
    client.asked, client.folder = asked, folder
    return client


def rows(folder):
    return {s["source_id"]: s for s in load_sources(folder)}


def test_check_saves_the_kind_but_never_enables(admin_client):
    c = admin_client
    r = c.post("/admin/sources/hm_fr/check")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "sitemap" and body["saved"] and "stays off" in body["note"]
    assert c.asked == [("https://www2.hm.com/fr_fr/", "productpage")]     # the source's own pattern
    before = rows(ROOT / "mappings")["hm_fr"]
    hm = rows(c.folder)["hm_fr"]
    # the check fills the kind only: enabled / approved_on stay what the team set
    assert hm["kind"] == "sitemap"
    assert (hm["enabled"], hm["approved_on"]) == (before["enabled"], before["approved_on"])
    if before["enabled"] == "yes":       # approved by the team on 2026-10-05: it can run now
        assert usable(hm) == "" and "Terms approved by the team on 2026-10-05" in hm["note"]
    else:
        assert usable(hm) == "not enabled"

    overview = {s["source_id"]: s for s in c.get("/admin/listings/overview").json()["sources"]}
    assert overview["hm_fr"]["last_check"]["kind"] == "sitemap"
    assert overview["hm_fr"]["last_check"]["by"] == "admin@example.com"
    assert overview["hm_fr"]["checkable"] and not overview["zara_tn"]["checkable"]


def test_nothing_found_saves_nothing(admin_client):
    c = admin_client
    body = c.post("/admin/sources/zen_tn/check").json()
    assert body["kind"] == "" and not body["saved"] and "cannot be listed" in body["note"]
    assert rows(c.folder)["zen_tn"]["kind"] == ""


def test_refusals(admin_client, client):
    c = admin_client
    assert c.post("/admin/sources/nope/check").status_code == 404
    assert c.post("/admin/sources/zara_tn/check").status_code == 400          # Inditex: not this way
    assert c.post("/admin/sources/inditex_snapshot/check").status_code == 400
    c.app.state.jobs.running = lambda: {"_id": "x"}                           # a collector run
    assert c.post("/admin/sources/hm_fr/check").status_code == 409
    assert c.asked == []                                                       # the shop was never contacted
    user = sign_up(client, "user@example.com", "User")
    assert client.post("/admin/sources/hm_fr/check", headers=user).status_code == 403
