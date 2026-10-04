"""
Listing collector runs ("jobs") started from the admin page (Admin > Listings).

A job is src/collect_listings.py started as a SEPARATE process, exactly as the
nightly task runs it (it loads the models and can take hours), with:
    <storage>/jobs/<id>.log    everything it prints (shown live on the page)
    <storage>/jobs/<id>.json   its progress (src/job_progress.py)
    <storage>/jobs/<id>.stop   created when an admin presses Stop
MongoDB `listing_jobs` keeps one document per job (who, when, options, result).

Rules:
  - one job at a time (the models need the GPU memory, and shops must not get
    two of us at once);
  - the same gate as the command line: only sources enabled and approved in
    mappings/listing_sources.csv run; "force" only skips refresh_days;
  - Stop is polite first: the run finishes its current item, saves nothing more
    and marks nothing gone. If it has not ended after STOP_GRACE_S, the whole
    process tree is ended (the scraper and its browser too);
  - a job whose heartbeat is older than LOST_AFTER_S (backend or computer
    restarted) is shown as "lost".
"""

import json
import os
import signal
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone

from bson import ObjectId

from .config import ROOT

STOP_GRACE_S = 30
LOST_AFTER_S = 120
FINAL = {"finished", "failed", "stopped", "lost"}


class JobBusy(Exception):
    """Another job is still running."""


def collector_command(job, paths):
    """The command line of one job (tests replace it with a small fake)."""
    cmd = [sys.executable, "-u", str(ROOT / "src" / "collect_listings.py"),
           "--status-file", str(paths["status"]), "--stop-file", str(paths["stop"])]
    if job["sources"]:
        cmd += ["--source", *job["sources"]]
    if job["catalogue"]:
        cmd.append("--catalogue")
    if job["force"]:
        cmd.append("--force")
    if job["limit"]:
        cmd += ["--limit", str(job["limit"])]
    return cmd


def kill_tree(proc):
    """End the process and everything it started (scraper, browser)."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)   # started in its own session (see start)
        except ProcessLookupError:
            pass


def parse_time(text):
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt


class JobRunner:
    def __init__(self, db, storage_dir, command=collector_command):
        self.db, self.command = db, command
        self.folder = storage_dir / "jobs"
        self.folder.mkdir(parents=True, exist_ok=True)
        self._procs = {}                     # job id -> Popen, while it runs
        self._lock = threading.Lock()

    def paths(self, job_id):
        base = self.folder / str(job_id)
        return {"log": base.with_suffix(".log"), "status": base.with_suffix(".json"),
                "stop": base.with_suffix(".stop")}

    # ---------------------------------------------------------------- start / stop
    def running(self):
        """The job still running, if any (a dead one is marked lost on the way)."""
        for job in self.db.listing_jobs.find({"status": {"$in": ["running", "stopping"]}}):
            job = self.refresh(job)
            if job["status"] not in FINAL:
                return job
        return None

    def start(self, sources, catalogue, force, limit, user):
        with self._lock:
            busy = self.running()
            if busy:
                raise JobBusy(str(busy["_id"]))
            job = {"_id": ObjectId(), "sources": list(sources), "catalogue": bool(catalogue),
                   "force": bool(force), "limit": int(limit or 0), "status": "running",
                   "started_by": user["email"], "started_at": datetime.now(timezone.utc)}
            paths = self.paths(job["_id"])
            log = open(paths["log"], "wb")
            extra = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                     else {"start_new_session": True})        # so Stop can end the whole tree
            proc = subprocess.Popen(self.command(job, paths), stdout=log, stderr=subprocess.STDOUT,
                                    cwd=ROOT, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **extra)
            log.close()                      # the child keeps its own handle
            job["pid"] = proc.pid
            self.db.listing_jobs.insert_one(job)
            self._procs[str(job["_id"])] = proc
            threading.Thread(target=self._watch, args=(job["_id"], proc), daemon=True).start()
            return job

    def stop(self, job_id):
        job = self.db.listing_jobs.find_one({"_id": job_id})
        if not job or job["status"] in FINAL:
            return job
        self.paths(job_id)["stop"].touch()   # polite: the run checks it between items
        self.db.listing_jobs.update_one({"_id": job_id}, {"$set": {
            "status": "stopping", "stop_requested_at": datetime.now(timezone.utc)}})
        proc = self._procs.get(str(job_id))
        if proc:
            timer = threading.Timer(STOP_GRACE_S, kill_tree, args=(proc,))
            timer.daemon = True
            timer.start()
        return self.db.listing_jobs.find_one({"_id": job_id})

    def _watch(self, job_id, proc):
        code = proc.wait()
        self._procs.pop(str(job_id), None)
        self._finish(job_id, code)

    def _finish(self, job_id, code):
        job = self.db.listing_jobs.find_one({"_id": job_id})
        if not job or job["status"] in FINAL:
            return
        progress = self.progress(job_id)
        if job.get("stop_requested_at"):
            status = "stopped"
        elif code == 0 and progress.get("status") in ("finished", "stopped"):
            status = "finished"
        else:
            status = "failed"
        self.db.listing_jobs.update_one({"_id": job_id}, {"$set": {
            "status": status, "exit_code": code, "finished_at": datetime.now(timezone.utc),
            "results": progress.get("results", {}), "plan": progress.get("plan", {})}})

    # ---------------------------------------------------------------- reading
    def progress(self, job_id):
        try:
            return json.loads(self.paths(job_id)["status"].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def refresh(self, job):
        """Mark a running job whose process is gone (backend restarted, computer
        rebooted) as lost, so a new job can start."""
        if job["status"] in FINAL or str(job["_id"]) in self._procs:
            return job
        beat = parse_time(self.progress(job["_id"]).get("heartbeat")) or aware(job["started_at"])
        if datetime.now(timezone.utc) - beat > timedelta(seconds=LOST_AFTER_S):
            self.db.listing_jobs.update_one({"_id": job["_id"]}, {"$set": {
                "status": "lost", "finished_at": datetime.now(timezone.utc)}})
            job = self.db.listing_jobs.find_one({"_id": job["_id"]})
        return job

    def log(self, job_id, offset=0, size=64_000):
        """A piece of the log from `offset` (bytes), for the page to append."""
        path = self.paths(job_id)["log"]
        if not path.exists():
            return {"text": "", "offset": 0}
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read(size)
        # never cut a letter in two (Arabic / accents): keep its bytes for the next read
        for cut in range(4):
            try:
                text = data[:len(data) - cut].decode("utf-8")
                break
            except UnicodeDecodeError:
                continue
        else:
            text, cut = data.decode("utf-8", "replace"), 0
        return {"text": text, "offset": offset + len(data) - cut}
