"""
Set the two "close" cuts of the wardrobe search (step 3b), on the validation split, and report them on the test split.

The search (src/phase4/search.py) says a piece is a CLOSE match when its cosine similarity with the query is at
least a cut. Words and photos need different cuts, and nobody can guess them: this script measures them.

For each split it builds fake wardrobes of `wardrobe_size` random pieces from the dataset pictures (their FashionCLIP
vectors were made once and sit in data/processed/embeddings/), asks about 300 queries per mode, and checks the answer
against the pieces' labels:

  words   "<type>" or "<colour> <type>", e.g. "jeans", "black jeans", turned into a vector by FashionCLIP's text side
          (through search.normalise_query, like the app). RIGHT = the piece has that type (and that colour).
  photo   another picture of the same type and colour, NOT in the wardrobe. RIGHT = same type and colour.

About 30% of the queries get a wardrobe with NO right piece, to see whether the search honestly says "nothing close".

  cut        the LOWEST cut (on validation) where, among the queries whose best result is above the cut ("shown as
             close"), that best result is right at least `target_precision` of the time
  precision  how often the best result above the cut is right
  top5       among queries with a right piece in the wardrobe: how often one is in the best 5
  honest     among queries with NO right piece: how often nothing was marked close

The pieces are Fashion Product pictures only: their colours are real labels (the other datasets' colours are our own
estimates, so "right" would be a guess). The words cut is steady from one seed to the next; the photo cut is not (about 0.82 to
0.86, and with more queries no photo cut reaches the target: look-alike labels such as blue / navy confuse it). Random wardrobes are easier than real ones (real ones hold many look-alikes),
and catalogue pictures are not phone photos: read the numbers as an honest start, not a guarantee.

    python src/phase4/calibrate_search.py [--queries 300] [--seed 0] [--no-write]

Writes reports/phase4/search_calibration.csv and the two cuts in mappings/search_rules.csv (unless --no-write).
"""

import argparse
import csv
import math
from collections import Counter

import numpy as np
import pandas as pd

import src_path  # noqa: F401  (finds modules in src/common, src/phase3, src/phase4)
import fashionclip
import search
from item_images import DATA, ROOT
from similarity import EMB_DIR

REPORT = ROOT / "reports" / "phase4" / "search_calibration.csv"
ABSENT_SHARE = 0.3          # queries whose wardrobe holds no right piece
MIN_PIECES = 3              # a label (type, or colour + type) must have this many pieces in the split to be asked about
GRID = 0.001                # cuts are tried in steps of this
TOP = 5                     # the "top5" check
SPLITS = ("val", "test")
DISPLAY = {"t-shirt": "t-shirt"}            # a type is typed with a space for its hyphen ("casual shoes")


def load_pool():
    """Fashion Product pictures of the validation and test splits that have a vector: labels + one unit vector each."""
    df = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False,
                     usecols=["id", "dataset", "sub_category", "primary_colour", "colour_source", "split", "duplicate"])
    df = df[(df["dataset"] == "fashion_product") & (df["colour_source"] == "label") & (df["duplicate"] != "True")
            & df["split"].isin(SPLITS) & (df["sub_category"] != "") & (df["primary_colour"] != "")]
    ids = pd.read_csv(EMB_DIR / "fashionclip_ids.csv", dtype=str)["id"]
    row_of = pd.Series(np.arange(len(ids)), index=ids)
    df = df[df["id"].isin(row_of.index)].reset_index(drop=True)
    vectors = np.load(EMB_DIR / "fashionclip.npy", mmap_mode="r")
    df["vector_row"] = row_of[df["id"]].values
    return df, vectors


def typed(sub_category):
    return DISPLAY.get(sub_category, sub_category.replace("-", " "))


