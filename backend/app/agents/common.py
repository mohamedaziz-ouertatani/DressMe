"""
What the three DressMe agents share (see AGENTS.md): the item pictures shown
under an answer, and the list_wardrobe tool every agent can call.
"""

from functools import wraps

from ..routers.outfits import wardrobe


def image_attachments(value, group=""):
    """Extract safe, displayable item images from a tool result."""
    if isinstance(value, dict):
        if isinstance(value.get("image_url"), str) and isinstance(value.get("id"), str):
            yield {
                "id": value["id"],
                "category": value.get("category", ""),
                "sub_category": value.get("sub_category", ""),
                "colour": value.get("colour", ""),
                "image_url": value["image_url"],
                "group": group,
            }
        for child in value.values():
            yield from image_attachments(child, group)
    elif isinstance(value, list):
        for index, child in enumerate(value, 1):
            child_group = group or f"outfit-{index}"
            yield from image_attachments(child, child_group)


def with_attachments(functions, attachments):
    """The tools as {name: function}. With an `attachments` list, every item picture a
    tool returns is also added to it (once), so the app can show it under the answer."""
    if attachments is None:
        return dict(functions)

    def capture(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            result = fn(*args, **kwargs)
            seen = {item["id"] for item in attachments}
            for item in image_attachments(result):
                if item["id"] not in seen:
                    attachments.append(item)
                    seen.add(item["id"])
            return result
        return wrapped

    return {name: capture(fn) for name, fn in functions.items()}


def list_wardrobe_tool(request, user):
    """The list_wardrobe tool, bound to this user (every agent has it)."""
    def list_wardrobe(category: str = "") -> list[dict]:
        """List the user's clothes. category: optional filter (top, bottom, dress, outerwear,
        shoes, bag, accessory, traditional, swimwear)."""
        docs, _ = wardrobe(request, user)
        return [{"id": str(d["_id"]), "category": d["category"], "sub_category": d["sub_category"],
                 "colour": d["colour"], "pattern": d["pattern"],
                 "image_url": f"/items/{d['_id']}/image"}
                for d in docs if not category or d["category"] == category]
    return list_wardrobe
