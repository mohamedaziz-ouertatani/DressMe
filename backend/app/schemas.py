"""Request bodies, validated by pydantic (wrong values -> 422 with a clear message)."""

from pydantic import BaseModel, EmailStr, Field, field_validator

from .vocab import CATEGORIES, COLOURS, LANGUAGES, PATTERNS, SEASONS, SUB_PARENT, USAGES


class Register(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=60)


class Login(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    min_coverage: int | None = Field(None, ge=1, le=5)   # modesty level, 1-5
    language: str | None = None

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


class Complete(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=8)
    k: int = Field(5, ge=1, le=20)


class BuyAdvice(BaseModel):
    candidate_id: str
    corrections: ItemUpdate | None = None


class ChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
