"""
The wardrobe tools: list_wardrobe (step 3c) and search_wardrobe (step 3d, the Wardrobe page's search).

A tool only shows the model CODED fields (category, type, colour, pattern, season): no database id, no free text,
no photo. The model names a piece by the small number the ledger gives it.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .. import ml  # noqa: F401  (puts src/ on the import path)
import search

from ..routers.search import find_owned
from ..vocab import CATEGORIES
from .tools import Tool, ToolError

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


class SearchWardrobeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=80)
    category: Optional[Category] = None


def search_wardrobe(ctx, args):
    """The Wardrobe page's word search (step 3b): the words in English, FashionCLIP's text vector, the words cut,
    the same `find_owned` as POST /search. Only ctx.user_id's pieces."""
    rules = search.load_rules()
    query = search.normalise_query(args.query, search.load_terms())
    if not query:
        raise ToolError("no_words", "The query has no words to search for. Use the names of clothes or colours.")
    vector = ctx.request.app.state.analyzer.embed_text(query)
    ranked = find_owned(ctx.db, ctx.user_id, vector, rules["text_cut"], int(rules["default_limit"]), rules,
                        category=args.category)
    pieces = [{"ref": ctx.ledger.add(r["item"]["_id"]), "category": r["item"]["category"],
               "type": r["item"]["sub_category"], "colour": r["item"]["colour"], "close": r["close"]}
              for r in ranked["results"]]
    return {"pieces": pieces, "nothing_close": ranked["nothing_close"]}


SEARCH_WARDROBE = Tool(
    name="search_wardrobe",
    description=("Find the user's own pieces that look like a short description, best match first; close = a sure "
                 "match. Example: search_wardrobe(query='white shirt') to check whether the user owns one. "
                 "Do not use it to list everything (use list_wardrobe) or to find shop items."),
    args_model=SearchWardrobeArgs,
    fn=search_wardrobe,
)
