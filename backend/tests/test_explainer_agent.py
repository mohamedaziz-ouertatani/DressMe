"""The Explainer agent (app/agents/explainer.py): its tools on a wardrobe built
through the API (fake models), the explain chat action, and its routing."""

from types import SimpleNamespace

from app.agents import AGENTS, explainer
from app.agents.common import chat_actions
from app.agents.router import by_keywords, load_keywords
from tests.conftest import BLACK, BLUE, RED, photo, sign_up, upload


def tools_for(client, email="amira@example.com"):
    user = client.app.state.db.users.find_one({"email": email})
    return explainer.AGENT.bound_tools(SimpleNamespace(app=client.app), user)


def outfit(client, headers):
    """A top, jeans and shoes uploaded through the API: their ids."""
    return [upload(client, headers, rgb)["id"] for rgb in (RED, BLUE, BLACK)]


def test_explainer_is_registered_with_its_tools():
    assert "explainer" in AGENTS
    assert set(explainer.tools(None, None)) == {
        "list_wardrobe", "explain_outfit", "what_if", "explain_labels", "explain_similarity",
        "explain_verdict", "how_scoring_works"}


def test_explain_outfit_matches_the_app_score(client):
    headers = sign_up(client)
    ids = outfit(client, headers)
    why = tools_for(client)["explain_outfit"](ids)
    app_score = client.post("/outfits/score", json={"item_ids": ids}, headers=headers).json()["score"]
    assert why["score"] == app_score
    counted = [p for p in why["points"].values() if p["counted"]]
    assert round(sum(p["points"] for p in counted), 1) == why["score"]
    assert "a complete outfit with shoes" in why["works"]
    assert all(isinstance(s, str) and "_" not in s for s in why["works"] + why["problems"])   # sentences, not codes
    assert [i["id"] for i in why["items"]] == ids


def test_explain_outfit_ignores_other_users_items(client):
    owner = sign_up(client)
    ids = outfit(client, owner)
    sign_up(client, "sami@example.com", "Sami")
    answer = tools_for(client, "sami@example.com")["explain_outfit"](ids)
    assert "error" in answer and "score" not in answer


def test_what_if_compares_before_and_after(client):
    headers = sign_up(client)
    top, jeans, shoes = outfit(client, headers)
    t = tools_for(client)
    answer = t["what_if"]([top, jeans, shoes], remove_id=shoes)
    assert answer["before"]["score"] > answer["after"]["score"]          # no shoes: lower
    assert answer["change"] == round(answer["after"]["score"] - answer["before"]["score"], 1)
    assert "no shoes" in answer["after"]["problems"]
    other_jeans = upload(client, headers, BLUE)["id"]
    clash = t["what_if"]([top, jeans, shoes], add_id=other_jeans)        # two pairs of jeans
    assert "error" in clash


def test_explain_labels_of_an_item_and_the_last_scan(client):
    headers = sign_up(client)
    top = upload(client, headers, RED)["id"]
    client.patch(f"/items/{top}", json={"colour": "navy"}, headers=headers)
    t = tools_for(client)
    answer = t["explain_labels"](top)
    assert answer["fields"]["category"]["model_guess"] == "top"
    assert answer["fields"]["category"]["confidence"] == 0.95
    assert answer["fields"]["colour"]["corrected_by_user"] is True
    assert answer["fields"]["colour"]["current_value"] == "navy"
    assert answer["action"] == {"kind": "explain", "url": f"/wardrobe/{top}?why=1"}
    client.post("/analyze", files={"photo": photo(BLUE)}, headers=headers)
    scan = t["explain_labels"]("last_scan")
    assert scan["fields"]["sub_category"]["model_guess"] == "jeans" and "action" not in scan
    sign_up(client, "sami@example.com", "Sami")
    assert "error" in tools_for(client, "sami@example.com")["explain_labels"](top)


def test_explain_verdict(client):
    headers = sign_up(client)
    outfit(client, headers)
    t = tools_for(client)
    assert "error" in t["explain_verdict"]()                             # no scan yet
    client.post("/analyze", files={"photo": photo(RED)}, headers=headers)
    answer = t["explain_verdict"]()
    assert answer["verdict"] in ("buy", "think", "skip")
    assert answer["path"]["good"] == answer["good_outfits"]
    assert {"beats", "lost_to", "near_misses", "twins"} <= set(answer)


