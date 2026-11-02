# search_calibration.csv is superseded by the Encoder Validation Lab

`search_calibration.csv` is the history of step 3b (2026-10-25): cuts words 0.297 and photo 0.823, chosen by
`src/phase4/calibrate_search.py` on random wardrobes of 30 Fashion Product pieces (300 queries per mode and split).
It is kept as it was and is NOT the source of the cuts used today.

The cuts in force are in `mappings/search_rules.csv`:

| | cut | how it was chosen |
|---|---|---|
| words | 0.292 | Encoder Validation Lab, Phase 6 (tuning rule commit 1fa3bca): precision 0.90 on validation (test 0.900, coverage 0.674) |
| photo | 0.792 | same lab: precision target 0.75, the highest reachable (test 0.772, coverage 0.300) |

The lab's rules were written before any score was computed: decision rule commit 4d84265, tuning rule commit 1fa3bca.
Encoder choice validated in the Encoder Validation Lab; FashionCLIP 2.0 kept.

`calibrate_search.py` no longer writes by itself: run it with `--write` only if the team decides to replace the lab's
cuts (it also rewrites `search_calibration.csv`).
