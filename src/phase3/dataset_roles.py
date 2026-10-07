"""
What each dataset brings to DressMe and how the project uses it.

One place for this text, read by:
    eda_*.py                  "What this dataset brings to DressMe" section of each EDA report
    build_phase3_report.py    the "Dataset roles" section and the box in each EDA section
    notebooks/phase3_walkthrough.ipynb   section 2
Full field-by-field mapping: reports/phase3/dataset_feature_map.md

Edit the text here (not in the reports), then re-run the scripts that use it.
"""

# key -> name, kind of pictures, features it brings, what the project uses it for
ROLES = {
    "fashion_product": {
        "name": "Kaggle Fashion Product Images (Small)",
        "prefix": "fp_",
        "pictures": "60x80 px catalogue shots on white",
        "brings": [
            "the only real labels for colour (`baseColour` → `primary_colour`), "
            "`season` and `usage`",
            "category / sub_category from `articleType` (142 types)",
            "pattern from keywords in `productDisplayName`",
            "`gender`",
        ],
        "used_for": [
            "trains the colour model (`estimate_colours.py`) that fills colours for "
            "PolyVore and Fashionpedia",
            "trains the EfficientNet classifier (category, sub_category, pattern)",
            "FashionCLIP embeddings and the `/similar` search catalogue",
        ],
    },
    "fashionpedia": {
        "name": "Fashionpedia",
        "prefix": "fpd_",
        "pictures": "street / runway photos, several items per photo",
        "brings": [
            "real-life worn items with a bounding box (cropped for the models)",
            "pattern from the `textile pattern` attribute",
            "sub_category from the `nickname` attribute (kaftan → traditional)",
            "`coverage` (modesty, 1-5) from item length + linked sleeve / neckline parts",
            "outfits: every photo is one outfit (`outfit_id`)",
            "no colour label: colour is estimated",
        ],
        "used_for": [
            "trains the classifier on crops closer to real photos than catalogue shots",
            "coverage for the modest filter of the style profile (`min_coverage`)",
            "compatibility evaluation (AUC / FITB on the test photos)",
            "street → shop retrieval check of the FashionCLIP embeddings",
        ],
    },
    "polyvore": {
        "name": "Maryland PolyVore (Re-PolyVore)",
        "prefix": "pv_",
        "pictures": "product shots on white",
        "brings": [
            "31,333 user-made outfits (`outfit_id` + `position` from the file name)",
            "category (and sub_category for some folders) from the folder name",
            "no text, colour or pattern labels: colour is estimated, pattern predicted",
        ],
        "used_for": [
            "main source for outfit compatibility (`outfit_split`, clean test outfits "
            "for AUC / FITB)",
            "trains the classifier (category)",
            "FashionCLIP embeddings and the `/similar` search catalogue",
        ],
    },
    "local": {
        "name": "Local photos (wardrobe / friperie)",
        "prefix": "lc_",
        "pictures": "our own phone photos, one item each",
        "brings": [
            "every schema field labelled by hand, including `style`, `secondary_colour` "
            "and `source` = wardrobe / friperie",
            "the only real DressMe setting: friperie items and local garments (jebba, sefsari)",
        ],
        "used_for": [
            "test set only (`merge_and_split.py` forces it), to measure the gap between "
            "public data and our users",
        ],
    },
    "hm": {
        "name": "H&M Personalized Fashion Recommendations",
        "prefix": "hm_",
        "pictures": "shop product photos (shrunk to 320 px)",
        "brings": [
            "63k adult articles with category, colour, pattern (`graphical_appearance_name`) "
            "and usage labels",
            "product name, description and `product_code` (the colours of one product); "
            "no price",
        ],
        "used_for": [
            "shop catalogue, never training data: the H&M row of `/similar` "
            "(\"buy something similar\")",
        ],
    },
    "shop_demo": {
        "name": "Shop demo (Zara, Bershka, Pull&Bear)",
        "prefix": "zr_ / bk_ / pb_",
        "pictures": "shop product photos",
        "brings": [
            "real prices (TND), sizes and stock per colour; not mapped to the schema",
        ],
        "used_for": [
            "frozen snapshot of shop listings (scraping is stopped), shown by the "
            "`snapshot` listings connector",
        ],
    },
}


def role_markdown(key, level=2):
    """The "What this dataset brings to DressMe" section, as Markdown lines."""
    r = ROLES[key]
    lines = [f"{'#' * level} What this dataset brings to DressMe\n",
             "**Features it brings:**\n"]
    lines += [f"- {b}" for b in r["brings"]]
    lines += ["", "**How the project uses it:**\n"]
    lines += [f"- {u}" for u in r["used_for"]]
    lines += ["", "Field-by-field mapping: [dataset_feature_map.md](dataset_feature_map.md)\n"]
    return lines
