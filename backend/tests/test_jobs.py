"""Collector runs started from the admin page (app/jobs.py): start, live
progress and log, polite stop, hard stop, failure, one at a time, the source
gate, and the Listings dashboard. A tiny fake collector stands in for
src/collect_listings.py, so no model or shop is touched."""

import sys
import time

import pytest

from app import jobs
from tests.conftest import sign_up

# Behaves like collect_listings.py: writes progress + heartbeat, prints, checks the stop file.
FAKE = r'''
import json, os, sys, time
a = sys.argv
status, stop, mode = a[a.index("--status-file") + 1], a[a.index("--stop-file") + 1], a[a.index("--mode") + 1]
def write(**s):
    s["heartbeat"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    open(status + ".tmp", "w").write(json.dumps(s)); os.replace(status + ".tmp", status)
write(status="running", phase="reading the shop", source="inditex_snapshot", done=0, total=3,
      results={"inditex_snapshot": "running"}, plan={"inditex_snapshot": "run"})
print("[inditex_snapshot] reading the shop — é ي", flush=True)
if mode == "fail":
    sys.exit(1)
for i in range(600 if mode in ("wait", "deaf") else 3):
    if mode != "deaf" and os.path.exists(stop):
        print("[inditex_snapshot] STOPPED by an admin", flush=True)
        write(status="stopped", results={"inditex_snapshot": "stopped"})
        sys.exit(0)
    write(status="running", phase="saving", source="inditex_snapshot", done=i, total=3,
          results={"inditex_snapshot": "running"})
    time.sleep(0.05)
write(status="finished", phase="done", results={"inditex_snapshot": "ok"})
print("summary: ok", flush=True)
'''


@pytest.fixture
def admin_client(client, tmp_path):
    script = tmp_path / "fake_collector.py"
    script.write_text(FAKE, encoding="utf-8")
    runner = client.app.state.jobs
    runner.mode = "ok"
    runner.commands = []

    def command(job, paths):
        cmd = [sys.executable, "-u", str(script), "--status-file", str(paths["status"]),
               "--stop-file", str(paths["stop"]), "--mode", runner.mode]
        runner.commands.append(jobs.collector_command(job, paths))
        return cmd

    runner.command = command
    headers = sign_up(client, "admin@example.com", "Admin")
    client.app.state.db.users.update_one({}, {"$set": {"role": "admin"}})
    client.headers.update(headers)
    yield client
    for proc in list(runner._procs.values()):     # never leave a fake running
        jobs.kill_tree(proc)


