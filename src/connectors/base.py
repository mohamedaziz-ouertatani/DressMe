"""What every connector returns (see __init__.py)."""

from dataclasses import dataclass, field


@dataclass
class FetchResult:
    status: str                # ok / blocked / error
    message: str = ""
    listings: list = field(default_factory=list)    # RawListing (backend/app/listings.py)
    mode: str = ""             # e.g. catalogue / stock
