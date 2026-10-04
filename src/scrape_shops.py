"""
Scrape the men's and women's catalogue of Zara, Bershka and Pull&Bear
(Tunisia by default) and check which items are in stock.

All three brands belong to Inditex and their websites load the catalogue
from JSON endpoints. We open the shop's home page in a real browser
(Playwright + Chromium) so the site's bot protection lets us in, then call
those same endpoints from inside the page:

    Zara               /{cc}/{lang}/categories?ajax=true
                       /{cc}/{lang}/category/<id>/products?ajax=true
                       /itxrest/1/catalog/store/<store>/product/id/<id>/availability
    Bershka, Pull&Bear /itxrest/2/catalog/store/<store>/<catalog>/category
                       /itxrest/3/catalog/store/<store>/<catalog>/category/<id>/product
                       /itxrest/3/catalog/store/<store>/<catalog>/productsArray
                       /itxrest/2/catalog/store/<store>/<catalog>/product/<id>/stock

These endpoints are NOT a public API: they can change without notice. Every
answer is saved untouched under raw/, so if the parsing breaks we fix the
code and re-run without downloading again. The store / catalog / language ids
are read from the requests the home page makes; --store-id etc. override them.

Usage (from the project root; install first: see requirements-scraping.txt):
    python src/scrape_shops.py --brand zara --limit 50     # quick smoke test
    python src/scrape_shops.py --brand all                 # full catalogue + stock
    python src/scrape_shops.py --brand all --stock-only    # re-check stock only
    python src/scrape_shops.py --brand bershka --images    # also save pictures
A full run sends thousands of requests (one stock check per item): launch it
as a separate process writing a log, and keep the delay polite.

Output (inside data/, so never committed; for our academic use only, the
shops' terms do not allow redistributing it):
    data/raw/Shops/<brand>_<cc>/products.csv       one row per product colour
    data/raw/Shops/<brand>_<cc>/stock_history.csv  one row per stock check
    data/raw/Shops/<brand>_<cc>/raw/*.json         untouched API answers
    data/raw/Shops/<brand>_<cc>/images/<id>.jpg    with --images
"""

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw" / "Shops"

# kind = which family of endpoints the site uses; prefix = id prefix
BRANDS = {
    "zara": {"origin": "https://www.zara.com", "kind": "zara", "prefix": "zr"},
    "bershka": {"origin": "https://www.bershka.com", "kind": "itx", "prefix": "bk"},
    "pullandbear": {"origin": "https://www.pullandbear.com", "kind": "itx", "prefix": "pb"},
}

# Words that mark the top-level "women" / "men" sections (fr, en, es, ar).
GENDER_WORDS = {
    "women": {"woman", "women", "femme", "femmes", "mujer", "ella", "نساء", "امرأة"},
    "men": {"man", "men", "homme", "hommes", "hombre", "él", "رجال", "رجل"},
}

# Stop the whole run when this many URLs in a row stay refused (403 / 429)
# after their retries: the site is blocking us, and we never work around it.
MAX_REFUSED_IN_A_ROW = 3

# Stock values the shops use that mean "can be bought now".
IN_STOCK = {"in_stock", "low_on_stock"}

COLUMNS = [
    "id", "brand", "country", "language", "gender", "product_id", "colour_id",
    "name", "colour_name", "category_paths", "price_raw", "price", "url",
    "image_url", "sizes", "sku_sizes", "stock_id", "catalogue_availability",
    "availability", "availability_from", "sizes_in_stock", "n_sizes",
    "n_sizes_in_stock", "checked_at",
]

# Runs inside the page, so the request carries the site's own cookies/headers.
FETCH_JS = """async (url) => {
    const r = await fetch(url, {credentials: 'include',
                                headers: {accept: 'application/json'}});
    return [r.status, await r.text()];
}"""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def detect_gender(*texts):
    """'women' / 'men' if one of the texts is a section name, else None."""
    for text in texts:
        words = set(re.findall(r"\w+", str(text or "").lower()))
        for gender, keys in GENDER_WORDS.items():
            if words & keys:
                return gender
    return None


def leaf_categories(nodes, path=(), gender=None):
    """Yield (gender, 'A > B > C', node) for every category without children.

    The gender comes from the first ancestor whose name is a section name
    (e.g. 'FEMME', 'Homme'); categories outside both sections get None.
    """
    for node in nodes or []:
        name = str(node.get("name") or "").strip()
        g = gender or detect_gender(name, node.get("sectionName"), node.get("key"))
        p = path + (name,)
        subs = node.get("subcategories") or []
        if subs:
            yield from leaf_categories(subs, p, g)
        else:
            yield g, " > ".join(p), node