def build_wardrobe(everyone, right, left_out, absent, size, rng):
    """The positions of `size` random pieces. `right` = the pieces that answer the query (none of them if absent,
    else 1 to 3 of them); `left_out` = pieces that must not be in the wardrobe (the photo itself)."""
    others = np.setdiff1d(everyone, np.concatenate([right, left_out]))
    if absent:
        return rng.choice(others, size, replace=False)
    k = min(int(rng.integers(1, 4)), len(right))
    return np.concatenate([rng.choice(right, k, replace=False), rng.choice(others, size - k, replace=False)])


def run_queries(mode, pool, vectors, n, size, rng, encode_text, terms):
    """One row per query: has_right, top1_sim, top1_right, top5_right (the best result's similarity and rightness),
    and what was asked / what came first (for the list of confusions)."""
    types, colours = pool["sub_category"].to_numpy(), pool["primary_colour"].to_numpy()
    everyone = np.arange(len(pool))
    # the labels we may ask about: types, and (colour, type) pairs, each with enough pieces
    by_type = pool.groupby("sub_category").size()
    by_pair = pool.groupby(["primary_colour", "sub_category"]).size()
    asked_types = list(by_type[by_type >= MIN_PIECES].index)
    asked_pairs = list(by_pair[by_pair >= MIN_PIECES].index)
    rows = []
    for _ in range(n):
        absent = rng.random() < ABSENT_SHARE
        if mode == "text" and rng.random() < 0.5:            # "<type>"
            kind = asked_types[rng.integers(len(asked_types))]
            right = everyone[types == kind]
            query = typed(kind)
        else:                                                # "<colour> <type>" (and every photo query)
            colour, kind = asked_pairs[rng.integers(len(asked_pairs))]
            right = everyone[(types == kind) & (colours == colour)]
            query = f"{colour} {typed(kind)}"
        left_out = np.empty(0, int)
        if mode == "photo":                                  # the query picture is one of the right ones, kept out
            picture = rng.choice(right)
            left_out, right = np.array([picture]), right[right != picture]
            query_vec = vectors[picture]
        else:
            query_vec = encode_text(search.normalise_query(query, terms))
        wardrobe = build_wardrobe(everyone, right, left_out, absent, size, rng)
        is_right = np.isin(wardrobe, right)
        items = [{"vector": vectors[w], "right": bool(r), "label": f"{colours[w]} {typed(types[w])}"}
                 for w, r in zip(wardrobe, is_right)]
        ranked = search.rank_owned(query_vec, items, cut=0.0, limit=TOP)["results"]
        rows.append({"has_right": bool(is_right.any()), "top1_sim": ranked[0]["similarity"],
                     "top1_right": ranked[0]["item"]["right"], "asked": query, "got": ranked[0]["item"]["label"],
                     "top5_right": any(r["item"]["right"] for r in ranked)})
    return pd.DataFrame(rows)


def measure(rows, cut):
    """The report numbers of one set of queries at one cut."""
    shown = rows["top1_sim"] >= cut
    present, absent = rows[rows["has_right"]], rows[~rows["has_right"]]
    return {"cut": cut, "n_queries": len(rows),
            "precision": rows.loc[shown, "top1_right"].mean() if shown.any() else float("nan"),
            "top5_hit_rate": present["top5_right"].mean(),
            "honest_nothing_rate": (absent["top1_sim"] < cut).mean()}


