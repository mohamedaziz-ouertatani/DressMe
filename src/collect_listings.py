"""
Collect shop listings into the app (MongoDB `listings`), from the sources the
team approved in mappings/listing_sources.csv. Design: LISTINGS.md.

For each source that may run (enabled = yes + an approved_on date) and is due
(its last good run is older than `refresh_days`):
  1. its connector (src/connectors/) reads the shop;
  2. new products, or products with a new picture, are analysed like a
     wardrobe upload: background removed, then classifier + colour model +
     FashionCLIP (backend/app/ml.py). The labels are predictions, never
     shop labels; colour stays empty below 0.7 confidence;
  3. products not seen in a complete run become "gone".
A source that blocks us (403 / 429 / bot check) is stopped and reported on the
admin page (Admin > Sources); nothing is saved for it. Never work around it.

Run from the project root, with the backend's settings (backend/.env) and
models; Inditex sources also need requirements-scraping.txt. A full run takes
hours (polite delays), so start it as a separate process writing a log:
    python src/collect_listings.py --list                     # what would run, and why not
    python src/collect_listings.py --source zara_tn --catalogue --limit 30   # smoke test
    python src/collect_listings.py > data/logs/listings.log 2>&1   # the nightly job
Admins can also start, follow and stop a run from the app (Admin > Listings):
the backend (app/jobs.py) then adds --status-file and --stop-file (src/job_progress.py).
Windows Task Scheduler (nightly, e.g. 02:00): program = the venv's python.exe,
arguments = src\\collect_listings.py, start in = the project folder.
"""

import argparse
import io
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image  # noqa: E402

from app.config import Settings  # noqa: E402
from app.db import connect  # noqa: E402
from app.listings import (THUMB_SIDE, SourceBlocked, last_run, load_sources,  # noqa: E402
                          record_run, sync_listings, usable)
from app.wardrobe import fields_from_analysis  # noqa: E402
from connectors import CONNECTORS  # noqa: E402
from job_progress import JobStopped, Progress, now_iso  # noqa: E402

USER_AGENT = "DressMe student project (ESPRIT, academic, non-commercial)"
MAX_FAILED_PICTURES_IN_A_ROW = 5    # then the image server is refusing us: stop the source


def due(db, source, now):
    """'' if the source should run now, else why not (refresh_days not over)."""
    run = last_run(db, source["source_id"], "ok")
    if not run:
        return ""
    finished = run["finished_at"]
    if finished.tzinfo is None:        # mongomock / old servers give naive UTC dates
        finished = finished.replace(tzinfo=timezone.utc)
    wait = timedelta(days=float(source.get("refresh_days") or 1))
    if now - finished < wait:
        return f"last good run {finished:%Y-%m-%d %H:%M}, refresh every {source.get('refresh_days') or 1} day(s)"
    return ""


class Labeller:
    """Downloads a listing's picture (slowly) and analyses it like an upload."""

    def __init__(self, settings, delay):
        from app.background import load_remover, on_white
        from app.ml import Analyzer

        print("loading the models (~1 min)")
        self.settings, self.delay = settings, delay
        self.analyzer = Analyzer()
        self.remover = load_remover(settings, self.analyzer.classify_for_mask)
        self.on_white = on_white
        self.failed_in_a_row = 0

    def download(self, url):
        time.sleep(self.delay)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                img = Image.open(io.BytesIO(resp.read()))
                img.load()
        except Exception as err:
            print(f"  no picture ({err}): {url}")
            self.failed_in_a_row += 1
            if self.failed_in_a_row >= MAX_FAILED_PICTURES_IN_A_ROW:
                raise SourceBlocked(f"{self.failed_in_a_row} pictures in a row could not be "
                                    f"downloaded (last: {err})")
            return None
        self.failed_in_a_row = 0
        return img.convert("RGB")

    def open_local(self, path):
        """A picture we already have (the frozen snapshot): no download, no delay."""
        try:
            with Image.open(path) as img:
                return img.convert("RGB")
        except OSError as err:
            print(f"  no picture ({err}): {path}")
            return None

    def __call__(self, raw):
        img = self.open_local(raw.image_path) if raw.image_path else self.download(raw.image_url)
        if img is None:
            return None
        thumb = img.copy()
        thumb.thumbnail((THUMB_SIDE, THUMB_SIDE))
        side = self.settings.max_image_side
        img.thumbnail((side, side))
        if self.remover:                     # same cleaning as an uploaded photo
            img = self.on_white(img, self.remover.mask(img))
        analysis = self.analyzer.analyze(img)
        fields, predicted = fields_from_analysis(analysis)
        return {"fields": fields, "predicted": predicted, "vector": analysis["vector"],
                "thumbnail": thumb}


