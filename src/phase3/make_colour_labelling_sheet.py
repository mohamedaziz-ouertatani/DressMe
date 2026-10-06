"""
Prepare a hand-labelling set to measure the REAL accuracy of the colour model
on PolyVore and Fashionpedia (the model was only tested on Fashion Product).

Picks 200 random PolyVore items and 200 random Fashionpedia items:
  - from the val / test splits only (never seen by anything we train later),
  - that the colour model could look at (usable pixels; Fashionpedia crops
    >= 64 px with a polygon mask), whatever its confidence, so that the
    accuracy can be measured for any confidence cut,
  - no duplicate pictures.

Writes (inside data/, so never committed):
    data/interim/colour_labelling/images/<id>.jpg     the pictures to label
    data/interim/colour_labelling/colour_labelling.html  labelling page (open in a browser)
    data/interim/colour_labelling/colour_labels_template.csv  same thing as a spreadsheet

Fashionpedia pictures are crops around the item; everything outside the item's
mask is faded, so the labeller knows WHICH garment to label.
The model's guess is never shown (it would bias the labeller).

Then: label, save the CSV as data/interim/colour_labelling/colour_labels.csv and run
    python src/phase3/evaluate_colour_labels.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from eda_fashionpedia import DATA_DIR as FPD_DIR, SPLITS

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT_DIR = DATA / "interim" / "colour_labelling"
IMG_DIR = OUT_DIR / "images"
PALETTE = ROOT / "mappings" / "colour_palette.csv"

N_PER_DATASET = 200
SEED = 7
MAX_SIDE = 360   # pictures are shrunk to this size for the page
FADE = 0.75      # how much the area outside a Fashionpedia item is faded to white


def sample():
    df = pd.read_csv(DATA / "processed" / "dressme.csv", dtype=str, keep_default_na=False)
    est = pd.read_csv(DATA / "processed" / "colour_estimates.csv", dtype=str,
                      keep_default_na=False, usecols=["id"])
    pool = df[df["dataset"].isin(["polyvore", "fashionpedia"])
              & df["split"].isin(["val", "test"])
              & (df["duplicate"] == "False")
              & df["id"].isin(est["id"])]
    picked = pool.groupby("dataset").sample(N_PER_DATASET, random_state=SEED)
    return picked.sample(frac=1, random_state=SEED).reset_index(drop=True)  # mix datasets


def fashionpedia_masks(ids):
    """Polygons of the chosen Fashionpedia items (reads the big JSON once)."""
    masks = {}
    for split in ["train", "val"]:
        print(f"Reading {SPLITS[split][0]} ...")
        with open(FPD_DIR / SPLITS[split][0], encoding="utf-8") as f:
            for a in json.load(f)["annotations"]:
                item_id = f"fpd_{split}_{a['id']}"
                if item_id in ids:
                    masks[item_id] = a["segmentation"]
    return masks


def save_picture(row, polygons):
    img = Image.open(DATA / row.image_path).convert("RGB")
    if row.dataset == "fashionpedia":
        # fade everything outside the item, then crop around it with a margin
        mask = Image.new("L", img.size, 0)
        for poly in polygons:
            if len(poly) >= 6:
                ImageDraw.Draw(mask).polygon(poly, fill=255)
        white = Image.new("RGB", img.size, (255, 255, 255))
        faded = Image.blend(img, white, FADE)
        img = Image.composite(img, faded, mask)
        x, y, w, h = (float(v) for v in (row.bbox_x, row.bbox_y, row.bbox_w, row.bbox_h))
        m = 0.15 * max(w, h)
        img = img.crop((max(0, x - m), max(0, y - m),
                        min(img.width, x + w + m), min(img.height, y + h + m)))
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    img.save(IMG_DIR / f"{row.id}.jpg", quality=90)


def write_page(items, palette):
    """A single offline HTML page: one item at a time, click a colour."""
    data = json.dumps([{"id": r.id, "dataset": r.dataset, "category": r.category,
                        "label": r.original_label} for r in items.itertuples()])
    colours = json.dumps([[c, h] for c, h in zip(palette["colour"], palette["hex"])])
    html = PAGE.replace("__ITEMS__", data).replace("__COLOURS__", colours)
    (OUT_DIR / "colour_labelling.html").write_text(html, encoding="utf-8")


def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    items = sample()
    fpd_ids = set(items.loc[items["dataset"] == "fashionpedia", "id"])
    masks = fashionpedia_masks(fpd_ids)
    for row in items.itertuples():
        save_picture(row, masks.get(row.id, []))

    palette = pd.read_csv(PALETTE, keep_default_na=False)
    write_page(items, palette)
    template = items[["id", "dataset", "category", "original_label"]].assign(
        image_file=lambda d: "images/" + d["id"] + ".jpg", true_colour="", note="")
    template.to_csv(OUT_DIR / "colour_labels_template.csv", index=False)
    print(f"\n{len(items)} items ({items['dataset'].value_counts().to_dict()})")
    print(f"Open {OUT_DIR / 'colour_labelling.html'} in a browser, label, then "
          f"'Download CSV' and save it as {OUT_DIR / 'colour_labels.csv'}")


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Colour Labelling</title>
<style>
:root { --rust:#8E4420; --gold:#C9A063; --cream:#F2E8DA; --dark:#23201C; }
body { margin:0; font-family:system-ui,sans-serif; background:var(--cream); color:var(--dark); }
header { display:flex; gap:12px; align-items:center; flex-wrap:wrap; padding:12px 16px;
         background:var(--dark); color:var(--cream); }
header b { color:var(--gold); }
button { font:inherit; cursor:pointer; }
.bar { flex:1; min-width:120px; height:8px; background:#4a443c; border-radius:4px; }
.bar div { height:100%; background:var(--gold); border-radius:4px; }
main { max-width:900px; margin:0 auto; padding:16px; display:grid; gap:16px;
       grid-template-columns:minmax(0,1fr) minmax(0,1fr); }
@media (max-width:700px) { main { grid-template-columns:1fr; } }
.pic { background:#fff; border-radius:8px; display:flex; align-items:center;
       justify-content:center; min-height:360px; }
.pic img { max-width:100%; max-height:420px; }
.meta { font-size:14px; margin:4px 0 12px; }
.grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:6px; }
.c { display:flex; align-items:center; gap:6px; padding:6px; border:2px solid transparent;
     border-radius:6px; background:#fff; text-align:left; font-size:14px; }
.c span { width:18px; height:18px; border-radius:50%; border:1px solid #0003; flex:none; }
.c.on { border-color:var(--rust); background:#fbeee5; }
.nav { display:flex; gap:8px; margin-top:12px; flex-wrap:wrap; }
.nav button { padding:8px 14px; border-radius:6px; border:1px solid var(--dark); background:#fff; }
.nav .main { background:var(--rust); color:#fff; border-color:var(--rust); }
textarea { width:100%; box-sizing:border-box; margin-top:8px; font:inherit; }
.help { font-size:13px; color:#5b544b; margin-top:10px; }
</style></head><body>
<header><b>DressMe</b> colour labelling <span id="count"></span>
<div class="bar"><div id="prog"></div></div>
<button id="dl">Download CSV</button></header>
<main>
  <div class="pic"><img id="img" alt="item to label"></div>
  <div>
    <div class="meta" id="meta"></div>
    <div class="grid" id="grid"></div>
    <textarea id="note" rows="2" placeholder="Optional note (e.g. two colours, bad crop)"></textarea>
    <div class="nav">
      <button id="prev">← Back</button><button id="next" class="main">Next →</button>
      <button id="todo">Next unlabelled</button>
    </div>
    <p class="help">Label the <b>main colour of the item</b> (the non-faded part).
    “multicolour” = no single dominant colour; “unsure” = cannot tell (excluded from the
    accuracy). Answers are saved in this browser automatically.</p>
  </div>
</main>
<script>
const ITEMS = __ITEMS__;
const COLOURS = __COLOURS__.concat([["unsure", ""]]);
const KEY = "dressme-colour-labels-v1";
let labels = {};
try { labels = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
let i = 0;
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(labels)); } catch (e) {} };

const grid = document.getElementById("grid");
COLOURS.forEach(([name, hex]) => {
  const b = document.createElement("button");
  b.className = "c"; b.dataset.name = name;
  b.innerHTML = `<span style="background:${hex || "linear-gradient(90deg,#ccc,#fff)"}"></span>${name}`;
  if (name === "multicolour") b.firstChild.style.background =
      "conic-gradient(#C0392B,#F4D03F,#2E8B57,#2F6FD6,#7D3C98,#C0392B)";
  b.onclick = () => { set(name); if (i < ITEMS.length - 1) { i++; show(); } };
  grid.appendChild(b);
});

function set(name) {
  const it = ITEMS[i];
  labels[it.id] = Object.assign(labels[it.id] || {}, { colour: name });
  save(); show();
}
function show() {
  const it = ITEMS[i], lab = labels[it.id] || {};
  document.getElementById("img").src = "images/" + it.id + ".jpg";
  document.getElementById("meta").textContent =
    `${i + 1} / ${ITEMS.length} · ${it.dataset} · ${it.category} (${it.label})`;
  document.getElementById("note").value = lab.note || "";
  grid.querySelectorAll(".c").forEach(b => b.classList.toggle("on", b.dataset.name === lab.colour));
  const done = ITEMS.filter(x => labels[x.id] && labels[x.id].colour).length;
  document.getElementById("count").textContent = `${done} / ${ITEMS.length} labelled`;
  document.getElementById("prog").style.width = (100 * done / ITEMS.length) + "%";
}
document.getElementById("note").oninput = e => {
  const it = ITEMS[i];
  labels[it.id] = Object.assign(labels[it.id] || {}, { note: e.target.value }); save();
};
document.getElementById("prev").onclick = () => { if (i > 0) { i--; show(); } };
document.getElementById("next").onclick = () => { if (i < ITEMS.length - 1) { i++; show(); } };
document.getElementById("todo").onclick = () => {
  const j = ITEMS.findIndex(x => !(labels[x.id] && labels[x.id].colour));
  if (j >= 0) { i = j; show(); }
};
document.getElementById("dl").onclick = () => {
  const q = s => '"' + String(s || "").replace(/"/g, '""') + '"';
  const rows = [["id", "dataset", "category", "original_label", "image_file", "true_colour", "note"]]
    .concat(ITEMS.map(it => [it.id, it.dataset, it.category, it.label, "images/" + it.id + ".jpg",
                             (labels[it.id] || {}).colour, (labels[it.id] || {}).note]));
  const blob = new Blob([rows.map(r => r.map(q).join(",")).join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "colour_labels.csv"; a.click();
};
show();
</script></body></html>
"""

if __name__ == "__main__":
    main()
