"""Request bodies, validated by pydantic (wrong values -> 422 with a clear message)."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from .vocab import CATEGORIES, COLOURS, LANGUAGES, PATTERNS, SEASONS, SUB_PARENT, USAGES


Gender = Literal["men", "women"]


class Register(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=60)
    gender: Gender                       # required: shops, look-alikes and rules follow it
    consent: bool | None = None          # the sign-up checkbox; true stamps users.consent_at (step 5)


class DeleteMe(BaseModel):
    """DELETE /me: the password is asked again before an account and everything it owns is deleted."""
    password: str = Field(max_length=128)


class Login(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    min_coverage: int | None = Field(None, ge=1, le=5)   # modesty level, 1-5
    language: str | None = None
    gender: Gender | None = None
    budget_tnd: float | None = Field(None, gt=0, le=1_000_000)   # optional; null clears it

    @field_validator("language")
    @classmethod
    def _language(cls, v):
        if v is not None and v not in LANGUAGES:
            raise ValueError(f"language must be one of {LANGUAGES}")
        return v


def _one_of(allowed, name):
    def check(v):
        if v is not None and v != "" and v not in allowed:
            raise ValueError(f"{name} must be one of {sorted(allowed)}")
        return v
    return check


class ItemUpdate(BaseModel):
    """Corrections from the user. Only the fields sent are changed."""
    category: str | None = None
    sub_category: str | None = None
    pattern: str | None = None
    colour: str | None = None
    coverage: int | None = Field(None, ge=1, le=5)
    season: list[str] | None = None
    usage: list[str] | None = None

    _category = field_validator("category")(_one_of(CATEGORIES, "category"))
    _sub = field_validator("sub_category")(_one_of(SUB_PARENT, "sub_category"))
    _pattern = field_validator("pattern")(_one_of(PATTERNS, "pattern"))
    _colour = field_validator("colour")(_one_of(COLOURS, "colour"))

    @field_validator("season")
    @classmethod
    def _season(cls, v):
        for s in v or []:
            _one_of(SEASONS, "season")(s)
        return v

    @field_validator("usage")
    @classmethod
    def _usage(cls, v):
        for u in v or []:
            _one_of(USAGES, "usage")(u)
        return v


class ItemIds(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=10)


class OutfitFeedback(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=10)
    rating: Literal[-1, 1]


class Complete(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=8)
    k: int = Field(5, ge=1, le=20)


class BuyAdvice(BaseModel):
    candidate_id: str
    corrections: ItemUpdate | None = None
    price_tnd: float | None = Field(None, gt=0, le=100000)    # the price on the tag; missing = unknown (never 0)


class DecisionIn(BaseModel):
    """What the user did after a verdict: bought the piece, or left it."""
    candidate_id: str
    answer: Literal["bought", "left"]
    price_paid: float | None = Field(None, gt=0, le=100000)      # optional: what they really paid


class BuildIn(BaseModel):
    """The Dress page, Build mode: the pieces picked so far, and what to dress for."""
    item_ids: list[str] = Field(min_length=1, max_length=8)
    occasion: str | None = Field(None, max_length=40)       # a chip of mappings/dress_occasions.csv
    shuffle: int = Field(0, ge=0, le=1_000_000)             # "New outfits" counts up


class WearIn(BaseModel):
    """"I wore this": the pieces worn today, and what the app showed for that outfit."""
    item_ids: list[str] = Field(min_length=1, max_length=10)
    occasion: str | None = None
    event_name: str | None = Field(None, max_length=80)
    score_shown: float | None = Field(None, ge=0, le=100)
    label_shown: Literal["safe", "bolder", "experimental"] | None = None
    source: Literal["card", "build"]

    @field_validator("occasion")
    @classmethod
    def _occasion(cls, v):
        return v if v is None else _one_of(USAGES, "usage")(v)


class ChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
