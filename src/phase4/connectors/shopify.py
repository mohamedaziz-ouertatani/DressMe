"""
Shops on Shopify (many Tunisian brands): every Shopify shop publishes its
catalogue at /products.json, read page by page through the polite client
(http.py: robots.txt, delay, stop on a block). Only for shops the team has
checked (src/phase4/check_shop_source.py) and approved in listing_sources.csv.

One listing per product colour: the variants of one colour share a picture,
and their sizes tell what is in stock (`available`), so availability_level
is "colour". Prices are in the shop's currency (TND for a .tn shop; the
check script prints one so the team can confirm it).
"""

from app.listings import RawListing, SourceBlocked

from .base import FetchResult
from .http import Client, Forbidden

COLOUR_NAMES = {"color", "colour", "couleur", "coloris", "اللون"}
SIZE_NAMES = {"size", "taille", "pointure", "tailles", "المقاس"}
PAGE_SIZE = 250
MAX_PAGES = 200            # a safety stop: 50,000 products


def option_index(product, names):
    """Which variant field (option1/2/3) holds the colour or the size, or None."""
    for opt in product.get("options") or []:
        if str(opt.get("name", "")).strip().lower() in names:
            return f"option{opt.get('position', 1)}"
    return None


def to_raws(product, base_url, brand):
    colour_key = option_index(product, COLOUR_NAMES)
    size_key = option_index(product, SIZE_NAMES)
    images = product.get("images") or []
    by_colour = {}
    for v in product.get("variants") or []:
        by_colour.setdefault(v.get(colour_key) if colour_key else "", []).append(v)
    url = f"{base_url.rstrip('/')}/products/{product.get('handle', '')}"
    raws = []
    for colour, variants in by_colour.items():
        # the colour's own picture, else the product's first one
        ids = {v.get("id") for v in variants}
        picture = next((v["featured_image"]["src"] for v in variants if v.get("featured_image")), None) \
            or next((i["src"] for i in images if ids & set(i.get("variant_ids") or [])), None) \
            or (images[0]["src"] if images else "")
        if not picture:
            continue
        picture = ("https:" + picture if picture.startswith("//") else picture).split("?")[0]
        prices = [float(v["price"]) for v in variants if v.get("price") not in (None, "")]
        sizes = [v.get(size_key) for v in variants if size_key and v.get(size_key)]
        in_stock_sizes = [v.get(size_key) for v in variants if size_key and v.get(size_key) and v.get("available")]
        raws.append(RawListing(
            external_id=f"{product['id']}_{colour}" if colour else str(product["id"]),
            url=url + (f"?variant={variants[0]['id']}" if colour else ""),
            title=product.get("title", ""), image_url=picture,
            brand=brand, shop_colour=colour or "", price_tnd=min(prices) if prices else None,
            sizes=sizes, sizes_in_stock=in_stock_sizes,
            in_stock=any(v.get("available") for v in variants),
            availability_level="colour" if size_key else "product"))
    return raws


def fetch(source, args, opener=None):
    client = Client(source["base_url"], source["source_id"], source.get("delay_s") or 5, opener)
    limit = getattr(args, "limit", 0)
    listings, data = [], None
    try:
        for page in range(1, MAX_PAGES + 1):
            if getattr(args, "should_stop", lambda: False)():
                return FetchResult("stopped", f"stopped by an admin after {page - 1} page(s)", mode="catalogue")
            data = client.get_json(f"products.json?limit={PAGE_SIZE}&page={page}")
            products = (data or {}).get("products") or []
            if not products:
                break
            for product in products:
                listings += to_raws(product, client.base, source.get("brand", ""))
            if limit and len(listings) >= limit:
                return FetchResult("ok", f"stopped at --limit {limit}", listings[:limit], "catalogue")
    except SourceBlocked as err:
        return FetchResult("blocked", str(err), mode="catalogue")
    except Forbidden as err:
        return FetchResult("error", f"{err}: this shop does not allow it, so we do not read it",
                           mode="catalogue")
    if data is None and not listings:
        return FetchResult("error", "no /products.json here: not a Shopify shop?", mode="catalogue")
    return FetchResult("ok", f"{len(listings)} product colours", listings, "catalogue")
