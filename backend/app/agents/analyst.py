"""
The Wardrobe analyst agent: "what's missing? what do I never wear?". It reads
the same facts as the Insights page (compatibility.wardrobe_insights).
"""

from .. import ml  # noqa: F401  (puts src/ on the import path)
import compatibility

from ..routers.insights import wardrobe_counts
from ..routers.outfits import rules_of, user_profile, wardrobe
from ..wardrobe import describe, to_compat
from .common import Agent, list_wardrobe_tool

TOP = 5            # pieces listed per answer: keeps the prompt small


def tools(request, user):
    """The Wardrobe analyst's tools, bound to this user."""
    rules = rules_of(user)          # the team's rules for the user's gender
    def wardrobe_insights() -> dict:
        """How many good outfits the wardrobe makes, its most versatile pieces, the pieces
        that go with nothing, and what is missing (shoes, top, bottom)."""
        docs, by_id = wardrobe(request, user)
        facts = compatibility.wardrobe_insights([to_compat(d) for d in docs],
                                                user_profile(user, docs, request), rules)
        use = facts["outfit_use"]
        return {"good_outfits": facts["good_outfits"], "complete": facts["complete"],
                "versatile": [{**describe(i, by_id), "outfits": use[i["id"]]}
                              for i in facts["versatile"][:TOP]],
                "unmatched": [describe(i, by_id) for i in facts["unmatched"][:TOP]],
                "unmatched_count": len(facts["unmatched"]),
                "new_pairs": facts["new_pairs"], "missing": facts["missing"],
                "hidden_by_filters": len(facts["filtered"])}

    def wardrobe_stats() -> dict:
        """What the wardrobe is made of: counts per category, colour (neutral ones marked)
        and pattern, and how many items still have an empty colour, coverage, season or usage."""
        docs, _ = wardrobe(request, user)
        return wardrobe_counts(docs)

    def find_near_twins() -> dict:
        """Pairs of the user's pieces that look almost the same (useful before buying another)."""
        docs, by_id = wardrobe(request, user)
        twins = compatibility.near_twins([to_compat(d) for d in docs], rules)
        return {"twins": [{"items": [describe(a, by_id), describe(b, by_id)], "similarity": round(s, 3)}
                          for a, b, s in twins[:TOP]]}

    functions = (list_wardrobe_tool(request, user), wardrobe_insights, wardrobe_stats, find_near_twins)
    return {f.__name__: f for f in functions}


AGENT = Agent(
    name="analyst", title="Wardrobe analyst",
    description="what the wardrobe lacks, too much of one thing, unused pieces, near-duplicates, statistics",
    job=("help the user understand their wardrobe so they buy less and better. Use wardrobe_insights "
         "for what is missing and which pieces work best or never match, wardrobe_stats for counts "
         "and colours, and find_near_twins for pieces they own twice."),
    tools=tools)
