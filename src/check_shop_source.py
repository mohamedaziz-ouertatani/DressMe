"""
Check a shop's website before the team adds it to mappings/listing_sources.csv.
Read-only and light: robots.txt + one product per platform it tries (3-4
requests, 5 s apart). It tells

  - which platform the shop runs on: Shopify (/products.json) or WooCommerce
    (/wp-json/wc/store/v1/products), so the collector knows which connector to use;
  - whether robots.txt allows those paths (if not, we do not list the shop);
  - one product with its price, so the team can confirm the prices are in TND;
  - with --save, the kind it found written into listing_sources.csv (still enabled = no).

Enabling the shop stays a team step: someone reads the shop's terms of use,
then sets enabled = yes and approved_on = the date in the CSV.

Run on the team machine (the cloud sessions cannot reach these sites):
    python src/check_shop_source.py --all            # every shop in the CSV with a base_url
    python src/check_shop_source.py exist_tn --save  # one shop; --save writes the kind found
    python src/check_shop_source.py https://www.example.tn new_shop_tn   # a shop not in the CSV yet
--save only fills `kind` (and `note`) in mappings/listing_sources.csv: the shop
stays OFF (enabled = no) until a team member has read its terms.
"""

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.listings import SOURCES_FILE, SourceBlocked, load_sources  # noqa: E402
from connectors.http import Client, Forbidden  # noqa: E402

TRIES = [  # (kind, path of one product)
    ("shopify", "products.json?limit=1"),
    ("woocommerce", "wp-json/wc/store/v1/products?per_page=1"),
]


def sample(kind, data):
    """(name, price text) of the first product of the answer, or None."""
    if kind == "shopify":
        products = (data or {}).get("products") or []
        if products:
            p = products[0]
            price = (p.get("variants") or [{}])[0].get("price", "?")
            return p.get("title", ""), f"{price} (Shopify gives no currency: check it on the site)"
    elif isinstance(data, list) and data:
        p = data[0]
        prices = p.get("prices") or {}
        try:
            value = int(prices["price"]) / 10 ** int(prices.get("currency_minor_unit", 0))
        except (KeyError, TypeError, ValueError):
            value = "?"
        return p.get("name", ""), f"{value} {prices.get('currency_code', '?')}"
    return None


def check(base_url, client=None):
    """What the site is, as printable lines + the kind found ('' if none)."""
    client = client or Client(base_url, "check", delay=5, save=False)
    lines, kind_found = [], ""
    for kind, path in TRIES:
        try:
            data = client.get_json(path)
        except Forbidden:
            lines.append(f"  {kind:<12} robots.txt FORBIDS {path.split('?')[0]}: we must not read it")
            continue
        except SourceBlocked as err:
            lines.append(f"  {kind:<12} BLOCKED ({err}): stop here, do not retry today")
            break
        except Exception as err:          # timeouts, bad JSON, other HTTP codes
            lines.append(f"  {kind:<12} no ({err})")
            continue
        found = sample(kind, data)
        if found:
            lines.append(f"  {kind:<12} YES, e.g. '{found[0]}' at {found[1]}")
            kind_found = kind_found or kind
        else:
            lines.append(f"  {kind:<12} no")
    return lines, kind_found


SHOP_KINDS = ("", "shopify", "woocommerce")     # the rows this script may fill


def save_kind(path, source_id, kind):
    """Write the kind found into listing_sources.csv; enabled stays as it is (no)."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row["source_id"] == source_id:
            row["kind"] = kind
            row["note"] = (f"Checked {date.today().isoformat()} with check_shop_source.py: {kind}. "
                           "A team member must read the shop's terms before enabled=yes.")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def check_one(url, source_id, save, csv_path):
    print(f"\n{source_id}: checking {url} (robots.txt first, then one product per platform)")
    lines, kind = check(url)
    print("\n".join(lines))
    if not kind:
        print("  -> no platform we support was found (or the shop does not allow it): do not list it.")
        return
    if save:
        save_kind(csv_path, source_id, kind)
        print(f"  -> saved kind={kind} in {csv_path.name}; still OFF until its terms are read.")
    else:
        print(f"  -> kind={kind}. Add --save to write it into {csv_path.name} (it stays OFF).")


def main():
    ap = argparse.ArgumentParser(description="Check a shop site before listing it (read-only)")
    ap.add_argument("target", nargs="?", help="a source_id from listing_sources.csv, or a site URL")
    ap.add_argument("source_id", nargs="?", default="new_shop_tn", help="with a URL: the id to use")
    ap.add_argument("--all", action="store_true", help="every shop in the CSV that has a base_url")
    ap.add_argument("--save", action="store_true", help="write the kind found into the CSV (stays OFF)")
    args = ap.parse_args()

    csv_path = Settings().mappings_dir / SOURCES_FILE
    sources = {s["source_id"]: s for s in load_sources(csv_path.parent)}
    if args.all:
        todo = [(s["base_url"], sid) for sid, s in sources.items()
                if s.get("base_url") and s.get("kind", "") in SHOP_KINDS]
    elif args.target and args.target.startswith("http"):
        todo = [(args.target, args.source_id)]
        if args.source_id not in sources:
            brand = args.source_id.rsplit("_", 1)[0]
            print("Not in the CSV yet: add this line to mappings/listing_sources.csv first "
                  "(then run again with its id and --save):")
            print(f'{args.source_id},,{brand},tn,{args.target},no,,5,2,7,,"to check"')
            args.save = False
    elif args.target in sources:
        if not sources[args.target].get("base_url"):
            sys.exit(f"ERROR: {args.target} has no base_url in {csv_path.name}")
        todo = [(sources[args.target]["base_url"], args.target)]
    else:
        ap.error("give --all, a source_id from listing_sources.csv, or a URL")
    for url, sid in todo:
        check_one(url, sid, args.save and sid in sources, csv_path)


if __name__ == "__main__":
    main()