def find_image(obj):
    """First picture URL found anywhere inside a product/colour JSON object."""
    if isinstance(obj, dict):
        url = obj.get("url")
        if isinstance(url, str) and ("http" in url or url.startswith("//")):
            url = url.replace("{width}", "750")
            return "https:" + url if url.startswith("//") else url
        # Zara's older format: path + name + timestamp
        if {"path", "name", "timestamp"} <= obj.keys():
            return (f"https://static.zara.net/photos/{obj['path']}/w/750/"
                    f"{obj['name']}.jpg?ts={obj['timestamp']}")
        items = obj.values()
    elif isinstance(obj, list):
        items = obj
    else:
        return ""
    for item in items:
        found = find_image(item)
        if found:
            return found
    return ""


def summarize_stock(stock, sku_sizes):
    """Per-SKU stock {sku: availability} -> (availability, sizes in stock, n)."""
    ok = [sku for sku, a in stock.items() if str(a).lower() in IN_STOCK]
    if not ok:
        return "out_of_stock", "", 0
    low = all(str(stock[s]).lower() == "low_on_stock" for s in ok)
    names = [sku_sizes.get(s, s) for s in ok]
    return ("low_on_stock" if low else "in_stock"), "|".join(names), len(ok)


def pack_skus(sku_sizes):
    return "|".join(f"{sku}:{size}" for sku, size in sku_sizes.items())


def unpack_skus(text):
    pairs = (item.split(":", 1) for item in str(text or "").split("|") if ":" in item)
    return dict(pairs)


# ---------------------------------------------------------------------------
# Browser session
# ---------------------------------------------------------------------------

