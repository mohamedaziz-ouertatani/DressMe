# Step 0: safety net (plan)

Goal: before the upgrade starts, add a way to **prove that nothing that works today was broken**.
This step changes **no behaviour of the app**: it only adds tests, test data, scripts and docs.
Facts about the current code: `docs/superpowers/discovery/2026-10-23-codebase-facts.md`.

## Rules

- No change under `backend/app/`, `src/` or `frontend/src/`. If one looks necessary, stop and ask.
- No existing test is changed or deleted.
- All tests run inside the backend container:
  `docker exec dressme-backend-1 python -m pytest -p no:cacheprovider -q`
  (PowerShell, or `MSYS_NO_PATHCONV=1` in Git Bash).
- Everything stays local (no push, no PR) until the team says "start pushing".
- Baseline before this step: **307 passed, 3 skipped** (on `main` at `4d85041`).

## Pieces, in order

Each piece is one or a few small commits.

| # | Piece | Files (all new) |
|---|---|---|
| 1 | **Frozen test wardrobe.** About 17 realistic items (the PolyVore pieces `app.seed_demo` uses, with their real FashionCLIP vectors and the classifier's predictions, read from `data/processed/`, no photos), 3 candidates (target verdicts: skip, think, buy), 1 shop listing, a user profile and fixed season / occasion inputs. | `backend/tests/golden/make_wardrobe.py`, `backend/tests/golden/wardrobe.json` |
| 2 | **Golden output tests.** Seed the frozen wardrobe into `dressme_test`, call the real routes (`/buy-advice` x3, the listing path, `/outfits/suggest`, `/outfits/score`, `/outfits/complete`, `/insights`) and compare with recorded answers. `GOLDEN_RECORD=1` re-records. Two known, expected-to-change behaviours are documented ("Bought it" re-analyses the photo; `/outfits/score` rates top + shoes 86.0). | `backend/tests/test_golden.py`, `backend/tests/golden/expected/*.json`, `backend/tests/golden/README.md` |
| 3 | **Account deletion test** that finds collections by itself: create data in every place the API allows, delete the account as admin, scan every collection for the user id, check the storage folder and thumbnails. | `backend/tests/test_deletion_complete.py` |
| 4 | **Backup and restore** (PowerShell): `mongodump` inside the Mongo container to `backups/`, restore only into `dressme_copy`, print document counts side by side. | `scripts/db_backup.ps1`, `scripts/db_restore_copy.ps1`, `.gitignore` (`backups/`) |
| 5 | **Demo check**, read-only: containers healthy, backend `/health`, frontend, Ollama (warning only). | `scripts/check_demo.ps1` |
| 6 | **Docs.** Fix `CLAUDE.md` (MongoDB 7.0.45 single node, test counts, how to run tests in the container, `DRESSME_SLOW`, `GOLDEN_RECORD`); finish `backend/tests/golden/README.md`; write the PR text. | `CLAUDE.md`, `backend/tests/golden/README.md`, `docs/superpowers/prs/step-0-safety-net.md` |

## How the golden tests are made reliable

- **Fixed ids:** every item, candidate and the listing has a fixed `ObjectId` in `wardrobe.json`, so item ids and their order in the answers are stable. Inserted in a fixed order.
- **Real rules:** the answers depend on the team's `mappings/*.csv`. That is the point: changing a weight changes the goldens, and the diff shows how. The test reloads the real rules first, so test order cannot leak a changed formula into it.
- **Stable verdicts:** the script rejects any wardrobe / candidate whose relevant outfit scores are within 1 point of the good-outfit threshold (60), or within 1 point of the owned piece it is compared with, so the score tolerance can never flip a verdict.
- **Tolerances:** verdict, `good_outfits`, ids and their order, reasons and explanation codes must be identical; scores +-0.5, part values (0-1 scale) +-0.005 (the same 0.5 points), confidences +-0.01. A mismatch prints a readable diff of what changed.
- **Three runs in a row** to find any unstable ordering; order-independent comparison only where the order has no meaning (reported).

## Acceptance

- In the container: 307 existing tests pass, the new tests pass, 3 skipped.
- `git diff main --stat` shows nothing under `backend/app/`, `src/`, `frontend/src/`.
- Golden tests pass 3 runs in a row.
- Backup and restore into `dressme_copy` each ran once.
- No merge into `main`: the branch `upgrade/step-0-safety-net` stays local until the team decides.
