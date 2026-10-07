"""
Shops that are neither Shopify nor WooCommerce (e.g. H&M France), read the way
search engines read them, through the polite client (http.py: robots.txt
before every path, our own User-Agent, a delay, stop at the first block):

  1. robots.txt lists the shop's sitemaps;
  2. the sitemaps list every product page (kept: addresses under the source's
     base_url that match its `product_pattern`, e.g. "productpage" for H&M);
  3. each product page carries the standard product data search engines read
     (schema.org Product in JSON-LD): name, picture, price, currency, stock.

A big shop has tens of thousands of products: at 5 s a page a full pass takes
days. So one run fetches at most `max_pages` product pages (new ones first, then
the ones checked longest ago), and only products MISSING FROM THE SITEMAP are
marked gone (FetchResult.present_ids). Prices are converted to TND with the
team's table mappings/currency_rates.csv; a currency missing from it is an error
(never guessed). Only for shops the team has checked (src/phase4/check_shop_source.py)
and approved in listing_sources.csv.
"""

import csv
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from app.listings import RawListing, SourceBlocked

from .base import FetchResult
from .http import Client, Forbidden

RATES_FILE = Path(__file__).resolve().parents[3] / "mappings" / "currency_rates.csv"
MAX_SITEMAPS = 50           # sitemap files read per run, at most
EMPTY_IN_A_ROW = 5          # product pages in a row without product data: a bot check, stop
DEFAULT_MAX_PAGES = 500


# ------------------------------------------------------------------ sitemaps
def _name(el):
    return el.tag.rsplit("}", 1)[-1]


def sitemap_locs(text):
    """(is_index, [addresses]) of one sitemap file. Only the <loc> of each <url> / <sitemap>:
    the pictures some shops add inside a <url> (<image:loc>, Exist) are not pages."""
    root = ET.fromstring(text.encode("utf-8"))
    locs = [loc.text.strip() for entry in root for loc in entry
            if _name(entry) in ("url", "sitemap") and _name(loc) == "loc" and loc.text]
    return _name(root) == "sitemapindex", locs


def products_first(urls):
    """An index's sitemaps, the product ones first: H&M lists ~1,000 per country
    (pictures, filters, campaigns...) and only MAX_SITEMAPS are read per run."""
    return sorted(urls, key=lambda u: "product" not in urlsplit(u).path.lower())


def under(url, base):
    """Is this address part of the source's site (same host, under its path)?"""
    u, b = urlsplit(url), urlsplit(base)
    return u.netloc == b.netloc and u.path.startswith(b.path)


def relevant_sitemap(url, base):
    """A sitemap of the shop's country / language (H&M's robots.txt lists all of them)."""
    u, b = urlsplit(url), urlsplit(base)
    if u.netloc != b.netloc:
        return False
    parts = [p for p in b.path.split("/") if p]   # e.g. ["fr_fr"]
    return not parts or any(p in u.path for p in parts)


def product_urls(client, source, should_stop=lambda: False):
    """Every product page address the shop lists, and whether every sitemap was read."""
    pattern = re.compile(source.get("product_pattern") or "product", re.I)
    listed = client.sitemaps()
    # the sitemaps of this country / language; if none is named that way, every one of this site
    todo = [u for u in listed if relevant_sitemap(u, client.base)] or \
        [u for u in listed if urlsplit(u).netloc == urlsplit(client.base).netloc]
    seen, found, complete = set(), [], True
    while todo:
        if len(seen) >= MAX_SITEMAPS:
            complete = False
            break
        if should_stop():
            raise InterruptedError("stopped while reading the sitemaps")
        sm = todo.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            text = client.get_text(sm, "xml")
        except Forbidden:
            continue                       # robots.txt says no: we do not read it
        if text is None:
            continue
        is_index, locs = sitemap_locs(text)
        if is_index:
            todo += products_first([u for u in locs if relevant_sitemap(u, client.base) and u not in seen])
        else:
            # keep the whole address: some shops (H&M) put the product number after the "?"
            found += [u.split("#")[0] for u in locs if under(u, client.base) and pattern.search(u)]
    return list(dict.fromkeys(found)), complete


# ------------------------------------------------------------------ product pages
class _JsonLd(HTMLParser):
    """Collects the <script type="application/ld+json"> blocks of a page."""

    def __init__(self):
        super().__init__()
        self.blocks, self._on = [], False

    def handle_starttag(self, tag, attrs):
        self._on = tag == "script" and dict(attrs).get("type", "").lower() == "application/ld+json"
        if self._on:
            self.blocks.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self._on = False

    def handle_data(self, data):
        if self._on:
            self.blocks[-1] += data


def _things(obj):
    """Every JSON-LD object inside a block (lists and @graph included)."""
    if isinstance(obj, list):
        for x in obj:
            yield from _things(x)
    elif isinstance(obj, dict):
        yield obj
        for x in obj.get("@graph", []) or []:
            yield from _things(x)


def _is(obj, kind):
    t = obj.get("@type")
    return kind in (t if isinstance(t, list) else [t])


def _first(value):
    if isinstance(value, list):
        return _first(value[0]) if value else ""
    if isinstance(value, dict):
        return value.get("url") or value.get("contentUrl") or value.get("name") or ""
    return value or ""


def _offer(obj):
    """(price, currency, in_stock) of a Product's offers (Offer, list or AggregateOffer)."""
    offers = obj.get("offers") or {}
    offers = offers if isinstance(offers, list) else [offers]
    prices, currency, stock = [], "", None
    for o in offers:
        price = o.get("price", o.get("lowPrice"))
        try:
            prices.append(float(str(price).replace(",", ".")))
        except (TypeError, ValueError):
            pass
        currency = currency or o.get("priceCurrency", "")
        avail = str(o.get("availability", ""))
        if avail:
            ok = avail.rsplit("/", 1)[-1] in ("InStock", "LimitedAvailability", "InStoreOnly", "OnlineOnly")
            stock = ok if stock is None else (stock or ok)
    return (min(prices) if prices else None), currency, stock


