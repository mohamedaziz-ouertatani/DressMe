"""Shop connectors on recorded answers (never a real site): Shopify,
WooCommerce, the polite HTTP client, the check script and the frozen snapshot."""

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import ml  # noqa: F401  (puts src/ on the import path)
import check_shop_source
from connectors import shopify, snapshot, woocommerce
from connectors.http import Client

FIXTURES = Path(__file__).parent / "fixtures"
SHOPIFY = json.loads((FIXTURES / "shopify_products.json").read_text(encoding="utf-8"))
WOO = json.loads((FIXTURES / "woocommerce_products.json").read_text(encoding="utf-8"))
ARGS = SimpleNamespace(limit=0, catalogue=False)


class FakeSite:
    """Answers like a shop: {path start: (status, content type, body)}; records each URL."""

    def __init__(self, routes, robots="User-agent: *\nDisallow: /checkout\n"):
        self.routes, self.urls, self.accepts = routes, [], []
        self.robots = robots

    def __call__(self, url, timeout=30, accept="*/*"):
        self.urls.append(url)
        self.accepts.append(accept)
        path = url.split("example.tn", 1)[1]
        if path == "/robots.txt":
            return (200, "text/plain", self.robots.encode()) if self.robots is not None else (404, "", b"")
        for start, answer in self.routes.items():
            if path.startswith(start):
                status, ctype, body = answer(path) if callable(answer) else answer
                return status, ctype, body if isinstance(body, bytes) else json.dumps(body).encode()
        return 404, "text/html", b"not found"


def source(kind):
    return {"source_id": "test_tn", "kind": kind, "brand": "test", "base_url": "https://shop.example.tn",
            "delay_s": "0"}


def paged(first_page, empty):
    """Page 1 = the fixture, page 2 = empty: the end."""
    return lambda path: (200, "application/json", first_page if path.endswith("&page=1") else empty)


@pytest.fixture(autouse=True)
def no_saving(monkeypatch, tmp_path):
    monkeypatch.setattr("connectors.http.RAW_DIR", tmp_path / "raw")


# ------------------------------------------------------------------ Shopify
def test_shopify_one_listing_per_colour_with_sizes():
    site = FakeSite({"/products.json": paged(SHOPIFY, {"products": []})})
    result = shopify.fetch(source("shopify"), ARGS, opener=site)
    assert result.status == "ok"
    by_id = {r.external_id: r for r in result.listings}
    assert set(by_id) == {"101_Blanc", "101_Bleu", "102"}            # gift card has no picture
    white = by_id["101_Blanc"]
    assert white.image_url == "https://cdn.example.tn/blanc.jpg"      # https added, ?v= dropped
    assert (white.price_tnd, white.sizes, white.sizes_in_stock, white.in_stock) == (89.0, ["S", "M"], ["S"], True)
    assert white.availability_level == "colour" and white.shop_colour == "Blanc"
    assert white.url == "https://shop.example.tn/products/chemise-en-lin?variant=1"
    blue = by_id["101_Bleu"]
    assert blue.image_url == "https://cdn.example.tn/bleu.jpg" and blue.in_stock is False
    bag = by_id["102"]
    assert bag.shop_colour == "" and bag.availability_level == "product" and bag.price_tnd == 45.5
    assert any("page=2" in u for u in site.urls)                      # it read until the empty page


def test_shopify_respects_robots_and_stops_on_blocks():
    forbidden = FakeSite({"/products.json": (200, "application/json", SHOPIFY)},
                         robots="User-agent: *\nDisallow: /products.json\n")
    result = shopify.fetch(source("shopify"), ARGS, opener=forbidden)
    assert result.status == "error" and "robots.txt forbids" in result.message
    assert not any("products.json" in u for u in forbidden.urls)      # never even asked

    for answer in [(403, "text/html", b"denied"), (429, "text/html", b"slow down"),
                   (200, "text/html", b"<html>captcha</html>")]:
        result = shopify.fetch(source("shopify"), ARGS, opener=FakeSite({"/products.json": answer}))
        assert result.status == "blocked" and result.listings == []

    result = shopify.fetch(source("shopify"), ARGS, opener=FakeSite({}))  # 404: not Shopify
    assert result.status == "error" and "not a Shopify shop" in result.message


def test_shopify_limit():
    site = FakeSite({"/products.json": paged(SHOPIFY, {"products": []})})
    result = shopify.fetch(source("shopify"), SimpleNamespace(limit=1), opener=site)
    assert len(result.listings) == 1


