"""
Slow check of the REAL models (classifier, colour, FashionCLIP, catalog) on
real dataset photos. Skipped by default; run with:
    DRESSME_SLOW=1 python -m pytest tests/test_real_models.py
Needs the trained models and data/ (see the README).
"""

import os

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.skipif(os.getenv("DRESSME_SLOW") != "1", reason="set DRESSME_SLOW=1")


@pytest.fixture(scope="module")
def models():
    from app.ml import Analyzer, Catalog
    return Analyzer(), Catalog()


def test_analyzer_on_test_photos(models):
    from item_images import DATA, load_item_image
    analyzer, _ = models
    df = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False,
                     usecols=["id", "dataset", "image_path", "bbox_x", "bbox_y", "bbox_w", "bbox_h",
                              "category", "split"], nrows=200_000)
    sample = df[(df["split"] == "test") & (df["dataset"] == "fashion_product")].sample(40, random_state=0)
    right = 0
    for row in sample.to_dict("records"):
        out = analyzer.analyze(load_item_image(row))
        assert set(out) == {"category", "sub_category", "pattern", "colour", "vector"}
        assert abs(np.linalg.norm(out["vector"].astype(np.float32)) - 1) < 0.01
        right += out["category"]["value"] == row["category"]
    assert right >= 36          # the classifier is ~98% right on Fashion Product test photos


def test_catalog_search(models):
    _, catalog = models
    hits = catalog.search(np.ones(512, np.float32) / np.sqrt(512), k=4, category="shoes")
    assert len(hits) == 4 and all(h["category"] == "shoes" for h in hits)
    assert catalog.image(hits[0]["id"]) is not None
