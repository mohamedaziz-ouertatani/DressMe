"""
Live status of a collector run started from the admin page (backend/app/jobs.py).

The backend starts src/collect_listings.py as a separate process with
    --status-file <jobs>/<id>.json   this run writes its progress there
    --stop-file   <jobs>/<id>.stop   the backend creates it when an admin presses Stop
Files, not the database, so the status works the same on every machine and
the backend can read it even if the run crashes. A run started by hand (no
files given) uses a Progress that does nothing.

A heartbeat is written every 10 s: if it stops for 2 minutes, the backend
knows the run died (computer restarted, process killed) and says so.
"""

import json
import os
import threading
import time
from datetime import datetime, timezone

HEARTBEAT_S = 10
REPLACE_TRIES = 5          # Windows: the backend may be reading the file at that moment
REPLACE_WAIT_S = 0.05


class JobStopped(Exception):
    """An admin pressed Stop: finish the current item, save nothing more, mark nothing gone."""


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Progress:
    def __init__(self, status_path=None, stop_path=None):
        self.status_path, self.stop_path = status_path, stop_path
        self.state = {"status": "running", "phase": "starting", "results": {}, "started_at": now_iso()}
        self._lock = threading.Lock()
        if status_path:
            self._write()
            threading.Thread(target=self._beat, daemon=True).start()

    def update(self, **fields):
        """Merge these fields into the status and write it (does nothing without a file)."""
        with self._lock:
            self.state.update(fields)
            if self.status_path:
                self._write()

    def result(self, source_id, outcome):
        with self._lock:
            self.state["results"][source_id] = outcome
        self.update()

    def stopping(self):
        return bool(self.stop_path) and os.path.exists(self.stop_path)

    def check(self):
        """Raise JobStopped if an admin pressed Stop (called between items)."""
        if self.stopping():
            raise JobStopped("stopped by an admin")

    def _write(self):
        """Write the status file. A status update must never stop the run: on Windows the
        file cannot be replaced while the backend is reading it (WinError 5, 'Access is
        denied', seen on 2026-10-05), so we try again a few times, then skip this update
        (the next one, at most a second or a heartbeat later, writes everything again)."""
        self.state["heartbeat"] = now_iso()
        tmp = f"{self.status_path}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False)
        except OSError:
            return
        for attempt in range(REPLACE_TRIES):
            try:
                os.replace(tmp, self.status_path)    # never a half-written file
                return
            except PermissionError:                  # the backend is reading it right now
                time.sleep(REPLACE_WAIT_S * (attempt + 1))
            except OSError:
                return

    def _beat(self):
        while True:
            time.sleep(HEARTBEAT_S)
            with self._lock:
                self._write()
