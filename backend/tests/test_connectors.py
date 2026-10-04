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
            {"id": "zr_3_4", "url": "u2", "image_url": "i2", "image_path": ""}]        # no picture saved: skipped
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows([{c: r.get(c, "") for c in cols} for r in rows])
    monkeypatch.setattr(snapshot, "DATA", tmp_path)
    monkeypatch.setattr(snapshot, "SNAPSHOT", path)
    result = snapshot.fetch({}, ARGS)
    assert result.status == "ok" and len(result.listings) == 1
    r = result.listings[0]
    assert r.snapshot and r.checked_at == "2026-10-03T10:00:00Z" and r.sizes_in_stock == ["M"]
    assert r.image_path == str(tmp_path / "processed/shop_demo_images/zr_1_2.jpg")
    monkeypatch.setattr(snapshot, "SNAPSHOT", tmp_path / "missing.csv")
    assert snapshot.fetch({}, ARGS).status == "error"


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
