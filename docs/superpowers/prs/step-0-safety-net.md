# Step 0: safety net (golden outputs, deletion test, backup, demo check)

Branch `upgrade/step-0-safety-net`, from `main` at `4d85041` (the Docker setup). Not merged.

## Summary

The upgrade will change a lot. This step adds a way to **prove, after every later step, that
nothing that works today was broken**. It changes **no behaviour of the app**: nothing under
`backend/app/`, `src/` or `frontend/src/` is touched, and no existing test is changed.

- **Golden output tests.** A frozen wardrobe (17 items, 3 scans, 1 shop listing, real FashionCLIP
  vectors, no photos) goes through the real routes; each answer is compared with the one recorded
  today. The three scans give today's verdicts **skip** (a near twin of an owned top, 0 good
  outfits), **think** (a shirt, 2 good outfits) and **buy** (a coat, 12 good outfits); the shop
  listing gives **think** (1 good outfit). A failure prints exactly what changed.
- **Account deletion test.** A user writes to every place the API allows; the account is deleted
  as an admin; every collection is scanned for what is left. Today nothing is left behind.
- **Backup and restore scripts** (PowerShell) and a read-only **demo check**.
- **Docs:** `CLAUDE.md` facts corrected; `backend/tests/golden/README.md`.

Two behaviours are recorded as **known and expected to change** (tests named `test_known_issue_*`):

1. "Bought it" re-uploads and re-analyses the photo instead of reusing the scan (step 1 replaces it).
2. `POST /outfits/score` rates an incomplete outfit (top + shoes) 86.0, above the good-outfit line.

## Files added or changed

| File | What |
|---|---|
| `backend/tests/test_golden.py` | Golden tests (8 comparisons + the 2 known-issue tests). `GOLDEN_RECORD=1` re-records. |
| `backend/tests/golden/wardrobe.json` | The frozen wardrobe, scans, listing, user and fixed inputs. |
| `backend/tests/golden/make_wardrobe.py` | Generator (deterministic; `--search` shows how the scans were found; refuses to write an unstable wardrobe). |
| `backend/tests/golden/expected/*.json` | 8 recorded answers (`buy_advice_near_twin|think|buy|listing`, `outfits_suggest|score|complete`, `insights`). |
| `backend/tests/golden/README.md` | What each file is, how answers are compared, how to record, the re-record rule. |
| `backend/tests/test_deletion_complete.py` | Account deletion leaves nothing behind. |
| `scripts/db_backup.ps1`, `scripts/db_restore_copy.ps1` | Backup to `backups/`; restore only into `dressme_copy`. |
| `scripts/check_demo.ps1` | Read-only check before the demo. |
| `.gitignore` | `backups/`. |
| `CLAUDE.md` | MongoDB 7.0.45 single node (no transactions), tests run in the container, test counts, `DRESSME_SLOW`, `GOLDEN_RECORD`, the scripts. |
| `docs/superpowers/discovery/2026-10-23-codebase-facts.md` | The verified facts about the current code this step relies on. |
| `docs/superpowers/plans/2026-10-23-step-0-safety-net.md` | The plan. |
| `docs/superpowers/prs/step-0-safety-net.md` | This text. |

## How to run the checks

Tests (in the backend container; in Git Bash put `MSYS_NO_PATHCONV=1` in front):

```
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q                      # everything (~3 min)
docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_golden.py # the golden tests (~15 s)
docker exec -e GOLDEN_RECORD=1 dressme-backend-1 python -m pytest -p no:cacheprovider -q tests/test_golden.py   # re-record
```

Re-record only in a pull request that explains why each difference is intended.

Scripts (PowerShell, from the project folder):

```
powershell -ExecutionPolicy Bypass -File scripts\db_backup.ps1
powershell -ExecutionPolicy Bypass -File scripts\db_restore_copy.ps1 backups\dressme-<timestamp>.archive.gz
powershell -ExecutionPolicy Bypass -File scripts\check_demo.ps1
```

## Test counts

| | Passed | Skipped | Failed |
|---|---|---|---|
| Before (`main` at `4d85041`) | 307 | 3 | 0 |
| After (this branch) | **318** | 3 | 0 |

The 11 new tests: 8 golden comparisons, 2 known-issue tests, 1 deletion test. The 3 skipped are
the real-model tests (`DRESSME_SLOW=1`). The golden tests passed 3 runs in a row.

## Reviewer notes

- The golden answers depend on the team's `mappings/*.csv`: changing a weight changes them on purpose.
- The wardrobe is a woman's; men's rules, swimwear / beach outfits, outfit feedback, the chat,
  try-on and weather are not covered by the goldens.
- The stability checks in `make_wardrobe.py` keep every outfit that decides a verdict at least 1
  point away from the good-outfit line (60), so the score tolerance (+-0.5) cannot flip a verdict.
- Not pushed anywhere: all work is local until the team decides.
