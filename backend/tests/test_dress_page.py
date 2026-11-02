"""
Step 2b: the Dress page's two routes, on the frozen golden wardrobe (real vectors, so the labels are real):
GET /outfits/today and POST /outfits/build.
"""

from tests.test_golden import golden, real_rules  # noqa: F401  (fixtures)


def keys(outfits):
    return [sorted(i["id"] for i in o["items"]) for o in outfits]


def test_today_is_stable_for_a_day_and_a_shuffle(golden):  # noqa: F811 (a fixture imported above)
    c, h = golden.client, golden.headers
    first = c.get("/outfits/today", headers=h)
    assert first.status_code == 200, first.text
    body = first.json()
    assert set(body) == {"date", "occasion", "season", "weather", "outfits", "missing"}
    assert body["occasion"] == "everyday" and 1 <= len(body["outfits"]) <= 3 and body["missing"] == []
    for o in body["outfits"]:        # what a card needs: label, confidence and its reasons, and the "fits today" line
        assert o["label"] in ("safe", "bolder", "experimental") and o["confidence"] in ("high", "medium", "low")
        assert isinstance(o["confidence_reasons"], list) and o["explanations"][-1]["code"] == "fits_context"

    # the same day and shuffle: the same outfits; a new shuffle: a valid answer (usually other outfits)
    assert keys(c.get("/outfits/today", headers=h).json()["outfits"]) == keys(body["outfits"])
    shuffled = c.get("/outfits/today", params={"shuffle": 1}, headers=h)
    assert shuffled.status_code == 200 and shuffled.json()["outfits"]
    assert c.get("/outfits/today", params={"occasion": "nonsense"}, headers=h).status_code == 422

    # step 2c: three outfits shown = one of each label (fewer than three keep the absolute cuts)
    if len(body["outfits"]) == 3:
        assert {o["label"] for o in body["outfits"]} == {"safe", "bolder", "experimental"}


def test_build_keeps_the_chosen_piece_and_refuses_other_users_pieces(golden):  # noqa: F811
    c, h = golden.client, golden.headers
    top = golden.ids["top_1"]
    r = c.post("/outfits/build", json={"item_ids": [top]}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["used_item_ids"] == [top] and 1 <= len(body["outfits"]) <= 3
    assert all(top in [i["id"] for i in o["items"]] for o in body["outfits"])           # the pick is in every outfit
    assert all(o["pick"] is False for o in body["outfits"])                                # one piece: no complete pick yet
    if len(body["outfits"]) == 3:
        assert {o["label"] for o in body["outfits"]} == {"safe", "bolder", "experimental"}

    # a complete set of pieces comes back first, as the pick
    full = c.post("/outfits/build", json={"item_ids": [golden.ids[k] for k in ("top_1", "bottom_1", "shoes_2")]}, headers=h).json()
    assert full["outfits"][0]["pick"] is True and len(full["outfits"]) <= 3

    # two pieces of the same kind: the newest replaces the earlier one, and the answer says so
    swapped = c.post("/outfits/build", json={"item_ids": [golden.ids["top_1"], golden.ids["top_2"]]}, headers=h).json()
    assert swapped["used_item_ids"] == [golden.ids["top_2"]]
    assert swapped["notes"] == [{"code": "clash_swapped", "params": {"dropped": golden.ids["top_1"], "kept": golden.ids["top_2"]}}]

    # another user's piece: 404
    from tests.conftest import RED, sign_up, upload
    other = sign_up(c, "karim@example.com", "Karim")
    theirs = upload(c, other, RED)
    assert c.post("/outfits/build", json={"item_ids": [top, theirs["id"]]}, headers=h).status_code == 404