class Shop:
    """One open shop website: fetches JSON through the page, with a cache."""

    def __init__(self, browser, brand, args):
        self.brand = brand
        self.kind = BRANDS[brand]["kind"]
        self.prefix = BRANDS[brand]["prefix"]
        self.origin = args.origin or BRANDS[brand]["origin"]
        self.delay = args.delay
        self.fresh = args.fresh
        self.refused_in_a_row = 0   # URLs still refused after the retries (see get_json)
        self.context = browser.new_context(locale=f"{args.language}-{args.country.upper()}")
        self.page = self.context.new_page()

        # Remember the API calls the home page makes: they hold the ids we need.
        self.seen = []
        self.page.on("request", lambda req: self.seen.append(req.url))
        home = f"{self.origin}/{args.country}/{args.language}/"
        print(f"[{brand}] opening {home}")
        self.page.goto(home, wait_until="domcontentloaded", timeout=90_000)
        self.page.wait_for_timeout(8_000)  # let the site's scripts run

        # The site may redirect (other language, or another country if it
        # does not serve this one): use what it actually shows.
        m = re.match(r"https?://[^/]+/([a-z]{2})/(?:([a-z]{2})/)?", self.page.url)
        self.country = m.group(1) if m else args.country
        self.language = (m.group(2) if m and m.group(2) else args.language)
        if self.country != args.country:
            print(f"[{brand}] WARNING: the site redirected to country "
                  f"'{self.country}' ({self.page.url}): it may not serve '{args.country}'")
        self.base = f"{self.origin}/{self.country}/{self.language}/"

        self.dir = OUT_DIR / f"{brand}_{self.country}"
        (self.dir / "raw").mkdir(parents=True, exist_ok=True)

        # Debug files: what the site showed us (helps when ids are not found
        # or the site answered with a bot-check page instead of the shop).
        html = self.page.content()
        (self.dir / "debug_home.html").write_text(html, encoding="utf-8")
        (self.dir / "debug_requests.txt").write_text("\n".join(self.seen), encoding="utf-8")
        self.page.screenshot(path=str(self.dir / "debug_home.png"))

        # The shop's bot protection answered instead of the shop: stop here.
        if re.search(r"<title>\s*(Access Denied|Attention Required|Just a moment)", html, re.I):
            sys.exit(f"ERROR: {brand} refused the automated browser ('Access Denied' page, see "
                     f"{self.dir / 'debug_home.png'}). If it worked before, the site is "
                     "probably slowing us down after too many requests: wait a few hours, then "
                     "retry with a larger --delay (e.g. 5). Do not try to get around the block.")

        found = find_ids(self.seen, html + "\n" + self.js_config())
        self.store_id = args.store_id or found["store"]
        self.catalog_id = args.catalog_id or found["catalog"]
        self.language_id = args.language_id or found["language"] or "-1"
        print(f"[{brand}] country={self.country} language={self.language} "
              f"store={self.store_id} catalog={self.catalog_id} languageId={self.language_id}")
        # Zara lists products without ids; its store id is only needed for
        # the stock check and is looked for again on a product page later.
        if self.kind == "itx" and not (self.store_id and self.catalog_id):
            sys.exit(f"ERROR: could not find the {brand} store/catalog ids (see the debug_* "
                     f"files in {self.dir}). Open the site in your browser, look for an "
                     "/itxrest/.../catalog/store/<store>/<catalog>/ request in the dev tools "
                     "(Network tab) and pass --store-id / --catalog-id.")

    def js_config(self):
        """The site's own config object as text (Zara keeps its ids there)."""
        try:
            return self.page.evaluate("""() => {
                const z = window.zara || {};
                return JSON.stringify(z.appConfig || z.viewPayload || {});
            }""") or ""
        except Exception:
            return ""

    def find_store_on_page(self, url):
        """Open a product page and catch the store id in the stock request it makes."""
        print(f"[{self.brand}] looking for the store id on {url}")
        start = len(self.seen)
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            self.page.wait_for_timeout(8_000)
        except Exception as err:
            print(f"  could not open it: {str(err).splitlines()[0]}")
            return None
        found = find_ids(self.seen[start:], self.page.content() + "\n" + self.js_config())
        return found["store"]

    def get_json(self, url, cache=True):
        """GET a JSON endpoint from inside the page. None if it fails."""
        path = self.dir / "raw" / (hashlib.sha1(url.encode()).hexdigest()[:20] + ".json")
        if cache and not self.fresh and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["data"]

        status, text = 0, ""
        for attempt in range(3):
            time.sleep(self.delay * random.uniform(0.7, 1.3))  # be polite
            try:
                status, text = self.page.evaluate(FETCH_JS, url)
            except Exception as err:  # page crashed or navigated away
                status, text = 0, str(err)
            if status == 200:
                break
            if status in (0, 403, 429):  # blocked or rate limited: wait, reload
                print(f"  HTTP {status} on {url}, waiting {30 * (attempt + 1)} s")
                time.sleep(30 * (attempt + 1))
                self.page.reload(wait_until="domcontentloaded")
            else:
                break
        if status in (0, 403, 429):
            self.refused_in_a_row += 1
            if self.refused_in_a_row >= MAX_REFUSED_IN_A_ROW:
                sys.exit(f"ERROR: {self.brand} keeps refusing our requests (HTTP {status} on "
                         f"{MAX_REFUSED_IN_A_ROW} URLs in a row, after waiting): the site is blocking "
                         "or slowing us down. Wait a few hours, then retry with a larger --delay. "
                         "Do not try to get around the block.")
        else:
            self.refused_in_a_row = 0
        if status != 200:
            print(f"  skipped (HTTP {status}): {url}")
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            print(f"  skipped (not JSON): {url}")
            return None
        if cache:
            path.write_text(json.dumps({"url": url, "data": data}, ensure_ascii=False),
                            encoding="utf-8")
        return data

    def itx(self, path, **params):
        """URL of an Inditex /itxrest/ endpoint (Bershka, Pull&Bear)."""
        path = path.format(store=self.store_id, catalog=self.catalog_id)
        query = urlencode({"languageId": self.language_id, "appId": 1, **params})
        return f"{self.origin}/itxrest/{path}?{query}"


def find_ids(urls, html):
    """Store / catalog / language ids from the page's API calls or its HTML."""
    found = {"store": None, "catalog": None, "language": None}
    for url in urls:
        m = re.search(r"/itxrest/\d+/catalog/store/(\d+)/(\d+)/", url)
        if m and not found["catalog"]:
            found["store"], found["catalog"] = m.group(1), m.group(2)
        m = re.search(r"/itxrest/\d+/catalog/store/(\d+)/", url)
        if m and not found["store"]:
            found["store"] = m.group(1)
        m = re.search(r"[?&]languageId=(-?\d+)", url)
        if m and not found["language"]:
            found["language"] = m.group(1)
    for key, name in (("store", "storeId"), ("catalog", "catalogId"), ("language", "languageId")):
        m = re.search(name + r"""["']?\s*[:=]\s*["']?(-?\d+)""", html)
        if m and not found[key]:
            found[key] = m.group(1)
    m = re.search(r"/catalog/store/(\d+)/", html)  # an API link written in the page
    if m and not found["store"]:
        found["store"] = m.group(1)
    return found


