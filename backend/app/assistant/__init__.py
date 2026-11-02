"""
The new assistant (step 3c, the walking skeleton): tools, a registry, a piece ledger, agents read from
mappings/agents.yaml, a model interface and the loop that ties them together. See docs/learn/step-3c.md.
"""

from .tools import Registry
from .tools_analyst import NEAR_TWINS, WARDROBE_INSIGHTS
from .tools_explainer import EXPLAIN_OUTFIT, HOW_SCORING_WORKS
from .tools_seller import PRICE_ESTIMATE
from .tools_shopping import BUY_ADVICE, PRICE_ESTIMATE_LISTING, SEARCH_LISTINGS, SIMILAR_PIECES
from .tools_stylist import BUILD_OUTFIT, GET_WEATHER, SCORE_OUTFIT, SUGGEST_OUTFITS
from .tools_wardrobe import LIST_WARDROBE, SEARCH_WARDROBE


def default_registry():
    """Every tool the assistant has (an agent uses the ones mappings/agents.yaml gives it)."""
    registry = Registry()
    for tool in (LIST_WARDROBE, SEARCH_WARDROBE, GET_WEATHER, SUGGEST_OUTFITS, BUILD_OUTFIT, SCORE_OUTFIT,
                 WARDROBE_INSIGHTS, NEAR_TWINS, EXPLAIN_OUTFIT, HOW_SCORING_WORKS,
                 PRICE_ESTIMATE, SEARCH_LISTINGS, SIMILAR_PIECES, BUY_ADVICE, PRICE_ESTIMATE_LISTING):
        registry.register(tool)
    return registry
