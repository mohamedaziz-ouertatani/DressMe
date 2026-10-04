"""
Check a shop's website before the team adds it to mappings/listing_sources.csv.
Read-only and light: robots.txt + one product per platform it tries (3-4
requests, 5 s apart). It tells

  - which platform the shop runs on: Shopify (/products.json) or WooCommerce
    (/wp-json/wc/store/v1/products), so the collector knows which connector to use;
  - whether robots.txt allows those paths (if not, we do not list the shop);
  - one product with its price, so the team can confirm the prices are in TND;
  - a ready-to-paste CSV line, still with enabled = no.

Enabling the shop stays a team step: someone reads the shop's terms of use,
then sets enabled = yes and approved_on = the date in the CSV.

Run on the team machine (the cloud sessions cannot reach these sites):
    python src/check_shop_source.py https://www.example.tn exist_tn
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.listings import SourceBlocked  # noqa: E402
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


def main():
    ap = argparse.ArgumentParser(description="Check a shop site before listing it (read-only)")
    ap.add_argument("url", help="the shop's home page, e.g. https://www.example.tn")
    ap.add_argument("source_id", nargs="?", default="new_shop_tn", help="its id in listing_sources.csv")
    args = ap.parse_args()

    print(f"checking {args.url} (robots.txt first, then one product per platform)")
    lines, kind = check(args.url)
    print("\n".join(lines))
    if not kind:
        print("\nNo platform we support was found (or the shop does not allow it): do not add it.")
        return
    brand = args.source_id.rsplit("_", 1)[0]
    print("\nCSV line for mappings/listing_sources.csv (still OFF: read the shop's terms first,")
    print("then set enabled=yes and approved_on=<date>):")
    print(f'{args.source_id},{kind},{brand},tn,{args.url},no,,5,2,7,,"checked with check_shop_source.py"')


if __name__ == "__main__":
    main()
