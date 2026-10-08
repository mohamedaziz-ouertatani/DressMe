"""The Seller assistant's price rule (app/resale.py): pure functions, no database."""

import pytest

from app.resale import load_rules, price_range

RULES = {"factor": {"*": 0.3, "shoes": 0.5}, "neighbours": 8, "min_friperie": 3}


def hit(price, source="exist_tn", category="top", score=0.9, title="Shirt", snapshot=False):
    return {"price_tnd": price, "source_id": source, "category": category, "score": score,
            "title": title, "snapshot": snapshot}


def test_team_table_loads():
    rules = load_rules()
    assert rules["factor"]["*"] > 0
    assert rules["neighbours"] >= 1 and rules["min_friperie"] >= 1


def test_shop_prices_use_the_category_factor_or_the_default():
    r = price_range([hit(100), hit(100, category="shoes")], RULES)
    assert r["based_on"] == "shops" and r["count"] == 2
    assert sorted(e["resale_price"] for e in r["examples"]) == [30, 50]
    assert r["low"] <= r["median"] <= r["high"]


def test_enough_friperie_prices_replace_shop_prices():
    hits = [hit(10, "sellers"), hit(14, "sellers"), hit(20, "sellers"), hit(300)]
    r = price_range(hits, RULES)
    assert r["based_on"] == "friperie" and r["count"] == 3
    assert r["median"] == 14 and 10 <= r["low"] <= r["high"] <= 20


def test_few_friperie_prices_are_mixed_with_shops():
    r = price_range([hit(12, "sellers"), hit(50)], RULES)
    assert r["based_on"] == "both" and r["count"] == 2      # 12 and 50 x 0.3 = 15


def test_few_friperie_prices_alone_stay_friperie():
    r = price_range([hit(12, "sellers")], RULES)
    assert r["based_on"] == "friperie" and r["median"] == 12


def test_rows_without_price_are_dropped_and_examples_capped():
    hits = [hit(None), hit(0)] + [hit(100 + i) for i in range(7)]
    r = price_range(hits, RULES)
    assert r["count"] == 7 and len(r["examples"]) == 5


def test_nothing_priced_gives_none():
    assert price_range([], RULES) is None
    assert price_range([hit(None)], RULES) is None


@pytest.mark.parametrize("rows, message", [
    ("factor,*,0.3,\nsetting,neighbours,8,\nsetting,min_friperie,3,\nmood,x,1,\n", "unknown kind"),
    ("factor,*,0.3,\nfactor,hats,0.5,\nsetting,neighbours,8,\nsetting,min_friperie,3,\n", "unknown category"),
    ("factor,top,0.3,\nsetting,neighbours,8,\nsetting,min_friperie,3,\n", r"\*"),
    ("factor,*,0.3,\nsetting,neighbours,8,\n", "min_friperie"),
])
def test_broken_tables_stop_with_a_clear_error(tmp_path, rows, message):
    path = tmp_path / "resale_pricing.csv"
    path.write_text("kind,name,value,note\n" + rows, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_rules(path)
