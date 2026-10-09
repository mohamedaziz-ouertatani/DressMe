"""The XAI evaluation numbers read from the reports (src/phase4/xai_results.py),
shared by the jury report and Admin > Explainability."""

import sys

from app.config import ROOT, SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]
import xai_results as R  # noqa: E402


def test_md_tables():
    text = "intro\n\n| a | b |\n|---|---:|\n| x | 1.5 |\n| y | 2 |\n\ntext\n\n| c |\n|---|\n| z |\n"
    assert R.md_tables(text) == [[{"a": "x", "b": "1.5"}, {"a": "y", "b": "2"}], [{"c": "z"}]]


def test_results_from_the_real_reports():
    r = R.results(ROOT)
    labels, outfits, concepts = r["labels"], r["outfits"], r["concepts"]
    assert {row["field"] for row in labels["flag"]} == {"category", "sub_category", "pattern"}
    cat = next(row for row in labels["flag"] if row["field"] == "category")
    assert 0 <= cat["unsure_accuracy"] < cat["sure_accuracy"] <= 1
    assert {row["field"] for row in labels["deletion"]} == {"category", "sub_category", "pattern"}
    assert all(row["heatmap"] > row["shifted_region"] for row in labels["deletion"])
    assert {row["dataset"] for row in outfits["rows"]} == {"PolyVore", "Fashionpedia"}
    assert all(row["hit"] > row["chance"] for row in outfits["rows"])
    assert 0.5 < concepts["mean_auc"] <= 1 and any(c["concept"] == "denim" for c in concepts["rows"])
    for block in (labels, outfits, concepts):
        assert block["date"] and block["command"].startswith("python src/phase4/")


def test_missing_report(tmp_path):
    r = R.results(tmp_path)
    assert r["concepts"]["missing"] is True and r["concepts"]["command"]
