"""
The models behind the API, loaded once at start-up (they take ~1 min and
~1.5 GB of GPU memory). Tests replace them with small fakes.

    Analyzer.analyze(pil_image) -> {"category": {"value": "top", "conf": 0.98,
                                                 "alternatives": [top 3], "unsure": False},
                                    "sub_category": ..., "pattern": ..., "colour": ...,
                                    "vector": <512 FashionCLIP numbers>}
    Analyzer.explain(pil_image, head, value) -> pictures of why (src/phase4/explain.py)
    Catalog.search(vector, k)   -> nearest dataset product shots
    Catalog.search_shop(vector, k) -> nearest H&M products to buy ([] if not set up)
    Catalog.image(item_id)      -> PIL image of one dataset or H&M item (cropped)

They reuse the Phase 4 code in src/ (classifier, fashionclip, similarity,
estimate_colours, explain) instead of copying it.
"""

import io
import sys

from .config import SRC_DIRS

sys.path[:0] = [str(d) for d in SRC_DIRS]


class Analyzer:
    def __init__(self):
        import joblib
        import classifier
        import estimate_colours
        import explain
        import fashionclip
        from colour_utils import Palette

        self._classifier, self.device = classifier.load_classifier()
        self._clip, self._processor, _ = fashionclip.load_model(self.device)
        # our own file, written by src/phase3/estimate_colours.py (never load one from elsewhere)
        self._colour = joblib.load(estimate_colours.MODEL_PATH)
        self._modules = (classifier, fashionclip, estimate_colours)
        self._explain, self._palette = explain, Palette()

    def analyze(self, img):
        explain = self._explain
        p = self.classify_for_mask(img)
        out = {f: {"value": p[f], "conf": round(p[f + "_conf"], 3), "alternatives": p["top3"][f]}
               for f in ("category", "sub_category", "pattern")}
        colours = self.colour_alternatives(img, p["category"])
        out["colour"] = {"value": colours[0]["value"], "conf": colours[0]["conf"], "alternatives": colours}
        settings = explain.load_settings()
        for f, guess in out.items():
            guess["unsure"] = explain.is_unsure(f, guess["alternatives"], settings)
        fashionclip = self._modules[1]
        out["vector"] = fashionclip.embed_images([img], self._clip, self._processor, self.device)[0]
        return out

    def colour_alternatives(self, img, category):
        """Top 3 colours: same features and metal rule as the dataset estimates."""
        estimate_colours = self._modules[2]
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        X = estimate_colours.product_features(io.BytesIO(buf.getvalue())).reshape(1, -1)
        return estimate_colours.predict_top(self._colour, X, [category])[0]

    def explain(self, img, head=None, value=None):
        """Pictures of why each label was given (see src/phase4/explain.py). Without
        `head`: the 4 fields at their best answer; with `head` + `value`: that answer only."""
        explain = self._explain
        if head is not None and head not in explain.FIELDS:
            raise ValueError(f"unknown field {head!r}")
        p = self.classify_for_mask(img)
        out = {}
        for f in [head] if head else explain.FIELDS:
            alternatives = self.colour_alternatives(img, p["category"]) if f == "colour" else p["top3"][f]
            shown = value or alternatives[0]["value"]
            entry = {"shown": shown, "alternatives": alternatives}
            if f == "colour":
                mask, share, reliable = explain.colour_map(img, shown, self._palette)
                entry.update(pixels=explain.mask_overlay(img, mask), share=share, reliable=reliable)
            else:
                heat = explain.gradcam(self._classifier, img, f, explain.class_index(f, shown), self.device)
                entry["heatmap"] = explain.overlay(img, heat)
            out[f] = entry
        return out

    def concept_vectors(self):
        """{concept: unit text vector} for the team's concepts (mappings/style_concepts.csv),
        computed once with FashionCLIP's text side (XAI: why two pieces look alike)."""
        if getattr(self, "_concepts", None) is None:
            import explain_similarity
            fashionclip = self._modules[1]
            rows = explain_similarity.load_concepts()
            vecs = fashionclip.embed_texts([r["prompt"] for r in rows], self._clip, self._processor, self.device)
            self._concepts = {r["concept"]: v.astype("float32") for r, v in zip(rows, vecs)}
        return self._concepts

    def classify_for_mask(self, img):
        """Small category-only hook used before background removal."""
        return self._modules[0].predict([img], self._classifier, self.device)[0]


class Catalog:
    """Dataset product shots (PolyVore, Fashion Product) as inspiration, and the
    H&M shop catalogue as things to buy (only if src/phase4/embed_hm.py has been run)."""

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

    SAME_PICTURE = 0.99    # a hit this close is the query's own photo (demo pieces come from PolyVore)

    def search(self, vector, k=6, category=None):
        hits = self._index.search(vector, k=k + 3, datasets=self.DATASETS, category=category)
        hits = hits[hits["score"] < self.SAME_PICTURE].head(k)
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

    def vector(self, item_id):
        """The stored picture vector of a dataset or H&M item (None if unknown)."""
        index = self._shop if item_id.startswith("hm_") else self._index
        if index is None or item_id not in index.row_of:
            return None
        return index.vector(item_id)

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


def unsure(field, alternatives):
    """The team's "not sure, check" rule (mappings/xai_settings.csv), for stored guesses."""
    import explain
    return explain.is_unsure(field, alternatives, explain.load_settings())
