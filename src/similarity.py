"""
Find the items most similar to a FashionCLIP vector ("find it in a shop").

    index = SimilarityIndex.load()
    hits = index.search(index.vector("fpd_val_123"), k=5, datasets=["polyvore"])

`search` returns a DataFrame of the k best items (id, score, and the
dressme.csv columns), best first. The score is the cosine similarity
(1 = same direction, 0 = unrelated).

The ~300 MB vector file is memory-mapped (read from disk on demand, not loaded
at once), and the dot products are done in chunks, so RAM use stays small.
At this size a plain dot product is fast enough; no FAISS needed.

Needs data/processed/embeddings/ from src/embed_fashionclip.py.
"""

import numpy as np
import pandas as pd

from fashionclip import DATA

EMB_DIR = DATA / "processed" / "embeddings"
CHUNK = 50_000
META_COLS = ["id", "dataset", "image_path", "bbox_x", "bbox_y", "bbox_w", "bbox_h",
             "category", "sub_category", "primary_colour", "image_group", "split"]


class SimilarityIndex:
    def __init__(self, vectors, meta):
        self.vectors = vectors           # N x 512 float16, unit length
        self.meta = meta                 # dressme.csv columns, same row order
        self.row_of = pd.Series(np.arange(len(meta)), index=meta["id"])

    @classmethod
    def load(cls, emb_dir=EMB_DIR):
        vectors = np.load(emb_dir / "fashionclip.npy", mmap_mode="r")
        ids = pd.read_csv(emb_dir / "fashionclip_ids.csv", dtype=str)
        meta = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str,
                           keep_default_na=False, usecols=META_COLS)
        meta = ids.merge(meta, on="id", how="left")   # keeps the .npy row order
        return cls(vectors, meta)

    def vector(self, item_id):
        """The stored vector of one item."""
        return np.asarray(self.vectors[self.row_of[item_id]], dtype=np.float32)

    def search(self, query, k=5, datasets=None, category=None, exclude_ids=()):
        """The k items closest to `query` (a 512 vector), optionally filtered.

        Copies of the query picture (same image_group) are left out when the
        query is one of our items, so we never return the item itself.
        """
        query = np.asarray(query, dtype=np.float32)
        scores = np.empty(len(self.meta), np.float32)
        for s in range(0, len(self.meta), CHUNK):
            scores[s:s + CHUNK] = self.vectors[s:s + CHUNK].astype(np.float32) @ query

        keep = np.ones(len(self.meta), bool)
        if datasets is not None:
            keep &= self.meta["dataset"].isin(datasets).to_numpy()
        if category is not None:
            keep &= (self.meta["category"] == category).to_numpy()
        if len(exclude_ids):
            groups = self.meta.loc[self.meta["id"].isin(exclude_ids), "image_group"]
            keep &= ~self.meta["id"].isin(exclude_ids).to_numpy()
            # Fashionpedia's image_group is the whole photo: only exclude the
            # same picture for product shots, not every item of the photo
            same_pic = self.meta["image_group"].isin(groups) & (self.meta["dataset"] != "fashionpedia")
            keep &= ~same_pic.to_numpy()
        scores[~keep] = -np.inf
        # also drop exact duplicate pictures among the results
        best = np.argsort(-scores)[: k * 5]
        hits = self.meta.iloc[best].assign(score=scores[best])
        hits = hits[np.isfinite(hits["score"])]
        picture = hits["image_group"].where(hits["dataset"] != "fashionpedia", hits["id"])
        hits = hits[~picture.duplicated()]
        return hits.head(k).reset_index(drop=True)