# ------------------------------------------------------------------ WooCommerce
def test_woocommerce_products_prices_and_stock():
    site = FakeSite({"/wp-json/wc/store/v1/products": paged(WOO, [])})
    result = woocommerce.fetch(source("woocommerce"), ARGS, opener=site)
    assert result.status == "ok"
    dress, jeans = result.listings                                      # no-photo product skipped
    assert (dress.external_id, dress.price_tnd, dress.sizes, dress.shop_colour) == ("11", 129.0, ["S", "M"], "Noir")
    assert dress.in_stock is True and dress.availability_level == "product" and dress.sizes_in_stock == []
    assert dress.url == "https://shop.example.tn/produit/robe-midi/"
    assert jeans.in_stock is False


def test_woocommerce_refuses_other_currencies_and_blocks():
    euro = [{**WOO[0], "prices": {**WOO[0]["prices"], "currency_code": "EUR"}}]
    result = woocommerce.fetch(source("woocommerce"), ARGS,
                               opener=FakeSite({"/wp-json/": paged(euro, [])}))
    assert result.status == "error" and "EUR" in result.message
    result = woocommerce.fetch(source("woocommerce"), ARGS,
                               opener=FakeSite({"/wp-json/": (403, "text/html", b"no")}))
    assert result.status == "blocked"


# ------------------------------------------------------------------ the polite client + check script
def test_client_saves_raw_answers_and_reads_robots_once(tmp_path):
    site = FakeSite({"/products.json": (200, "application/json; charset=utf-8", SHOPIFY)})
    client = Client("https://shop.example.tn", "test_tn", delay=0, opener=site)
    client.get_json("products.json?page=1")
    client.get_json("products.json?page=2")
    assert sum(u.endswith("/robots.txt") for u in site.urls) == 1
    assert len(list(client.folder.glob("*.json"))) == 2                # one file per URL
    no_robots = FakeSite({"/products.json": (200, "application/json", SHOPIFY)}, robots=None)
    assert Client("https://shop.example.tn", delay=0, opener=no_robots, save=False).get_json("products.json")


def test_check_script_finds_the_platform():
    shop = FakeSite({"/products.json": (200, "application/json", SHOPIFY)})
    lines, kind = check_shop_source.check("https://shop.example.tn",
                                          Client("https://shop.example.tn", delay=0, opener=shop, save=False))
    assert kind == "shopify" and "Chemise en lin" in lines[0]
    woo = FakeSite({"/wp-json/": (200, "application/json", WOO)})
    lines, kind = check_shop_source.check("https://shop.example.tn",
                                          Client("https://shop.example.tn", delay=0, opener=woo, save=False))
    assert kind == "woocommerce" and "129.0 TND" in lines[1]
    closed = FakeSite({}, robots="User-agent: *\nDisallow: /\n")
    lines, kind = check_shop_source.check("https://shop.example.tn",
                                          Client("https://shop.example.tn", delay=0, opener=closed, save=False))
    assert kind == "" and all("FORBIDS" in line for line in lines[:2])


# ------------------------------------------------------------------ frozen snapshot
def test_snapshot_rows_keep_their_date_and_local_picture(tmp_path, monkeypatch):
    path = tmp_path / "processed" / "shop_demo.csv"
    path.parent.mkdir(parents=True)
    cols = ["id", "brand", "name", "colour_name", "price_tnd", "url", "image_url", "image_path", "sizes",
            "availability", "availability_level", "sizes_in_stock", "checked_at"]
    rows = [{"id": "zr_1_2", "brand": "zara", "name": "SHIRT", "price_tnd": "89.9", "url": "u", "image_url": "i",
             "image_path": "processed/shop_demo_images/zr_1_2.jpg", "sizes": "S|M", "availability": "in_stock",
             "availability_level": "colour", "sizes_in_stock": "M", "checked_at": "2026-10-03T10:00:00Z"},
            {"id": "zr_3_4", "url": "u2", "image_url": "i2", "image_path": ""},       # picture not saved: kept
            {"id": "zr_5_6", "url": "u3", "image_url": "", "image_path": ""}]         # no picture at all: skipped
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows([{c: r.get(c, "") for c in cols} for r in rows])
    monkeypatch.setattr(snapshot, "DATA", tmp_path)
    monkeypatch.setattr(snapshot, "SNAPSHOT", path)
    result = snapshot.fetch({}, ARGS)
    assert result.status == "ok" and [x.external_id for x in result.listings] == ["zr_1_2", "zr_3_4"]
    r, later = result.listings
    assert later.image_path == "" and later.image_url == "i2"          # the collector downloads it
    assert r.snapshot and r.checked_at == "2026-10-03T10:00:00Z" and r.sizes_in_stock == ["M"]
    assert r.image_path == str(tmp_path / "processed/shop_demo_images/zr_1_2.jpg")


