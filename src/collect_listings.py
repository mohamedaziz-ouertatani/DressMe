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

    def __call__(self, raw):
        img = self.download(raw.image_url)
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


def collect(db, settings, source, args, labeller_for):
    sid, started = source["source_id"], datetime.now(timezone.utc)
    print(f"[{sid}] reading the shop")
    result = CONNECTORS[source["kind"]].fetch(source, args)
    if result.status != "ok":
        print(f"[{sid}] {result.status.upper()}: nothing saved. {result.message.splitlines()[-1:]}")
        record_run(db, sid, started, result.status, result.message, mode=result.mode)
        return result.status
    print(f"[{sid}] {len(result.listings)} products; saving (new pictures are analysed)")
    try:
        counts = sync_listings(db, sid, result.listings, labeller_for(source), settings.storage_dir,
                               now=started, mark_gone=not args.limit)
    except SourceBlocked as err:
        print(f"[{sid}] BLOCKED while downloading pictures: {err}. Nothing marked gone.")
        record_run(db, sid, started, "blocked", str(err), mode=result.mode)
        return "blocked"
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
    args = ap.parse_args()

    settings = Settings()
    db = connect(settings)
    now = datetime.now(timezone.utc)
    sources = [s for s in load_sources(settings.mappings_dir)
               if not args.source or s["source_id"] in args.source]
    if args.source and len(sources) != len(set(args.source)):
        sys.exit(f"ERROR: unknown source in {args.source} (see mappings/listing_sources.csv)")

    todo = []
    for s in sources:
        why_not = usable(s) or ("" if args.force else due(db, s, now))
        print(f"  {s['source_id']:<16} {'RUN' if not why_not else 'skip: ' + why_not}")
        if not why_not:
            todo.append(s)
    if args.list or not todo:
        return

    labellers = {}

    def labeller_for(source):            # the models load once, on first use
        if "models" not in labellers:
            labellers["models"] = Labeller(settings, 0)
        labeller = labellers["models"]
        labeller.delay = float(source.get("delay_s") or 5) / 2
        labeller.failed_in_a_row = 0
        return labeller

    results = {s["source_id"]: collect(db, settings, s, args, labeller_for) for s in todo}
    print("summary:", results)


if __name__ == "__main__":
    main()
