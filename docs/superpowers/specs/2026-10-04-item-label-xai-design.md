# Item-label XAI — design (XAI sub-project 1 of 4)

Date: 2026-10-04. Status: approved in chat, waiting for spec review.

## Context

DressMe gets an explainability (XAI) layer for both end users (a short "why"
next to each answer) and the team / jury (offline analyses and reports). It is
split into four sub-projects, built in this order:

1. **Item labels** (this spec): why the classifier and the colour model chose a label.
2. Outfit score + buy advice: signed per-part contributions, positive reasons,
   the item that lowers the score most, evidence behind buy / skip.
3. Similarity + chat: why two items are similar, which tool calls led to a chat answer.
4. Team / jury layer: one XAI report in `reports/` + Admin > Explainability page.

Users buy unlabelled friperie pieces they can rarely return, so trusting (or
correcting) a label matters. Today the app stores a confidence per field but
shows no explanation, and the only "unsure" signal is the colour cut (0.7).

## Goals

- Show **where** the classifier looked for category, sub_category and pattern
  (Grad-CAM heatmap on the item photo), on demand.
- Show the **top 3 alternatives** with their confidence for every predicted field,
  and let the user see the heatmap of an alternative ("why not jeans?").
- Flag fields the model is **unsure** about and lead the user to correct them.
- Explain colour with a **pixel map** of the item pixels that look like the
  predicted colour.
- Measure, offline, whether the heatmaps and the "unsure" flag are honest.

## Non-goals

- Storing heatmaps (they are computed on demand, never saved).
- SHAP on the colour model's histogram features (goes to sub-project 4's report).
- Similarity, chat, outfit score explanations (sub-projects 2 and 3).
- Retraining or changing any model.

## Design

### 1. Free extras at analysis time (stored)

`classifier.decode` already has the full softmax per head. It now also returns,
per head, `top3`: a list of `{"value", "conf"}`.

- category, pattern: the 3 most probable classes.
- sub_category: the 3 most probable **inside the predicted category**,
  renormalised exactly like today's `sub_category_conf`.

`estimate_colours.predict` gets a sibling `predict_top(clf, X, categories, k=3)`
that returns the top 3 colours with the same metal rule (gold / silver never
for clothes) and renormalised probabilities.

`Analyzer.analyze` puts them in the answer: each field becomes
`{"value", "conf", "alternatives": [{"value","conf"}, ...], "unsure": bool}`.
`fields_from_analysis` stores this in `predicted` unchanged (existing items
without `alternatives` keep working: every reader uses `.get`).

**Unsure rule.** A field is unsure when `conf < min_conf[field]` **or**
`conf - second_conf < margin`. The values live in a new team-owned file
`mappings/xai_settings.csv` (`setting,value,note`), all rows marked `REVIEW`:

| setting | start value |
|---|---|
| `min_conf_category` | 0.6 |
| `min_conf_sub_category` | 0.5 |
| `min_conf_pattern` | 0.6 |
| `min_conf_colour` | 0.7 (same as `MIN_CONFIDENCE`; the empty-colour rule is unchanged) |
| `margin` | 0.15 |

The offline calibration table (section 5) shows the team what these cuts give.

### 2. `src/explain.py` (new, shared by the API and the evaluation script)

Pure functions, no web code, PIL + torch + numpy only.

- `gradcam(model, img, head, class_idx, device) -> np.ndarray (224 x 224, 0..1)`
  Hand-written Grad-CAM: a forward hook on `model.features[-1]` keeps the
  7 x 7 x 1280 map, one backward pass from the chosen head's logit, channel
  weights = mean gradient, ReLU, upsample to 224, normalise to 0..1. Runs in
  float32 with dropout off (`model.eval()`), gradients enabled only inside the
  function. The letterbox padding area is set to 0, so the map only covers the
  real picture. All three heads share one body, so the text in the app says
  "where the model looked to decide X", not "the part that is X".
- `class_index(head, value)` -> index in `classifier.HEADS[head]`, `ValueError`
  for an unknown class (the API turns it into 422).
