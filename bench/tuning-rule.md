DRESSME ENCODER LAB - TUNING RULE FOR FASHIONCLIP 2.0
Written and committed BEFORE any tuning result is seen. Date: 2026-11-02

1. Model: FashionCLIP 2.0 (patrickjohncyh/fashion-clip), kept by the
   project owner. The exam is the frozen Phase 3 exam.
2. Baseline = the settings the app uses now, as found in the repo check
   of 2026-11-02, applied to full-resolution pictures.
3. Every choice is made on VALIDATION only. TEST is opened once, at the
   end, to report the final settings against the baseline.
4. Settings and options (fixed in advance; nothing else is tried):
   a. image preparation: centre crop vs white padding to a square;
   b. text prompt: raw; "a photo of {}"; "a photo of a {}, a type of
      fashion item"; the average of 5 fixed templates;
   c. storage: float32 vs float16.
   Chosen in this order (a, b, c), one at a time, earlier choices fixed.
5. An option replaces the baseline choice only if, on validation, the
   paired 95% bootstrap interval (1,000 resamples, seed 0) of its gain is
   above 0 on words MRR or on photo MRR, and the interval of its change on
   the other track is not entirely below 0. If several options qualify,
   the one with the largest validation gain is taken. Otherwise the
   baseline choice stays.
6. Cuts, with the final settings, on validation: words at precision
   >= 0.90; photo at the highest target among 0.90, 0.85, 0.80, 0.75 that
   has a valid cut (lowest threshold on a 0.001 grid, at least
   max(20, n/10) answered).
7. Reported, not deciding: image source (small 60x80 vs full), per-type
   errors, score distributions, the cost of each change in the app.