# ---------------------------------------------------------------------------
# Catalogue: one row per product colour
# ---------------------------------------------------------------------------

def new_row(shop, gender, path, product_id, colour_id):
    return {
        "id": f"{shop.prefix}_{product_id}_{colour_id}", "brand": shop.brand,
        "country": shop.country, "language": shop.language, "gender": gender,
        "product_id": product_id, "colour_id": colour_id, "category_paths": path,
    }


def zara_catalogue(shop, genders, limit):
    tree = shop.get_json(shop.base + "categories?ajax=true") or {}
    leaves = [x for x in leaf_categories(tree.get("categories")) if x[0] in genders]
    print(f"[zara] {len(leaves)} categories")
    rows = {}
    for gender, path, cat in leaves:
        cat_id = cat.get("redirectCategoryId") or cat.get("id")
        data = shop.get_json(shop.base + f"category/{cat_id}/products?ajax=true") or {}
        for group in data.get("productGroups", []):
            for element in group.get("elements", []):
                for comp in element.get("commercialComponents", []):
                    if not comp.get("id") or comp.get("type", "Product") != "Product":
                        continue
                    for colour in (comp.get("detail") or {}).get("colors", []):
                        add_zara_row(shop, rows, gender, path, comp, colour)
        if limit and len(rows) >= limit:
            break
    return list(rows.values())[:limit or None]


def add_zara_row(shop, rows, gender, path, comp, colour):
    row = new_row(shop, gender, path, comp["id"], colour.get("id", ""))
    if row["id"] in rows:  # same item listed in several categories
        old = rows[row["id"]]
        if path not in old["category_paths"].split("|"):
            old["category_paths"] += "|" + path
        if gender not in old["gender"].split("|"):
            old["gender"] += "|" + gender
        return
    seo = comp.get("seo") or {}
    sizes = colour.get("sizes") or []
    sku_sizes = {str(s["sku"]): s.get("name", "") for s in sizes if s.get("sku")}
    row.update({
        "name": comp.get("name", ""),
        "colour_name": colour.get("name", ""),
        "price_raw": colour.get("price", comp.get("price", "")),
        "url": (f"{shop.base}{seo['keyword']}-p{seo['seoProductId']}.html"
                f"?v1={colour.get('productId', '')}") if seo.get("keyword") else "",
        "image_url": find_image(colour.get("xmedia") or comp.get("xmedia")),
        "sizes": "|".join(s.get("name", "") for s in sizes),
        "sku_sizes": pack_skus(sku_sizes),
        "stock_id": colour.get("productId") or comp["id"],
        "catalogue_availability": colour.get("availability") or comp.get("availability", ""),
    })
    rows[row["id"]] = row


def itx_catalogue(shop, genders, limit):
    tree = shop.get_json(shop.itx("2/catalog/store/{store}/{catalog}/category",
                                  typeCatalog=1)) or {}
    leaves = [x for x in leaf_categories(tree.get("categories")) if x[0] in genders]
    print(f"[{shop.brand}] {len(leaves)} categories")

    # 1) which products are in which category
    where = {}  # product id -> ([genders], [paths])
    for gender, path, cat in leaves:
        url = shop.itx("3/catalog/store/{store}/{catalog}/category/%s/product" % cat.get("id"),
                       showProducts="false")
        data = shop.get_json(url) or {}
        ids = data.get("productIds") or [p.get("id") for p in data.get("products", [])]
        for pid in ids:
            genders_, paths = where.setdefault(str(pid), ([], []))
            if gender not in genders_:
                genders_.append(gender)
            if path not in paths:
                paths.append(path)
        if limit and len(where) >= limit:
            break
    ids = sorted(where)[:limit or None]
    print(f"[{shop.brand}] {len(ids)} products")

    # 2) product details, 50 per request
    rows = {}
    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]
        url = shop.itx("3/catalog/store/{store}/{catalog}/productsArray",
                       productIds=",".join(batch))
        for prod in (shop.get_json(url) or {}).get("products", []):
            genders_, paths = where.get(str(prod.get("id")), ([], []))
            add_itx_rows(shop, rows, "|".join(genders_), "|".join(paths), prod)
    return list(rows.values())


