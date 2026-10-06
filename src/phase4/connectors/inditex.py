"""
Zara / Bershka / Pull&Bear listings, through our existing scraper
(src/phase3/scrape_shops.py). Team vote 2026-10-04: a polite retry of these sites.

Each run starts the scraper as a separate process (it needs Playwright, see
requirements-scraping.txt), then reads the products.csv it wrote:
  - a full catalogue run when products.csv is missing or older than the
    source's `catalogue_days` (or with --catalogue);
  - otherwise only a stock re-check (--stock-only), which is much lighter.
The scraper stops by itself when the site blocks it ("Access Denied", or
several 403 / 429 answers in a row). We then report "blocked" and save
nothing: wait hours before the next try, and never try to get around it.
"""

import csv
import subprocess
import sys
import time
from pathlib import Path

from app.listings import RawListing

from .base import FetchResult

ROOT = Path(__file__).resolve().parents[3]
SCRAPER = ROOT / "src" / "phase3" / "scrape_shops.py"
SHOPS_DIR = ROOT / "data" / "raw" / "Shops"

STOPPED = "STOPPED by an admin"
# phrases of the scraper's own stop messages (scrape_shops.py) when a site blocks it
BLOCK_PHRASES = ("refused the automated browser", "keeps refusing our requests")
IN_STOCK = {"in_stock", "low_on_stock"}


def products_file(source):
    return SHOPS_DIR / f"{source['brand']}_{source['country']}" / "products.csv"


def catalogue_due(path, days, now=None):
    """True if the catalogue must be read again (missing, or older than `days`)."""
    if not path.exists():
        return True
    age_days = ((now or time.time()) - path.stat().st_mtime) / 86400
    return age_days >= float(days or 7)


def command(source, catalogue, limit=0):
    cmd = [sys.executable, str(SCRAPER), "--brand", source["brand"], "--country", source["country"],
           "--delay", str(source.get("delay_s") or 5)]
    if not catalogue:
        cmd.append("--stock-only")
    if limit:
        cmd += ["--limit", str(limit)]
    return cmd


def outcome(returncode, output):
    """(status, message) from the scraper's exit code and the end of its output."""
    tail = "\n".join(output.strip().splitlines()[-15:])
    if STOPPED in output:
        return "stopped", tail
    if returncode == 0:
        return "ok", tail
    if any(p in output for p in BLOCK_PHRASES):
        return "blocked", tail
    return "error", tail


def split(text):
    return [x for x in str(text or "").split("|") if x]


def to_raw(row):
    """One products.csv row -> RawListing. The stock level follows the same rule
    as src/phase3/freeze_shop_demo.py: per colour only when the colour's SKUs were known."""
    from_api = row.get("availability_from") == "stock_api"
    if from_api:
        level = "colour" if row.get("sku_sizes") else "product"
    else:
        level = "catalogue" if row.get("availability_from") == "catalogue" else ""
    availability = row.get("availability", "")
    in_stock = True if availability in IN_STOCK else False if availability == "out_of_stock" else None
    try:
        price = float(row["price"]) if row.get("price") not in (None, "") else None
    except ValueError:
        price = None
    return RawListing(
        external_id=row["id"], url=row.get("url", ""), title=row.get("name", ""),
        image_url=row.get("image_url", ""), brand=row.get("brand", ""),
        shop_colour=row.get("colour_name", ""), gender=row.get("gender", ""), price_tnd=price,
        sizes=split(row.get("sizes")),
        # for "product" rows these are SKU numbers of mixed colours: useless
        sizes_in_stock=split(row.get("sizes_in_stock")) if level == "colour" else [],
        in_stock=in_stock, availability_level=level)


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # a listing needs a link to the shop and a picture to analyse
    return [to_raw(r) for r in rows if r.get("url") and r.get("image_url")]


def run(cmd, should_stop=lambda: False):
    """Run the scraper, echo its output to our log, return (exit code, output).
    When an admin presses Stop, the scraper is ended at its next line of output
    (the backend also ends the whole process tree if that takes too long)."""
    lines = []
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          encoding="utf-8", errors="replace", cwd=ROOT) as proc:
        for line in proc.stdout:
            print("   ", line, end="", flush=True)
            lines.append(line)
            if should_stop():
                proc.terminate()
                lines.append(f"\n{STOPPED}\n")
                break
    return proc.returncode, "".join(lines)


def fetch(source, args, runner=None):
    path = products_file(source)
    catalogue = getattr(args, "catalogue", False) or catalogue_due(path, source.get("catalogue_days"))
    mode = "catalogue" if catalogue else "stock"
    runner = runner or (lambda cmd: run(cmd, getattr(args, "should_stop", lambda: False)))
    code, output = runner(command(source, catalogue, getattr(args, "limit", 0)))
    status, message = outcome(code, output)
    if status != "ok":
        return FetchResult(status, message, mode=mode)
    if not path.exists():
        return FetchResult("error", f"the scraper finished but wrote no {path}", mode=mode)
    return FetchResult("ok", message, read_rows(path), mode)