def test_how_scoring_works_reads_the_team_files():
    import compatibility
    answer = explainer.tools(None, None)["how_scoring_works"]()
    assert answer["weights"] == compatibility.RULES.weights
    assert answer["good_outfit"] == compatibility.RULES.settings["good_outfit"]
    assert set(answer["parts"]) == {"style", "colour", "pattern", "structure"}


def test_explain_action_is_the_only_new_link_allowed():
    good = {"action": {"kind": "explain", "url": "/wardrobe/6ac04729eed30b2111c1971d?why=1"}}
    sell = {"action": {"kind": "sell", "url": "/sell?item=1"}}
    bad = [{"action": {"kind": "explain", "url": "https://evil.example/?why=1"}},
           {"action": {"kind": "explain", "url": "/wardrobe/abc?why=1"}},
           {"action": {"kind": "explain", "url": "/admin?why=1"}},
           {"action": {"kind": "other", "url": "/wardrobe/6ac04729eed30b2111c1971d?why=1"}}]
    assert list(chat_actions(good)) == [good["action"]]
    assert list(chat_actions(sell)) == [sell["action"]]
    assert all(list(chat_actions(b)) == [] for b in bad)


def test_why_questions_go_to_the_explainer():
    keywords = load_keywords()
    for message in ["Why is my outfit only 62?", "pourquoi ce score ?", "3lech skip?",
                    "explain the verdict", "علاش؟"]:
        assert by_keywords(message, keywords) == "explainer", message
    assert by_keywords("what should I wear today?", keywords) == "stylist"


def test_pieces_can_be_named_by_description(client):
    """Small models often pass 'jeans' instead of an id: a description that matches
    exactly one piece is accepted; an ambiguous one returns the candidates, never a guess."""
    headers = sign_up(client)
    top, jeans, shoes = outfit(client, headers)
    t = tools_for(client)
    by_ids = t["explain_outfit"]([top, jeans, shoes])
    by_words = t["explain_outfit"](["red t-shirt", "jeans", "black_sneakers"])
    assert by_words["score"] == by_ids["score"]
    upload(client, headers, RED)                                     # a second red t-shirt
    ambiguous = t["explain_outfit"](["red t-shirt", "jeans", "sneakers"])
    assert "error" in ambiguous and len(ambiguous["candidates"]["red t-shirt"]) == 2
    assert "error" in t["explain_outfit"](["blue dress", "jeans"])  # matches nothing


def test_explain_similarity_of_two_pieces(client):
    headers = sign_up(client)
    first = upload(client, headers, RED)["id"]
    second = upload(client, headers, RED)["id"]
    jeans = upload(client, headers, BLUE)["id"]
    t = tools_for(client)
    twins = t["explain_similarity"](first, second)
    assert {"field": "sub_category", "value": "t-shirt"} in twins["shared_labels"]
    assert 0 <= twins["similarity"] <= 1.0001 and isinstance(twins["near_twin"], bool)
    apart = t["explain_similarity"](first, "jeans")                  # a description is fine
    assert {"field": "category", "a": "top", "b": "bottom"} in apart["different_labels"]
    assert "candidates" in t["explain_similarity"](jeans, "t-shirt")  # two t-shirts: ask which
    sign_up(client, "sami@example.com", "Sami")
    assert "error" in tools_for(client, "sami@example.com")["explain_similarity"](first, second)


def test_my_two_pieces_are_compared_with_each_other(client):
    """'Why do my two red t-shirts look alike?': the model often passes 'red t-shirt 1' and
    'red t-shirt 2'; the same description matching exactly two pieces means those two."""
    headers = sign_up(client)
    first = upload(client, headers, RED)["id"]
    second = upload(client, headers, RED)["id"]
    t = tools_for(client)
    answer = t["explain_similarity"]("red t-shirt 1", "red t-shirt 2")
    assert {p["id"] for p in answer["pieces"]} == {first, second}
    assert t["explain_similarity"]("first t-shirt", "other t-shirt")["pieces"][0]["id"] in (first, second)
    upload(client, headers, RED)                                         # now three: ask which
    assert "candidates" in t["explain_similarity"]("red t-shirt 1", "red t-shirt 2")
