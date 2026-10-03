"""
The models behind the API, loaded once at start-up (they take ~1 min and
~1.5 GB of GPU memory). Tests replace them with small fakes.

    Analyzer.analyze(pil_image) -> {"category": {"value": "top", "conf": 0.98},
                                    "sub_category": ..., "pattern": ..., "colour": ...,
                                    "vector": <512 FashionCLIP numbers>}
    Catalog.search(vector, k)   -> nearest dataset product shots
    Catalog.search_shop(vector, k) -> nearest H&M products to buy ([] if not set up)
    Catalog.image(item_id)      -> PIL image of one dataset or H&M item (cropped)

They reuse the Phase 4 code in src/ (classifier, fashionclip, similarity,
estimate_colours) instead of copying it.
"""

import io
import sys

from .config import ROOT

sys.path.insert(0, str(ROOT / "src"))


class Analyzer:
    def __init__(self):
        import joblib
        import classifier
        import estimate_colours
        import fashionclip

        self._classifier, self.device = classifier.load_classifier()
        self._clip, self._processor, _ = fashionclip.load_model(self.device)
        # our own file, written by src/estimate_colours.py (never load one from elsewhere)
        self._colour = joblib.load(estimate_colours.MODEL_PATH)
        self._modules = (classifier, fashionclip, estimate_colours)

    def analyze(self, img):
        classifier, fashionclip, estimate_colours = self._modules
        p = classifier.predict([img], self._classifier, self.device)[0]
        out = {f: {"value": p[f], "conf": round(p[f + "_conf"], 3)}
               for f in ("category", "sub_category", "pattern")}
        # colour: same features and metal rule as the dataset estimates
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        X = estimate_colours.product_features(io.BytesIO(buf.getvalue())).reshape(1, -1)
        colour, conf = estimate_colours.predict(self._colour, X, [p["category"]])
        out["colour"] = {"value": str(colour[0]), "conf": round(float(conf[0]), 3)}
        out["vector"] = fashionclip.embed_images([img], self._clip, self._processor, self.device)[0]
        return out


class Catalog:
    """Dataset product shots (PolyVore, Fashion Product) as inspiration, and the
    H&M shop catalogue as things to buy (only if src/embed_hm.py has been run)."""

    DATASETS = ["polyvore", "fashion_product"]

    def __init__(self):
        import similarity
        from item_images import load_item_image

        self._index = similarity.SimilarityIndex.load()
        try:
            self._shop = similarity.SimilarityIndex.load_shop()
        except FileNotFoundError:
            print("H&M shop catalogue not found: /similar returns no shop items")
            self._shop = None
        self._load = load_item_image

    def search(self, vector, k=6, category=None):
        hits = self._index.search(vector, k=k, datasets=self.DATASETS, category=category)
        return [{"id": r.id, "category": r.category, "sub_category": r.sub_category,
                 "colour": r.primary_colour, "score": round(float(r.score), 3)}
                for r in hits.itertuples()]

    def search_shop(self, vector, k=6, category=None):
        if self._shop is None:
            return []
        hits = self._shop.search(vector, k=k, category=category)
        return [{"id": r.id, "name": r.name, "shop": "H&M", "department": r.department,
                 "category": r.category, "sub_category": r.sub_category,
                 "colour": r.primary_colour, "score": round(float(r.score), 3)}
                for r in hits.itertuples()]

    def image(self, item_id):
        if item_id.startswith("hm_"):
            if self._shop is None:
                return None
            meta = self._shop.meta
            rows = meta[meta["id"] == item_id]
        else:
            meta = self._index.meta
            rows = meta[(meta["id"] == item_id) & meta["dataset"].isin(self.DATASETS)]
        return self._load(rows.iloc[0].to_dict()) if len(rows) else None


def colour_min_confidence():
    """Below this, a predicted colour is only a suggestion (same cut as the dataset)."""
    try:
        import estimate_colours
        return estimate_colours.MIN_CONFIDENCE
    except Exception:
        return 0.7
