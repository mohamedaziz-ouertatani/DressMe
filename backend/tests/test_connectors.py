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
        self.routes, self.urls = routes, []
        self.robots = robots

    def __call__(self, url, timeout=30):
        self.urls.append(url)
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
    assert kind == "" and all("FORBIDS" in line for line in lines)


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
    """A products.csv like the one src/scrape_shops.py wrote on 2026-10-03."""
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
    import shutil
    from app.listings import load_sources, usable
    csv_path = tmp_path / "listing_sources.csv"
    shutil.copy(Path(__file__).parents[2] / "mappings" / "listing_sources.csv", csv_path)
    monkeypatch.setattr(check_shop_source, "Settings", lambda: SimpleNamespace(mappings_dir=tmp_path))
    found = {"https://www.exist.com.tn/": "shopify", "https://ha.com.tn/": "woocommerce", "https://zen.com.tn/fr/": ""}
    checked = []

    def fake_check(url):
        checked.append(url)
        return [f"  checked {url}"], found[url]

    monkeypatch.setattr(check_shop_source, "check", fake_check)
    monkeypatch.setattr("sys.argv", ["check_shop_source.py", "--all", "--save"])
    check_shop_source.main()
    assert sorted(checked) == sorted(found)            # only the shops, never Inditex or the snapshot
    rows = {s["source_id"]: s for s in load_sources(tmp_path)}
    assert rows["exist_tn"]["kind"] == "shopify" and rows["hamadiabid_tn"]["kind"] == "woocommerce"
    assert rows["zen_tn"]["kind"] == ""                  # nothing supported found: left empty
    assert all(rows[s]["enabled"] == "no" and rows[s]["approved_on"] == "" for s in ("exist_tn", "hamadiabid_tn"))
    assert usable(rows["exist_tn"]) == "not enabled"     # the team still has to read the terms
    assert rows["zara_tn"] == {**rows["zara_tn"]} and rows["inditex_snapshot"]["kind"] == "snapshot"
    assert "no platform we support" in capsys.readouterr().out