- `colour_map(img, colour) -> (mask 224 x 224 bool, share float)`
  Item pixels = pixels farther than ΔE 6 from pure white (the cleaned photos are
  on white). Each item pixel is snapped to the nearest colour of
  `mappings/colour_palette.csv` in Lab; the mask is the pixels whose nearest
  colour is the predicted one, `share` = mask / item pixels. Known limit: for
  white / cream items the item area is unreliable on a white background; the
  response then says `"reliable": false` and the app shows only the top 3.
  This is a picture to help a user, not the colour model's own reasoning
  (the model reads Lab histograms); the app and report say so.
- `overlay(img, heat) -> PIL.Image` (jet colours blended 45% on the letterboxed
  photo) and `mask_overlay(img, mask) -> PIL.Image` (pixels outside the mask
  greyed out).

### 3. Backend

- `Analyzer.explain(img, head=None, value=None)` in `app/ml.py`:
  without `head`, explains the predicted class of category, sub_category and
  pattern + the colour map of the predicted colour; with `head` + `value`,
  only that head for that class (colour: the map of that colour). Returns
  overlays as JPEG data URLs (like `/tryon`).
- Endpoints (new router `routers/explain.py`, same `own_item` privacy rule:
  another user's item answers 404):
  - `GET /items/{id}/explain?head=&value=`
  - `GET /candidates/{id}/explain?head=&value=` (scans keep their cleaned photo)
- Response:
  ```json
  {"fields": {"category": {"value": "top", "conf": 0.91, "unsure": false,
                           "alternatives": [...], "heatmap": "data:image/jpeg;base64,..."},
              "colour": {"value": "navy", "conf": 0.64, "unsure": true,
                         "alternatives": [...], "pixels": "data:...", "share": 0.71,
                         "reliable": true}},
   "note": "..."}
  ```
  `value` / `conf` / `alternatives` come from the stored `predicted` (the
  stored answer is what is explained). For items saved before this change, the
  alternatives are recomputed from the photo on the fly. A corrected field
  still returns the model's view, marked `"corrected": true`.
- Errors: 404 (not yours / no photo), 422 (unknown head or value), 503 when the
  models are not loaded (same as the other model endpoints).
- Speed: about 0.1-0.3 s on the GPU for the full answer; no new dependency.
- The test fake Analyzer gets an `explain` that returns fixed small images.

### 4. Frontend

- `ScanPage` and the item view in `WardrobePage`: a "Why?" link next to the
  labels opens an `ExplainPanel` (new `ui/ExplainPanel.tsx`): the heatmap /
  pixel overlay, the top 3 as small confidence bars, a one-line note.
  Clicking an alternative reloads the panel for that class.
- A field marked `unsure` shows a "not sure, please check" badge that opens the
  existing correction control.
- New strings in en / fr / ar in `i18n`.

### 5. Offline evaluation (feeds sub-project 4)

`src/evaluate_explanations.py` → `reports/explanations_evaluation.md` +
`reports/figures/gradcam_examples.png`, on the test split from the image cache:

- **Examples:** Grad-CAM grid, correct and wrong predictions per category.
- **Deletion test:** blank (white) the top 10 / 20 / 40% heatmap pixels vs the
  same share of random item pixels; the predicted class's confidence must drop
  faster with the heatmap. Reported per head, on a sample (default 2,000 pictures,
  `--limit`).
- **Calibration of "unsure":** accuracy of sure vs unsure predictions per field
  with the `xai_settings.csv` cuts, plus accuracy per confidence bucket, so the
  team can tune the cuts.
- Runs > 10 min must be started as a separate process with a log (project rule).

### 6. Tests

- `tests` for `src/explain.py` on synthetic pictures: Grad-CAM shape and range,
  zero on the letterbox padding, a different map for a different class;
  `colour_map` on a two-colour picture gives the expected share; `class_index`
  rejects unknown values.
- `decode` returns `top3`; sub_category alternatives stay in the category.
- API (`backend/tests`, fake Analyzer): shape of both endpoints, 404 for another
  user's item, 422 for an unknown head / value, old items without
  `alternatives` still answer.
- Real model behind `DRESSME_SLOW=1`: one real photo end to end.

### 7. Documentation

`CLAUDE.md` Phase 4 gets an "XAI" item (sub-project 1 done, what lives where,
the REVIEW settings file); the team decides the final cuts.

## Open questions for the team

- The unsure cuts in `mappings/xai_settings.csv` (start values above, REVIEW).