def wait_for(client, job_id, statuses, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/admin/jobs/{job_id}").json()
        if job["status"] in statuses:
            return job
        time.sleep(0.1)
    raise AssertionError(f"job still {job['status']}")


def test_run_to_the_end_with_log_and_progress(admin_client):
    c = admin_client
    r = c.post("/admin/jobs", json={"sources": ["inditex_snapshot"], "force": True, "limit": 5})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "running" and job["sources"] == ["inditex_snapshot"]
    # the real command line it would have run
    cmd = c.app.state.jobs.commands[-1]
    assert cmd[2].endswith("collect_listings.py") and "--force" in cmd and cmd[-2:] == ["--limit", "5"]
    assert cmd[cmd.index("--source") + 1] == "inditex_snapshot"

    done = wait_for(c, job["id"], {"finished", "failed"})
    assert done["status"] == "finished" and done["exit_code"] == 0
    assert done["results"] == {"inditex_snapshot": "ok"} and done["finished_at"]
    log = c.get(f"/admin/jobs/{job['id']}/log").json()
    assert "é ي" in log["text"] and "summary: ok" in log["text"]
    more = c.get(f"/admin/jobs/{job['id']}/log?offset={log['offset']}").json()
    assert more["text"] == "" and more["offset"] == log["offset"]
    assert [j["id"] for j in c.get("/admin/jobs").json()] == [job["id"]]


def test_one_at_a_time_and_polite_stop(admin_client):
    c = admin_client
    c.app.state.jobs.mode = "wait"
    job = c.post("/admin/jobs", json={}).json()
    assert c.post("/admin/jobs", json={}).status_code == 409             # one run at a time
    time.sleep(0.5)
    live = c.get(f"/admin/jobs/{job['id']}").json()
    assert live["progress"]["source"] == "inditex_snapshot" and live["progress"]["total"] == 3
    r = c.post(f"/admin/jobs/{job['id']}/stop")
    assert r.json()["status"] == "stopping"
    stopped = wait_for(c, job["id"], {"stopped", "failed", "finished"})
    assert stopped["status"] == "stopped" and stopped["results"] == {"inditex_snapshot": "stopped"}
    assert c.post("/admin/jobs", json={}).status_code == 201             # free again


def test_hard_stop_when_the_run_does_not_listen(admin_client, monkeypatch):
    monkeypatch.setattr(jobs, "STOP_GRACE_S", 0.5)
    c = admin_client
    c.app.state.jobs.mode = "deaf"
    job = c.post("/admin/jobs", json={}).json()
    time.sleep(0.3)
    c.post(f"/admin/jobs/{job['id']}/stop")
    assert wait_for(c, job["id"], {"stopped"})["status"] == "stopped"


def test_failed_and_lost_runs(admin_client, monkeypatch):
    c = admin_client
    c.app.state.jobs.mode = "fail"
    job = c.post("/admin/jobs", json={}).json()
    failed = wait_for(c, job["id"], {"failed", "finished"})
    assert failed["status"] == "failed" and failed["exit_code"] == 1

    # a run whose process is gone and whose heartbeat is old (backend restarted): lost
    db = c.app.state.db
    from datetime import datetime, timedelta, timezone
    from bson import ObjectId
    old = ObjectId()
    db.listing_jobs.insert_one({"_id": old, "sources": [], "catalogue": False, "force": False, "limit": 0,
                                "status": "running", "started_by": "x",
                                "started_at": datetime.now(timezone.utc) - timedelta(hours=1)})
    assert c.get(f"/admin/jobs/{old}").json()["status"] == "lost"
    assert c.post("/admin/jobs", json={}).status_code == 201


def test_gate_and_admin_only(admin_client, client):
    c = admin_client
    r = c.post("/admin/jobs", json={"sources": ["zen_tn"]})                 # off: robots.txt forbids it
    assert r.status_code == 422 and "zen_tn" in r.json()["detail"]
    assert c.post("/admin/jobs", json={"sources": ["exist_tn"]}).status_code == 422   # not checked yet
    assert c.post("/admin/jobs", json={"sources": ["nope"]}).status_code == 422
    assert c.post("/admin/jobs", json={"limit": -1}).status_code == 422
    user = sign_up(client, "user@example.com", "User")
    assert client.get("/admin/jobs", headers=user).status_code == 403
    assert client.post("/admin/jobs", json={}, headers=user).status_code == 403
    assert c.get("/admin/jobs/nope").status_code == 404


def test_overview(admin_client):
    from datetime import datetime, timezone
    from app.listings import record_run
    c = admin_client
    db = c.app.state.db
    db.listings.insert_many([
        {"source_id": "inditex_snapshot", "external_id": "a", "status": "active", "in_stock": True, "category": "top"},
        {"source_id": "inditex_snapshot", "external_id": "b", "status": "gone", "in_stock": False, "category": "top"},
        {"source_id": "sellers", "external_id": "c", "status": "pending", "in_stock": True, "category": "dress"},
        {"source_id": "sellers", "external_id": "d", "status": "active", "in_stock": True, "category": "dress"}])
    record_run(db, "zara_tn", datetime.now(timezone.utc), "blocked", "Access Denied")
    body = c.get("/admin/listings/overview").json()
    t = body["totals"]
    assert (t["active"], t["in_stock"], t["gone"], t["pending"], t["sellers_active"]) == (2, 2, 1, 1, 1)
    # on: only the snapshot (Inditex blocked again on 2026-10-05; the shops wait for a kind)
    assert t["sources_on"] == 1 and t["sources_total"] == 8
    snap = next(s for s in body["sources"] if s["source_id"] == "inditex_snapshot")
    assert (snap["active"], snap["in_stock"], snap["gone"], snap["refused"]) == (1, 1, 1, "")
    assert {x["category"]: x["count"] for x in body["categories"]} == {"top": 1, "dress": 1}
    assert body["runs_by_day"][-1]["blocked"] == 1
    assert body["running"] is None


def test_real_collector_stops_between_items_and_marks_nothing_gone(client, tmp_path, monkeypatch):
    """collect_listings.collect() with a Progress whose stop file appears mid-run."""
    import json
    from types import SimpleNamespace
    import collect_listings
    from connectors import FetchResult
    from job_progress import Progress
    from tests.test_listings import FakeLabeller, raw

    db, settings = client.app.state.db, client.app.state.settings
    source = {"source_id": "inditex_snapshot", "kind": "snapshot"}
    fake = SimpleNamespace(fetch=lambda s, a: FetchResult("ok", "", [raw("a"), raw("b")], "snapshot"))
    monkeypatch.setitem(collect_listings.CONNECTORS, "snapshot", fake)
    args = SimpleNamespace(limit=0)
    progress = Progress(tmp_path / "job.json", tmp_path / "job.stop")
    assert collect_listings.collect(db, settings, source, args, lambda s: FakeLabeller(), progress) == "ok"
    status = json.loads((tmp_path / "job.json").read_text())
    assert status["done"] == 2 and status["total"] == 2 and status["heartbeat"]

    (tmp_path / "job.stop").touch()                                     # Stop pressed
    fake.fetch = lambda s, a: FetchResult("ok", "", [raw("c")], "snapshot")
    assert collect_listings.collect(db, settings, source, args, lambda s: FakeLabeller(), progress) == "stopped"
    assert db.listings.count_documents({"status": "active"}) == 2       # a and b not marked gone
    assert db.listing_runs.find_one(sort=[("finished_at", -1)])["result"] == "stopped"


def test_status_file_busy_on_windows_never_stops_the_run(tmp_path, monkeypatch):
    """2026-10-05, Windows: os.replace raised PermissionError (WinError 5) because the
    backend was reading the status file at that moment, and the whole run crashed."""
    import json
    import os
    import job_progress
    from job_progress import Progress

    progress = Progress(tmp_path / "job.json", tmp_path / "job.stop")
    real_replace, calls = os.replace, {"n": 0}

    def busy_twice(src, dst):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError(13, "Access is denied")
        return real_replace(src, dst)

    monkeypatch.setattr(job_progress.os, "replace", busy_twice)
    progress.update(phase="saving", done=3)            # retried, then written
    assert json.loads((tmp_path / "job.json").read_text())["done"] == 3

    monkeypatch.setattr(job_progress.os, "replace", lambda s, d: (_ for _ in ()).throw(PermissionError(13, "busy")))
    progress.update(done=4)                             # still busy: skipped, no crash
    progress.result("zara_tn", "blocked")
    assert progress.state["results"]["zara_tn"] == "blocked"