def collect(db, settings, source, args, labeller_for, progress=None):
    """Run one source and save it. Returns ok / blocked / error / stopped."""
    progress = progress or Progress()
    sid, started = source["source_id"], datetime.now(timezone.utc)
    print(f"[{sid}] reading the shop")
    progress.update(phase="reading the shop", source=sid, done=0, total=0)
    result = CONNECTORS[source["kind"]].fetch(source, args)
    if result.status != "ok":
        print(f"[{sid}] {result.status.upper()}: nothing saved. {result.message.splitlines()[-1:]}")
        record_run(db, sid, started, result.status, result.message, mode=result.mode)
        return result.status
    print(f"[{sid}] {len(result.listings)} products; saving (new pictures are analysed)")
    labeller = labeller_for(source)            # may load the models (~1 min) the first time
    progress.update(phase="saving (new pictures are analysed)", total=len(result.listings))
    last = [0.0]

    def on_item(done, total):
        progress.check()                       # Stop pressed: JobStopped
        if time.time() - last[0] > 1:          # at most one status write per second
            progress.update(done=done, total=total)
            last[0] = time.time()

    try:
        counts = sync_listings(db, sid, result.listings, labeller, settings.storage_dir,
                               now=started, mark_gone=not args.limit, on_item=on_item)
    except SourceBlocked as err:
        print(f"[{sid}] BLOCKED while downloading pictures: {err}. Nothing marked gone.")
        record_run(db, sid, started, "blocked", str(err), mode=result.mode)
        return "blocked"
    except JobStopped:
        print(f"[{sid}] STOPPED by an admin: what was saved stays, nothing marked gone.")
        record_run(db, sid, started, "stopped", "stopped by an admin", mode=result.mode)
        return "stopped"
    progress.update(done=len(result.listings))
    print(f"[{sid}] done: {counts}")
    record_run(db, sid, started, "ok", result.message, counts, mode=result.mode)
    return "ok"


def main():
    ap = argparse.ArgumentParser(description="Collect shop listings into the app (LISTINGS.md)")
    ap.add_argument("--source", nargs="+", help="only these source_ids")
    ap.add_argument("--list", action="store_true", help="only show which sources would run")
    ap.add_argument("--force", action="store_true", help="ignore refresh_days (still never a refused source)")
    ap.add_argument("--catalogue", action="store_true", help="read the whole catalogue, not only stock")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after ~N products (smoke test; then nothing is marked gone)")
    ap.add_argument("--status-file", help="write live progress here (set by the backend, app/jobs.py)")
    ap.add_argument("--stop-file", help="stop when this file appears (set by the backend)")
    args = ap.parse_args()
    progress = Progress(args.status_file, args.stop_file)
    args.should_stop = progress.stopping       # the connectors check it between pages

    settings = Settings()
    db = connect(settings)
    now = datetime.now(timezone.utc)
    sources = [s for s in load_sources(settings.mappings_dir)
               if not args.source or s["source_id"] in args.source]
    if args.source and len(sources) != len(set(args.source)):
        sys.exit(f"ERROR: unknown source in {args.source} (see mappings/listing_sources.csv)")

    todo, plan = [], {}
    for s in sources:
        why_not = usable(s) or ("" if args.force else due(db, s, now))
        print(f"  {s['source_id']:<16} {'RUN' if not why_not else 'skip: ' + why_not}")
        plan[s["source_id"]] = why_not or "run"
        if not why_not:
            todo.append(s)
    progress.update(plan=plan, sources=[s["source_id"] for s in todo])
    if args.list or not todo:
        progress.update(status="finished", phase="nothing to run" if not todo else "listed", finished_at=now_iso())
        return

    labellers = {}

    def labeller_for(source):            # the models load once, on first use
        if "models" not in labellers:
            progress.update(phase="loading the models (~1 min)")
            labellers["models"] = Labeller(settings, 0)
        labeller = labellers["models"]
        labeller.delay = float(source.get("delay_s") or 5) / 2
        labeller.failed_in_a_row = 0
        return labeller

    for s in todo:
        if progress.stopping():                # Stop pressed: the next sources do not start
            progress.result(s["source_id"], "not started")
            continue
        progress.result(s["source_id"], "running")
        try:
            outcome = collect(db, settings, s, args, labeller_for, progress)
        except Exception as err:               # one broken source does not stop the others
            print(f"[{s['source_id']}] ERROR: {err!r}")
            record_run(db, s["source_id"], datetime.now(timezone.utc), "error", repr(err))
            outcome = "error"
        progress.result(s["source_id"], outcome)
    results = progress.state["results"]
    print("summary:", results)
    progress.update(status="stopped" if progress.stopping() else "finished", phase="done",
                    source=None, finished_at=now_iso())


if __name__ == "__main__":
    main()