def choose_cut(rows, target):
    """The lowest cut (a grid of 0.001) whose precision reaches the target, with at least a tenth of the queries shown
    as close (a cut that only keeps 3 queries proves nothing). If no cut reaches it, the most precise one."""
    min_shown = max(20, len(rows) // 10)
    sims, right = rows["top1_sim"].to_numpy(), rows["top1_right"].to_numpy()
    best = None
    for cut in np.arange(math.floor(sims.min() / GRID) * GRID, sims.max() + GRID, GRID):
        shown = sims >= cut
        if shown.sum() < min_shown:
            break
        precision = right[shown].mean()
        if precision >= target:
            return round(float(cut), 3), True
        if best is None or precision > best[0]:
            best = (precision, round(float(cut), 3))
    return best[1], False


def write_cuts(cuts, test_precision, args, rules):
    """Put the two cuts (and where they come from) in the team's rules file; every other row stays as it was."""
    path = search.RULES_CSV
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    why = (f"REVIEW: set by src/phase4/calibrate_search.py on the validation split ({args.queries} queries, seed {args.seed}, "
           f"fake wardrobes of {int(rules['wardrobe_size'])} Fashion Product pieces): the lowest cut where the best result shown "
           f"as close is right at least {rules['target_precision']:.0%} of the time. On the test split it is right "
           "{:.1%} of the time (reports/phase4/search_calibration.csv). Re-run the script after changing the model or the data.")
    for row in rows:
        if row["name"] in ("text_cut", "photo_cut"):
            mode = row["name"].split("_")[0]
            row["value"] = f"{cuts[mode]:g}"
            row["note"] = why.format(test_precision[mode]) + (" Words are compared with pictures, so the numbers are low."
                                                              if mode == "text" else " A picture is compared with pictures, so the numbers are high. This is the less certain cut: with other seeds or more "
                                                              "queries it moves and the target is not always reached (labels such as blue / navy or flats / casual shoes look alike), "
                                                              "so check it with a larger run (--queries 1000).")
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "value", "note"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--queries", type=int, default=300, help="queries per mode per split")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-write", action="store_true", help="only print; change no file")
    args = parser.parse_args()

    rules, terms = search.load_rules(), search.load_terms()
    size, target = int(rules["wardrobe_size"]), rules["target_precision"]
    df, vectors = load_pool()
    model, processor, device = fashionclip.load_model()
    cache = {}

    def encode_text(text):                                   # the same words are asked about many times
        if text not in cache:
            cache[text] = fashionclip.embed_texts([text], model, processor, device)[0].astype(np.float32)
        return cache[text]

    table, cuts, test_precision = [], {}, {}
    for mode_no, mode in enumerate(("text", "photo")):
        results = {}
        for split_no, split in enumerate(SPLITS):
            pool = df[df["split"] == split].reset_index(drop=True)
            unit = np.asarray(vectors[pool["vector_row"].to_numpy()], np.float32)
            unit /= np.linalg.norm(unit, axis=1, keepdims=True)
            rng = np.random.default_rng([args.seed, mode_no, split_no])
            results[split] = run_queries(mode, pool, unit, args.queries, size, rng, encode_text, terms)
            print(f"{mode:5} {split:4}: {len(pool)} pieces in the pool, {args.queries} queries")
        cut, reached = choose_cut(results["val"], target)
        cuts[mode] = cut
        if not reached:
            print(f"WARNING: no {mode} cut reaches precision {target}; using the most precise one")
        for split, name in (("val", "validation"), ("test", "test")):
            table.append({"split": name, "mode": mode, **measure(results[split], cut)})
        test_precision[mode] = table[-1]["precision"]
        right, wrong = results["val"][results["val"]["top1_right"]], results["val"][~results["val"]["top1_right"]]
        print(f"      best result's similarity on validation: median {right['top1_sim'].median():.3f} when right, "
              f"{wrong['top1_sim'].median():.3f} when wrong")
        # what goes wrong above the cut: the labels the search takes for each other (often near-synonyms)
        above = wrong[wrong["top1_sim"] >= cut]
        seen = Counter(zip(above["asked"], above["got"])).most_common(6)
        print("      wrong answers above the cut, asked -> got:", "; ".join(f"{a} -> {g} (x{n})" for (a, g), n in seen))

    out = pd.DataFrame(table)[["split", "mode", "cut", "n_queries", "precision", "top5_hit_rate", "honest_nothing_rate"]]
    out = out.round({"cut": 3, "precision": 3, "top5_hit_rate": 3, "honest_nothing_rate": 3})
    print("\n" + out.to_string(index=False))
    if not args.no_write:
        out.to_csv(REPORT, index=False, lineterminator="\n")
        write_cuts(cuts, test_precision, args, rules)
        print(f"\nwritten: {REPORT.relative_to(ROOT)} and the cuts in {search.RULES_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