def add_itx_rows(shop, rows, gender, paths, prod):
    # A "bundle" product keeps its colours in bundleProductSummaries.
    for summary in prod.get("bundleProductSummaries") or [prod]:
        detail = summary.get("detail") or {}
        for colour in detail.get("colors", []):
            row = new_row(shop, gender, paths, prod.get("id"), colour.get("id", ""))
            sizes = colour.get("sizes") or []
            sku_sizes = {str(s["sku"]): s.get("name", "") for s in sizes if s.get("sku")}
            shown = [s for s in sizes if str(s.get("visibilityValue", "SHOW")).upper() == "SHOW"]
            slug = summary.get("productUrl") or prod.get("productUrl") or ""
            row.update({
                "name": prod.get("name") or summary.get("name", ""),
                "colour_name": colour.get("name", ""),
                "price_raw": next((s.get("price") for s in sizes if s.get("price")), ""),
                "url": f"{shop.base}{slug}" if slug else "",
                "image_url": find_image(colour) or find_image(detail.get("xmedia")),
                "sizes": "|".join(s.get("name", "") for s in sizes),
                "sku_sizes": pack_skus(sku_sizes),
                "stock_id": summary.get("id") or prod.get("id"),
                # what the catalogue itself says (SHOW = can be bought)
                "catalogue_availability": ("in_stock" if shown else "out_of_stock") if sizes else "",
            })
            rows[row["id"]] = row


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------

def fill_zara_sizes(shop, rows):
    """Zara's listing has no sizes: read them (with their SKUs) per colour
    from the product page data, so the stock check keeps only our colour."""
    todo = [r for r in rows if not r.get("sku_sizes") and r.get("url")]
    for i, row in enumerate(todo, 1):
        # one answer per product (all colours): cache it without ?v1=
        page_url = row["url"].split("?")[0] + "?ajax=true"
        data = shop.get_json(page_url) or {}
        product = data.get("product") or data
        for colour in (product.get("detail") or {}).get("colors", []):
            if str(colour.get("id")) == str(row["colour_id"]) or \
               str(colour.get("productId")) == str(row["stock_id"]):
                sizes = colour.get("sizes") or []
                row["sizes"] = "|".join(s.get("name", "") for s in sizes)
                row["sku_sizes"] = pack_skus({str(s["sku"]): s.get("name", "")
                                              for s in sizes if s.get("sku")})
                break
        if i % 100 == 0:
            print(f"  sizes {i}/{len(todo)}")
    missing = sum(1 for r in rows if not r.get("sku_sizes"))
    if missing:
        print(f"[zara] WARNING: no sizes for {missing} colours: their stock may mix colours")


def fetch_stock(shop, stock_id, cache):
    """{sku: availability} for one product, or {} if the shop gives nothing."""
    if stock_id in cache:
        return cache[stock_id]
    if shop.kind == "zara" and not shop.store_id:
        stock = {}
    elif shop.kind == "zara":
        url = (f"{shop.origin}/itxrest/1/catalog/store/{shop.store_id}"
               f"/product/id/{stock_id}/availability")
        data = shop.get_json(url, cache=False) or {}
        stock = {str(s.get("sku")): s.get("availability")
                 for s in data.get("skusAvailability", [])}
    else:
        url = shop.itx("2/catalog/store/{store}/{catalog}/product/%s/stock" % stock_id)
        data = shop.get_json(url, cache=False) or {}
        stock = {str(s.get("id")): s.get("availability")
                 for entry in data.get("stocks", []) for s in entry.get("stocks", [])}
    cache[stock_id] = stock
    return stock


def check_stock(shop, rows):
    """Fill the availability columns and append to stock_history.csv."""
    cache, checked = {}, now()
    for i, row in enumerate(rows, 1):
        stock = fetch_stock(shop, str(row["stock_id"]), cache)
        sku_sizes = unpack_skus(row.get("sku_sizes"))
        if sku_sizes:  # a product's stock lists all its colours: keep ours
            stock = {sku: a for sku, a in stock.items() if sku in sku_sizes}
        if stock:
            availability, sizes_ok, n_ok = summarize_stock(stock, sku_sizes)
            row.update(availability=availability, availability_from="stock_api",
                       sizes_in_stock=sizes_ok, n_sizes_in_stock=n_ok)
        else:  # no stock answer (e.g. no online shop in this country)
            row.update(availability=row.get("catalogue_availability") or "unknown",
                       availability_from="catalogue" if row.get("catalogue_availability") else "",
                       sizes_in_stock="", n_sizes_in_stock="")
        # Zara's listing has no sizes: then sizes_in_stock holds SKU numbers
        row["n_sizes"] = len(sku_sizes) or len(stock) or ""

        row["checked_at"] = checked
        if i % 100 == 0:
            print(f"  stock {i}/{len(rows)}")

    history = shop.dir / "stock_history.csv"
    new_file = not history.exists()
    with open(history, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["checked_at", "id", "availability", "sizes_in_stock"])
        for row in rows:
            writer.writerow([row["checked_at"], row["id"], row["availability"],
                             row["sizes_in_stock"]])


