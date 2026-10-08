# Item-label explanations: evaluation

Test split of the image cache. Calibration on 29,633 pictures, deletion test on 2,000. Thresholds from `mappings/xai_settings.csv` (REVIEW). Made by `src/phase4/evaluate_explanations.py`.

## 1. Is the "not sure, check" flag honest?

Accuracy of the answers the app shows as sure vs unsure (pictures with a label only). A useful flag catches answers that are much less accurate than the sure ones.

| field | group | pictures | share | accuracy |
|---|---|---:|---:|---:|
| category | sure | 28867 | 0.974 | 0.969 |
| category | unsure | 766 | 0.026 | 0.496 |
| sub_category | sure | 15473 | 0.953 | 0.889 |
| sub_category | unsure | 755 | 0.047 | 0.355 |
| pattern | sure | 7103 | 0.906 | 0.911 |
| pattern | unsure | 741 | 0.094 | 0.459 |

Accuracy per confidence bucket:

| field | confidence | pictures | accuracy |
|---|---|---:|---:|
| category | 0.0-0.5 | 259 | 0.436 |
| category | 0.5-0.6 | 507 | 0.527 |
| category | 0.6-0.7 | 483 | 0.573 |
| category | 0.7-0.8 | 638 | 0.674 |
| category | 0.8-0.9 | 1022 | 0.825 |
| category | 0.9-1.0 | 26724 | 0.989 |
| sub_category | 0.0-0.5 | 515 | 0.280 |
| sub_category | 0.5-0.6 | 705 | 0.467 |
| sub_category | 0.6-0.7 | 706 | 0.545 |
| sub_category | 0.7-0.8 | 786 | 0.606 |
| sub_category | 0.8-0.9 | 1143 | 0.759 |
| sub_category | 0.9-1.0 | 12373 | 0.955 |
| pattern | 0.0-0.5 | 334 | 0.338 |
| pattern | 0.5-0.6 | 407 | 0.558 |
| pattern | 0.6-0.7 | 434 | 0.627 |
| pattern | 0.7-0.8 | 504 | 0.702 |
| pattern | 0.8-0.9 | 701 | 0.779 |
| pattern | 0.9-1.0 | 5464 | 0.969 |

## 2. Deletion test

Mean drop of the predicted class's confidence after whitening a share of the item's pixels, three ways: the hottest Grad-CAM pixels (`heatmap`); the same heatmap moved by half the picture, i.e. a solid region of the same size in the wrong place (`shifted_region`); and scattered random item pixels (`scattered_pixels`). A bigger drop with the heatmap means it points at what the model really uses.

| field | share | heatmap | shifted_region | scattered_pixels | beats_shifted | beats_scattered |
|---|---:|---:|---:|---:|---:|---:|
| category | 0.100 | 0.056 | 0.016 | 0.181 | True | False |
| category | 0.200 | 0.112 | 0.038 | 0.292 | True | False |
| category | 0.400 | 0.238 | 0.113 | 0.392 | True | False |
| pattern | 0.100 | 0.144 | 0.019 | 0.449 | True | False |
| pattern | 0.200 | 0.195 | 0.037 | 0.501 | True | False |
| pattern | 0.400 | 0.244 | 0.093 | 0.521 | True | False |
| sub_category | 0.100 | 0.173 | 0.054 | 0.276 | True | False |
| sub_category | 0.200 | 0.260 | 0.097 | 0.372 | True | False |
| sub_category | 0.400 | 0.398 | 0.223 | 0.464 | True | False |

How to read it: whitening a solid region leaves a smaller item on white, which looks like the product shots the model was trained on; scattered white pixels cover the whole item with noise it never saw, so they lower the confidence for a reason unrelated to WHERE the model looks. `shifted_region` is the fair comparison; `scattered_pixels` is kept because it was the test planned first, and it shows that the model is sensitive to pixel noise.

## 3. Examples

![Grad-CAM examples](figures/gradcam_examples.png)

All three heads share one body, so a heatmap shows where the model looked to decide, not the outline of a part.
