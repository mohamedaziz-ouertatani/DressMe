"""
Check a shop's website before the team adds it to mappings/listing_sources.csv.
Read-only and light: robots.txt + one product per platform it tries (3-4
requests, 5 s apart). It tells

  - which platform the shop runs on: Shopify (/products.json) or WooCommerce
    (/wp-json/wc/store/v1/products), so the collector knows which connector to use;
    if neither, whether its sitemaps + product pages carry the standard product
    data search engines read (kind "sitemap", e.g. H&M);
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
from connectors import sitemap as sitemap_connector  # noqa: E402
from connectors.http import Client, Forbidden, NotJSON  # noqa: E402

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


def check(base_url, client=None, pattern=""):
    """What the site is, as printable lines + the kind found ('' if none)."""
    client = client or Client(base_url, "check", delay=5, save=False)
    lines, kind_found = [], ""
    for kind, path in TRIES:
        try:
            data = client.get_json(path, html_is_block=False)
        except NotJSON:
            lines.append(f"  {kind:<12} no (a web page answered: not this platform)")
            continue
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
    if not kind_found and not any("BLOCKED" in line for line in lines):
        line, ok = check_sitemap(client, pattern or "product")
        lines.append(line)
        if ok:
            kind_found = "sitemap"
    return lines, kind_found


def check_sitemap(client, pattern="product"):
    """Third try: robots.txt lists sitemaps, they list product pages, and one of
    them carries schema.org Product data. Reads one sitemap file and one page."""
    name = f"  {'sitemap':<12}"
    try:
        listed = client.sitemaps()
        if not listed:
            return f"{name} no (robots.txt lists no sitemap)", False
        source = {"product_pattern": pattern}
        sitemap_connector.MAX_SITEMAPS, saved = 3, sitemap_connector.MAX_SITEMAPS   # stay light
        try:
            urls, _ = sitemap_connector.product_urls(client, source)
        finally:
            sitemap_connector.MAX_SITEMAPS = saved
        if not urls:
            return look_for_products(client, name, pattern)
        html = client.get_text(urls[0], "html")
        data = sitemap_connector.parse_product(html or "")
        if not data:
            return f"{name} no ({urls[0]} carries no product data)", False
        return (f"{name} YES, e.g. '{data['name']}' at {data['price']} {data['currency']} "
                f"({len(urls)} product pages in the first sitemaps)"), True
    except Forbidden as err:
        return f"{name} robots.txt FORBIDS it ({err}): we must not read it", False
    except SourceBlocked as err:
        return f"{name} BLOCKED ({err}): stop here, do not retry today", False
    except Exception as err:
        return f"{name} no ({err})", False


def look_for_products(client, name, pattern):
    """No address matched the product pattern: show what the sitemaps hold, and test a few
    of the deepest addresses (product pages usually are) for product data, so the team can
    set product_pattern in listing_sources.csv. Never saves a kind on its own."""
    sitemap_connector.MAX_SITEMAPS, saved = 3, sitemap_connector.MAX_SITEMAPS
    try:
        every, _ = sitemap_connector.product_urls(client, {"product_pattern": "."})
    finally:
        sitemap_connector.MAX_SITEMAPS = saved
    if not every:
        return f"{name} no (the sitemaps list no page under this site)", False
    deepest = sorted(every, key=lambda u: (u.rstrip("/").count("/"), len(u)), reverse=True)[:3]
    lines = [f"{name} no address contains '{pattern}' ({len(every)} pages in the first sitemaps); "
             "testing a few of them:"]
    for url in deepest:
        data = sitemap_connector.parse_product(client.get_text(url, "html") or "")
        if data:
            lines.append(f"      {url} HAS product data ('{data['name']}' at {data['price']} {data['currency']}): "
                         "set product_pattern in listing_sources.csv to a part of such addresses, then check again")
        else:
            lines.append(f"      {url}: no product data")
    return "\n".join(lines), False


SHOP_KINDS = ("", "shopify", "woocommerce", "sitemap")     # the rows this script may fill


def save_kind(path, source_id, kind):
    """Write the kind found into listing_sources.csv; enabled stays as it is (no)."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row["source_id"] == source_id:
            row["kind"] = kind
            if row.get("enabled", "").strip().lower() == "yes" and row.get("approved_on"):
                # the team already approved the terms: keep saying so
                row["note"] = (f"Checked {date.today().isoformat()} with check_shop_source.py: {kind}. "
                               f"Terms approved by the team on {row['approved_on']}.")
            else:
                row["note"] = (f"Checked {date.today().isoformat()} with check_shop_source.py: {kind}. "
                               "A team member must read the shop's terms before enabled=yes.")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def check_one(url, source_id, save, csv_path, pattern=""):
    print(f"\n{source_id}: checking {url} (robots.txt first, then one product per platform)")
    lines, kind = check(url, pattern=pattern)
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
        pattern = sources.get(sid, {}).get("product_pattern", "")
        check_one(url, sid, args.save and sid in sources, csv_path, pattern)


if __name__ == "__main__":
    main()