def parse_product(html):
    """The page's Product data as a dict, or None when the page carries none."""
    parser = _JsonLd()
    parser.feed(html)
    for block in parser.blocks:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for obj in _things(data):
            if _is(obj, "ProductGroup") or _is(obj, "Product"):
                variants = [v for v in obj.get("hasVariant", []) or [] if isinstance(v, dict)]
                price, currency, stock = _offer(obj)
                sizes, sizes_ok = [], []
                for v in variants:
                    v_price, v_cur, v_stock = _offer(v)
                    price = price if price is not None else v_price
                    currency = currency or v_cur
                    if v.get("size"):
                        sizes.append(str(_first(v["size"])))
                        if v_stock:
                            sizes_ok.append(str(_first(v["size"])))
                    if v_stock is not None:
                        stock = bool(stock) or v_stock
                return {"id": str(obj.get("sku") or obj.get("productID") or obj.get("productGroupID") or ""),
                        "name": _first(obj.get("name")), "image": _first(obj.get("image")),
                        "colour": _first(obj.get("color")), "price": price, "currency": currency,
                        "in_stock": stock, "sizes": sizes, "sizes_in_stock": sizes_ok}
    return None


# ------------------------------------------------------------------ prices
def load_rates(path=RATES_FILE):
    """{currency: TND per unit}, from the team's table."""
    with open(path, newline="", encoding="utf-8") as f:
        return {r["currency"].strip().upper(): float(r["tnd_per_unit"]) for r in csv.DictReader(f)}


def to_tnd(price, currency, rates):
    """(price in TND, the original as text). Unknown currency: ValueError."""
    if price is None:
        return None, ""
    currency = (currency or "TND").upper()
    if currency not in rates:
        raise ValueError(f"prices in {currency}, which mappings/currency_rates.csv has no rate for")
    original = "" if currency == "TND" else f"{price:g} {currency}"
    return round(price * rates[currency], 3), original


def page_id(url):
    """A product's id in this source: its page address without the host (query kept:
    some shops name the product there, e.g. productpage.html?article=...)."""
    parts = urlsplit(url)
    return parts.path + (f"?{parts.query}" if parts.query else "")


def to_raw(url, data, source, rates):
    price, original = to_tnd(data["price"], data["currency"], rates)
    image = data["image"]
    if image.startswith("//"):
        image = "https:" + image
    return RawListing(
        external_id=page_id(url), url=url, title=data["name"], image_url=image,
        brand=source.get("brand", ""), shop_colour=data["colour"], price_tnd=price,
        price_original=original, sizes=data["sizes"], sizes_in_stock=data["sizes_in_stock"],
        in_stock=data["in_stock"], availability_level="colour" if data["sizes"] else "product")


def pick(urls, last_seen, how_many, key=page_id):
    """New pages first, then the ones checked longest ago (`key`: a page's id in last_seen)."""
    oldest = datetime.min.replace(tzinfo=timezone.utc)

    def when(url):
        seen = last_seen.get(key(url))
        if seen is None:
            return (0, oldest)
        return (1, seen if seen.tzinfo else seen.replace(tzinfo=timezone.utc))

    return sorted(urls, key=when)[:how_many]


def fetch(source, args, opener=None):
    should_stop = getattr(args, "should_stop", lambda: False)
    client = Client(source["base_url"], source["source_id"], source.get("delay_s") or 5, opener)
    try:
        rates = load_rates()
        urls, complete = product_urls(client, source, should_stop)
        if not urls:
            return FetchResult("error", "no product page found in the shop's sitemaps "
                                        "(check product_pattern in listing_sources.csv)", mode="sitemap")
        how_many = int(source.get("max_pages") or DEFAULT_MAX_PAGES)
        if getattr(args, "limit", 0):
            how_many = min(how_many, args.limit)
        listings, empty, skipped, forbidden = [], 0, 0, 0
        chosen = pick(urls, getattr(args, "last_seen", {}) or {}, how_many)
        for url in chosen:
            if should_stop():
                return FetchResult("stopped", f"stopped by an admin after {len(listings)} pages",
                                   mode="sitemap")
            try:
                html = client.get_text(url, "html")
            except Forbidden:
                skipped += 1
                forbidden += 1
                continue
            if html is None:                   # 404: the page is gone
                skipped += 1
                continue
            data = parse_product(html)
            if not data or not data["image"]:
                skipped += 1
                empty += 1
                if empty >= EMPTY_IN_A_ROW:
                    raise SourceBlocked(f"{EMPTY_IN_A_ROW} product pages in a row carry no product data "
                                        "(a bot check?)")
                continue
            empty = 0
            listings.append(to_raw(url, data, source, rates))
    except SourceBlocked as err:
        return FetchResult("blocked", str(err), mode="sitemap")
    except InterruptedError as err:
        return FetchResult("stopped", str(err), mode="sitemap")
    except (ValueError, ET.ParseError) as err:
        return FetchResult("error", str(err), mode="sitemap")
    if chosen and forbidden == len(chosen):
        return FetchResult("error", "robots.txt forbids the product pages: this shop cannot be listed",
                           mode="sitemap")
    present = {page_id(u) for u in urls} if complete else None
    return FetchResult("ok", f"{len(listings)} product pages read, {skipped} skipped, "
                             f"{len(urls)} in the sitemaps", listings, "sitemap", present_ids=present)
