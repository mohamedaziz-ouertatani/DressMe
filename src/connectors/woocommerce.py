"""
Shops on WordPress + WooCommerce: their public Store API
(/wp-json/wc/store/v1/products) lists the catalogue page by page, read
through the polite client (http.py). Only for shops the team has checked
(src/check_shop_source.py) and approved in listing_sources.csv.

One listing per product. The Store API says whether the product can be
bought (`is_in_stock`) but not per size, so availability_level is "product".
Prices come in the smallest unit (millimes for TND): divided by
10 ** currency_minor_unit. A shop that is not in TND is refused.
"""

from app.listings import RawListing, SourceBlocked

from .base import FetchResult
from .http import Client, Forbidden

SIZE_NAMES = {"size", "taille", "pointure", "tailles", "المقاس"}
COLOUR_NAMES = {"color", "colour", "couleur", "coloris", "اللون"}
PAGE_SIZE = 100
MAX_PAGES = 500


def attribute_terms(product, names):
    for att in product.get("attributes") or []:
        if str(att.get("name", "")).strip().lower() in names:
            return [t.get("name", "") for t in att.get("terms") or [] if t.get("name")]
    return []


def to_raw(product, brand):
    images = product.get("images") or []
    if not images or not product.get("permalink"):
        return None
    prices = product.get("prices") or {}
    if prices.get("currency_code") and prices["currency_code"] != "TND":
        raise ValueError(f"prices in {prices['currency_code']}, not TND")
    try:
        price = int(prices["price"]) / 10 ** int(prices.get("currency_minor_unit", 0))
    except (KeyError, TypeError, ValueError):
        price = None
    colours = attribute_terms(product, COLOUR_NAMES)
    return RawListing(
        external_id=str(product["id"]), url=product["permalink"], title=product.get("name", ""),
        image_url=images[0].get("src", ""), brand=brand,
        shop_colour=colours[0] if len(colours) == 1 else "", price_tnd=price,
        sizes=attribute_terms(product, SIZE_NAMES), sizes_in_stock=[],
        in_stock=bool(product.get("is_in_stock")), availability_level="product")


def fetch(source, args, opener=None):
    client = Client(source["base_url"], source["source_id"], source.get("delay_s") or 5, opener)
    limit = getattr(args, "limit", 0)
    listings, data = [], None
    try:
        for page in range(1, MAX_PAGES + 1):
            if getattr(args, "should_stop", lambda: False)():
                return FetchResult("stopped", f"stopped by an admin after {page - 1} page(s)", mode="catalogue")
            data = client.get_json(f"wp-json/wc/store/v1/products?per_page={PAGE_SIZE}&page={page}")
            if not data:             # empty page (or 404): the end
                break
            for product in data:
                raw = to_raw(product, source.get("brand", ""))
                if raw:
                    listings.append(raw)
            if limit and len(listings) >= limit:
                return FetchResult("ok", f"stopped at --limit {limit}", listings[:limit], "catalogue")
    except SourceBlocked as err:
        return FetchResult("blocked", str(err), mode="catalogue")
    except Forbidden as err:
        return FetchResult("error", f"{err}: this shop does not allow it, so we do not read it",
                           mode="catalogue")
    except ValueError as err:
        return FetchResult("error", str(err), mode="catalogue")
    if data is None and not listings:
        return FetchResult("error", "no WooCommerce Store API here: not a WooCommerce shop?",
                           mode="catalogue")
    return FetchResult("ok", f"{len(listings)} products", listings, "catalogue")
