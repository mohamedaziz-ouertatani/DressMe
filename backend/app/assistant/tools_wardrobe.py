"""
The wardrobe tools (step 3c). One so far: list_wardrobe. More arrive in step 3d.

A tool only shows the model CODED fields (category, type, colour, pattern, season): no database id, no free text,
no photo. The model names a piece by the small number the ledger gives it.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..vocab import CATEGORIES
from .tools import Tool

Category = Literal[tuple(CATEGORIES)]       # the app's categories, as a fixed list the model must choose from


class ListWardrobeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Optional[Category] = None
    colour: Optional[str] = None
    limit: int = Field(default=30, ge=1, le=60)


def list_wardrobe(ctx, args):
    """Only ctx.user_id's pieces: the user filter is in the query itself, and the id is not an argument."""
    query = {"user_id": ctx.user_id}
    if args.category:
        query["category"] = args.category
    if args.colour:
        query["colour"] = args.colour.strip().lower()
    docs = list(ctx.db.items.find(query).sort("created_at", 1))
    pieces = []
    for doc in docs[:args.limit]:
        pieces.append({"ref": ctx.ledger.add(doc["_id"]), "category": doc["category"],
                       "type": doc["sub_category"], "colour": doc["colour"], "pattern": doc["pattern"],
                       "season": doc.get("season", [])})
    return {"pieces": pieces, "total": len(docs)}


LIST_WARDROBE = Tool(
    name="list_wardrobe",
    description=("List the pieces in the user's wardrobe, optionally only one category or one colour. "
                 "Example: list_wardrobe(category='bottom', colour='black') for the black bottoms. "
                 "Do not use it to find a piece by a description, and do not use it for shop items."),
    args_model=ListWardrobeArgs,
    fn=list_wardrobe,
)