@pytest.fixture
def frozen_paths(tmp_path, monkeypatch):
    """freeze_shop_demo + the snapshot connector pointed at a temporary data/ folder."""
    import freeze_shop_demo as fz
    data = tmp_path / "data"
    monkeypatch.setattr(fz, "ROOT", tmp_path)
    monkeypatch.setattr(fz, "OUT_DIR", data / "raw" / "Shops")
    monkeypatch.setattr(fz, "OUT_CSV", data / "processed" / "shop_demo.csv")
    monkeypatch.setattr(fz, "IMG_DIR", data / "processed" / "shop_demo_images")
    monkeypatch.setattr(snapshot, "DATA", data)
    monkeypatch.setattr(snapshot, "SNAPSHOT", data / "processed" / "shop_demo.csv")
    return fz, data


def scraped(data, rows):
    """A products.csv like the one src/phase3/scrape_shops.py wrote on 2026-10-03."""
    path = data / "raw" / "Shops" / "zara_tn" / "products.csv"
    path.parent.mkdir(parents=True)
    cols = ["id", "brand", "country", "gender", "name", "colour_name", "category_paths", "price", "url",
            "image_url", "sizes", "sku_sizes", "availability", "availability_from", "sizes_in_stock", "checked_at"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows([{c: r.get(c, "") for c in cols} for r in rows])


ROWS = [{"id": "zr_1_2", "brand": "zara", "name": "SHIRT", "price": "89.9", "url": "u1", "image_url": "https://img/1.jpg",
         "sku_sizes": "11:S", "availability": "in_stock", "availability_from": "stock_api", "sizes_in_stock": "S",
         "checked_at": "2026-10-03T10:00:00Z"},
        {"id": "zr_3_4", "brand": "zara", "name": "JEAN", "price": "119", "url": "u2", "image_url": "https://img/2.jpg",
         "availability": "in_stock", "checked_at": "2026-10-03T10:00:00Z"}]


def test_snapshot_builds_itself_when_missing(frozen_paths, monkeypatch):
    fz, data = frozen_paths
    scraped(data, ROWS)
    asked = []

    def fake_download(url, path):            # picture 2 fails, like a refused CDN
        asked.append(url)
        if url.endswith("1.jpg"):
            path.write_bytes(b"jpeg")
            return True
        return False

    monkeypatch.setattr(fz, "download", fake_download)
    result = snapshot.fetch({"delay_s": "0"}, ARGS)
    assert result.status == "ok" and (data / "processed" / "shop_demo.csv").exists()
    shirt, jean = result.listings
    assert shirt.image_path == str(data / "processed/shop_demo_images/zr_1_2.jpg") and shirt.price_tnd == 89.9
    assert shirt.availability_level == "colour" and shirt.checked_at == "2026-10-03T10:00:00Z"
    assert jean.image_path == "" and jean.image_url == "https://img/2.jpg"   # tried again by the collector
    # the next run reads the file: no picture asked again
    asked.clear()
    assert snapshot.fetch({"delay_s": "0"}, ARGS).status == "ok" and asked == []


def test_snapshot_says_plainly_when_nothing_was_ever_scraped(frozen_paths):
    result = snapshot.fetch({}, ARGS)
    assert result.status == "error" and "ever scraped on this computer" in result.message


def test_snapshot_build_can_be_stopped(frozen_paths, monkeypatch):
    fz, data = frozen_paths
    scraped(data, ROWS)
    monkeypatch.setattr(fz, "download", lambda url, path: path.write_bytes(b"x") or True)
    result = snapshot.fetch({"delay_s": "0"}, SimpleNamespace(limit=0, should_stop=lambda: True))
    assert result.status == "stopped" and not (data / "processed" / "shop_demo.csv").exists()


def test_connectors_stop_between_pages_when_asked():
    site = FakeSite({"/products.json": paged(SHOPIFY, {"products": []})})
    result = shopify.fetch(source("shopify"), SimpleNamespace(limit=0, should_stop=lambda: True), opener=site)
    assert result.status == "stopped" and not any("products.json" in u for u in site.urls)
    site = FakeSite({"/wp-json/": paged(WOO, [])})
    result = woocommerce.fetch(source("woocommerce"), SimpleNamespace(limit=0, should_stop=lambda: True), opener=site)
    assert result.status == "stopped"


def test_inditex_stop_is_reported():
    from connectors import inditex
    assert inditex.outcome(-15, "[zara] opening\nSTOPPED by an admin\n")[0] == "stopped"


def test_check_script_saves_the_kind_but_never_enables(tmp_path, monkeypatch, capsys):
    from app.listings import load_sources, usable
    csv_path = tmp_path / "listing_sources.csv"
    # the team's table as it was before any check: the shops' kinds empty
    with open(Path(__file__).parents[2] / "mappings" / "listing_sources.csv", newline="", encoding="utf-8") as f:
        table = list(csv.DictReader(f))
    for row in table:
        if row["source_id"] in ("exist_tn", "hamadiabid_tn", "zen_tn", "hm_fr"):
            row["kind"] = ""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    monkeypatch.setattr(check_shop_source, "Settings", lambda: SimpleNamespace(mappings_dir=tmp_path))
    found = {"https://www.exist.com.tn/": "shopify", "https://ha.com.tn/": "woocommerce", "https://zen.com.tn/fr/": "",
             "https://www2.hm.com/fr_fr/": ""}
    checked = []

    def fake_check(url, **kw):
        checked.append(url)
        return [f"  checked {url}"], found[url]

    monkeypatch.setattr(check_shop_source, "check", fake_check)
    monkeypatch.setattr("sys.argv", ["check_shop_source.py", "--all", "--save"])
    check_shop_source.main()
    assert sorted(checked) == sorted(found)            # only the shops, never Inditex or the snapshot
    rows = {s["source_id"]: s for s in load_sources(tmp_path)}
    assert rows["exist_tn"]["kind"] == "shopify" and rows["hamadiabid_tn"]["kind"] == "woocommerce"
    assert rows["zen_tn"]["kind"] == ""                  # nothing supported found: left empty
    # --save fills the kind only: enabled / approved_on stay exactly what the team set
    before = {s["source_id"]: s for s in load_sources(Path(__file__).parents[2] / "mappings")}
    for sid in ("exist_tn", "hamadiabid_tn", "zen_tn"):
        assert (rows[sid]["enabled"], rows[sid]["approved_on"]) == (before[sid]["enabled"], before[sid]["approved_on"])
    # approved by the team on 2026-10-05: with a kind, Exist can run; Zen (nothing found) cannot
    assert usable(rows["exist_tn"]) == ("" if before["exist_tn"]["enabled"] == "yes" else "not enabled")
    assert "kind not set yet" in usable(rows["zen_tn"])
    assert rows["zara_tn"] == {**rows["zara_tn"]} and rows["inditex_snapshot"]["kind"] == "snapshot"
    assert "no platform we support" in capsys.readouterr().out


def test_check_moves_on_when_a_web_page_answers(monkeypatch):
    """ha.com.tn, 2026-10-04: /products.json answered an ordinary page (200, text/html).
    That means "not Shopify", not a block: the check must still try WooCommerce."""
    site = FakeSite({"/products.json": (200, "text/html; charset=utf-8", b"<html>page</html>"),
                     "/wp-json/": (200, "application/json", WOO)})
    client = Client("https://shop.example.tn", delay=0, opener=site, save=False)
    lines, kind = check_shop_source.check("https://shop.example.tn", client)
    assert kind == "woocommerce"
    assert "not this platform" in lines[0] and "YES" in lines[1]
    # a real refusal still stops the check
    refused = FakeSite({"/products.json": (403, "text/html", b"denied")})
    lines, kind = check_shop_source.check(
        "https://shop.example.tn", Client("https://shop.example.tn", delay=0, opener=refused, save=False))
    assert kind == "" and "BLOCKED" in lines[0] and len(lines) == 1
    # during a real run, a web page where JSON was expected still stops the source
    result = shopify.fetch(source("shopify"), ARGS,
                           opener=FakeSite({"/products.json": (200, "text/html", b"<html>captcha</html>")}))
    assert result.status == "blocked"


# ------------------------------------------------------------------ sitemap + product pages (H&M France)
from datetime import datetime, timedelta, timezone  # noqa: E402

from connectors import sitemap  # noqa: E402

SM = FIXTURES / "sitemap"


def sm_site(products=None, robots=None, index=None, overrides=None):
    """A shop answering like www2.hm.com/fr_fr: robots.txt -> sitemap index -> product sitemap -> pages."""
    pages = {"111": "product-111.html", "222": "product-222.html", "333": "product-111.html", **(products or {})}
    routes = {"/sitemaps/index.xml": (200, "application/xml", (index or (SM / "index.xml").read_bytes())),
              "/sitemaps/fr_fr/products-1.xml": (200, "text/xml", (SM / "products-fr.xml").read_bytes()),
              "/sitemaps/de_de/": (200, "text/xml", b"<?xml version='1.0'?><urlset/>")}
    for pid, name in pages.items():
        body = (SM / name).read_bytes() if name.endswith(".html") else name
        routes[f"/fr_fr/productpage.{pid}.html"] = (200, "text/html", body) if isinstance(body, bytes) else body
    routes.update(overrides or {})
    return FakeSite(routes, robots=robots if robots is not None else (SM / "robots.txt").read_text())


def sm_source(**kw):
    return {"source_id": "hm_fr", "kind": "sitemap", "brand": "hm", "base_url": "https://shop.example.tn/fr_fr/",
            "delay_s": "0", "product_pattern": "productpage", "max_pages": "500", **kw}


def test_sitemap_reads_products_prices_and_sizes():
    site = sm_site()
    result = sitemap.fetch(sm_source(), SimpleNamespace(limit=0, last_seen={}), opener=site)
    assert result.status == "ok", result.message
    by_id = {r.external_id: r for r in result.listings}
    assert set(by_id) == {"/fr_fr/productpage.111.html", "/fr_fr/productpage.222.html", "/fr_fr/productpage.333.html"}
    shirt = by_id["/fr_fr/productpage.111.html"]
    assert (shirt.title, shirt.image_url, shirt.shop_colour) == ("Chemise en lin", "https://img.example.tn/111.jpg", "Blanc")
    assert shirt.price_tnd == round(29.99 * 3.40, 3) and shirt.price_original == "29.99 EUR"
    assert shirt.in_stock is True and shirt.availability_level == "product" and shirt.brand == "hm"
    jeans = by_id["/fr_fr/productpage.222.html"]
    assert jeans.url == "https://shop.example.tn/fr_fr/productpage.222.html"
    assert (jeans.sizes, jeans.sizes_in_stock, jeans.availability_level) == (["36", "38"], ["36"], "colour")
    # only the French sitemap, never the category page, and every product is "present"
    assert not any("de_de" in u and "productpage" in u for u in site.urls)
    assert result.present_ids == set(by_id)


def test_sitemap_cap_new_first_then_oldest():
    now = datetime.now(timezone.utc)
    last_seen = {"/fr_fr/productpage.111.html": now - timedelta(days=1),
                 "/fr_fr/productpage.222.html": now - timedelta(days=9)}
    site = sm_site()
    result = sitemap.fetch(sm_source(max_pages="2"), SimpleNamespace(limit=0, last_seen=last_seen), opener=site)
    # 333 is new, then 222 (checked 9 days ago) before 111 (checked yesterday)
    assert [r.external_id for r in result.listings] == ["/fr_fr/productpage.333.html", "/fr_fr/productpage.222.html"]
    assert len(result.present_ids) == 3                  # 111 not fetched, but still listed: not gone


def test_sitemap_respects_robots_and_stops_on_blocks():
    closed = sm_site(robots="User-agent: *\nDisallow: /fr_fr/productpage\nSitemap: https://shop.example.tn/sitemaps/index.xml\n")
    result = sitemap.fetch(sm_source(), SimpleNamespace(limit=0), opener=closed)
    assert result.status == "error" and "forbids the product pages" in result.message
    assert not any("productpage" in u for u in closed.urls)          # never asked for a forbidden page

    challenge = sm_site(overrides={"/sitemaps/index.xml": (200, "text/html", b"<html>Access Denied</html>")})
    assert sitemap.fetch(sm_source(), SimpleNamespace(limit=0), opener=challenge).status == "blocked"
    refused = sm_site(overrides={"/fr_fr/productpage.111.html": (403, "text/html", b"denied")})
    assert sitemap.fetch(sm_source(), SimpleNamespace(limit=0), opener=refused).status == "blocked"
    bot_check = sm_site(products={"111": "product-empty.html", "222": "product-empty.html", "333": "product-empty.html"})
    import connectors.sitemap as smod
    smod_empty, smod.EMPTY_IN_A_ROW = smod.EMPTY_IN_A_ROW, 3
    try:
        assert sitemap.fetch(sm_source(), SimpleNamespace(limit=0), opener=bot_check).status == "blocked"
    finally:
        smod.EMPTY_IN_A_ROW = smod_empty


def test_sitemap_stop_limit_and_currency(tmp_path, monkeypatch):
    stopped = sitemap.fetch(sm_source(), SimpleNamespace(limit=0, should_stop=lambda: True), opener=sm_site())
    assert stopped.status == "stopped"
    limited = sitemap.fetch(sm_source(), SimpleNamespace(limit=1), opener=sm_site())
    assert len(limited.listings) == 1
    rates = tmp_path / "rates.csv"
    rates.write_text("currency,tnd_per_unit,checked_on,note\nTND,1,,\n")
    monkeypatch.setattr(sitemap, "RATES_FILE", rates)
    monkeypatch.setattr(sitemap, "load_rates", lambda path=rates: {"TND": 1.0})
    no_rate = sitemap.fetch(sm_source(), SimpleNamespace(limit=0), opener=sm_site())
    assert no_rate.status == "error" and "EUR" in no_rate.message     # never guessed


def test_check_script_finds_the_sitemap_route():
    lines, kind = check_shop_source.check(
        "https://shop.example.tn/fr_fr/",
        Client("https://shop.example.tn/fr_fr/", delay=0, opener=sm_site(), save=False), pattern="productpage")
    assert kind == "sitemap" and "Chemise en lin" in lines[-1] and "EUR" in lines[-1]


def test_gone_only_when_missing_from_the_sitemap(client):
    from tests.test_listings import FakeLabeller, raw
    db, storage = client.app.state.db, client.app.state.settings.storage_dir
    t0 = datetime.now(timezone.utc)
    from app.listings import sync_listings
    sync_listings(db, "hm_fr", [raw("a"), raw("b"), raw("c")], FakeLabeller(), storage, now=t0)
    # next run fetched only "a"; the sitemap still lists a and b, c disappeared
    counts = sync_listings(db, "hm_fr", [raw("a")], FakeLabeller(), storage, now=t0 + timedelta(days=1),
                           keep_ids={"a", "b"})
    status = {d["external_id"]: d["status"] for d in db.listings.find()}
    assert counts["gone"] == 1 and status == {"a": "active", "b": "active", "c": "gone"}


def test_sitemap_keeps_the_query_that_names_the_product():
    """www2.hm.com, 2026-10-05: the check read 'productpage.html' alone, because the article
    number sits after the '?' and was cut off. Each article must stay its own page."""
    urlset = (b"<?xml version='1.0'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
              b"<url><loc>https://shop.example.tn/fr_fr/productpage.html?article=444</loc></url>"
              b"<url><loc>https://shop.example.tn/fr_fr/productpage.html?article=555</loc></url></urlset>")
    site = sm_site(overrides={"/sitemaps/fr_fr/products-1.xml": (200, "text/xml", urlset),
                              "/fr_fr/productpage.html": (200, "text/html", (SM / "product-111.html").read_bytes())})
    result = sitemap.fetch(sm_source(), SimpleNamespace(limit=0, last_seen={}), opener=site)
    assert sorted(r.external_id for r in result.listings) == [
        "/fr_fr/productpage.html?article=444", "/fr_fr/productpage.html?article=555"]
    assert any(u.endswith("?article=555") for u in site.urls)


def test_check_shows_sample_pages_when_no_address_matches():
    """exist.com.tn / ha.com.tn, 2026-10-05: sitemaps exist, but no address contains 'product'.
    The check tests a few of the deepest addresses and says which carry product data."""
    urlset = (b"<?xml version='1.0'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
              b"<url><loc>https://shop.example.tn/fr_fr/</loc></url>"
              b"<url><loc>https://shop.example.tn/fr_fr/homme/chemises/123-chemise-lin.html</loc></url></urlset>")
    site = sm_site(overrides={"/sitemaps/fr_fr/products-1.xml": (200, "text/xml", urlset),
                              "/fr_fr/homme/": (200, "text/html", (SM / "product-111.html").read_bytes())})
    lines, kind = check_shop_source.check(
        "https://shop.example.tn/fr_fr/",
        Client("https://shop.example.tn/fr_fr/", delay=0, opener=site, save=False), pattern="productpage")
    text = "\n".join(lines)
    assert kind == ""                                           # never saved without a pattern
    assert "no address contains 'productpage'" in text
    assert "123-chemise-lin.html HAS product data" in text and "set product_pattern" in text


# ------------------------------------------------------------------ fixes of 2026-10-07 (live checks)
def test_pages_are_asked_for_as_html_and_api_answers_as_json():
    """exist.com.tn (PrestaShop) answers a page request that prefers JSON with an empty HTTP 500."""
    site = sm_site()
    sitemap.fetch(sm_source(), SimpleNamespace(limit=0, last_seen={}), opener=site)
    asked = dict(zip(site.urls, site.accepts))
    assert asked["https://shop.example.tn/fr_fr/productpage.111.html"].startswith("text/html")
    assert asked["https://shop.example.tn/sitemaps/index.xml"].startswith("application/xml")
    site = FakeSite({"/products.json": paged(SHOPIFY, {"products": []})})
    shopify.fetch(source("shopify"), ARGS, opener=site)
    assert site.accepts[-1].startswith("application/json")


def test_accented_addresses_are_percent_encoded():
    """ha.com.tn's sitemap lists e.g. .../sac-à-main: urllib refused it ('ascii' codec)."""
    from connectors.http import ascii_url
    assert ascii_url("https://ha.com.tn/catalogue/femme/sac-à-main") == \
        "https://ha.com.tn/catalogue/femme/sac-%C3%A0-main"
    already = "https://ha.com.tn/catalogue/femme/sac-%C3%A0-main?a=1&b=x%20y"
    assert ascii_url(already) == already                       # never encoded twice


def test_sitemap_pictures_are_not_pages_and_product_sitemaps_come_first():
    # Exist lists each product's picture inside its <url> (<image:loc>)
    text = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
            '<url><loc>https://shop.example.tn/jeans/7885-jean.html</loc>'
            '<image:image><image:loc>https://shop.example.tn/169496-home_default/jean.jpg</image:loc></image:image>'
            '</url></urlset>')
    assert sitemap.sitemap_locs(text) == (False, ["https://shop.example.tn/jeans/7885-jean.html"])
    # H&M's index lists ~1,000 sitemaps, the products ones among pictures and filters
    listed = ["https://x/fr_fr.image.0.xml", "https://x/fr_fr.filterpages.0.xml", "https://x/fr_fr.product.0.xml"]
    assert sitemap.products_first(listed)[0] == "https://x/fr_fr.product.0.xml"


