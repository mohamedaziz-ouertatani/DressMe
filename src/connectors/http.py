"""
Polite HTTP for the shop connectors (shopify.py, woocommerce.py) and
src/check_shop_source.py:
  - asks robots.txt before every path, and never fetches a forbidden one;
  - sends a User-Agent that says who we are;
  - waits `delay_s` (± 30%) between two requests;
  - stops at the first sign of a block (403, 429, or an HTML page such as a
    captcha where JSON was expected): we never try to get around it;
  - saves every answer untouched under data/raw/Listings/<source>/<date>/,
    so a broken parser can be fixed and re-run without downloading again.
"""

import hashlib
import json
import random
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from app.listings import SourceBlocked

USER_AGENT = "DressMe student project (ESPRIT, academic, non-commercial)"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "Listings"


class Forbidden(Exception):
    """robots.txt does not allow this path: the connector must not read it."""


def urlopen(url, timeout=30):
    """(status, content type, body bytes). Tests replace this function."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.headers.get("Content-Type", "") if err.headers else "", err.read()


class Client:
    def __init__(self, base_url, source_id="check", delay=5.0, opener=None, save=True):
        self.base = base_url if base_url.endswith("/") else base_url + "/"
        self.delay = float(delay)
        self.opener = opener or urlopen
        self.folder = RAW_DIR / source_id / date.today().isoformat() if save else None
        self.robots = None
        self._first = True

    def _wait(self):
        if not self._first and self.delay:
            time.sleep(self.delay * random.uniform(0.7, 1.3))
        self._first = False

    def allowed(self, path):
        """What robots.txt says about this path (no robots.txt = allowed)."""
        if self.robots is None:
            self.robots = urllib.robotparser.RobotFileParser()
            self._wait()
            status, _, body = self.opener(urljoin(self.base, "/robots.txt"))
            if status == 200:
                self.robots.parse(body.decode("utf-8", "replace").splitlines())
            elif status in (403, 429):
                raise SourceBlocked(f"robots.txt answered HTTP {status}")
            else:                       # 404 etc.: no rules
                self.robots.parse([])
        return self.robots.can_fetch(USER_AGENT, urljoin(self.base, path))

    def get_json(self, path):
        """The JSON answer of `path` (relative to the shop's base URL), or None for a 404."""
        if not self.allowed(path):
            raise Forbidden(f"robots.txt forbids {path}")
        url = urljoin(self.base, path)
        self._wait()
        status, ctype, body = self.opener(url)
        if status in (403, 429):
            raise SourceBlocked(f"HTTP {status} on {url}")
        if status == 404:
            return None
        if status != 200:
            raise RuntimeError(f"HTTP {status} on {url}")
        if "json" not in ctype.lower():
            # a bot check or a login page instead of the data
            raise SourceBlocked(f"{url} answered {ctype or 'no content type'}, not JSON (a bot check?)")
        data = json.loads(body)
        if self.folder:
            self.folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha1(url.encode()).hexdigest()[:20] + ".json"
            (self.folder / name).write_text(json.dumps({"url": url, "data": data}, ensure_ascii=False),
                                            encoding="utf-8")
        return data