# ---------------------------------------------------------------------------

def save_images(shop, rows):
    folder = shop.dir / "images"
    folder.mkdir(exist_ok=True)
    for row in rows:
        path = folder / f"{row['id']}.jpg"
        if not row.get("image_url") or path.exists():
            continue
        time.sleep(shop.delay * 0.5)
        try:
            resp = shop.context.request.get(row["image_url"], timeout=30_000)
            if resp.ok:
                path.write_bytes(resp.body())
        except Exception as err:
            print(f"  image failed for {row['id']}: {str(err).splitlines()[0]}")


def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_brand(browser, brand, args):
    shop = Shop(browser, brand, args)
    products = shop.dir / "products.csv"

    if args.stock_only:
        if not products.exists():
            sys.exit(f"ERROR: {products} not found. Run once without --stock-only.")
        with open(products, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        genders = set(args.gender)
        catalogue = zara_catalogue if shop.kind == "zara" else itx_catalogue
        rows = catalogue(shop, genders, args.limit)
        for row in rows:  # Inditex sends prices as whole numbers (cents)
            raw = str(row.get("price_raw", "")).strip()
            row["price"] = round(int(raw) / args.price_divisor, 3) if raw.isdigit() else ""
        print(f"[{brand}] {len(rows)} product colours")
        if not rows:
            print(f"[{brand}] nothing found: check the raw/ answers in {shop.dir}")
            shop.context.close()
            return

    if not args.no_stock and shop.kind == "zara" and not shop.store_id:
        for row in [r for r in rows if r.get("url")][:3]:  # try up to 3 product pages
            shop.store_id = shop.find_store_on_page(row["url"])
            if shop.store_id:
                print(f"[zara] store id = {shop.store_id}")
                break
        if not shop.store_id:
            print("[zara] WARNING: no store id found, so no stock check: availability comes "
                  "from the catalogue only. Find it in your browser (product page, dev tools, "
                  "Network tab, filter 'availability') and pass --store-id.")
    if not args.no_stock:
        if shop.kind == "zara":
            fill_zara_sizes(shop, rows)
        check_stock(shop, rows)
    if args.images:
        save_images(shop, rows)
    write_rows(products, rows)

    counts = {}
    for row in rows:
        counts[row.get("availability") or "not checked"] = counts.get(row.get("availability") or "not checked", 0) + 1
    print(f"[{brand}] wrote {products} | availability: {counts}")
    shop.context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--brand", choices=[*BRANDS, "all"], default="all")
    parser.add_argument("--country", default="tn", help="2-letter shop country (default: tn)")
    parser.add_argument("--language", default="fr", help="site language (default: fr)")
    parser.add_argument("--gender", nargs="+", choices=["women", "men"], default=["women", "men"])
    parser.add_argument("--limit", type=int, default=0, help="stop after ~N products (smoke test)")
    parser.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    parser.add_argument("--stock-only", action="store_true", help="only re-check stock of products.csv")
    parser.add_argument("--no-stock", action="store_true", help="skip the stock check")
    parser.add_argument("--images", action="store_true", help="also download one picture per colour")
    parser.add_argument("--fresh", action="store_true", help="ignore cached catalogue answers")
    parser.add_argument("--show", action="store_true", help="show the browser window")
    parser.add_argument("--price-divisor", type=float, default=100,
                        help="price = price_raw / this (check it on the site once)")
    parser.add_argument("--store-id")
    parser.add_argument("--catalog-id")
    parser.add_argument("--language-id")
    parser.add_argument("--origin", help=argparse.SUPPRESS)  # tests: local fake shop
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright  # only needed here

    brands = list(BRANDS) if args.brand == "all" else [args.brand]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show)
        for brand in brands:
            run_brand(browser, brand, args)
        browser.close()


if __name__ == "__main__":
    main()