# ------------------------------------------------------------------ Hamadi Abid (sitemap + the shop's JSON API)
from connectors import hamadiabid  # noqa: E402

HA_SITEMAP = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
              '<url><loc>https://shop.example.tn/catalogue/femme</loc></url>'
              '<url><loc>https://shop.example.tn/catalogue/femme/jeans/jean-mom/0039585-article-pantalon-mom-fit</loc></url>'
              '<url><loc>https://shop.example.tn/catalogue/homme/pulls/pull-col-rond/0040001-article-pull-côtelé</loc></url>'
              '<url><loc>https://shop.example.tn/catalogue/fillette/t-shirts/t-shirt-mc/0050756-article-t-shirt</loc></url>'
              '</urlset>').encode("utf-8")


def ha_item(ref, section, price="79,99 TND", discounted=None, stock=(1, 0)):
    return {"list": [{"ref": ref, "title": f"Article {ref}", "image": f"img-{ref}",
                      "price": price, "priceDiscounted": discounted or price,
                      "section": {"seoName": section}, "color": {"name": "DARK BLUE"},
                      "sizes": {"38": [{"stock": stock[0]}], "40": [{"stock": stock[1]}]}}]}


def ha_site(answers):
    def api(path):
        ref = path.split("reference=")[1].split("&")[0]
        return (200, "application/json", answers[ref]) if ref in answers else (400, "application/json", b"{}")
    return FakeSite({"/sitemap.xml": (200, "text/xml", HA_SITEMAP), "/api/items/ref": api},
                    robots="User-agent: *\nAllow: /\nDisallow: /panier\nSitemap: https://shop.example.tn/sitemap.xml\n")


