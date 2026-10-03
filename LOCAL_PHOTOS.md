# Local photos: how to take and label them

Our own phone photos are the only data from the real DressMe setting: second-hand and wardrobe clothes in Tunisia. They form the **test set only** (never training), so we can say how well the models work on the photos our users will take. They are also the only way to measure traditional wear (jebba, kaftan) and swimwear, which are too rare in the public datasets.

Targets (Phase 3 plan): 500–1,000 wardrobe items, 150–300 friperie items, 50–100 local / traditional garments.

## Consent and privacy (before the first photo)

- Every contributor signs the consent form and can withdraw their photos at any time.
- Each contributor gets an **anonymous id** (`c01`, `c02`, …). Keep the list matching ids to people separate, in the team's private storage, never in the repo or in `labels.csv`.
- **No faces, no people.** Photograph the item alone. If a person or face is visible anyway, crop it out before adding the photo.
- In a friperie, ask the owner first. Don't photograph customers.
- Photos stay in `data/` (never committed, never shared outside the team) and are used only for this academic project.

## Taking the photos

- **One item per photo**, the **whole** piece in the frame (sleeves, hem and both shoes included).
- On a plain surface: bed, floor, wall or hanger. Don't look for a perfect background; real conditions are the point.
- Daylight if possible, no flash, item in focus. Portrait or landscape both work (the phone's rotation is handled).
- Shoes: the pair, side view. Bags: front view.
- Save as **JPEG** (on iPhone: Settings → Camera → Formats → *Most Compatible*, otherwise HEIC files are refused). At least 224 px on the short side; any phone photo is fine.

## Folder

```
data/raw/Local/
  photos/
    c01/  IMG_2041.jpg  IMG_2042.jpg ...     one folder per contributor
    c02/  ...
  labels.csv                                  made by --init, filled in by hand
```

## Labelling

```bash
python src/map_local.py --init     # adds one row per new photo to labels.csv (file + contributor filled)
# open labels.csv in Excel / LibreOffice / Google Sheets, fill in the rows, save as CSV
python src/map_local.py            # checks every label; fix what it lists, run again
python src/merge_and_split.py      # adds the photos to dressme.csv (test split)
```

Run `--init` again whenever new photos arrive: existing rows are kept. A row with no `category` counts as "not labelled yet" and is skipped, so you can label in several sessions.

| Column | What to write | Allowed values |
|---|---|---|
| `file` | filled by `--init`, don't change | |
| `contributor` | filled by `--init` (the folder name) | anonymous id: `c01` |
| `source` | where the item is | `wardrobe` (someone owns it), `friperie` (photographed in a shop) |
| `category` | **required** | top, bottom, dress, outerwear, shoes, bag, accessory, traditional, swimwear |
| `sub_category` | the type, if it is in the list | `mappings/sub_category_vocabulary.csv` (must belong to the category) |
| `primary_colour` | main colour | `mappings/colour_palette.csv` (21 colours) |
| `secondary_colour` | second colour, if clearly visible | same palette, different from primary |
| `pattern` | | solid, striped, checked, floral, printed |
| `season` | several allowed, separated by `\|` | summer, winter, mid-season |
| `usage` | several allowed, `\|` | casual, formal, sport, wedding, eid, work |
| `style` | several allowed, `\|` | classic, streetwear, modest, sporty, trendy |
| `coverage` | modesty level | 1 (very open) … 5 (fully covered) |
| `gender` | | men, women, unisex |
| `outfit_id` | optional: same number for pieces the owner wears together (per contributor, e.g. `1`) | any short text |
| `labelled_by` | who filled the row | first name or initials (team members only) |
| `checked_by` | a **second** team member who re-read the row | must differ from `labelled_by` |
| `note` | anything unclear | free text |

Rules (the same as for the public datasets):

- **Unknown stays empty. Never guess.** Unsure about the pattern or season? Leave it blank.
- Values are not case-sensitive (`Black` = `black`), but spelling must match the lists.
- The script stops on any mistake and says the line in `labels.csv`: wrong value, a type that doesn't belong to the category, a missing or unreadable photo, the same photo saved twice, a contributor id that looks like a name.
- It also reports how many rows are not double-checked yet. Aim for every row checked by a second person before the evaluation.

## After labelling

`data/processed/dressme.csv` then contains the photos with `dataset = local`, ids `lc_…`, `split = test` and their real colour labels. Evaluating the classifier, the colour model and the compatibility formula on them is the next step. `build_image_cache.py`, `embed_fashionclip.py` and the evaluation scripts don't read the `local` dataset yet; add it there once there are photos to test with.
