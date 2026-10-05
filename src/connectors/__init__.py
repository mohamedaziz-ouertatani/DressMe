"""
Listing connectors for src/collect_listings.py: one module per `kind` of source in
mappings/listing_sources.csv. Each module has

    fetch(source, args) -> FetchResult(status, message, listings, mode)   (base.py)

status is "ok", "blocked" (the shop refused us: stop, never work around it)
or "error". Only an "ok" result is saved, so a blocked or broken run never
marks listings as gone.
"""

from . import inditex, shopify, sitemap, snapshot, woocommerce
from .base import FetchResult  # noqa: F401

CONNECTORS = {"inditex": inditex, "snapshot": snapshot, "shopify": shopify, "woocommerce": woocommerce,
              "sitemap": sitemap}