def ha_source(**kw):
    return {"source_id": "hamadiabid_tn", "kind": "hamadiabid", "brand": "hamadiabid",
            "base_url": "https://shop.example.tn/", "delay_s": "0",
            "product_pattern": "/catalogue/(femme|homme)/.*-article-", **kw}


def test_hamadiabid_reads_the_api_for_each_sitemap_product():
    site = ha_site({"0039585": ha_item("0039585", "femme", discounted="59,99 TND"),
                    "0040001": ha_item("0040001", "homme", price="1.299,00 TND", stock=(0, 0))})
    result = hamadiabid.fetch(ha_source(), SimpleNamespace(limit=0, last_seen={}), opener=site)
    assert result.status == "ok", result.message
    by_id = {r.external_id: r for r in result.listings}
    assert set(by_id) == {"0039585", "0040001"}                     # kids' section left out by the pattern
    jeans = by_id["0039585"]
    assert (jeans.price_tnd, jeans.gender, jeans.shop_colour) == (59.99, "women", "DARK BLUE")
    assert (jeans.sizes, jeans.sizes_in_stock, jeans.in_stock) == (["38", "40"], ["38"], True)
    assert jeans.image_url == "https://shop.example.tn/api/image/get/product/img-0039585"
    assert jeans.url.endswith("0039585-article-pantalon-mom-fit")
    pull = by_id["0040001"]
    assert (pull.price_tnd, pull.gender, pull.in_stock) == (1299.0, "men", False)
    # the same question the shop's page asks, accents encoded
    api = [u for u in site.urls if "/api/items/ref" in u]
    assert any("reference=0039585&selectedSection=femme&selectedGroupName=jeans&selectedSubGroupName=jean-mom" in u
               for u in api)
    assert result.present_ids == {"0039585", "0040001"}


