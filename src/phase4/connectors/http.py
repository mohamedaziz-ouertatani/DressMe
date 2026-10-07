"""
Polite HTTP for the shop connectors (shopify.py, woocommerce.py) and
src/phase4/check_shop_source.py:
  - asks robots.txt before every path, and never fetches a forbidden one;
  - sends a User-Agent that says who we are;
  - waits `delay_s` (± 30%) between two requests;
  - stops at the first sign of a block (403, 429, or an HTML page such as a
    captcha where JSON was expected): we never try to get around it;
  - saves every answer untouched under data/raw/Listings/<source>/<date>/,
    so a broken parser can be fixed and re-run without downloading again.
"""

import gzip
import hashlib
import json
import random
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin

from app.listings import SourceBlocked

USER_AGENT = "DressMe student project (ESPRIT, academic, non-commercial)"
RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "Listings"


class Forbidden(Exception):
    """robots.txt does not allow this path: the connector must not read it."""


class NotJSON(Exception):
    """A web page answered where JSON was expected (only raised when the caller
    says a web page is not a block: the platform check, see get_json)."""


# what each kind of request asks for: some shops (Exist, on PrestaShop) answer a page
# request that prefers JSON with an empty HTTP 500, so a page is asked for as a browser does
ACCEPT = {"json": "application/json, */*;q=0.5",
          "xml": "application/xml, text/xml;q=0.9, */*;q=0.5",
          "html": "text/html, application/xhtml+xml;q=0.9, */*;q=0.5"}


def ascii_url(url):
    """The address with accents percent-encoded (urllib refuses them): Hamadi Abid's
    sitemap lists e.g. .../sac-à-main. Characters already encoded are left as they are."""
    return quote(url, safe=":/?#[]@!$&'()*+,;=%~")


def urlopen(url, timeout=30, accept="*/*"):
    """(status, content type, body bytes). Tests replace this function."""
    req = urllib.request.Request(ascii_url(url), headers={"User-Agent": USER_AGENT, "Accept": accept})
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
            status, _, body = self.opener(urljoin(self.base, "/robots.txt"), accept="text/plain, */*;q=0.5")
            if status == 200:
                self.robots.parse(body.decode("utf-8", "replace").splitlines())
            elif status in (403, 429):
                raise SourceBlocked(f"robots.txt answered HTTP {status}")
            else:                       # 404 etc.: no rules
                self.robots.parse([])
        return self.robots.can_fetch(USER_AGENT, urljoin(self.base, path))

    def sitemaps(self):
        """The sitemap addresses robots.txt lists (reads robots.txt if not done yet)."""
        self.allowed("")
        return list(self.robots.site_maps() or [])

    def get_json(self, path, html_is_block=True):
        """The JSON answer of `path` (relative to the shop's base URL), or None for a 404.

        A web page (HTML) where JSON was expected: during a real run it may be a
        bot check, so it stops the source (SourceBlocked). The platform check
        (check_shop_source.py) passes html_is_block=False: many sites answer an
        unknown address with an ordinary page, which only means "not this
        platform" (NotJSON). 403 / 429 always count as a block."""
        if not self.allowed(path):
            raise Forbidden(f"robots.txt forbids {path}")
        url = urljoin(self.base, path)
        self._wait()
        status, ctype, body = self.opener(url, accept=ACCEPT["json"])
        if status in (403, 429):
            raise SourceBlocked(f"HTTP {status} on {url}")
        if status == 404:
            return None
        if status != 200:
            raise RuntimeError(f"HTTP {status} on {url}")
        if "json" not in ctype.lower():
            if not html_is_block:
                raise NotJSON(f"{url} answered a web page ({ctype or 'no content type'})")
            # a bot check or a login page instead of the data
            raise SourceBlocked(f"{url} answered {ctype or 'no content type'}, not JSON (a bot check?)")
        data = json.loads(body)
        self._save(url, data)
        return data

    def _save(self, url, data):
        """Keep the untouched answer, so a broken parser can be fixed without downloading again."""
        if self.folder:
            self.folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha1(url.encode()).hexdigest()[:20] + ".json"
            (self.folder / name).write_text(json.dumps({"url": url, "data": data}, ensure_ascii=False),
                                            encoding="utf-8")

    def get_text(self, path, kind="xml"):
        """The text of `path` (a sitemap or a product page), or None for a 404.

        kind="xml": a sitemap. A web page instead (a bot check) stops the source.
        kind="html": a product page. Gzipped sitemaps (.xml.gz) are unpacked."""
        if not self.allowed(path):
            raise Forbidden(f"robots.txt forbids {path}")
        url = urljoin(self.base, path)
        self._wait()
        status, ctype, body = self.opener(url, accept=ACCEPT[kind])
        if status in (403, 429):
            raise SourceBlocked(f"HTTP {status} on {url}")
        if status == 404:
            return None
        if status != 200:
            raise RuntimeError(f"HTTP {status} on {url}")
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        text = body.decode("utf-8", "replace")
        if kind == "xml" and not text.lstrip().startswith(("<?xml", "<urlset", "<sitemapindex")):
            raise SourceBlocked(f"{url} answered {ctype or 'something'} instead of a sitemap (a bot check?)")
        self._save(url, text if kind == "xml" else text[:200_000])
        return text
