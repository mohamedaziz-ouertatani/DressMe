"""Puts the three code folders on the import path, so a script in src/phase3/
or src/phase4/ can import a module from any of them by its plain name
(e.g. `from plot_style import apply`, `from merge_and_split import bucket`):

    src/common/   shared by both phases (chart style)
    src/phase3/   data collection, label mapping, EDA, merge + splits
    src/phase4/   prototype: models, compatibility, chat, listings

Import it before the project modules: `import src_path  # noqa: F401`.
The same file sits in src/phase3/ and src/phase4/ (Python only looks in the
script's own folder). The backend adds the same folders in app/config.py."""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
for folder in ("common", "phase3", "phase4"):
    if str(SRC / folder) not in sys.path:
        sys.path.append(str(SRC / folder))