def test_hamadiabid_skips_unknown_products_and_stops_on_blocks():
    site = ha_site({"0040001": ha_item("0040001", "homme")})        # 0039585: HTTP 400 from the API
    result = hamadiabid.fetch(ha_source(), SimpleNamespace(limit=0, last_seen={}), opener=site)
    assert result.status == "ok" and [r.external_id for r in result.listings] == ["0040001"]
    assert "1 skipped" in result.message
    refused = FakeSite({"/sitemap.xml": (200, "text/xml", HA_SITEMAP), "/api/items/ref": (403, "text/html", b"no")},
                       robots="User-agent: *\nSitemap: https://shop.example.tn/sitemap.xml\n")
    assert hamadiabid.fetch(ha_source(), SimpleNamespace(limit=0), opener=refused).status == "blocked"
    page = FakeSite({"/sitemap.xml": (200, "text/xml", HA_SITEMAP), "/api/items/ref": (200, "text/html", b"<html>")},
                    robots="User-agent: *\nSitemap: https://shop.example.tn/sitemap.xml\n")
    assert hamadiabid.fetch(ha_source(), SimpleNamespace(limit=0), opener=page).status == "blocked"
    closed = ha_site({})
    closed.robots = "User-agent: *\nDisallow: /api/\nSitemap: https://shop.example.tn/sitemap.xml\n"
    result = hamadiabid.fetch(ha_source(), SimpleNamespace(limit=0), opener=closed)
    assert result.status == "error" and not any("/api/" in u for u in closed.urls)
    with pytest.raises(ValueError):
        hamadiabid.tnd("29,99 EUR")


def test_product_pages_keep_only_their_product_data(tmp_path, monkeypatch):
    """Whole Exist pages were ~190 KB each (~95 MB a run): only what was read is kept."""
    monkeypatch.setattr("connectors.http.RAW_DIR", tmp_path / "raw")
    handed = []
    args = SimpleNamespace(limit=0, last_seen={}, on_listing=handed.append, on_total=lambda n: handed.append(n))
    result = sitemap.fetch(sm_source(), args, opener=sm_site())
    assert result.status == "ok" and handed[0] == 3 and len(handed) == 4   # the total, then each product
    saved = [json.loads(p.read_text(encoding="utf-8")) for p in (tmp_path / "raw").rglob("*.json")]
    pages = [s for s in saved if "productpage" in s["url"]]
    assert len(pages) == 3 and all(isinstance(s["data"], dict) and "name" in s["data"] for s in pages)
    assert any(isinstance(s["data"], str) and "<urlset" in s["data"] for s in saved)   # sitemaps kept whole
