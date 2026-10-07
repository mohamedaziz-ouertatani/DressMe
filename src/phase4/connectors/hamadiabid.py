"""
Hamadi Abid (ha.com.tn): the shop is a JavaScript app, so its product pages
carry no product data until a browser runs them (no schema.org Product for
sitemap.py to read), and it is neither Shopify nor WooCommerce. The app itself
reads each product from the shop's JSON API; we ask that API the same question,
through the polite client (http.py: robots.txt, our own User-Agent, a delay,
stop at the first block):

  1. robots.txt -> sitemap.xml lists every product page (sitemap.product_urls),
     e.g. /catalogue/femme/robes/robe-longue/0049876-article-robe-...;
  2. that address names the product: reference 0049876, section femme, group
     robes, sub-group robe-longue -> /api/items/ref?reference=...&selectedSection=...
     (the call the shop's own page makes) answers its name, price in TND, colour,
     sizes with stock and pictures.

Like sitemap.py, one run reads at most `max_pages` products (new ones first,
then the ones checked longest ago), and only products missing from the
sitemap are marked gone. `product_pattern` in listing_sources.csv says which
sitemap addresses are products (and which sections are kept).
Only for a shop the team has approved in listing_sources.csv.
"""

import re
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlencode, urlsplit

from app.listings import RawListing, SourceBlocked

from . import sitemap
from .base import FetchResult
from .http import Client, Forbidden

EMPTY_IN_A_ROW = 5          # products in a row the API says nothing about: something changed, stop
DEFAULT_PATTERN = "-article-"
GENDERS = {"femme": "women", "homme": "men"}


def page_parts(url):
    """(reference, {API parameters}) of a product page address, or None if it is not one.
    /catalogue/<section>/<group>/<sub-group>/<reference>-article-<name>"""
    parts = [unquote(p) for p in urlsplit(url).path.split("/") if p]
    if "catalogue" not in parts or "-article-" not in parts[-1]:
        return None
    ref = parts[-1].split("-article-", 1)[0]
    levels = parts[parts.index("catalogue") + 1:-1]
    params = {"reference": ref}
    for name, value in zip(("selectedSection", "selectedGroupName", "selectedSubGroupName"), levels):
        params[name] = value
    return ref, params


def tnd(text):
    """'1.299,99 TND' -> 1299.99. A price in another currency is an error (never guessed)."""
    text = str(text or "")
    if not text:
        return None
    if "TND" not in text.upper() and "DT" not in text.upper():
        raise ValueError(f"price '{text}' is not in TND")
    number = re.search(r"[\d.,]+", text)
    if not number:
        return None
    value = number.group()
    if "," in value:                     # French style: dots group thousands, the comma is the decimal point
        value = value.replace(".", "").replace(",", ".")
    return float(value)


def to_raw(url, item, base_url, brand=""):
    """One listing from the API's answer about one product (one colour per reference)."""
    sizes, in_stock = [], []
    for size, variants in (item.get("sizes") or {}).items():
        sizes.append(str(size))
        if any((v.get("stock") or 0) > 0 for v in variants or []):
            in_stock.append(str(size))
    section = ((item.get("section") or {}).get("seoName") or "").lower()
    return RawListing(
        external_id=str(item.get("ref") or ""), url=url, title=item.get("title", ""),
        image_url=f"{base_url}api/image/get/product/{item['image']}",
        brand=brand, shop_colour=(item.get("color") or {}).get("name", ""),
        gender=GENDERS.get(section, ""),
        # the price the customer pays today (after a discount, if any)
        price_tnd=tnd(item.get("priceDiscounted") or item.get("price")),
        sizes=sizes, sizes_in_stock=in_stock, in_stock=bool(in_stock) if sizes else None,
        availability_level="colour" if sizes else "product")


def fetch(source, args, opener=None):
    should_stop = getattr(args, "should_stop", lambda: False)
    client = Client(source["base_url"], source["source_id"], source.get("delay_s") or 5, opener)
    source = {**source, "product_pattern": source.get("product_pattern") or DEFAULT_PATTERN}
    try:
        urls, complete = sitemap.product_urls(client, source, should_stop)
        pages = {}
        for url in urls:
            found = page_parts(url)
            if found:
                pages.setdefault(found[0], (url, found[1]))
        if not pages:
            return FetchResult("error", "no product page found in the shop's sitemap "
                                        "(check product_pattern in listing_sources.csv)", mode="api")
        how_many = int(source.get("max_pages") or sitemap.DEFAULT_MAX_PAGES)
        if getattr(args, "limit", 0):
            how_many = min(how_many, args.limit)
        chosen = sitemap.pick(list(pages), getattr(args, "last_seen", {}) or {}, how_many, key=str)
        listings, empty, skipped = [], 0, 0
        for ref in chosen:
            if should_stop():
                return FetchResult("stopped", f"stopped by an admin after {len(listings)} products", mode="api")
            url, params = pages[ref]
            try:
                data = client.get_json("api/items/ref?" + urlencode(params))
            except RuntimeError:             # e.g. HTTP 400: the API does not know this address
                data = None
            items = [i for i in (data or {}).get("list") or [] if i.get("image")]
            if not items:                    # sold out and taken off the shop, or a changed API
                skipped += 1
                empty += 1
                if empty >= EMPTY_IN_A_ROW:
                    return FetchResult("error", f"the shop's API answered nothing for {EMPTY_IN_A_ROW} "
                                                "products in a row: has it changed?", mode="api")
                continue
            empty = 0
            listings.append(to_raw(url, items[0], client.base, source.get("brand", "")))
    except SourceBlocked as err:
        return FetchResult("blocked", str(err), mode="api")
    except Forbidden as err:
        return FetchResult("error", f"{err}: this shop does not allow it, so we do not read it", mode="api")
    except InterruptedError as err:
        return FetchResult("stopped", str(err), mode="api")
    except (ValueError, ET.ParseError) as err:
        return FetchResult("error", str(err), mode="api")
    return FetchResult("ok", f"{len(listings)} products read, {skipped} skipped, {len(pages)} in the sitemap",
                       listings, "api", present_ids=set(pages) if complete else None)
